"""PRISM engine: replays a RouteViews RIB + UPDATE stream and emits per-announcement
anomaly flags against per-prefix routing history (IPv4 only).

Flag types
  NO   novel-origin: origin not in prefix's history (or, for an unseen more-specific,
       not in the covering prefix's history) and not CAIDA-related to any historical origin.
  NOr  same as NO but WITHOUT the relationship filter            (ablation)
  NOs  novel vs. RIB snapshot only (no update history), no rel filter  (naive baseline)
  NX   novel non-cone export: transit AS x exports prefix P to a provider/peer/unknown
       neighbour although P's origin is outside x's customer cone and x did not learn P
       from a customer; (P,x) never seen in history.
  NXa  same export test WITHOUT per-prefix novelty                (ablation)
  VF   classical valley-free violation using known relationships only (baseline)
Output: parquet of flags (ts, type, offender, prefix, peer) + per-minute volume counts.
"""
import sys, os, glob, time, ipaddress
from collections import defaultdict
import bgpkit, pandas as pd
from asrel import ASRel

def clean_path(s):
    if s is None or "{" in s: return None
    out=[]
    for t in s.split():
        a=int(t)
        if 64512<=a<=65534 or a>=4200000000 or a==23456: return None
        if not out or out[-1]!=a: out.append(a)
    return out

def v4key(pfx):
    net,l=pfx.split("/"); l=int(l)
    return int(ipaddress.IPv4Address(net)), l

class Engine:
    def __init__(self, rel):
        self.rel=rel
        self.hist=defaultdict(set)      # prefix -> origins ever seen (RIB + updates so far)
        self.rib=defaultdict(set)       # prefix -> origins in RIB snapshot only
        self.nx_hist=set()              # (prefix, x) non-cone exports ever seen
        self.len_index=defaultdict(set) # prefix length -> set of network ints in history
        self.pathcache={}
        self.flags=[]
    def covering(self, pfx):
        n,l=v4key(pfx)
        for L in range(l-1,7,-1):
            m=(n>>(32-L))<<(32-L)
            if m in self.len_index[L]:
                return f"{ipaddress.IPv4Address(m)}/{L}"
        return None
    def export_anoms(self, path):
        """returns (nx_list, vf_list) of offending transit ASes; path[0]=collector peer, path[-1]=origin"""
        key=tuple(path)
        r=self.pathcache.get(key)
        if r is not None: return r
        rel=self.rel; nx=[]; vf=[]
        o=path[-1]
        # walk from origin toward collector: x=path[i], learned from path[i+1], exports to path[i-1]
        for i in range(len(path)-2,0,-1):
            x=path[i]; frm=path[i+1]; to=path[i-1]
            r_to=rel.rel(x,to); r_frm=rel.rel(x,frm)
            if r_to!="c" and r_frm!="c" and o not in rel.cone(x):
                nx.append(x)
            if r_to in ("p","e") and r_frm in ("p","e"):
                vf.append(x)
        r=(tuple(nx),tuple(vf))
        if len(self.pathcache)>600_000: self.pathcache.clear()
        self.pathcache[key]=r
        return r
    def learn(self, pfx, path, from_rib):
        o=path[-1]
        if pfx not in self.hist:
            n,l=v4key(pfx); self.len_index[l].add(n)
        self.hist[pfx].add(o)
        if from_rib: self.rib[pfx].add(o)
        for x in self.export_anoms(path)[0]: self.nx_hist.add((pfx,x))
    def score(self, ts, pfx, path, peer):
        o=path[-1]; F=self.flags
        h=self.hist.get(pfx)
        ref=h if h else (self.hist.get(self.covering(pfx)) if True else None)
        if ref and o not in ref:
            F.append((ts,"NOr",o,pfx,peer))
            if not any(self.rel.related(o,b) for b in ref):
                F.append((ts,"NO",o,pfx,peer))
        rs=self.rib.get(pfx)
        if rs is None:
            c=self.covering_rib(pfx); rs=self.rib.get(c) if c else None
        if rs and o not in rs: F.append((ts,"NOs",o,pfx,peer))
        nx,vf=self.export_anoms(path)
        for x in nx:
            F.append((ts,"NXa",x,pfx,peer))
            if (pfx,x) not in self.nx_hist: F.append((ts,"NX",x,pfx,peer))
        for x in vf: F.append((ts,"VF",x,pfx,peer))
    def covering_rib(self,pfx):
        n,l=v4key(pfx)
        for L in range(l-1,7,-1):
            m=(n>>(32-L))<<(32-L); p=f"{ipaddress.IPv4Address(m)}/{L}"
            if p in self.rib: return p
        return None

def run(case_dir, asrel_path, t0, t1, out):
    rel=ASRel(asrel_path); E=Engine(rel)
    T=time.time(); n=0
    rib=sorted(glob.glob(f"{case_dir}/rib.*"))[0]   # rib.bz2 (RouteViews) or rib.gz (RIPE RIS bview)
    for e in bgpkit.Parser(url=rib):
        p=e.prefix
        if ":" in p: continue
        path=clean_path(e.as_path)
        if not path or len(path)<1: continue
        E.learn(p,path,True); n+=1
    print(f"RIB {n} elems {time.time()-T:.0f}s prefixes={len(E.hist)} nxhist={len(E.nx_hist)}",flush=True)
    vol=defaultdict(int); nupd=0
    import pyarrow as pa, pyarrow.parquet as pq
    writer=None; nflags=0
    def flush():
        nonlocal writer,nflags
        if not E.flags: return
        ts,ty,off,pf,pe=zip(*E.flags)
        tb=pa.table({"ts":pa.array(ts,pa.float64()),"type":pa.array(ty,pa.string()),"off":pa.array(off,pa.int64()),
                     "prefix":pa.array(pf,pa.string()),"peer":pa.array(pe,pa.int64())})
        if writer is None: writer=pq.ParquetWriter(out+".flags.parquet",tb.schema)
        writer.write_table(tb); nflags+=len(E.flags); E.flags.clear()
    for f in sorted(glob.glob(f"{case_dir}/upd.*.bz2")+glob.glob(f"{case_dir}/upd.*.gz")):
        flush()
        for e in bgpkit.Parser(url=f):
            if e.elem_type!="A": continue
            p=e.prefix
            if ":" in p: continue
            path=clean_path(e.as_path)
            if not path: continue
            ts=e.timestamp; nupd+=1
            vol[int(ts//60)]+=1
            if ts>=t0 and ts<t1:
                E.score(ts,p,path,e.peer_asn)
            elif ts>=t1: continue
            else:
                # warm-up period is ALSO scored (for self-calibration) before learning
                E.score(ts,p,path,e.peer_asn)
            E.learn(p,path,False)
    flush(); writer.close()
    print(f"UPD {nupd} {time.time()-T:.0f}s flags={nflags}",flush=True)
    pd.DataFrame(sorted(vol.items()),columns=["minute","ann"]).to_parquet(out+".vol.parquet")

if __name__=="__main__":
    case_dir,asrel_path,t0,t1,out=sys.argv[1:6]
    run(case_dir,asrel_path,float(t0),float(t1),out)

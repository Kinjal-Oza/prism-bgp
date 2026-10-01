"""Post-hoc alert filter (VA): for every export unit with score>=5, measure the share of its flagged
announcements in which the offender sits directly next to the collector peer (path position 1) with
no inferred relationship to that peer. Output: out/<case>.va.parquet"""
import sys, glob, pandas as pd, numpy as np, bgpkit
from datetime import datetime, timezone
from cases import all_cases as cases
from engine import clean_path
from asrel import ASRel
from run_case import asrel_for
import evaluate as E
def run(case):
    c=[x for x in cases() if x["case"]==case][0]
    u=pd.read_parquet(f"out/{case}.units.parquet"); u=u[(u.det=="PRISM-export")&(u.score>=5)]
    if len(u)==0: pd.DataFrame(columns=["w","off","va_share"]).to_parquet(f"out/{case}.va.parquet"); return
    rel=ASRel(asrel_for(c))
    need={}  # window -> set offenders
    for w,o in zip(u.w,u.off): need.setdefault(int(w),set()).add(int(o))
    wins=sorted(need); lo=min(wins)*E.W; hi=(max(wins)+1)*E.W
    f=pd.read_parquet(f"out/{case}.flags.parquet",columns=["ts","off","prefix","peer"],
                      filters=[("type","==","NX"),("ts",">=",lo),("ts","<",hi)])
    f["w"]=(f.ts//E.W).astype(int); f=f[[ (int(w) in need and int(o) in need[int(w)]) for w,o in zip(f.w,f.off)]]
    keys={}
    for k,o in zip(zip(f.ts,f.prefix,f.peer),f.off): keys.setdefault(k,set()).add(int(o))
    files=set()
    for w in wins:
        for t in (w*E.W, w*E.W+E.W-1):
            q=datetime.fromtimestamp(t,timezone.utc); q=q.replace(minute=q.minute-q.minute%15,second=0)
            files.update(glob.glob(f"data/{case}/upd.{q:%Y%m%d.%H%M}.bz2"))
    if case.startswith("PT2008"):   # 2008 files are not aligned to quarter hours
        files=set(fn for fn in glob.glob(f"data/{case}/upd.*.bz2")
                  if any(abs(datetime.strptime(fn.split('upd.')[1][:13],'%Y%m%d.%H%M').replace(tzinfo=timezone.utc).timestamp()-w*E.W)<1200 for w in wins))
    adj={}; tot={}
    for fn in sorted(files):
        for e in bgpkit.Parser(url=fn):
            if e.elem_type!="A": continue
            k=(e.timestamp,e.prefix,e.peer_asn)
            if k not in keys: continue
            p=clean_path(e.as_path)
            if not p: continue
            w=int(e.timestamp//E.W)
            for o in keys[k]:
                tot[(w,o)]=tot.get((w,o),0)+1
                if len(p)>2 and p[1]==o and rel.rel(o,p[0]) is None: adj[(w,o)]=adj.get((w,o),0)+1
            del keys[k]
    rows=[dict(w=w,off=o,va_share=adj.get((w,o),0)/tot[(w,o)],matched=tot[(w,o)]) for (w,o) in tot]
    pd.DataFrame(rows).to_parquet(f"out/{case}.va.parquet"); print(case,len(u),len(rows))
if __name__=="__main__": run(sys.argv[1])

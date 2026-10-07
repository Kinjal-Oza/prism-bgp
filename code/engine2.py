"""PRISM engine, multi-view replay for the history-poisoning study.

One parse of a case's RIB + UPDATE stream drives several detector *views* that share the RIB-derived history
(read-only) and keep their own additions on top of it:

  D0  the published PRISM engine (engine.py), NO and NX flags only. Must reproduce engine.py's flags exactly.
  D1  persistence-gated learning: a (prefix, origin) or (prefix, non-cone exporter) pair enters history only after
      some collector session (peer IP) has carried it continuously for T_ADM seconds. RIB pairs are admitted at once.
      While pending, the NO/NX test is applied at the start of each presence episode, against admitted history only.
      Admissions are logged so evaluation can build H_a from admitted pairs only.

Each view may carry its own list of injected messages (synthetic session "inj"), merged by timestamp into the real
stream. Injected messages are the only synthetic data; see HELDOUT_PREREGISTRATION.md (history-poisoning addendum).
"""
import sys, glob, time, heapq, ipaddress, json
from collections import defaultdict
import bgpkit, pyarrow as pa, pyarrow.parquet as pq
from asrel import ASRel
from engine import clean_path, v4key

T_ADM = 3600

class Shared:
    """RIB-derived history shared by all views, plus the path cache (depends only on the path and CAIDA data)."""
    def __init__(self, rel):
        self.rel = rel; self.hist = {}; self.rib_nx = set(); self.len_index = defaultdict(set); self.pathcache = {}
    def export_anoms(self, path):
        key = tuple(path); r = self.pathcache.get(key)
        if r is not None: return r
        rel = self.rel; nx = []; o = path[-1]
        for i in range(len(path) - 2, 0, -1):
            x = path[i]; frm = path[i + 1]; to = path[i - 1]
            if rel.rel(x, to) != "c" and rel.rel(x, frm) != "c" and o not in rel.cone(x): nx.append(x)
        r = tuple(nx)
        if len(self.pathcache) > 600_000: self.pathcache.clear()
        self.pathcache[key] = r; return r
    def learn_rib(self, pfx, path):
        o = path[-1]; h = self.hist.get(pfx)
        if h is None:
            n, l = v4key(pfx); self.len_index[l].add(n); h = self.hist[pfx] = set()
        h.add(o)
        for x in self.export_anoms(path): self.rib_nx.add((pfx, x))

class View:
    def __init__(self, name, S, mode, inject=(), record=None):
        self.name, self.S, self.mode = name, S, mode
        self.hist = {}; self.nx = set(); self.len_add = defaultdict(set)
        self.flags = []; self.writer = None; self.nflags = 0
        self.inj = sorted(inject); self.ii = 0
        self.record = record            # optional (culprits, t_lo, t_hi): log paths of culprit flags (D0 only)
        self.recorded = {}
        # D1 state
        self.pend = {}                  # item -> [since or None, set(sessions), episode]
        self.carry = {}                 # (session, prefix) -> tuple(items carried that were pending at the time)
        self.heap = []; self.adm = []   # admissions: (fam, prefix, off, since, admit_ts)
    # ---------- history lookups (shared RIB + own additions)
    def has_origin(self, p, o):
        h = self.S.hist.get(p)
        if h is not None and o in h: return True
        h = self.hist.get(p); return h is not None and o in h
    def ref(self, p):
        a = self.S.hist.get(p); b = self.hist.get(p)
        if a is None and b is None: return None
        return (a or set()) | (b or set())
    def known(self, p): return p in self.S.hist or p in self.hist
    def covering(self, p):
        n, l = v4key(p); S = self.S
        for L in range(l - 1, 7, -1):
            m = (n >> (32 - L)) << (32 - L)
            if m in S.len_index[L] or m in self.len_add[L]: return f"{ipaddress.IPv4Address(m)}/{L}"
        return None
    def has_nx(self, p, x): return (p, x) in self.S.rib_nx or (p, x) in self.nx
    def add_origin(self, p, o):
        if not self.known(p):
            n, l = v4key(p); self.len_add[l].add(n)
        self.hist.setdefault(p, set()).add(o)
    # ---------- tests
    def no_test(self, p, o):
        """returns True if NO flags (same logic as engine.py)"""
        r = self.ref(p)
        if not r:
            c = self.covering(p); r = self.ref(c) if c else None
        if r and o not in r:
            rel = self.S.rel
            return not any(rel.related(o, b) for b in r)
        return False
    def emit(self, ts, ty, off, p, peer, path):
        self.flags.append((ts, ty, off, p, peer))
        R = self.record
        if R and off in R[0] and R[1] <= ts <= R[2]:
            k = (ty, p, off)
            if k not in self.recorded: self.recorded[k] = (ts, list(path))
    # ---------- D0: score then learn (engine.py semantics)
    def d0(self, ts, p, path, peer):
        o = path[-1]
        if self.no_test(p, o): self.emit(ts, "NO", o, p, peer, path)
        nx = self.S.export_anoms(path)
        for x in nx:
            if not self.has_nx(p, x): self.emit(ts, "NX", x, p, peer, path)
        self.add_origin(p, o)
        for x in nx: self.nx.add((p, x))
    # ---------- D1
    def admit_due(self, ts):
        H = self.heap
        while H and H[0][0] <= ts:
            t, ep, item = heapq.heappop(H); e = self.pend.get(item)
            if e is None or e[2] != ep or e[0] is None: continue
            fam, p, a = item
            if fam == "NO": self.add_origin(p, a)
            else: self.nx.add((p, a))
            self.adm.append((fam, p, a, e[0], t)); del self.pend[item]
    def end_carry(self, sess, p):
        old = self.carry.pop((sess, p), None)
        if not old: return
        for it in old:
            e = self.pend.get(it)
            if e is None: continue
            e[1].discard(sess)
            if not e[1]: e[0] = None
    def d1_ann(self, ts, p, path, peer, sess):
        self.end_carry(sess, p)
        o = path[-1]; nx = self.S.export_anoms(path); items = []
        if not self.has_origin(p, o): items.append(("NO", p, o))
        for x in nx:
            if not self.has_nx(p, x): items.append(("NX", p, x))
        if not items: return
        for it in items:
            e = self.pend.get(it)
            if e is None: e = self.pend[it] = [None, set(), 0]
            if e[0] is None:                       # new presence episode
                e[0] = ts; e[2] += 1
                heapq.heappush(self.heap, (ts + T_ADM, e[2], it))
                if it[0] == "NO":
                    if self.no_test(p, o): self.emit(ts, "NO", o, p, peer, path)
                else:
                    self.emit(ts, "NX", it[2], p, peer, path)
            e[1].add(sess)
        self.carry[(sess, p)] = tuple(items)
    # ---------- dispatch
    def ann(self, ts, p, path, peer, sess):
        if self.mode == "D0": self.d0(ts, p, path, peer)
        else: self.admit_due(ts); self.d1_ann(ts, p, path, peer, sess)
    def wd(self, ts, p, sess):
        if self.mode == "D1": self.admit_due(ts); self.end_carry(sess, p)
    def inject_until(self, ts):
        L = self.inj
        while self.ii < len(L) and L[self.ii][0] <= ts:
            t, kind, p, path = L[self.ii]; self.ii += 1
            if kind == "A": self.ann(t, p, path, path[0], "inj")
            else: self.wd(t, p, "inj")
    def flush(self, out):
        if not self.flags: return
        ts, ty, off, pf, pe = zip(*self.flags)
        tb = pa.table({"ts": pa.array(ts, pa.float64()), "type": pa.array(ty, pa.string()), "off": pa.array(off, pa.int64()),
                       "prefix": pa.array(pf, pa.string()), "peer": pa.array(pe, pa.int64())})
        if self.writer is None: self.writer = pq.ParquetWriter(f"{out}.{self.name}.flags.parquet", tb.schema)
        self.writer.write_table(tb); self.nflags += len(self.flags); self.flags.clear()
    def close(self, out):
        self.inject_until(float("inf")); self.flush(out)
        if self.writer is None:   # no flags at all: write an empty file with the schema
            pq.write_table(pa.table({"ts": pa.array([], pa.float64()), "type": pa.array([], pa.string()), "off": pa.array([], pa.int64()),
                                     "prefix": pa.array([], pa.string()), "peer": pa.array([], pa.int64())}), f"{out}.{self.name}.flags.parquet")
        else: self.writer.close()
        if self.mode == "D1":
            if self.adm:
                f, p, a, s, t = zip(*self.adm)
                tb = pa.table({"fam": pa.array(f, pa.string()), "prefix": pa.array(p, pa.string()), "off": pa.array(a, pa.int64()),
                               "since": pa.array(s, pa.float64()), "admit": pa.array(t, pa.float64())})
            else:
                tb = pa.table({"fam": pa.array([], pa.string()), "prefix": pa.array([], pa.string()), "off": pa.array([], pa.int64()),
                               "since": pa.array([], pa.float64()), "admit": pa.array([], pa.float64())})
            pq.write_table(tb, f"{out}.{self.name}.adm.parquet")
        if self.record:
            json.dump([[k[0], k[1], k[2], v[0], v[1]] for k, v in self.recorded.items()], open(f"{out}.{self.name}.seeds.json", "w"))

def run(case_dir, asrel_path, t1, out, views_spec):
    rel = ASRel(asrel_path); S = Shared(rel)
    T = time.time(); n = 0
    rib = sorted(glob.glob(f"{case_dir}/rib.*"))[0]
    for e in bgpkit.Parser(url=rib):
        p = e.prefix
        if ":" in p: continue
        path = clean_path(e.as_path)
        if not path: continue
        S.learn_rib(p, path); n += 1
    print(f"RIB {n} elems {time.time()-T:.0f}s prefixes={len(S.hist)} nxhist={len(S.rib_nx)}", flush=True)
    V = [View(S=S, **v) for v in views_spec]
    nupd = 0; nwd = 0
    for f in sorted(glob.glob(f"{case_dir}/upd.*.bz2") + glob.glob(f"{case_dir}/upd.*.gz")):
        for v in V: v.flush(out)
        for e in bgpkit.Parser(url=f):
            p = e.prefix
            if ":" in p: continue
            ts = e.timestamp
            if ts >= t1: continue
            for v in V: v.inject_until(ts)
            if e.elem_type == "A":
                path = clean_path(e.as_path)
                if not path: continue
                nupd += 1
                for v in V: v.ann(ts, p, path, e.peer_asn, e.peer_ip)
            else:
                nwd += 1
                for v in V: v.wd(ts, p, e.peer_ip)
    for v in V: v.close(out)
    print(f"UPD {nupd} WD {nwd} {time.time()-T:.0f}s " + " ".join(f"{v.name}={v.nflags}" for v in V), flush=True)

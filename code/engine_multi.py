"""Multi-collector replay (pre-registered 2026-10-07). Merges the RIBs and UPDATE streams of several collectors into one
time-ordered stream and drives the same views as engine2 (D0 = published PRISM, D1 = persistence-gated).
History is the union over collectors; sessions are (collector, peer IP); vantage points are (collector, peer AS)."""
import glob, heapq, time
import bgpkit
from asrel import ASRel
from engine import clean_path
from engine2 import Shared, View

def _stream(cidx, files):
    for f in files:
        try:
            for e in bgpkit.Parser(url=f):
                p = e.prefix
                if ":" in p: continue
                yield (e.timestamp, cidx, e.elem_type, p, e.as_path, e.peer_asn, e.peer_ip)
        except Exception as ex:   # a corrupt archive file is skipped and reported, never silently
            print(f"WARN parse {f}: {ex!r}", flush=True)

def run(collector_dirs, asrel_path, t1, out, views_spec, diag=None):
    rel = ASRel(asrel_path); S = Shared(rel); T = time.time(); n = 0
    for cidx, d in enumerate(collector_dirs):
        ribs = sorted(glob.glob(f"{d}/rib.*"))
        if not ribs: continue
        try:
            for e in bgpkit.Parser(url=ribs[0]):
                p = e.prefix
                if ":" in p: continue
                path = clean_path(e.as_path)
                if not path: continue
                S.learn_rib(p, path); n += 1
                if diag is not None: diag.rib(p, path)
        except Exception as ex:
            print(f"WARN rib {ribs[0]}: {ex!r}", flush=True)
    print(f"RIB {n} elems from {len(collector_dirs)} collectors {time.time()-T:.0f}s prefixes={len(S.hist)}", flush=True)
    V = [View(S=S, **v) for v in views_spec]
    streams = [_stream(i, sorted(glob.glob(f"{d}/upd.*"))) for i, d in enumerate(collector_dirs)]
    nupd = nwd = 0; last_flush = 0
    for ts, cidx, et, p, ap, pasn, pip in heapq.merge(*streams, key=lambda x: x[0]):
        if ts >= t1: continue
        if ts - last_flush > 900:
            for v in V: v.flush(out)
            last_flush = ts
        sess = f"{cidx}|{pip}"; vp = (cidx << 33) + int(pasn)
        for v in V: v.inject_until(ts)
        if et == "A":
            path = clean_path(ap)
            if not path: continue
            nupd += 1
            for v in V: v.ann(ts, p, path, vp, sess)
            if diag is not None: diag.ann(ts, p, path)
        else:
            nwd += 1
            for v in V: v.wd(ts, p, sess)
    for v in V: v.close(out)
    print(f"UPD {nupd} WD {nwd} {time.time()-T:.0f}s " + " ".join(f"{v.name}={v.nflags}" for v in V), flush=True)

"""Multi-collector replay of one case (pre-registered 2026-10-07).
Cases: the 178 RouteLLM events (ids X###) and our 16 incidents + 16 controls (ids as in cases.py).
For each: find every RouteViews collector with a RIB at or before (test-window start - 24 h) via the BGPKIT broker,
download that RIB and its UPDATE files up to the window end, replay all collectors merged (frozen PRISM, D0), score,
write mc_out/<id>.json (+ units parquet for our cases), and delete the raw data.
Usage: python3 mc_run.py list | python3 mc_run.py ID..."""
import sys, os, json, glob, shutil, subprocess
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, bgpkit
import engine_multi, eval_poison as P, ext_run as X
import evaluate as E
from cases import all_cases
from run_case import asrel_for
W = 300; TAU = {"NO": 50, "NX": 2000}
OURS = {c["case"]: c for c in all_cases() if not c["case"].endswith("_wk")}
EXT = {c["id"]: c for c in X.cases()}
B = bgpkit.Broker()
iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S")

def case(cid):
    if cid in EXT:
        c = EXT[cid]; return dict(id=cid, t0=c["t0"], t1=c["t1"], kind="ext", c=c)
    c = OURS[cid]; return dict(id=cid, t0=c["t0"], t1=c["t1"], kind="ours", c=c)

def plan(k):
    start = k["t0"] - timedelta(hours=24)
    ribs = B.query(ts_start=iso(start - timedelta(days=3)), ts_end=iso(start), project="route-views", data_type="rib")
    best = {}
    for r in ribs:
        t = datetime.fromisoformat(r.ts_start)
        if t <= start and (r.collector_id not in best or t > best[r.collector_id][0]): best[r.collector_id] = (t, r.url)
    J = {}
    for col, (t, url) in sorted(best.items()):
        ups = B.query(ts_start=iso(t), ts_end=iso(k["t1"]), collector_id=col, data_type="updates")
        ups = [u for u in ups if datetime.fromisoformat(u.ts_start) < k["t1"]]
        if not ups: continue
        J[col] = [(url, "rib.bz2" if url.endswith("bz2") else "rib.gz")] + \
                 [(u.url, "upd." + os.path.basename(u.url).split(".", 1)[1]) for u in ups]
    return J

def download(d, J):
    jobs = []
    for col, files in J.items():
        os.makedirs(f"{d}/{col}", exist_ok=True)
        jobs += [(u, f"{d}/{col}/{n}") for u, n in files]
    def get(a):
        u, dst = a
        if os.path.exists(dst) and os.path.getsize(dst) > 0: return 0
        return subprocess.run(["curl", "-sS", "-f", "--retry", "5", "-o", dst, u], capture_output=True).returncode
    with ThreadPoolExecutor(int(os.environ.get("MC_DL_THREADS", "16"))) as ex: rc = list(ex.map(get, jobs))
    bad = [j for j, r in zip(jobs, rc) if r]
    for u, dst in bad:
        if os.path.exists(dst): os.remove(dst)
    return len(jobs), len(bad)

def run(cid):
    os.makedirs("mc_out", exist_ok=True)
    if os.path.exists(f"mc_out/{cid}.json"): return
    k = case(cid); d = f"mc_data/{cid}"; res = dict(id=cid, kind=k["kind"])
    try:
        J = plan(k); nf, nbad = download(d, J)
        res.update(collectors=sorted(J), n_collectors=len(J), files=nf, failed_files=nbad)
        t0 = k["t0"].replace(tzinfo=timezone.utc).timestamp(); t1 = k["t1"].replace(tzinfo=timezone.utc).timestamp()
        out = f"mc_flags/{cid}"; os.makedirs("mc_flags", exist_ok=True)
        dirs = [f"{d}/{col}" for col in sorted(J)]
        if k["kind"] == "ext":
            c = k["c"]; att = set(c["attackers"])
            class Diag:
                def __init__(s): s.v = dict(listed_ann=0, att_origin_ann=0, att_inpath_ann=0, rib_att_origin=0, rib_att_inpath=0)
                def rel(s, p):
                    try: return bool(c["prefixes"]) and X.covers(c["prefixes"], p)
                    except Exception: return False
                def rib(s, p, pa):
                    if s.rel(p):
                        if pa[-1] in att: s.v["rib_att_origin"] += 1
                        elif att & set(pa): s.v["rib_att_inpath"] += 1
                def ann(s, ts, p, pa):
                    if t0 <= ts < t1 and s.rel(p):
                        s.v["listed_ann"] += 1
                        if pa[-1] in att: s.v["att_origin_ann"] += 1
                        elif att & set(pa): s.v["att_inpath_ann"] += 1
            D = Diag()
            engine_multi.run(dirs, X.asrel(c["T"]), t1, out, [dict(name="D0", mode="D0")], diag=D)
            f = pd.read_parquet(f"{out}.D0.flags.parquet"); alerts = []
            for ty in ("NO", "NX"):
                g = P.units(f, ty, "all"); g = g[(g.w * W >= t0) & (g.w * W < t1) & (g.s >= TAU[ty])]
                for r in g.itertuples(): alerts.append(dict(fam=ty, off=int(r.off), c=int(r.c), first=float(r.first)))
            hit = [a for a in alerts if a["off"] in att]
            own = f[(f.ts >= t0) & (f.ts < t1) & f.off.isin(att)]
            own = own[[X.covers(c["prefixes"], p) for p in own.prefix]] if len(own) and c["prefixes"] else own.iloc[0:0]
            T = c["T"].replace(tzinfo=timezone.utc).timestamp()
            res.update(D.v, ok=True, time=str(c["T"]), attackers=c["attackers"], category=c["category"], detected=bool(hit),
                       first_alert_s=(min(a["first"] for a in hit) - T) if hit else None, false_alerts=len(alerts) - len(hit),
                       owner_detected=bool(len(own)), hours=12.0)
        else:
            c = k["c"]
            ap = asrel_for(c)
            if not os.path.exists(ap):
                os.makedirs("asrel", exist_ok=True)
                subprocess.run(["curl", "-sSf", "--retry", "5", "-o", ap, X.CAIDA + os.path.basename(ap)], check=True)
            engine_multi.run(dirs, ap, t1, out, [dict(name="D0", mode="D0")])
            f = pd.read_parquet(f"{out}.D0.flags.parquet"); parts = []
            for ty, det in (("NO", "PRISM-origin"), ("NX", "PRISM-export")):
                g = P.units(f, ty, "all"); g = g[(g.w * W >= t0) & (g.w * W < t1)].copy()
                g["det"] = det; g["score"] = g.s; g["case"] = cid; parts.append(g)
            pd.concat(parts, ignore_index=True).to_parquet(f"mc_out/{cid}.units.parquet")
            res.update(ok=True)
    except Exception as e:
        res.update(ok=False, error=repr(e)[:400])
    json.dump(res, open(f"mc_out/{cid}.json", "w"), indent=1, default=str)
    shutil.rmtree(d, ignore_errors=True)
    for x in glob.glob(f"mc_flags/{cid}.*"): os.remove(x)
    print(cid, res.get("ok"), res.get("n_collectors"), res.get("detected", ""), res.get("error", ""), flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "list":
        print(" ".join(list(OURS) + list(EXT))); sys.exit()
    for a in sys.argv[1:]: run(a)

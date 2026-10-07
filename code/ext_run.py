"""External benchmark (pre-registered 2026-10-07): RouteLLM incidents (arXiv:2608.22812, Apache-2.0).
For one event index: download route-views2 RIB + updates, replay frozen PRISM (D0), score at the Quiet point,
write ext_out/<id>.json, delete the raw data. Usage: python3 ext_run.py IDX..."""
import sys, os, re, json, glob, shutil, subprocess, ipaddress
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, numpy as np
import engine2, eval_poison as P
from engine import v4key
BASE = "http://archive.routeviews.org/bgpdata"
CAIDA = "https://publicdata.caida.org/datasets/as-relationships/serial-1/"
W = 300; TAU = {"NO": 50, "NX": 2000}
EV = pd.read_csv("ext/routellm_event.csv")

def cases():
    out = []
    for i, r in EV.iterrows():
        T = datetime.strptime(r.Time, "%Y/%m/%d %H:%M")
        if T < datetime(2002, 1, 1): continue
        att = [int(x) for x in re.findall(r"\d+", str(r.Attacker))]
        pf = [p.strip() for p in str(r.Prefixes).split(";") if p.strip() and ":" not in p]
        out.append(dict(idx=int(i), id=f"X{i:03d}", T=T, attackers=att, prefixes=pf, category=r.Category,
                        victim=str(r.Victim), t0=T - timedelta(hours=6), t1=T + timedelta(hours=6)))
    return out

_ls = {}
def listing(path, pat):
    if path not in _ls:
        html = subprocess.run(["curl", "-s", "--retry", "3", path], capture_output=True, text=True).stdout
        _ls[path] = sorted(set(re.findall(pat, html)))
    return _ls[path]
ts = lambda f: datetime.strptime(".".join(f.split(".")[1:3]), "%Y%m%d.%H%M")
def months(a, b):
    m = a.replace(day=1, hour=0, minute=0)
    while m <= b:
        yield f"{m:%Y.%m}"; m = (m + timedelta(days=32)).replace(day=1)

def download(c, d):
    os.makedirs(d, exist_ok=True)
    start = c["t0"] - timedelta(hours=24)
    ribs = [(m, f) for m in months(start - timedelta(days=3), start) for f in listing(f"{BASE}/{m}/RIBS/", r"rib\.\d{8}\.\d{4}\.bz2") if ts(f) <= start]
    if not ribs: return "no RIB"
    m, rib = ribs[-1]; J = [(f"{BASE}/{m}/RIBS/{rib}", f"{d}/rib.bz2")]
    for m in months(ts(rib) - timedelta(minutes=15), c["t1"]):
        for f in listing(f"{BASE}/{m}/UPDATES/", r"updates\.\d{8}\.\d{4}\.bz2"):
            if ts(rib) <= ts(f) < c["t1"]: J.append((f"{BASE}/{m}/UPDATES/{f}", f"{d}/upd.{ts(f):%Y%m%d.%H%M}.bz2"))
    def get(a):
        url, dst = a
        if os.path.exists(dst) and os.path.getsize(dst) > 0: return 0
        return subprocess.run(["curl", "-sS", "-f", "--retry", "5", "-o", dst, url], capture_output=True).returncode
    with ThreadPoolExecutor(8) as ex: rc = list(ex.map(get, J))
    bad = sum(1 for r in rc if r)
    return None if bad == 0 else f"{bad}/{len(J)} files failed"

def asrel(T):
    files = listing(CAIDA, r"\d{8}\.as-rel\.txt\.bz2")
    f = [x for x in files if x[:8] <= T.strftime("%Y%m%d")][-1]
    p = f"asrel/{f}"
    if not os.path.exists(p): subprocess.run(["curl", "-sSf", "-o", p, CAIDA + f], check=True)
    return p

_cv = {}
def covers(listed, p):
    key = id(listed)
    if key not in _cv:
        m = {}
        for q in listed:
            try: qn, ql = v4key(q)
            except Exception: continue
            m.setdefault(ql, set()).add(qn >> (32 - ql) if ql else 0)
        _cv[key] = m
    n, l = v4key(p)
    return any(l >= ql and ((n >> (32 - ql)) if ql else 0) in s for ql, s in _cv[key].items())

def run(idx):
    c = [x for x in cases() if x["idx"] == idx][0]; k = c["id"]; os.makedirs("ext_out", exist_ok=True)
    if os.path.exists(f"ext_out/{k}.json"): return
    d = f"ext_data/{k}"; err = download(c, d)
    res = dict(id=k, idx=idx, time=str(c["T"]), attackers=c["attackers"], category=c["category"], n_prefixes=len(c["prefixes"]))
    try:
        if err and not os.path.exists(f"{d}/rib.bz2"): raise RuntimeError(err)
        res["download_note"] = err
        t0 = c["t0"].replace(tzinfo=timezone.utc).timestamp(); t1 = c["t1"].replace(tzinfo=timezone.utc).timestamp()
        out = f"ext_flags/{k}"; os.makedirs("ext_flags", exist_ok=True)
        att = set(c["attackers"])
        class Diag:   # visibility diagnostic, descriptive only; does not change any metric
            def __init__(s): s.v = dict(listed_ann=0, att_origin_ann=0, att_inpath_ann=0, rib_att_origin=0, rib_att_inpath=0)
            def rel(s, p):
                try: return bool(c["prefixes"]) and covers(c["prefixes"], p)
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
        D = Diag(); vis = D.v
        engine2.run(d, asrel(c["T"]), t1, out, [dict(name="D0", mode="D0")], diag=D)
        f = pd.read_parquet(f"{out}.D0.flags.parquet"); att = set(c["attackers"])
        alerts = []
        for ty in ("NO", "NX"):
            g = P.units(f, ty, "all"); g = g[(g.w * W >= t0) & (g.w * W < t1) & (g.s >= TAU[ty])]
            for r in g.itertuples(): alerts.append(dict(fam=ty, off=int(r.off), c=int(r.c), first=float(r.first), s=float(r.s)))
        hit = [a for a in alerts if a["off"] in att]
        own = f[(f.ts >= t0) & (f.ts < t1) & f.off.isin(att)]
        own = own[[covers(c["prefixes"], p) for p in own.prefix]] if len(own) and c["prefixes"] else own.iloc[0:0]
        T = c["T"].replace(tzinfo=timezone.utc).timestamp()
        res.update(vis)
        res.update(ok=True, detected=bool(hit), first_alert_s=(min(a["first"] for a in hit) - T) if hit else None,
                   families=sorted({a["fam"] for a in hit}), false_alerts=len(alerts) - len(hit),
                   owner_detected=bool(len(own)), owner_first_s=float(own.ts.min() - T) if len(own) else None,
                   attacker_flags=int(f[(f.ts >= t0) & (f.ts < t1) & f.off.isin(att)].prefix.nunique()), hours=12.0)
    except Exception as e:
        res.update(ok=False, error=repr(e)[:300])
    json.dump(res, open(f"ext_out/{k}.json", "w"), indent=1)
    shutil.rmtree(d, ignore_errors=True)
    for x in glob.glob(f"ext_flags/{k}.*"): os.remove(x)
    print(k, res.get("ok"), res.get("detected"), res.get("owner_detected"), res.get("error", ""), flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "list": print(" ".join(str(c["idx"]) for c in cases())); sys.exit()
    for a in sys.argv[1:]: run(int(a))

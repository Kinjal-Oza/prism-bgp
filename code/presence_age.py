"""How long before the reported time were the attacker's routes already present? (pre-registered 2026-10-11)
For each benchmark event in class 'visible, attacker already present' (route-views2): at look-backs of 1, 7, 30 and
90 days before the listed time, take the latest route-views2 RIB at or before that moment and record whether any
route to a listed prefix (or a more-specific) has the attacker as origin or on the path. Real data only.
Usage: python3 presence_age.py ID...   -> age_out/<id>.json"""
import sys, os, json, re, subprocess
from datetime import timedelta
import bgpkit, ext_run as X
LOOK = [1, 7, 30, 90]
EV = {c["id"]: c for c in X.cases()}

def rib_at(t):
    for m in X.months(t - timedelta(days=3), t):
        pass
    cands = [(m, f) for m in X.months(t - timedelta(days=3), t)
             for f in X.listing(f"{X.BASE}/{m}/RIBS/", r"rib\.\d{8}\.\d{4}\.bz2") if X.ts(f) <= t]
    if not cands: return None, None
    m, f = cands[-1]; return f"{X.BASE}/{m}/RIBS/{f}", X.ts(f)

def present(url, att, prefixes):
    hits = 0
    for a in att:
        for e in bgpkit.Parser(url=url, filters={"as_path": rf"(^| ){a}( |$)"}):
            if ":" in e.prefix: continue
            if X.covers(prefixes, e.prefix): hits += 1
    return hits

def run(k):
    os.makedirs("age_out", exist_ok=True)
    if os.path.exists(f"age_out/{k}.json"): return
    c = EV[k]; res = dict(id=k, time=str(c["T"]), attackers=c["attackers"], n_prefixes=len(c["prefixes"]), look={})
    try:
        for d in LOOK:
            url, t = rib_at(c["T"] - timedelta(days=d))
            if url is None: res["look"][str(d)] = None; continue
            res["look"][str(d)] = dict(rib=str(t), routes=present(url, c["attackers"], c["prefixes"]))
        res["ok"] = True
    except Exception as e:
        res.update(ok=False, error=repr(e)[:300])
    json.dump(res, open(f"age_out/{k}.json", "w"), indent=1); print(k, res.get("look"), res.get("error", ""), flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "list":
        import pandas as pd
        x = pd.read_csv("../results/external/external_cases.csv")
        print(" ".join(x[x.cls.str.contains("already present")].id)); sys.exit()
    for k in sys.argv[1:]: run(k)

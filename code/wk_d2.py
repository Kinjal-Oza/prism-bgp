"""Validation of the capped D2 defense on held-back real data (pre-registered 2026-10-11).
The four 7-day week-long control windows (672 h, never used to choose the cap r) are replayed with persistence-gated
learning (D1), and false alerts at the Quiet point are counted for D1, D1+cap, D2 and D2+cap (cap r = 0.02, fixed in
the exploratory sweep). Every alert in these windows is false. Usage: python3 wk_d2.py CASE  -> wkd2_out/CASE.json"""
import sys, os, json, subprocess
import pandas as pd
import engine2, eval_poison as P, d2, evaluate as E, ext_run as X
from cases import longctl_cases
from run_case import asrel_for
W = 300; R = 0.02; CAPS = {"NO": R * 50, "NX": R * 2000}

def run(k):
    os.makedirs("wkd2_out", exist_ok=True); os.makedirs("out2", exist_ok=True)
    c = [x for x in longctl_cases() if x["case"] == k][0]
    subprocess.run(["python3", "download_case.py", k], check=True)
    ap = asrel_for(c)
    if not os.path.exists(ap):
        os.makedirs("asrel", exist_ok=True)
        subprocess.run(["curl", "-sSf", "--retry", "5", "-o", ap, X.CAIDA + os.path.basename(ap)], check=True)
    t0, t1 = E.TS(c["t0"]), E.TS(c["t1"])
    engine2.run(f"data/{k}", ap, t1, f"out2/{k}", [dict(name="D1", mode="D1")])
    f = pd.read_parquet(f"out2/{k}.D1.flags.parquet"); adm = pd.read_parquet(f"out2/{k}.D1.adm.parquet")
    keys = {}
    for name, caps in (("D1", None), ("D1cap", CAPS)):
        s = set()
        for ty in ("NO", "NX"):
            g = P.units(f, ty, "adm", adm, cap=None if caps is None else caps[ty])
            g = g[(g.w * W >= t0) & (g.w * W < t1) & (g.s >= P.TAU[ty])]
            s |= {(ty, int(w), int(o)) for w, o in zip(g.w, g.off)}
        keys[name] = s
    ep = set()
    for ty in ("NO", "NX"):
        e = d2.episodes(f, ty, adm, P.TAU[ty]); e = e[(e.w * W >= t0) & (e.w * W < t1)]
        ep |= {(ty, int(w), int(o)) for w, o in zip(e.w, e.off)}
    hrs = (t1 - t0) / 3600
    res = dict(case=k, hours=hrs, D1=len(keys["D1"]), D1cap=len(keys["D1cap"]), D2=len(keys["D1"] | ep), D2cap=len(keys["D1cap"] | ep),
               episodes=len(ep))
    json.dump(res, open(f"wkd2_out/{k}.json", "w"), indent=1); print(res, flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "list": print(" ".join(c["case"] for c in longctl_cases())); sys.exit()
    run(sys.argv[1])

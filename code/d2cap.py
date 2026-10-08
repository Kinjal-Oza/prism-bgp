"""Exploratory (post hoc, labeled in the paper): D2 with the offender-history cap r=0.02 on the 5-min score."""
import json, os, numpy as np, pandas as pd
import eval_poison as P, d2, evaluate as E
r = 0.02; caps = {"NO": r * 50, "NX": r * 2000}
done = [k for k in P.ALL if os.path.exists(f"out2/{k}.D1.adm.parquet")]
EP = pd.read_csv("../results/poison/d2_clean_episodes.csv")
U = pd.concat([P.case_units(k, "D1", "adm", caps=caps) for k in done], ignore_index=True)
rows = []
for sname, ks in (("development", [k for k in done if k in P.DEV]), ("held-out", [k for k in done if k in P.HO]), ("all", done)):
    o = P.ops(U, ks, extra=EP); o = o[o.point == "Quiet"]; o.insert(0, "set", sname); rows.append(o)
cl = pd.concat(rows); print(cl[["set", "detected", "n", "false_alerts", "fa_per_day"]].to_string())
att = []
for k in [k for k in P.ALL if os.path.exists(f"out2/{k}.A2Q.adm.parquet")]:
    c = P.C[k]; on = P.on_(c); cul = set(c["culprits"])
    for view, var in (("A1T", "T"), ("A1P", "P"), ("A1Q", "Q"), ("A2Q", "Q2")):
        info = (json.load(open(f"out2/{k}.attackq2.json")) if var == "Q2" else json.load(open(f"out2/{k}.attackq.json")) if var == "Q"
                else json.load(open(f"out2/{k}.attack.json"))[var])
        s0 = info["seed_start"]; f = P.flags(k, view); adm = pd.read_parquet(f"out2/{k}.{view}.adm.parquet"); hit = False
        for ty in ("NO", "NX"):
            g = P.units(f, ty, "adm", adm, cap=caps[ty]); a = g[(g.s >= P.TAU[ty]) & g.off.isin(cul)]
            hit |= bool(((a["first"] >= s0) & (a["first"] <= on + E.DET_POST)).any())
            e = d2.episodes(f, ty, adm, P.TAU[ty]); e = e[e.off.isin(cul) & (e["first"] >= s0) & (e["first"] <= on + E.DET_POST)]
            hit |= len(e) > 0
        att.append(dict(case=k, attack=var, detected=hit))
A = pd.DataFrame(att); print(A.groupby("attack").detected.sum())
cl.to_csv("../results/poison/d2cap_clean.csv", index=False); A.to_csv("../results/poison/d2cap_attack.csv", index=False)

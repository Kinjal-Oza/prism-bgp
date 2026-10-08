"""Owner mode vs the D2-aware attacker (Q2): first owner-mode origin flag (any NO flag naming a culprit, from seed start)
and first owner leak alert (>= kappa=20 prefixes of one victim origin by a culprit exporter in one 5-min window).
Same computation as eval_poison.py 'attack' for T/P/Q. Uses the A2Q (Q2 attack) flags."""
import json, pandas as pd
import eval_poison as P, evaluate as E, run2, engine2
from asrel import ASRel
from run_case import asrel_for
W = 300; rows = []
for k in ["TM2015","RT2017","DV2017","DQ2019","RT2020","ID2011","ID2014","GO2017","SH2019","VI2021"]:
    c = P.C[k]; on = P.on_(c); cul = set(c["culprits"]); ii = json.load(open(f"out2/{k}.attackq2.json")); s0 = ii["seed_start"]
    f = P.flags(k, "A2Q")
    no = f[(f.type == "NO") & f.off.isin(cul) & (f.ts >= s0) & (f.ts <= on + E.DET_POST)]
    own = float(no.ts.min() - on) if len(no) else None
    rel = ASRel(asrel_for(c)); m, _ = run2.schedule(k, "P", rel, lag=run2.GUARD + 1, slow=(72, 72 + run2.GUARD + 1))
    S = engine2.Shared(rel); cnt = {}
    for t, kind, p, path in m:
        if kind != "A": continue
        for x in S.export_anoms(path):
            if x in cul: key = (path[-1], x, int(t // W)); cnt[key] = cnt.get(key, 0) + 1
    al = [kk[2] * W for kk, n in cnt.items() if n >= 20]
    rows.append(dict(case=k, lead_min=ii["lead_s"] / 60, owner_origin_first_s=own, owner_leak_first_s=float(min(al) - on) if al else None))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv("../results/poison/owner_q2.csv", index=False)

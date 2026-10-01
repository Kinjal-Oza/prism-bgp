"""Development (8) + held-out (8) incidents together, at the frozen operating points.
Development units come from results/per_case_results_parquet.zip (unpacked to DEV_DIR)."""
import os, sys, json, numpy as np, pandas as pd
import evaluate as E
from cases import cases, heldout_cases
DEV_DIR = sys.argv[1] if len(sys.argv) > 1 else "dev_units"
dev = cases(); ho = [c for c in heldout_cases() if E.done(c["case"])]
U = pd.concat([pd.read_parquet(f"{DEV_DIR}/{c['case']}.units.parquet") for c in dev] +
              [E.case_units(c) for c in ho], ignore_index=True)
allc = dev + ho
inc = [c for c in allc if c["label"] == "incident"]
hours = sum((E.TS(c["t1"]) - E.TS(c["t0"])) / 3600 for c in allc)
rows = []
for name, to, tx, vp in (("Quiet", 50, 2000, 1), ("Quiet +2VP", 50, 2000, 2), ("Balanced", 50, 200, 1), ("Sensitive", 5, 200, 1)):
    a = pd.concat([U[(U.det == "PRISM-origin") & (U.score >= to)], U[(U.det == "PRISM-export") & (U.score >= tx) & (U.peers >= vp)]])
    got = []; fa = 0; d = []
    for c in inc:
        on = E.TS(E.datetime_parse(c["onset"])); ac = a[a.case == c["case"]]
        cm = ac.off.isin(c["culprits"]); w = (ac["first"] >= on - E.DET_PRE) & (ac["first"] <= on + E.DET_POST)
        if (cm & w).any(): got.append(c["case"]); d.append(float(ac[cm & w]["first"].min() - on))
        fa += int((~cm).sum())
    fa += int(a[a.case.str.endswith("_ctl")].shape[0])
    rows.append(dict(point=name, detected=len(got), n=len(inc), which=",".join(got), fa_per_day=fa / hours * 24,
                     median_first_flag_delay_s=float(np.median(d))))
df = pd.DataFrame(rows); df.to_csv("out/combined_ops.csv", index=False)
json.dump(dict(exposure_hours=hours, ops=rows), open("out/combined.json", "w"), indent=1)
print("exposure hours", hours); print(df.to_string())

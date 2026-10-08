"""Summarize the multi-collector runs (pre-registered 2026-10-07): our 32 cases at the frozen operating points, and the
178-event benchmark (detection, owner detection, visibility classes, false alerts), next to the single-collector results."""
import json, glob, os, pandas as pd
import eval_poison as P
from cases import cases, heldout_cases
from ext_eval import wilson
os.makedirs("../results/multicollector", exist_ok=True)
R = pd.DataFrame([json.load(open(f)) for f in sorted(glob.glob("mc_out/*.json"))])
print("cases", len(R), "ok", int((R.ok == True).sum()))
if (R.ok != True).any(): print(R[R.ok != True][["id", "error"]].to_string())
ours = [c["case"] for c in cases() + heldout_cases() if os.path.exists(f"mc_out/{c['case']}.units.parquet")]
if ours:
    U = pd.concat([pd.read_parquet(f"mc_out/{k}.units.parquet") for k in ours], ignore_index=True)
    o = P.ops(U, ours); o.to_csv("../results/multicollector/ours_ops.csv", index=False); print(o.to_string())
x = R[(R.kind == "ext") & (R.ok == True)].copy()
if len(x):
    x["vis"] = (x.att_origin_ann + x.att_inpath_ann) > 0; x["pre"] = (x.rib_att_origin + x.rib_att_inpath) > 0
    x["cls"] = x.apply(lambda r: "not visible" if not r.vis else ("visible, attacker already present" if r.pre else "visible and new"), axis=1)
    n = len(x); d = int(x.detected.sum()); w = int(x.owner_detected.sum())
    S = dict(n=n, observatory=d, obs_ci=wilson(d, n), owner=w, owner_ci=wilson(w, n),
             fa_per_day=float(x.false_alerts.sum() / x.hours.sum() * 24), median_collectors=float(x.n_collectors.median()))
    print(S); print(x.groupby("cls").agg(n=("id", "size"), obs=("detected", "sum"), own=("owner_detected", "sum")))
    x.to_csv("../results/multicollector/benchmark_cases.csv", index=False)
    json.dump(S, open("../results/multicollector/benchmark_summary.json", "w"), indent=1, default=str)

"""Summarize the external benchmark (pre-registered 2026-10-07)."""
import json, glob, math, pandas as pd
def wilson(k, n, z=1.96):
    if n == 0: return (None, None)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))
R = pd.DataFrame([json.load(open(f)) for f in sorted(glob.glob("ext_out/X*.json"))])
OVER = {"X007", "X072", "X073", "X074", "X075", "X092", "X093"}
R["overlap"] = R.id.isin(OVER); R["year"] = R.time.str[:4].astype(int)
R["period"] = pd.cut(R.year, [2001, 2009, 2016, 2025], labels=["2002-2009", "2010-2016", "2017-2024"])
ok = R[R.ok == True]
rows = []
def summ(name, g):
    n = len(g); d = int(g.detected.sum()); o = int(g.owner_detected.sum())
    rows.append(dict(subset=name, n=n, observatory=d, obs_pct=round(100 * d / n, 1) if n else None, obs_ci=wilson(d, n),
                     owner=o, owner_pct=round(100 * o / n, 1) if n else None, owner_ci=wilson(o, n),
                     fa_per_day=round(g.false_alerts.sum() / g.hours.sum() * 24, 2) if n else None))
summ("all", ok); summ("excluding our 16", ok[~ok.overlap])
for cat, g in ok.groupby("category"): summ(cat, g)
for per, g in ok.groupby("period", observed=True): summ(str(per), g)
S = pd.DataFrame(rows)
import os; os.makedirs("../results/external", exist_ok=True)
S.to_csv("../results/external/external_summary.csv", index=False); R.to_csv("../results/external/external_cases.csv", index=False)
print("total", len(R), "ok", len(ok), "failed", int((R.ok != True).sum()))
print(S.to_string())
if (R.ok != True).any(): print(R[R.ok != True][["id", "time", "error"]].to_string())

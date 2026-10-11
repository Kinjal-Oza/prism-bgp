"""Case-level bootstrap interval for the quiet-point false-alert rate (all 32 cases, 256 h, D0). Seed 20261011."""
import numpy as np, pandas as pd, eval_poison as P
ks = P.ALL; U = pd.concat([P.case_units(k, "D0") for k in ks], ignore_index=True)
rows = [(k, *P.ops(U, [k]).query("point == 'Quiet'")[["false_alerts", "hours"]].iloc[0]) for k in ks]
df = pd.DataFrame(rows, columns=["case", "fa", "h"]); rng = np.random.default_rng(20261011)
r = [(lambda i: df.fa.values[i].sum() / df.h.values[i].sum() * 24)(rng.integers(0, len(df), len(df))) for _ in range(20000)]
print("rate", df.fa.sum() / df.h.sum() * 24, "95% CI", np.percentile(r, [2.5, 97.5]))

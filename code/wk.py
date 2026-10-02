"""Week-long controls: false alerts at the frozen operating points and owner-mode false-flag rates
over the 7-day windows in cases.longctl_cases(). Every alert in these windows counts as false."""
import os, re, json, pandas as pd
import evaluate as E
from cases import longctl_cases
W = E.W
rows = []; own = []; leak = []
for c in longctl_cases():
    k = c["case"]
    if not os.path.exists(f"out/{k}.units.parquet"): continue
    U = pd.read_parquet(f"out/{k}.units.parquet"); hrs = (E.TS(c["t1"]) - E.TS(c["t0"])) / 3600
    for name, to, tx, vp in (("Quiet", 50, 2000, 1), ("Quiet +2VP", 50, 2000, 2), ("Balanced", 50, 200, 1), ("Sensitive", 5, 200, 1)):
        a = pd.concat([U[(U.det == "PRISM-origin") & (U.score >= to)], U[(U.det == "PRISM-export") & (U.score >= tx) & (U.peers >= vp)]])
        rows.append(dict(case=k, point=name, hours=hrs, false_alerts=len(a), fa_per_day=len(a) / hrs * 24))
    s = open(f"out/{k}.log").read(); npf = int(re.search(r"prefixes=(\d+)", s).group(1))
    f = pd.read_parquet(f"out/{k}.flags.parquet", columns=["ts", "prefix"],
                        filters=[("type", "==", "NO"), ("ts", ">=", E.TS(c["t0"])), ("ts", "<", E.TS(c["t1"]))])
    own.append(dict(case=k, prefixes=npf, hours=hrs, flagged=f.prefix.nunique(), per_prefix_day=f.prefix.nunique() / npf / (hrs / 24)))
    if os.path.exists(f"out/{k}.nxorigin.parquet"):
        act = int(open(f"out/{k}.active_origins").read())
        x = pd.read_parquet(f"out/{k}.nxorigin.parquet"); x["w"] = (x.ts // W).astype(int)
        g = x.groupby(["origin", "off", "w"]).prefix.nunique().rename("n").reset_index(); g = g[g.n >= 20]
        leak.append(dict(case=k, active_origins=act, hours=hrs, origins_alerted=g.origin.nunique(),
                         per_origin_day=g.origin.nunique() / act / (hrs / 24)))
R = pd.DataFrame(rows); O = pd.DataFrame(own); L = pd.DataFrame(leak)
tot = R.groupby("point").agg(false_alerts=("false_alerts", "sum"), hours=("hours", "sum")).reset_index()
tot["fa_per_day"] = tot.false_alerts / tot.hours * 24
for t, n in ((R, "wk_ops"), (tot, "wk_ops_total"), (O, "wk_owner"), (L, "wk_owner_leak")): t.to_csv(f"out/{n}.csv", index=False)
pooled = dict(owner=float(O.flagged.sum() / (O.prefixes * O.hours / 24).sum()) if len(O) else None,
              leak=float(L.origins_alerted.sum() / (L.active_origins * L.hours / 24).sum()) if len(L) else None)
json.dump(dict(per_case=rows, total=tot.to_dict("records"), owner=own, owner_leak=leak, pooled=pooled), open("out/wk.json", "w"), indent=1)
pd.set_option("display.width", 200)
print(R.to_string()); print(tot.to_string()); print(O.to_string()); print(L.to_string()); print(pooled)

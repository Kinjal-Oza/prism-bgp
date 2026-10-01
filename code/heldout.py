"""Held-out evaluation. Applies the frozen PRISM design and operating points (chosen on the eight
development incidents) unchanged to the held-out incidents in cases.HELDOUT. Writes out/heldout_*.csv
and out/heldout.json. Nothing here is tuned on the held-out data."""
import json, re, numpy as np, pandas as pd
import evaluate as E
from cases import heldout_cases, cases as dev_cases
TS = E.TS; W = E.W
H = [c for c in heldout_cases() if E.done(c["case"])]
C = {c["case"]: c for c in H}
U = pd.concat([E.case_units(c) for c in H], ignore_index=True)
inc = [c for c in H if c["label"] == "incident"]
ctl = {c["case"][:-4]: c for c in H if c["label"] == "control"}
hours = sum((TS(c["t1"]) - TS(c["t0"])) / 3600 for c in H)
R = {"cases": [c["case"] for c in H], "exposure_hours": hours}
on_ = lambda c: TS(E.datetime_parse(c["onset"]))

def log_info(k):
    s = open(f"out/{k}.log").read()
    return dict(rib_entries=int(re.search(r"RIB (\d+) elems", s).group(1)),
                rib_prefixes=int(re.search(r"prefixes=(\d+)", s).group(1)),
                announcements=int(re.search(r"UPD (\d+) (\d+)s", s).group(1)),
                runtime_s=int(re.search(r"UPD \d+ (\d+)s", s).group(1)))
rows = []
for k, c in C.items():
    vol = pd.read_parquet(f"out/{k}.vol.parquet"); t0, t1 = TS(c["t0"]), TS(c["t1"])
    rows.append(dict(case=k, label=c["label"], hours=(t1 - t0) / 3600,
                     test_announcements=int(vol[(vol.minute * 60 >= t0) & (vol.minute * 60 < t1)].ann.sum()), **log_info(k)))
ds = pd.DataFrame(rows); ds.to_csv("out/heldout_dataset.csv", index=False); R["dataset"] = rows

# 1. culprit rank, no threshold
FAM = {"origin": "PRISM-origin", "export": "PRISM-export"}
rows = []
for c in inc:
    on = on_(c)
    for fam, det in FAM.items():
        g = U[(U.det == det) & (U.case == c["case"])]
        cg = g[g.off.isin(c["culprits"]) & (g["first"] >= on - E.DET_PRE) & (g["first"] <= on + E.DET_POST)]
        if len(cg) == 0:
            rows.append(dict(case=c["case"], family=fam, found=False, units_in_window=len(g))); continue
        b = cg.sort_values("score", ascending=False).iloc[0]
        gc = U[(U.det == det) & (U.case == c["case"] + "_ctl")]
        rows.append(dict(case=c["case"], family=fam, found=True, culprit=int(b.off), prefixes=int(b.c), peers=int(b.peers),
                         score=float(b.score), rank_in_window=int((g.score > b.score).sum()) + 1, units_in_window=len(g),
                         first_flag_delay_s=float(b["first"] - on), ctl_week_before_max=float(gc.score.max()) if len(gc) else None))
cul = pd.DataFrame(rows); cul.to_csv("out/heldout_culprits.csv", index=False); R["culprits"] = rows

# 2. frozen operating points
OPS = [("Quiet", 50, 2000, 1), ("Quiet +2VP", 50, 2000, 2), ("Balanced", 50, 200, 1), ("Sensitive", 5, 200, 1)]
def run(a):
    got = []; fa = 0; delays = []
    for c in inc:
        on = on_(c); ac = a[a.case == c["case"]]
        cm = ac.off.isin(c["culprits"]); w = (ac["first"] >= on - E.DET_PRE) & (ac["first"] <= on + E.DET_POST)
        if (cm & w).any(): got.append(c["case"]); delays.append(float(ac[cm & w]["first"].min() - on))
        fa += int((~cm).sum())
    fa += int(a[a.case.str.endswith("_ctl")].shape[0])
    return got, fa, delays
rows = []
for name, to, tx, vp in OPS:
    a = pd.concat([U[(U.det == "PRISM-origin") & (U.score >= to)],
                   U[(U.det == "PRISM-export") & (U.score >= tx) & (U.peers >= vp)]])
    got, fa, d = run(a)
    rows.append(dict(point=name, tau_o=to, tau_x=tx, detected=len(got), n=len(inc), which=",".join(got),
                     false_alerts=fa, fa_per_day=fa / hours * 24, median_first_flag_delay_s=float(np.median(d)) if d else None))
ops = pd.DataFrame(rows); ops.to_csv("out/heldout_ops.csv", index=False); R["ops"] = rows

# 2b. baselines at the thresholds that matched PRISM's quiet budget on the development set
rows = []
for det, tau in (("base:volume-z", 30), ("base:MOAS-snapshot", 100), ("base:valley-free", 1000)):  # dev-set points quoted in the paper
    a = U[(U.det == det) & (U.score >= tau)]
    if det == "base:volume-z":
        got = []; fa = 0
        for c in inc:
            on = on_(c); ac = a[a.case == c["case"]]; w = (ac["first"] >= on - E.DET_PRE) & (ac["first"] <= on + E.DET_POST)
            if w.any(): got.append(c["case"])
            fa += int((~w).sum())
        fa += int(a[a.case.str.endswith("_ctl")].shape[0])
    else:
        got, fa, _ = run(a)
    rows.append(dict(detector=det, tau=tau, detected=len(got), which=",".join(got), fa_per_day=fa / hours * 24))
bl = pd.DataFrame(rows); bl.to_csv("out/heldout_baselines.csv", index=False); R["baselines"] = rows

# 3. week-before calibration
rows = []
for c in inc:
    if c["case"] not in ctl: continue
    on = on_(c); hit = False; fa = 0; first = None; taus = {}
    for fam, det in FAM.items():
        tau = U[(U.det == det) & (U.case == c["case"] + "_ctl")].score.max(); tau = 0.0 if not tau >= 0 else float(tau)
        taus[fam] = tau
        g = U[(U.det == det) & (U.case == c["case"]) & (U.score > tau)]
        cm = g.off.isin(c["culprits"]); w = (g["first"] >= on - E.DET_PRE) & (g["first"] <= on + E.DET_POST)
        h = g[cm & w]
        if len(h): hit = True; d = float(h["first"].min() - on); first = d if first is None else min(first, d)
        fa += int((~cm).sum())
    rows.append(dict(case=c["case"], detected=hit, first_flag_delay_s=first, false_alerts=fa,
                     tau_origin=taus["origin"], tau_export=taus["export"]))
wk = pd.DataFrame(rows); wk.to_csv("out/heldout_weekcal.csv", index=False); R["weekcal"] = rows

# 4. owner mode: every NO flag on a monitored prefix; NX aggregated per victim origin (kappa = 20)
rows = []
for k, c in C.items():
    t0, t1 = TS(c["t0"]), TS(c["t1"]); hrs = (t1 - t0) / 3600; npf = log_info(k)["rib_prefixes"]
    f = pd.read_parquet(f"out/{k}.flags.parquet", columns=["ts", "off", "prefix"],
                        filters=[("type", "==", "NO"), ("ts", ">=", t0), ("ts", "<", t1)])
    if c["label"] == "incident":
        on = on_(c); cm = f.off.isin(c["culprits"])
        v = f[cm & (f.ts >= on - E.DET_PRE) & (f.ts <= on + E.DET_POST)]
        nv = v.prefix.nunique(); d = float(v.ts.min() - on) if len(v) else None; ben = f[~cm].prefix.nunique()
    else:
        nv = None; d = None; ben = f.prefix.nunique()
    rows.append(dict(case=k, label=c["label"], prefixes=npf, hours=hrs, victim_prefixes_flagged=nv,
                     first_victim_flag_s=d, benign_flagged_prefixes=ben, per_prefix_day_rate=ben / npf / (hrs / 24)))
own = pd.DataFrame(rows); own.to_csv("out/heldout_owner.csv", index=False); R["owner"] = rows
oc = own[own.label == "control"]
R["owner_pooled_rate"] = float(oc.benign_flagged_prefixes.sum() / (oc.prefixes * oc.hours / 24).sum())
import os
rows = []
for k, c in C.items():
    if not os.path.exists(f"out/{k}.nxorigin.parquet"): continue
    act = int(open(f"out/{k}.active_origins").read()); hrs = (TS(c["t1"]) - TS(c["t0"])) / 3600
    f = pd.read_parquet(f"out/{k}.nxorigin.parquet"); f["w"] = (f.ts // W).astype(int)
    g = f.groupby(["origin", "off", "w"]).prefix.nunique().rename("n").reset_index(); a = g[g.n >= 20]
    if c["label"] == "incident":
        on = on_(c); cm = a.off.isin(c["culprits"]); win = (a.w * W >= on - E.DET_PRE - W) & (a.w * W <= on + E.DET_POST)
        vict = a[cm & win].origin.nunique(); ben = a[~cm].origin.nunique()
    else:
        vict = None; ben = a.origin.nunique()
    rows.append(dict(case=k, label=c["label"], active_origins=act, hours=hrs, victim_origins_alerted=vict,
                     benign_origins_alerted=ben, per_origin_day_rate=ben / act / (hrs / 24)))
ol = pd.DataFrame(rows); ol.to_csv("out/heldout_owner_leak.csv", index=False); R["owner_leak"] = rows
if len(ol):
    q = ol[ol.label == "control"]; R["owner_leak_pooled_rate"] = float(q.benign_origins_alerted.sum() / (q.active_origins * q.hours / 24).sum())
json.dump(R, open("out/heldout.json", "w"), indent=1, default=str)
pd.set_option("display.width", 200)
for t in (ds, cul, ops, bl, wk, own, ol): print(t.to_string(), "\n")
print("owner pooled", R.get("owner_pooled_rate"), "leak pooled", R.get("owner_leak_pooled_rate"))

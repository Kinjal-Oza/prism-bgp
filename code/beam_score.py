"""Score one BEAM detection run with the pre-registered metrics (addenda 1eba976, f8a6bfd).
Usage: python3 beam_score.py CASE TAG OUTDIR   (OUTDIR holds beam_<CASE>_<TAG>_info.json and out_<CASE>_<TAG>.tgz)
- detected: a BEAM alarm whose culprit ASes include a listed culprit and one of whose route changes falls in
  [onset-10 min, onset+60 min].
- attribution-free: an alarm with a route change in that window on a culprit-announced prefix (or a more-specific).
- false alarms: alarm groups in the 12-h control window, plus groups in the 4-h test window naming no culprit, per day.
- continuous: route changes in [onset-10, onset+60] whose new path contains the culprit: median diff_balance and the
  median of their percentiles among all route changes of the same hour.
"""
import sys, os, json, glob, tarfile, ipaddress
from datetime import datetime, timedelta, timezone
import numpy as np, pandas as pd
CASE, TAG, D = sys.argv[1:4]
CULP = {"GO2017": [15169], "SH2019": [21217], "VI2021": [55410]}[CASE]
here = os.path.dirname(os.path.abspath(__file__))
info = json.load(open(f"{D}/beam_{CASE}_{TAG}_info.json"))
x = f"{D}/x_{CASE}_{TAG}"
if not os.path.isdir(x):
    os.makedirs(x); tarfile.open(f"{D}/out_{CASE}_{TAG}.tgz").extractall(x, filter="data")
x = glob.glob(f"{x}/out_*")[0]
P = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
T = P(info["onset"]); W0, W1 = (T - timedelta(minutes=10)).timestamp(), (T + timedelta(minutes=60)).timestamp()
TEST = [P(s) for s in info["test"]]; CTL = [P(s) for s in info["ctl"]]

seeds = json.load(open(f"{here}/out2/{CASE}.D0.seeds.json"))
cpfx = [ipaddress.ip_network(s[1]) for s in seeds if s[2] in CULP]
cpfx_set = {str(p) for p in cpfx}
by_len = {}
for p in cpfx: by_len.setdefault(p.prefixlen, set()).add(int(p.network_address))
def culprit_prefix(s):
    try: n = ipaddress.ip_network(s)
    except ValueError: return False
    if n.version != 4: return False
    a = int(n.network_address)
    return any(((a >> (32 - L)) << (32 - L)) in v for L, v in by_len.items() if L <= n.prefixlen)

def culprit_ases(c):
    try: t = json.loads(c)
    except Exception: return set()
    out = set()
    def walk(v):
        if isinstance(v, list): [walk(i) for i in v]
        else: out.add(str(v))
    walk(t); return out

res = dict(case=CASE, tag=TAG, detected=False, attr_free=False, ctl_alarms=0, test_alarms_noculprit=0, test_alarms=0)
kept = [i for i in info["infos"] if i["kept"]]
for i in kept:
    d1 = datetime.strptime(i["d1"], "%Y%m%d%H").replace(tzinfo=timezone.utc)
    where = "ctl" if CTL[0] <= d1 < CTL[1] else ("test" if TEST[0] <= d1 < TEST[1] else None)
    if not i.get("save_path"): continue
    a = pd.read_csv(f"{x}/{os.path.basename(i['save_path'])}")
    for g, ev in a.groupby("group_id"):
        ases = set().union(*[culprit_ases(c) for c in ev["culprit"].unique()])
        names = bool(ases & {str(c) for c in CULP})
        ts = ev["timestamp"].astype(float)
        inwin = ((ts >= W0) & (ts <= W1)).any()
        if where == "ctl": res["ctl_alarms"] += 1
        if where == "test":
            res["test_alarms"] += 1
            if not names: res["test_alarms_noculprit"] += 1
        if inwin and names: res["detected"] = True
        if inwin and any(culprit_prefix(p) for p in pd.concat([ev["prefix1"], ev["prefix2"]]).unique()): res["attr_free"] = True
hrs = (CTL[1] - CTL[0] + TEST[1] - TEST[0]).total_seconds() / 3600
res["false_alarms_per_day"] = round((res["ctl_alarms"] + res["test_alarms_noculprit"]) / hrs * 24, 2)

# continuous metric (percentile within the same hour)
frames = []
for rc in sorted(glob.glob(f"{x}/*.csv")):
    if rc.endswith(".bm.csv") or "alarms" in rc: continue
    bm = rc[:-4] + ".bm.csv"
    if not os.path.exists(bm): continue
    ft = datetime.strptime(os.path.basename(rc)[:13], "%Y%m%d.%H%M").replace(tzinfo=timezone.utc)
    if not (T - timedelta(hours=2) <= ft <= T + timedelta(hours=2)): continue   # only hours that can hold the window
    try: r = pd.read_csv(rc, usecols=["timestamp", "path2"]); m = pd.read_csv(bm, usecols=["diff", "path_d1", "path_d2"])
    except pd.errors.EmptyDataError: continue
    df = pd.concat([r, m], axis=1); df["hour"] = os.path.basename(rc)[:11]; frames.append(df)
vals, pcts = [], []
if frames:
    df = pd.concat(frames, ignore_index=True)
    df["db"] = (df["diff"] / (df["path_d1"] + df["path_d2"])).replace([np.inf, -np.inf], np.nan)
    df["ts"] = df["timestamp"].astype(float)
    hit = (df.ts >= W0) & (df.ts <= W1) & df["path2"].astype(str).apply(lambda p: any(str(c) in p.split(" ") for c in CULP))
    for h, g in df.groupby("hour"):
        ref = np.sort(g["db"].dropna().values)
        for v in g.loc[hit[g.index], "db"].dropna().values:
            vals.append(v); pcts.append(100.0 * np.searchsorted(ref, v, side="right") / len(ref))
res["n_culprit_route_changes"] = len(vals)
res["median_diff_balance"] = float(np.median(vals)) if vals else None
res["median_percentile"] = float(np.median(pcts)) if pcts else None
print(json.dumps(res, indent=1))
json.dump(res, open(f"{D}/score_{CASE}_{TAG}.json", "w"), indent=1)

# after BEAM's own post-processing (alarm_postprocess + summary), if available
pp = sorted(glob.glob(f"{D}/pp_{CASE}_{TAG}_*.csv"))
if pp:
    a = pd.concat([pd.read_csv(f).assign(_src=i) for i, f in enumerate(pp)], ignore_index=True)   # group ids restart per month file
    r2 = dict(detected=False, attr_free=False, ctl_alarms=0, test_alarms=0, test_alarms_noculprit=0)
    for g, ev in a.groupby(["_src", "group_id"]):
        ts = ev["timestamp"].astype(float); t0 = datetime.fromtimestamp(ts.min(), timezone.utc).replace(minute=0, second=0, microsecond=0)
        ases = set().union(*[culprit_ases(c) for c in ev["culprit"].unique()])
        names = bool(ases & {str(c) for c in CULP}); inwin = ((ts >= W0) & (ts <= W1)).any()
        if CTL[0] <= t0 < CTL[1]: r2["ctl_alarms"] += 1
        if TEST[0] <= t0 < TEST[1]:
            r2["test_alarms"] += 1; r2["test_alarms_noculprit"] += (not names)
        if inwin and names: r2["detected"] = True
        if inwin and any(culprit_prefix(p) for p in pd.concat([ev["prefix1"], ev["prefix2"]]).unique()): r2["attr_free"] = True
    r2["false_alarms_per_day"] = round((r2["ctl_alarms"] + r2["test_alarms_noculprit"]) / hrs * 24, 2)
    res["after_postprocess"] = r2
    print(json.dumps(r2, indent=1)); json.dump(res, open(f"{D}/score_{CASE}_{TAG}.json", "w"), indent=1)

import shutil as _sh; _sh.rmtree(os.path.dirname(x), ignore_errors=True)   # keep disk small; the .tgz stays

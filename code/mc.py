"""Second-collector corroboration (rules fixed in HELDOUT_PREREGISTRATION.md before any RIS data was run).
Usage: python3 mc.py DEV_UNITS_DIR RV2_HELDOUT_OUT_DIR RIS_OUT_DIR"""
import sys, json, numpy as np, pandas as pd
import evaluate as E
from cases import cases, heldout_cases
DEV, HO, RIS = sys.argv[1:4]
dev, ho = cases(), heldout_cases()
FAMS = ("PRISM-origin", "PRISM-export")
def load(d, cs):
    if not cs: return pd.DataFrame(columns=["case", "det", "off", "w", "c", "peers", "first", "score"])
    U = pd.concat([pd.read_parquet(f"{d}/{c['case']}.units.parquet") for c in cs], ignore_index=True)
    return U[U.det.isin(FAMS)]
RV = pd.concat([load(DEV, dev), load(HO, ho)], ignore_index=True)
RS = load(RIS, dev + ho)
key = lambda U: set(zip(U.case, U.det, U.off, U.w))
seen = {"rv": key(RV), "ris": key(RS)}
def thr(U, to, tx):
    return U[((U.det == FAMS[0]) & (U.score >= to)) | ((U.det == FAMS[1]) & (U.score >= tx))]
def corroborated(A, other):
    S = seen[other]
    ok = [any((c, d, o, w + k) in S for k in (-1, 0, 1)) for c, d, o, w in zip(A.case, A.det, A.off, A.w)]
    return A[ok]
def alerts(rule, to, tx):
    a_rv, a_ris = thr(RV, to, tx), thr(RS, to, tx)
    if rule == "RV2 alone": A = a_rv
    elif rule == "RIS alone": A = a_ris
    elif rule == "Either": A = pd.concat([a_rv, a_ris])
    elif rule == "Corroborated": A = pd.concat([corroborated(a_rv, "ris"), corroborated(a_ris, "rv")])
    return A.groupby(["case", "det", "off", "w"], as_index=False)["first"].min()   # one alert per unit
def score(A, cs):
    inc = [c for c in cs if c["label"] == "incident"]
    hours = sum((E.TS(c["t1"]) - E.TS(c["t0"])) / 3600 for c in cs)
    names = {c["case"] for c in cs}; A = A[A.case.isin(names)]
    got = []; fa = 0; d = []
    for c in inc:
        on = E.TS(E.datetime_parse(c["onset"])); ac = A[A.case == c["case"]]
        cm = ac.off.isin(c["culprits"]); w = (ac["first"] >= on - E.DET_PRE) & (ac["first"] <= on + E.DET_POST)
        if (cm & w).any(): got.append(c["case"]); d.append(float(ac[cm & w]["first"].min() - on))
        fa += int((~cm).sum())
    fa += int(A[A.case.str.endswith("_ctl")].shape[0])
    return dict(detected=len(got), n=len(inc), which=",".join(got), false_alerts=fa, fa_per_day=fa / hours * 24,
                median_first_flag_delay_s=float(np.median(d)) if d else None)
rows = []
for pname, to, tx in (("Quiet", 50, 2000), ("Balanced", 50, 200), ("Sensitive", 5, 200)):
    for rule in ("RV2 alone", "RIS alone", "Either", "Corroborated"):
        A = alerts(rule, to, tx)
        for sname, cs in (("dev", dev), ("heldout", ho), ("all", dev + ho)):
            rows.append(dict(point=pname, rule=rule, set=sname, **score(A, cs)))
R = pd.DataFrame(rows); R.to_csv("out/mc_ops.csv", index=False)
# culprit visibility per collector (best culprit unit in the credit window, either family)
vis = []
for c in [c for c in dev + ho if c["label"] == "incident"]:
    on = E.TS(E.datetime_parse(c["onset"])); r = dict(case=c["case"])
    for name, U in (("rv", RV), ("ris", RS)):
        g = U[(U.case == c["case"]) & U.off.isin(c["culprits"]) & (U["first"] >= on - E.DET_PRE) & (U["first"] <= on + E.DET_POST)]
        r[f"{name}_best_score"] = float(g.score.max()) if len(g) else 0.0
        r[f"{name}_best_pfx"] = int(g.c.max()) if len(g) else 0
        r[f"{name}_peers"] = int(g.peers.max()) if len(g) else 0
    vis.append(r)
V = pd.DataFrame(vis); V.to_csv("out/mc_visibility.csv", index=False)
json.dump(dict(ops=rows, visibility=vis), open("out/mc.json", "w"), indent=1)
pd.set_option("display.width", 220)
print(R.to_string()); print(V.to_string())

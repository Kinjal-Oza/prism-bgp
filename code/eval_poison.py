"""Evaluation for the poisoning study and the added comparisons (pre-registered 2026-10-06).
Reads out2/ (engine2 runs), out3/ (ARTEMIS runs), rpki/. Writes results/poison/*.csv and poison.json."""
import os, re, json, math, heapq, numpy as np, pandas as pd
import evaluate as E
from cases import all_cases, cases as dev_cases, heldout_cases
W = 300; TAU = {"NO": 50, "NX": 2000}
C = {c["case"]: c for c in all_cases()}
DEV = [c["case"] for c in dev_cases()]; HO = [c["case"] for c in heldout_cases()]; ALL = DEV + HO
OUT = "../results/poison"; os.makedirs(OUT, exist_ok=True)
on_ = lambda c: E.TS(E.datetime_parse(c["onset"]))
OPS = [("Quiet", 50, 2000, 1), ("Quiet +2VP", 50, 2000, 2), ("Balanced", 50, 200, 1), ("Sensitive", 5, 200, 1)]
R = {}; SCHED = {}; SH = {}

def flags(k, view, ty=None):
    f = pd.read_parquet(f"out2/{k}.{view}.flags.parquet")
    return f if ty is None else f[f.type == ty]

def base_units(f):
    w = (f.ts // W).astype(np.int64)
    return (f.assign(w=w).groupby(["w", "off"]).agg(c=("prefix", "nunique"), peers=("peer", "nunique"),
            first=("ts", "min")).reset_index().sort_values(["w", "off"], kind="mergesort").reset_index(drop=True))

def score(g, events):
    """s = c / (1 + H_off(w)); events: iterable of (avail_window, off, value) entering H once w >= avail."""
    ev = sorted(events, key=lambda x: x[0]); i = 0; H = {}; s = []
    for w, o, c in g[["w", "off", "c"]].itertuples(index=False):
        while i < len(ev) and ev[i][0] <= w:
            _, oo, v = ev[i]; H[oo] = max(H.get(oo, 0), v); i += 1
        s.append(c / (1 + H.get(o, 0)))
    g = g.copy(); g["s"] = s; return g

def score2(g, ev_all, ev_adm, cap):
    """Exploratory (post hoc, see paper): H = max(H_admitted, min(H_all, cap))."""
    ea = sorted(ev_all, key=lambda x: x[0]); eb = sorted(ev_adm, key=lambda x: x[0]); i = j = 0; HA = {}; HB = {}; s = []
    for w, o, c in g[["w", "off", "c"]].itertuples(index=False):
        while i < len(ea) and ea[i][0] <= w: _, oo, v = ea[i]; HA[oo] = max(HA.get(oo, 0), v); i += 1
        while j < len(eb) and eb[j][0] <= w: _, oo, v = eb[j]; HB[oo] = max(HB.get(oo, 0), v); j += 1
        s.append(c / (1 + max(HB.get(o, 0), min(HA.get(o, 0), cap))))
    g = g.copy(); g["s"] = s; return g

def units(f, ty, mode="all", adm=None, guard=12, cap=None):
    """mode 'all': H from every unit (published PRISM); 'adm': H from later-admitted flags only (D1)."""
    f = f[f.type == ty]
    g = base_units(f)
    if mode == "all":
        ev = [(w + guard, o, c) for w, o, c in g[["w", "off", "c"]].itertuples(index=False)]
    else:
        a = adm[adm.fam == ty][["prefix", "off", "since", "admit"]].rename(columns={"since": "ts"})
        m = f.merge(a, on=["prefix", "off", "ts"], how="inner")
        m["w"] = (m.ts // W).astype(np.int64)
        ga = m.groupby(["w", "off"]).agg(a=("prefix", "nunique"), adm=("admit", "max")).reset_index()
        ev = [(max(w + guard, math.ceil(ad / W)), o, a) for w, o, a, ad in ga[["w", "off", "a", "adm"]].itertuples(index=False)]
        if cap is not None:
            ev_all = [(w + guard, o, c) for w, o, c in g[["w", "off", "c"]].itertuples(index=False)]
            return score2(g, ev_all, ev, cap)
    return score(g, ev)

def case_units(k, view, mode="all", guard=12, caps=None):
    c = C[k]; t0, t1 = E.TS(c["t0"]), E.TS(c["t1"])
    f = flags(k, view); adm = pd.read_parquet(f"out2/{k}.{view}.adm.parquet") if mode == "adm" else None
    parts = []
    for ty, det in (("NO", "PRISM-origin"), ("NX", "PRISM-export")):
        g = units(f, ty, mode, adm, guard, None if caps is None else caps[ty]); g = g[(g.w * W >= t0) & (g.w * W < t1)].copy()
        g["det"] = det; g["score"] = g.s; g["case"] = k; parts.append(g)
    return pd.concat(parts, ignore_index=True)

def ops(U, ks, extra=None):
    """Detection / false alerts at the frozen operating points, scored exactly as heldout.py/combined.py."""
    U = U[U.case.isin(ks)]
    if extra is not None: extra = extra[extra.case.isin(ks)]
    inc = [C[k] for k in ks if C[k]["label"] == "incident"]
    hours = sum((E.TS(C[k]["t1"]) - E.TS(C[k]["t0"])) / 3600 for k in ks)
    rows = []
    for name, to, tx, vp in OPS:
        a = pd.concat([U[(U.det == "PRISM-origin") & (U.score >= to)], U[(U.det == "PRISM-export") & (U.score >= tx) & (U.peers >= vp)]])
        if extra is not None and name == "Quiet": a = pd.concat([a, extra]).drop_duplicates(["case", "det", "w", "off"])
        got = []; fa = 0; d = []
        for c in inc:
            on = on_(c); ac = a[a.case == c["case"]]
            cm = ac.off.isin(c["culprits"]); w = (ac["first"] >= on - E.DET_PRE) & (ac["first"] <= on + E.DET_POST)
            if (cm & w).any(): got.append(c["case"]); d.append(float(ac[cm & w]["first"].min() - on))
            fa += int((~cm).sum())
        fa += int(a[a.case.str.endswith("_ctl")].shape[0])
        rows.append(dict(point=name, detected=len(got), n=len(inc), which=",".join(got), false_alerts=fa,
                         fa_per_day=fa / hours * 24, median_first_flag_delay_s=float(np.median(d)) if d else None, hours=hours))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    import sys
    parts = sys.argv[1:] or ["verify", "clean", "attack", "rpki", "guard", "artemis"]
    done = [k for k in ALL if os.path.exists(f"out2/{k}.D1.adm.parquet")]
    if "verify" in parts:
        rows = []
        for k in done:
            pub = pd.read_parquet(f"{'dev_units' if k in DEV else 'ho_units'}/{k}.units.parquet")
            U = case_units(k, "D0")
            for det in ("PRISM-origin", "PRISM-export"):
                cols = ["w", "off", "c", "peers", "first", "s"]
                a = U[U.det == det][cols].sort_values(["w", "off"]).reset_index(drop=True)
                b = pub[pub.det == det][cols].sort_values(["w", "off"]).reset_index(drop=True).astype(a.dtypes.to_dict())
                rows.append(dict(case=k, det=det, n_new=len(a), n_pub=len(b), identical=bool(len(a) == len(b) and np.allclose(a.values, b.values))))
        v = pd.DataFrame(rows); v.to_csv(f"{OUT}/verify_d0.csv", index=False)
        R["verify"] = dict(units_compared=int(v.n_new.sum()), all_identical=bool(v.identical.all()), cases=len(done))
        print(v[~v.identical].to_string() if not v.identical.all() else f"D0 reproduces published units in all {len(done)} cases")
    if "clean" in parts:
        res = []
        for label, mode, view in (("PRISM (D0)", "all", "D0"), ("D1 persistence-gated", "adm", "D1"), ("D1-hist (ablation)", "all", "D1")):
            U = pd.concat([case_units(k, view, mode) for k in done], ignore_index=True)
            for sname, ks in (("development", [k for k in done if k in DEV]), ("held-out", [k for k in done if k in HO]), ("all", done)):
                o = ops(U, ks); o.insert(0, "set", sname); o.insert(0, "variant", label); res.append(o)
        cl = pd.concat(res, ignore_index=True); cl.to_csv(f"{OUT}/clean_ops.csv", index=False); R["clean"] = cl.to_dict("records")
        print(cl[cl.point == "Quiet"].to_string())
    if "attack" in parts:
        import rpki
        rows = []
        for k in [k for k in ALL if os.path.exists(f"out2/{k}.A1P.adm.parquet")]:
            c = C[k]; on = on_(c); cul = set(c["culprits"]); info = json.load(open(f"out2/{k}.attack.json"))
            RO = rpki.load(c["t0"].strftime("%Y-%m-%d")) if os.path.exists(f"rpki/{c['t0']:%Y-%m-%d}_apnic.csv.xz") else None
            for view, var, mode in (("D0", "clean", "all"), ("D1", "clean", "adm"), ("A0", "T/P", "all"),
                                    ("A1T", "T", "adm"), ("A1T", "T", "all"), ("A1P", "P", "adm"), ("A1P", "P", "all"), ("A1Q", "Q", "adm")):
                f = flags(k, view); adm = pd.read_parquet(f"out2/{k}.{view}.adm.parquet") if mode == "adm" else None
                ii = (json.load(open(f"out2/{k}.attackq.json")) if var == "Q" else info["P" if var == "P" else "T"]); s0 = ii["seed_start"] if var != "clean" else on - 600
                hit = []; seedhit = []
                for ty in ("NO", "NX"):
                    g = units(f, ty, mode, adm); a = g[(g.s >= TAU[ty]) & g.off.isin(cul)]
                    hit += list(a[(a["first"] >= s0) & (a["first"] <= on + E.DET_POST)]["first"])
                    seedhit += list(a[(a["first"] >= s0) & (a["first"] < on - E.DET_PRE)]["first"])
                no = f[(f.type == "NO") & f.off.isin(cul) & (f.ts >= s0) & (f.ts <= on + E.DET_POST)]
                own = float(no.ts.min() - on) if len(no) else None
                rinv = None
                if RO is not None and len(no):
                    st = [rpki.state(RO, p, o) for p, o in zip(no.prefix, no.off)]
                    inv = no[[x == "invalid" for x in st]]; rinv = float(inv.ts.min() - on) if len(inv) else None
                ownleak = None
                if var != "clean":
                    import run2, engine2
                    from asrel import ASRel
                    from run_case import asrel_for
                    if k not in SCHED:
                        rel = ASRel(asrel_for(c)); SCHED[k] = {v: run2.schedule(k, v, rel)[0] for v in "TP"}; SCHED[k]["Q"] = run2.schedule(k, "P", rel, lag=13)[0]; SH[k] = engine2.Shared(rel)
                    cnt = {}
                    for t, kind, p, path in SCHED[k][var if var in ("P", "Q") else "T"]:
                        if kind != "A": continue
                        for x in SH[k].export_anoms(path):
                            if x in cul:
                                key = (path[-1], x, int(t // W)); cnt[key] = cnt.get(key, 0) + 1
                    al = [kk[2] * W for kk, n in cnt.items() if n >= 20]
                    ownleak = float(min(al) - on) if al else None
                rows.append(dict(case=k, view=view, attack=var, owner_leak_first_s=ownleak, defense={"D0": "PRISM", "A0": "PRISM"}.get(view, "D1" if mode == "adm" else "D1-hist"),
                                 detected=bool(hit), first_alert_s=float(min(hit) - on) if hit else None,
                                 alert_during_seeding=bool(seedhit), owner_first_flag_s=own, rpki_invalid_first_s=rinv,
                                 seed_announcements=ii["announcements"], seed_items=ii["items"], seed_windows=ii["windows"],
                                 lead_min=ii["lead_s"] / 60 if var != "clean" else None))
        at = pd.DataFrame(rows); at.to_csv(f"{OUT}/attack.csv", index=False); R["attack"] = rows
        print(at.to_string())
    if "rpki" in parts:
        import rpki
        rk = [k for k in done if os.path.exists(f"rpki/{C[k]['t0']:%Y-%m-%d}_apnic.csv.xz")]
        U = pd.concat([case_units(k, "D0") for k in rk], ignore_index=True)
        ext = []
        for k in rk:
            c = C[k]; t0, t1 = E.TS(c["t0"]), E.TS(c["t1"]); RO = rpki.load(c["t0"].strftime("%Y-%m-%d"))
            f = flags(k, "D0", "NO"); f = f[(f.ts >= t0) & (f.ts < t1)].copy()
            f["st"] = [rpki.state(RO, p, o) for p, o in zip(f.prefix, f.off)]
            inv = f[f.st == "invalid"]
            if len(inv):
                g = base_units(inv); g["det"] = "PRISM-origin"; g["score"] = np.inf; g["s"] = np.inf; g["case"] = k; ext.append(g)
        ext = pd.concat(ext, ignore_index=True) if ext else None
        o1 = ops(U, rk); o1.insert(0, "variant", "PRISM")
        o2 = ops(U, rk, extra=ext); o2.insert(0, "variant", "PRISM + RPKI tier")
        rt = pd.concat([o1[o1.point == "Quiet"], o2[o2.point == "Quiet"]]); rt.to_csv(f"{OUT}/rpki_tier.csv", index=False)
        R["rpki"] = dict(cases=rk, ops=rt.to_dict("records"), invalid_units=(0 if ext is None else len(ext)))
        print(rt.to_string())
    if "guard" in parts:
        rows = []
        for gmin in (0, 15, 30, 60, 120, 240):   # 0 = previous window only (identical to 5 min)
            U = pd.concat([case_units(k, "D0", "all", guard=max(1, gmin // 5)) for k in done], ignore_index=True)
            o = ops(U, done); o = o[o.point.isin(["Quiet", "Balanced"])]; o.insert(0, "G_min", gmin); rows.append(o)
        gs = pd.concat(rows, ignore_index=True); gs.to_csv(f"{OUT}/guard_sweep.csv", index=False); R["guard"] = gs.to_dict("records")
        print(gs.to_string())
    if "artemis" in parts:
        rows = []
        ak = [k for k in ALL if os.path.exists(f"out3/{k}.artemis.parquet") and os.path.exists(f"out2/{k}.D0.flags.parquet")]
        for k in ak:
            c = C[k]; t0, t1 = E.TS(c["t0"]), E.TS(c["t1"]); days = (t1 - t0) / 86400
            npf = int(re.search(r"prefixes=(\d+)", open(f"out2/{k}.clean.log").read()).group(1)) if os.path.exists(f"out2/{k}.clean.log") else None
            cul = set(c["culprits"]); inc = c["label"] == "incident"; on = on_(c) if inc else None
            A = pd.read_parquet(f"out3/{k}.artemis.parquet")
            no = flags(k, "D0", "NO"); no = no[(no.ts >= t0) & (no.ts < t1)].rename(columns={"off": "hijacker"})
            for name, d in (("PRISM owner (origin)", no), ("ARTEMIS-origin", A[A.type.isin(["E|0", "S|0"])]), ("ARTEMIS-full", A)):
                cm = d.hijacker.isin(cul) | (d.origin.isin(cul) if "origin" in d else False)
                det = None; dl = None
                if inc:
                    v = d[cm & (d.ts >= on - E.DET_PRE) & (d.ts <= on + E.DET_POST)]; det = len(v) > 0; dl = float(v.ts.min() - on) if det else None
                rows.append(dict(case=k, label=c["label"], detector=name, detected=det, first_s=dl,
                                 benign_prefixes=int(d[~cm].prefix.nunique()), rib_prefixes=npf, days=days))
        ar = pd.DataFrame(rows); ar.to_csv(f"{OUT}/artemis.csv", index=False)
        summ = ar.groupby("detector").apply(lambda g: pd.Series(dict(
            detected=int(g.detected.fillna(False).sum()), incidents=int((g.label == "incident").sum()),
            fa_per_prefix_day_pct=100 * g.benign_prefixes.sum() / (g.rib_prefixes * g.days).sum()))).reset_index()
        summ.to_csv(f"{OUT}/artemis_summary.csv", index=False); R["artemis"] = summ.to_dict("records")
        print(summ.to_string()); print(ar[ar.label == "incident"].pivot(index="case", columns="detector", values="first_s").to_string())
    if "capsweep" in parts:
        RS = [0, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, float("inf")]
        rows = []; atk = []
        AK = [k for k in ALL if os.path.exists(f"out2/{k}.A1Q.adm.parquet")]
        for r in RS:
            caps = {"NO": r * TAU["NO"], "NX": r * TAU["NX"]}
            U = pd.concat([case_units(k, "D1", "adm", caps=caps) for k in done], ignore_index=True)
            o = ops(U, done); o = o[o.point == "Quiet"]; o.insert(0, "cap_ratio", r); rows.append(o)
            for k in AK:
                c = C[k]; on = on_(c); cul = set(c["culprits"])
                for view in ("A1T", "A1P", "A1Q"):
                    f = flags(k, view); adm = pd.read_parquet(f"out2/{k}.{view}.adm.parquet")
                    info = json.load(open(f"out2/{k}.attackq.json")) if view == "A1Q" else json.load(open(f"out2/{k}.attack.json"))["T" if view == "A1T" else "P"]
                    hit = False
                    for ty in ("NO", "NX"):
                        g = units(f, ty, "adm", adm, cap=caps[ty]); a = g[(g.s >= TAU[ty]) & g.off.isin(cul)]
                        hit |= bool(((a["first"] >= info["seed_start"]) & (a["first"] <= on + E.DET_POST)).any())
                    atk.append(dict(cap_ratio=r, case=k, view=view, detected=hit))
        cs = pd.concat(rows, ignore_index=True); cs.to_csv(f"{OUT}/cap_sweep_clean.csv", index=False)
        ca = pd.DataFrame(atk); ca.to_csv(f"{OUT}/cap_sweep_attack.csv", index=False)
        print(cs[["cap_ratio", "detected", "fa_per_day"]].to_string())
        print(ca.pivot_table(index="cap_ratio", columns="view", values="detected", aggfunc="sum").to_string())
    json.dump(R, open(f"{OUT}/poison_{'_'.join(parts)}.json", "w"), indent=1, default=str)

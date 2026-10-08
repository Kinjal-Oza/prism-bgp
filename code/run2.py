"""Poisoning study runner.
  python3 run2.py clean CASE...   D0 (published engine, records culprit seed paths) + D1, one pass per case
  python3 run2.py attack CASE...  D0 and D1 under the pre-registered seeding attack (variants T and P)
Outputs go to out2/. See HELDOUT_PREREGISTRATION.md (history-poisoning addendum)."""
import sys, os, json, math
from datetime import timezone
from cases import all_cases
from run_case import asrel_for
import engine2
from asrel import ASRel

OUT = "out2"; W = 300; GUARD = 12; MARGIN = 0.8
TAU = {"NO": 50, "NX": 2000}           # Quiet operating point
TS = lambda d: d.replace(tzinfo=timezone.utc).timestamp()
ATTACKED = ["TM2015", "RT2017", "DV2017", "DQ2019", "RT2020", "ID2011", "ID2014", "GO2017", "SH2019", "VI2021"]
C = {c["case"]: c for c in all_cases()}

def onset(c):
    from evaluate import datetime_parse
    return TS(datetime_parse(c["onset"]))

def clean(k):
    c = C[k]; spec = [dict(name="D0", mode="D0"), dict(name="D1", mode="D1")]
    if c["label"] == "incident":
        on = onset(c); spec[0]["record"] = (set(c["culprits"]), on - 600, on + 3600)
    engine2.run(f"data/{k}", asrel_for(c), TS(c["t1"]), f"{OUT}/{k}", spec)

def schedule(k, variant, rel, lag=GUARD, slow=None):
    """Pre-registered greedy seeding schedule. Returns (messages, info)."""
    c = C[k]; cul = set(c["culprits"]); on = onset(c)
    seeds = json.load(open(f"{OUT}/{k}.D0.seeds.json"))           # [type, prefix, off, ts, path]
    items = {(t, p, o): path for t, p, o, ts, path in seeds}
    S = engine2.Shared(rel)
    def touches(path):
        t = set()
        if path[-1] in cul: t.add(("NO", path[-1]))
        for x in S.export_anoms(path):
            if x in cul: t.add(("NX", x))
        return t
    def covers(path, p):
        out = set()
        if path[-1] in cul and ("NO", p, path[-1]) in items: out.add(("NO", p, path[-1]))
        for x in S.export_anoms(path):
            if ("NX", p, x) in items: out.add(("NX", p, x))
        return out
    byp = {}
    for (t, p, o), path in items.items(): byp.setdefault(p, []).append(((t, p, o), path))
    anns = []                                                    # (prefix, path, touches)
    for p in sorted(byp):
        L = sorted(byp[p], key=lambda x: x[0][0] != "NO")         # NO path first
        left = set(i for i, _ in L)
        for it, path in L:
            if it not in left: continue
            cov = covers(path, p) or {it}
            left -= cov; anns.append((p, path, touches(path)))
    # greedy windows (attacker's own model of Eq. 2)
    hist = {}; counts = []; plan = []; i = 0; T6 = []
    while i < len(anns):
        k_ = len(counts)
        H = {}
        for j in range(0, k_ - lag + 1):
            for key, v in counts[j].items(): H[key] = max(H.get(key, 0), v)
        cnt = {}; batch = []
        if slow:   # D2-aware: trailing-L sums and their own lagged maxima (post: pre-registered Q2)
            L, lag6 = slow
            trail = {}
            for j in range(max(0, k_ - L + 1), k_):
                for key, v in counts[j].items(): trail[key] = trail.get(key, 0) + v
            H6 = {}
            for j in range(0, k_ - lag6 + 1):
                for key, v in T6[j].items(): H6[key] = max(H6.get(key, 0), v)
        while i < len(anns):
            tch = anns[i][2]
            ok = all(cnt.get(key, 0) + 1 <= math.floor(MARGIN * TAU[key[0]] * (1 + H.get(key, 0))) for key in tch)
            if ok and slow:
                ok = all(trail.get(key, 0) + cnt.get(key, 0) + 1 <= math.floor(MARGIN * TAU[key[0]] * (1 + H6.get(key, 0))) for key in tch)
            if ok:
                for key in tch: cnt[key] = cnt.get(key, 0) + 1
                batch.append(anns[i]); i += 1
            else: break
        if not batch and i < len(anns) and not slow: raise RuntimeError("cannot place seed")
        if slow:
            t6 = dict(trail)
            for key, v in cnt.items(): t6[key] = t6.get(key, 0) + v
            T6.append(t6)
            if len(counts) > 5000: raise RuntimeError("no progress")
        counts.append(cnt); plan.append(batch)
    K = len(plan)
    end = on - (900 if variant == "T" else 4500)   # Q: persistent, D1-aware (lag 13 windows)
    start = math.floor((end - K * W) / W) * W
    msgs = []
    for kk, batch in enumerate(plan):
        m = max(1, len(batch))
        for j, (p, path, _) in enumerate(batch):
            t = start + kk * W + (j + 0.5) * W / m
            msgs.append((t, "A", p, path))
            if variant == "T": msgs.append((t + 1, "W", p, path))
    ribtime = open(f"data/{k}/RIBTIME").read().strip() if os.path.exists(f"data/{k}/RIBTIME") else None
    info = dict(case=k, variant=variant, items=len(items), announcements=len(anns), windows=K, seed_start=start,
                seed_end=start + K * W, lead_s=on - start, onset=on, ribtime=ribtime,
                no_prefixes=sorted({p for (t, p, o) in items if t == "NO"}))
    return msgs, info

def attack(k):
    c = C[k]; rel = ASRel(asrel_for(c))
    mT, iT = schedule(k, "T", rel); mP, iP = schedule(k, "P", rel)
    json.dump(dict(T=iT, P=iP), open(f"{OUT}/{k}.attack.json", "w"))
    spec = [dict(name="A0", mode="D0", inject=mT), dict(name="A1T", mode="D1", inject=mT),
            dict(name="A1P", mode="D1", inject=mP)]
    engine2.run(f"data/{k}", asrel_for(c), TS(c["t1"]), f"{OUT}/{k}", spec)

def attackq(k):
    """Post-hoc variant (added 2026-10-06 after the TM2015 and RT2017 attack results, disclosed as such):
    a persistent attacker that paces against D1 rather than Eq. 2, i.e. counts its own windows into H only
    13 windows later (admission after T_adm plus the window boundary)."""
    c = C[k]; rel = ASRel(asrel_for(c))
    mQ, iQ = schedule(k, "P", rel, lag=GUARD + 1); iQ["variant"] = "Q"
    json.dump(iQ, open(f"{OUT}/{k}.attackq.json", "w"))
    engine2.run(f"data/{k}", asrel_for(c), TS(c["t1"]), f"{OUT}/{k}", [dict(name="A1Q", mode="D1", inject=mQ)])

def attackq2(k):
    """Pre-registered 2026-10-07: persistent attacker pacing against D2 (5-min with lag 13, 6-h trailing with lag 85)."""
    c = C[k]; rel = ASRel(asrel_for(c))
    m, i = schedule(k, "P", rel, lag=GUARD + 1, slow=(72, 72 + GUARD + 1)); i["variant"] = "Q2"
    first = min(int(f.split("upd.")[1][:8] + f.split("upd.")[1][9:13]) for f in os.listdir(f"data/{k}") if f.startswith("upd."))
    from datetime import datetime as _dt
    fs = _dt.strptime(str(first), "%Y%m%d%H%M").replace(tzinfo=timezone.utc).timestamp()
    i["first_update_ts"] = fs; i["representable"] = bool(i["seed_start"] >= fs)
    json.dump(i, open(f"{OUT}/{k}.attackq2.json", "w"))
    if not i["representable"]: print("not representable", k, i["lead_s"] / 3600, flush=True); return
    engine2.run(f"data/{k}", asrel_for(c), TS(c["t1"]), f"{OUT}/{k}", [dict(name="A2Q", mode="D1", inject=m)])

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    mode, ks = sys.argv[1], sys.argv[2:]
    for k in ks:
        print("CASE", mode, k, flush=True)
        {"clean": clean, "attack": attack, "attackq": attackq, "attackq2": attackq2}[mode](k)

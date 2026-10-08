"""D2 (pre-registered 2026-10-07): 6-h offender score on top of D1. Episodes of s6 = c6/(1+H6) >= tau."""
import math, numpy as np, pandas as pd
from collections import Counter, defaultdict
W = 300; L = 72; LAG6 = 72 + 12

def _c6_series(wins, pfx):
    """for sorted (w, prefix) lists, c6 at each flag window: distinct prefixes in [w-L+1, w]"""
    out = {}; cnt = Counter(); j = 0; n = len(wins)
    for i in range(n):
        w = wins[i]; cnt[pfx[i]] += 1
        while wins[j] < w - L + 1:
            cnt[pfx[j]] -= 1
            if cnt[pfx[j]] == 0: del cnt[pfx[j]]
            j += 1
        out[w] = len(cnt)
    return out

def episodes(f, ty, adm, tau):
    """f: flags (ts,type,off,prefix,peer); adm: D1 admissions. Returns DataFrame of episodes (off, w, first)."""
    f = f[f.type == ty].copy(); f["w"] = (f.ts // W).astype(np.int64)
    a = adm[adm.fam == ty][["prefix", "off", "since", "admit"]].rename(columns={"since": "ts"})
    fa = f.merge(a, on=["prefix", "off", "ts"], how="inner")
    rows = []
    adm_by = {o: g.sort_values("w") for o, g in fa.groupby("off")}
    for o, g in f.groupby("off"):
        g = g.sort_values(["w", "ts"])
        wins = g.w.tolist(); pf = g.prefix.tolist(); first = g.groupby("w").ts.min().to_dict()
        # H6 events from admitted flags of this AS
        ev = []
        if o in adm_by:
            ga = adm_by[o]; aw = ga.w.tolist(); ap = ga.prefix.tolist(); ad = ga.admit.tolist()
            c6a = _c6_series(aw, ap)
            for w_, v in c6a.items():
                mx = max(ad[k] for k in range(len(aw)) if w_ - L + 1 <= aw[k] <= w_)
                ev.append((max(w_ + LAG6, math.ceil(mx / W)), v))
        ev.sort()
        # evaluation points: flag windows, leave windows, H6 availability windows
        pts = sorted(set(wins) | {x + L for x in set(wins)} | {e[0] for e in ev})
        cnt = Counter(); j = 0; i = 0; n = len(wins); H6 = 0; k = 0; prev = False
        for w in pts:
            while i < n and wins[i] <= w: cnt[pf[i]] += 1; i += 1
            while j < i and wins[j] < w - L + 1:
                cnt[pf[j]] -= 1
                if cnt[pf[j]] == 0: del cnt[pf[j]]
                j += 1
            while k < len(ev) and ev[k][0] <= w: H6 = max(H6, ev[k][1]); k += 1
            s6 = len(cnt) / (1 + H6); on = s6 >= tau
            if on and not prev:
                fw = max([x for x in first if x <= w], default=w)
                rows.append(dict(off=int(o), w=int(w), first=float(first.get(fw, w * W)), c6=len(cnt), s6=s6))
            prev = on
    return pd.DataFrame(rows, columns=["off", "w", "first", "c6", "s6"])

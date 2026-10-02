"""Scores engine flags into alerts and evaluates against documented incidents + control windows."""
import sys, json, os
import numpy as np, pandas as pd
from datetime import timezone
from cases import cases
W=300  # 5-minute alert windows
DET_PRE=600; DET_POST=3600  # detection credit window around documented onset
TS=lambda d: d.replace(tzinfo=timezone.utc).timestamp()

def units(df, types):
    d=df[df.type.isin(types)]
    w=(d.ts//W).astype(np.int64)
    g=(d.assign(w=w).groupby(["w","off"],observed=True)
         .agg(c=("prefix","nunique"),peers=("peer","nunique"),first=("ts","min")).reset_index())
    return g.sort_values("w")

GUARD=12  # windows (=60 min) excluded from an offender's history, so an event in progress cannot suppress itself
def adaptive(g):
    """offender-adaptive score s = c/(1+H_x); H_x = max count of offender x in any window
    that ended at least GUARD windows before the current one (lagged per-offender history)."""
    from collections import deque
    H={}; pending=deque(); s=[]
    for w,o,c in g[["w","off","c"]].itertuples(index=False):
        while pending and pending[0][0] <= w-GUARD:
            _,oo,cc=pending.popleft(); H[oo]=max(H.get(oo,0),cc)
        s.append(c/(1+H.get(o,0))); pending.append((w,o,c))
    g=g.copy(); g["s"]=s; return g

DETECTORS={
 # name: (flag types, score column)
 "PRISM-origin":   (["NO"],"s"),
 "PRISM-export":   (["NX"],"s"),
 "abl:origin-noRel":(["NOr"],"s"),
 "abl:export-noNovelty":(["NXa"],"s"),
 "abl:origin-noAdapt":(["NO"],"c"),
 "abl:export-noAdapt":(["NX"],"c"),
 "base:MOAS-snapshot":(["NOs"],"c"),
 "base:valley-free":(["VF"],"c"),
}

def done(case):
    try: return "UPD " in open(f"out/{case}.log").read()
    except FileNotFoundError: return False
def load_case(c):
    df=pd.read_parquet(f"out/{c['case']}.flags.parquet")
    vol=pd.read_parquet(f"out/{c['case']}.vol.parquet")
    return df,vol

def case_units(c):
    """per-case cache of (offender, window) units for every detector (memory-lean)."""
    path=f"out/{c['case']}.units.parquet"
    if os.path.exists(path): return pd.read_parquet(path)
    t0,t1=TS(c["t0"]),TS(c["t1"]); parts=[]
    only=os.environ.get("PRISM_DETS")   # optional: restrict to some detectors (second-collector runs use PRISM-origin,PRISM-export)
    for name,(types,col) in DETECTORS.items():
        if only and name not in only.split(","): continue
        df=pd.read_parquet(f"out/{c['case']}.flags.parquet",columns=["ts","type","off","prefix","peer"],
                           filters=[("type","in",types)])
        g=adaptive(units(df,types)); del df
        g["score"]=g[col]; g=g[(g.w*W>=t0)&(g.w*W<t1)].copy(); g["det"]=name; parts.append(g)
    if only:
        out=pd.concat(parts,ignore_index=True); out["case"]=c["case"]; out.to_parquet(path); return out
    vol=pd.read_parquet(f"out/{c['case']}.vol.parquet")
    v=vol.assign(w=vol.minute*60//W).groupby("w").ann.sum().reset_index()
    warm=v[v.w*W<t0].ann; med=warm.median(); mad=(warm-med).abs().median()*1.4826+1e-9
    v["score"]=(v.ann-med)/mad; v["off"]=-1; v["c"]=v.ann; v["first"]=(v.w*W).astype(float); v["peers"]=0; v["s"]=v.score
    v=v[(v.w*W>=t0)&(v.w*W<t1)].drop(columns=["ann"]).copy(); v["det"]="base:volume-z"; parts.append(v)
    out=pd.concat(parts,ignore_index=True); out["case"]=c["case"]
    out.to_parquet(path); return out

def build_units():
    rows=[case_units(c) for c in cases() if done(c["case"])]
    allu=pd.concat(rows,ignore_index=True)
    return {k:g for k,g in allu.groupby("det")}

def evaluate(U, taus):
    meta={c["case"]:c for c in cases()}
    ctl_hours=sum((TS(c["t1"])-TS(c["t0"]))/3600 for c in meta.values() if c["label"]=="control" and done(c["case"]))
    inc_cases=[c for c in meta.values() if c["label"]=="incident" and done(c["case"])]
    res=[]
    for det,g in U.items():
        for tau in taus:
            a=g[g.score>=tau]
            det_n=0; delays=[]; fp=0; exposure=ctl_hours
            for c in inc_cases:
                on=TS(datetime_parse(c["onset"]))
                ac=a[a.case==c["case"]]
                inwin=(ac["first"]>=on-DET_PRE)&(ac["first"]<=on+DET_POST)
                cul=ac.off.isin(c["culprits"])
                hit=ac[inwin] if det=="base:volume-z" else ac[inwin & cul]
                if len(hit): det_n+=1; delays.append(hit["first"].min()-on)
                # false alerts: anything not attributable to the documented incident
                if det=="base:volume-z": fp+=int((~inwin).sum())
                else: fp+=int((~cul).sum())
                exposure+=(TS(c["t1"])-TS(c["t0"]))/3600
            fp+=int(a[a.case.str.endswith("_ctl")].shape[0])
            res.append(dict(det=det,tau=tau,detected=det_n,n_inc=len(inc_cases),
                            fa_per_day=fp/exposure*24,median_delay_s=float(np.median(delays)) if delays else None))
    return pd.DataFrame(res)

from datetime import datetime
def datetime_parse(s): return datetime.strptime(s,"%Y-%m-%d %H:%M")

if __name__=="__main__":
    U=build_units()
    pd.to_pickle(U,"out/units.pkl")
    for k,v in U.items(): print(k,len(v))

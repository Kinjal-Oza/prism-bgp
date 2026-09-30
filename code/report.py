"""Produces every table/figure number used in the paper from out/*.units.parquet and flags."""
import json, os, re, numpy as np, pandas as pd
import evaluate as E
from cases import cases, INCIDENTS
TS=E.TS; W=E.W
C={c["case"]:c for c in cases()}
done=[k for k in C if E.done(k)]
for k in done: E.case_units(C[k])
U=pd.concat([pd.read_parquet(f"out/{k}.units.parquet") for k in done],ignore_index=True)
# vantage-adjacency (VA) post-filter on export alerts: drop units whose flags mostly sit next to the collector peer
va=pd.concat([pd.read_parquet(f"out/{k}.va.parquet").assign(case=k) for k in done if os.path.exists(f"out/{k}.va.parquet")],ignore_index=True)
ex=U[(U.det=="PRISM-export")&(U.score>=5)].merge(va[["case","w","off","va_share"]],on=["case","w","off"],how="left")
assert ex.va_share.notna().all(), "missing VA rows"
U=pd.concat([U,ex[ex.va_share<0.5].drop(columns=["va_share"]).assign(det="PRISM-export+VA"),
             U[(U.det=="PRISM-export")&(U.peers>=2)].assign(det="PRISM-export+2VP")],ignore_index=True)
R={}   # all reported numbers

def log_info(k):
    s=open(f"out/{k}.log").read()
    rib=int(re.search(r"RIB (\d+) elems",s).group(1)); pf=int(re.search(r"prefixes=(\d+)",s).group(1))
    upd=int(re.search(r"UPD (\d+) (\d+)s",s).group(1)); secs=int(re.search(r"UPD \d+ (\d+)s",s).group(1))
    return dict(rib_entries=rib,rib_prefixes=pf,announcements=upd,runtime_s=secs)

# ---------- dataset table
rows=[]
for k in done:
    c=C[k]; li=log_info(k)
    vol=pd.read_parquet(f"out/{k}.vol.parquet"); t0,t1=TS(c["t0"]),TS(c["t1"])
    test_ann=int(vol[(vol.minute*60>=t0)&(vol.minute*60<t1)].ann.sum())
    rows.append(dict(case=k,label=c["label"],t0=str(c["t0"]),hours=(t1-t0)/3600,test_announcements=test_ann,**li))
ds=pd.DataFrame(rows); ds.to_csv("out/table_dataset.csv",index=False); R["dataset"]=rows

FAM={"origin":"PRISM-origin","export":"PRISM-export"}
FAMVA={"origin":"PRISM-origin","export":"PRISM-export+VA"}
FAM2={"origin":"PRISM-origin","export":"PRISM-export+2VP"}
def prism_units(tau_o,tau_x,dets=("PRISM-origin","PRISM-export")):
    a=U[((U.det==dets[0])&(U.score>=tau_o))|((U.det==dets[1])&(U.score>=tau_x))]
    return a

# ---------- per-incident culprit table (no threshold): best culprit unit, rank within its window
inc=[c for c in cases() if c["label"]=="incident" and c["case"] in done]
ctl={c["case"][:-4]:c for c in cases() if c["label"]=="control" and c["case"] in done}
rows=[]
for c in inc:
    on=TS(E.datetime_parse(c["onset"]))
    for fam,det in FAM.items():
        g=U[(U.det==det)&(U.case==c["case"])]
        cg=g[g.off.isin(c["culprits"])&(g["first"]>=on-E.DET_PRE)&(g["first"]<=on+E.DET_POST)]
        if len(cg)==0:
            rows.append(dict(case=c["case"],family=fam,found=False)); continue
        best=cg.sort_values("score",ascending=False).iloc[0]
        rank=int((g.score>best.score).sum())+1
        ctlmax=None
        if c["case"] in ctl:
            gc=U[(U.det==det)&(U.case==c["case"]+"_ctl")]; ctlmax=float(gc.score.max())
        rows.append(dict(case=c["case"],family=fam,found=True,culprit=int(best.off),prefixes=int(best.c),
             peers=int(best.peers),score=float(best.score),rank_in_window=rank,units_in_window=len(g),
             first_flag_delay_s=float(best["first"]-on),ctl_week_before_max=ctlmax,
             beats_week_before=(ctlmax is not None and best.score>ctlmax)))
cul=pd.DataFrame(rows); cul.to_csv("out/table_culprits.csv",index=False); R["culprits"]=rows

# ---------- week-before calibration: tau_f(case)=max score in the case's own control window
rows=[]
for variant,fams in (("PRISM",FAM),("PRISM+VA",FAMVA),("PRISM+2VP",FAM2)):
  for c in inc:
    if c["case"] not in ctl: continue
    on=TS(E.datetime_parse(c["onset"])); det_any=False; fa=0; first=None; taus={}
    for fam,det in fams.items():
        tau=U[(U.det==det)&(U.case==c["case"]+"_ctl")].score.max()
        tau=0.0 if not tau>=0 else tau
        tau=5.0 if (det.endswith("VA") and not tau>=5) else tau
        taus[fam]=float(tau)
        g=U[(U.det==det)&(U.case==c["case"])&(U.score>tau)]
        cul_m=g.off.isin(c["culprits"]); inwin=(g["first"]>=on-E.DET_PRE)&(g["first"]<=on+E.DET_POST)
        h=g[cul_m&inwin]
        if len(h): det_any=True; d=h["first"].min()-on; first=d if first is None else min(first,d)
        fa+=int((~cul_m).sum())
    hrs=(TS(c["t1"])-TS(c["t0"]))/3600
    rows.append(dict(variant=variant,case=c["case"],detected=det_any,delay_s=first,false_alerts=fa,hours=hrs,
                     tau_origin=taus["origin"],tau_export=taus["export"]))
wk=pd.DataFrame(rows); wk.to_csv("out/table_weekcal.csv",index=False); R["weekcal"]=rows

# ---------- threshold sweep for each detector (single tau; PRISM merged uses same tau for both families)
taus=[1,2,3,5,8,10,15,20,30,50,75,100,150,200,300,500,1000]
sw=E.evaluate({k:g for k,g in U.groupby("det")},taus)
# merged PRISM
def merged(tau):
    return U[((U.det=="PRISM-origin")|(U.det=="PRISM-export"))].assign(det="PRISM")
sw2=E.evaluate({"PRISM":merged(0),
   "PRISM+VA":U[(U.det=="PRISM-origin")|(U.det=="PRISM-export+VA")].assign(det="PRISM+VA"),
   "PRISM+2VP":U[(U.det=="PRISM-origin")|(U.det=="PRISM-export+2VP")].assign(det="PRISM+2VP")},taus)
sw=pd.concat([sw,sw2],ignore_index=True)
vz=E.evaluate({"base:volume-z":U[U.det=="base:volume-z"]},[2,3,5,8,10,15,20,30,50])
sw=pd.concat([sw[sw.det!="base:volume-z"],vz],ignore_index=True)
sw.to_csv("out/table_sweep.csv",index=False); R["sweep"]=sw.to_dict("records")

# ---------- owner mode: any NO / NX flag on a monitored prefix
rows=[]
for k in done:
    c=C[k]; t0,t1=TS(c["t0"]),TS(c["t1"]); hrs=(t1-t0)/3600; npf=log_info(k)["rib_prefixes"]
    for fam,t in (("origin","NO"),("export","NX")):
        f=pd.read_parquet(f"out/{k}.flags.parquet",columns=["ts","off","prefix"],filters=[("type","==",t),("ts",">=",t0),("ts","<",t1)])
        if c["label"]=="incident":
            on=TS(E.datetime_parse(c["onset"]))
            culm=f.off.isin(c["culprits"])
            vict=f[culm&(f.ts>=on-E.DET_PRE)&(f.ts<=on+E.DET_POST)]
            nv=vict.prefix.nunique(); d=float(vict.ts.min()-on) if len(vict) else None
            benign=f[~culm].prefix.nunique()
        else:
            nv=None; d=None; benign=f.prefix.nunique()
        rows.append(dict(case=k,label=c["label"],family=fam,prefixes=npf,hours=hrs,victim_prefixes_flagged=nv,
                         first_victim_flag_s=d,benign_flagged_prefixes=benign,
                         per_prefix_day_rate=benign/npf/(hrs/24)))
own=pd.DataFrame(rows); own.to_csv("out/table_owner.csv",index=False); R["owner"]=rows

# ---------- owner mode for leaks: per origin AS o, alert if one exporter newly leaks >=k of o's prefixes in 5 min
rows=[]
for k in done:
    if not os.path.exists(f"out/{k}.active_origins"): continue
    c=C[k]; t0,t1=TS(c["t0"]),TS(c["t1"]); hrs=(t1-t0)/3600
    act=int(open(f"out/{k}.active_origins").read())
    f=pd.read_parquet(f"out/{k}.nxorigin.parquet"); f["w"]=(f.ts//W).astype(int)
    g=f.groupby(["origin","off","w"]).prefix.nunique().rename("n").reset_index()
    for kap in (1,2,3,5,10,20):
        a=g[g.n>=kap]
        if c["label"]=="incident":
            on=TS(E.datetime_parse(c["onset"]))
            cm=a.off.isin(c["culprits"]); win=(a.w*W>=on-E.DET_PRE-W)&(a.w*W<=on+E.DET_POST)
            vict=a[cm&win].origin.nunique(); ben=a[~cm].origin.nunique()
        else: vict=None; ben=a.origin.nunique()
        rows.append(dict(case=k,label=c["label"],kappa=kap,active_origins=act,hours=hrs,victim_origins_alerted=vict,
                         benign_origins_alerted=ben,per_origin_day_rate=ben/act/(hrs/24)))
ol=pd.DataFrame(rows); ol.to_csv("out/table_owner_leak.csv",index=False); R["owner_leak"]=rows
json.dump(R,open("out/results.json","w"),indent=1,default=str)
print(ds.to_string()); print(cul.to_string()); print(wk.to_string())
print(own.to_string()); print(ol.to_string())

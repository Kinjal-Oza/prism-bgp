"""Two-threshold operating grid (tau_origin, tau_export) for PRISM and PRISM+2VP."""
import pandas as pd, evaluate as E
from cases import cases
C={c["case"]:c for c in cases()}
U=pd.concat([pd.read_parquet(f"out/{k}.units.parquet") for k in C],ignore_index=True)
inc=[c for c in cases() if c["label"]=="incident"]
hours=sum((E.TS(c["t1"])-E.TS(c["t0"]))/3600 for c in C.values())
def run(a):
    got=set(); fa=0; delays=[]
    for c in inc:
        on=E.TS(E.datetime_parse(c["onset"])); ac=a[a.case==c["case"]]
        cm=ac.off.isin(c["culprits"]); w=(ac["first"]>=on-E.DET_PRE)&(ac["first"]<=on+E.DET_POST)
        if (cm&w).any(): got.add(c["case"]); delays.append(ac[cm&w]["first"].min()-on)
        fa+=int((~cm).sum())
    fa+=int(a[a.case.str.endswith("_ctl")].shape[0])
    return got,fa,delays
rows=[]
for var,xdet,xf in (("PRISM","PRISM-export",lambda g:g),("PRISM+2VP","PRISM-export",lambda g:g[g.peers>=2])):
    for to in (3,5,10,20,30,50):
        for tx in (50,100,200,500,1000,2000):
            a=pd.concat([U[(U.det=="PRISM-origin")&(U.score>=to)], xf(U[(U.det==xdet)&(U.score>=tx)])])
            got,fa,d=run(a)
            rows.append(dict(variant=var,tau_o=to,tau_x=tx,detected=len(got),which=",".join(sorted(got)),
                             fa_per_day=fa/hours*24,median_delay_s=float(pd.Series(d).median()) if d else None))
g=pd.DataFrame(rows); g.to_csv("out/table_grid.csv",index=False)
print("exposure hours",hours); print(g.sort_values(["detected","fa_per_day"],ascending=[False,True]).groupby("detected").head(3).to_string())

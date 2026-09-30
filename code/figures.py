import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import evaluate as E
from cases import cases
plt.rcParams.update({"font.family":"serif","font.size":8,"axes.spines.top":False,"axes.spines.right":False,
                     "axes.edgecolor":"#888","axes.grid":True,"grid.color":"#e6e6e6","grid.linewidth":0.5})
BLUE,ORANGE,AQUA,YELLOW,MAG,GRAY="#2a78d6","#eb6834","#1baf7a","#eda100","#e87ba4","#9a9a9a"
C={c["case"]:c for c in cases()}
done=[k for k in C if E.done(k)]
U=pd.concat([pd.read_parquet(f"out/{k}.units.parquet") for k in done],ignore_index=True)

# Fig: per-incident timeline — culprit score vs best other offender per window
inc=[c for c in cases() if c["label"]=="incident" and c["case"] in done]
n=len(inc); cols=4; rows=int(np.ceil(n/cols))
fig,axs=plt.subplots(rows,cols,figsize=(7.16,1.55*rows),squeeze=False)
for ax,c in zip(axs.flat,inc):
    on=E.TS(E.datetime_parse(c["onset"]))
    fam = "PRISM-origin" if "hijack" in c["kind"] else "PRISM-export"
    g=U[(U.case==c["case"])&(U.det==fam)].copy(); g["m"]=(g.w*E.W-on)/60
    cul=g[g.off.isin(c["culprits"])].groupby("m").score.max()
    oth=g[~g.off.isin(c["culprits"])].groupby("m").score.max()
    ctl=U[(U.case==c["case"]+"_ctl")&(U.det==fam)].score.max() if c["case"]+"_ctl" in done else None
    ax.plot(oth.index,oth.values,color=GRAY,lw=0.8,label="best other AS")
    ax.plot(cul.index,cul.values,"o",color=ORANGE,ms=3,label="documented culprit")
    if ctl is not None: ax.axhline(ctl,color=BLUE,lw=0.8,ls="--",label="max, week-before control")
    ax.axvline(0,color="#444",lw=0.6,ls=":")
    ax.set_yscale("log"); ax.set_title(f"{c['case']} ({'NO' if fam.endswith('origin') else 'NX'})",fontsize=8)
    ax.set_xlim(-120,120)
for ax in axs.flat[n:]: ax.axis("off")
for ax in axs[-1]: ax.set_xlabel("min from reported onset")
for ax in axs[:,0]: ax.set_ylabel("score $s(a,w)$")
h,l=axs.flat[0].get_legend_handles_labels()
fig.tight_layout(pad=0.4,rect=(0,0.07,1,1)); fig.legend(h,l,loc="lower center",ncol=3,fontsize=7,frameon=False); fig.savefig("paper/fig_timelines.pdf"); plt.close(fig)

# Fig: operating curves
sw=pd.read_csv("out/table_sweep.csv")
fig,ax=plt.subplots(figsize=(7.0,2.5))
spec=[("PRISM","PRISM (NO+NX)",BLUE,"-o"),("PRISM-origin","PRISM origin only",AQUA,"-s"),
      ("PRISM-export","PRISM export only",YELLOW,"-^"),
      ("abl:export-noNovelty","NX without per-prefix novelty",YELLOW,":^"),
      ("base:MOAS-snapshot","MOAS vs RIB snapshot",MAG,":v"),
      ("base:valley-free","valley-free count",ORANGE,":D"),("base:volume-z","volume z-score",GRAY,":x")]
for d,lab,col,st in spec:
    s=sw[sw.det==d].sort_values("fa_per_day")
    if len(s)==0: continue
    ax.plot(s.fa_per_day.clip(lower=0.1),s.detected,st,color=col,ms=3,lw=1,label=lab)
ax.set_xscale("log"); ax.set_xlabel("false alerts per day"); ax.set_ylabel("incidents detected")
gr=pd.read_csv("out/table_grid.csv")
best=gr[gr.variant=="PRISM"].sort_values("fa_per_day").groupby("detected").head(1)
ax.plot(best.fa_per_day.clip(lower=0.1),best.detected,"*",color="#0d366b",ms=8,label=r"PRISM, separate $\tau_o,\tau_x$ (best per level)")
ax.legend(fontsize=6.5,frameon=False,loc="center left",bbox_to_anchor=(1.01,0.5)); fig.tight_layout(pad=0.3)
fig.savefig("paper/fig_operating.pdf"); plt.close(fig)
print("ok")

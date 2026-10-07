"""Fig: poisoning trade-off. x = clean false alerts/day (all 16 incidents, 256 h, Quiet point);
y = attacked incidents still detected (of 10), per attacker, as the H_a cap is varied (exploratory sweep)."""
import pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":"serif","font.size":8,"axes.spines.top":False,"axes.spines.right":False,
                     "axes.edgecolor":"#888","axes.grid":True,"grid.color":"#e6e6e6","grid.linewidth":0.5})
BLUE,ORANGE,AQUA,GRAY="#2a78d6","#eb6834","#1baf7a","#9a9a9a"
cl=pd.read_csv("../results/poison/cap_sweep_clean.csv"); at=pd.read_csv("../results/poison/cap_sweep_attack.csv")
d0=pd.read_csv("../results/poison/clean_ops.csv"); d0=d0[(d0.variant=="PRISM (D0)")&(d0.set=="all")&(d0.point=="Quiet")].fa_per_day.iloc[0]
s=at.groupby(["cap_ratio","view"]).detected.sum().unstack().reset_index().merge(cl[["cap_ratio","fa_per_day"]],on="cap_ratio")
fig,ax=plt.subplots(figsize=(3.45,2.5))
for v,col,lab,m in (("A1T",BLUE,"transient attacker","o"),("A1P",ORANGE,"persistent attacker","s"),("A1Q",AQUA,"persistent, D1-aware (post hoc)","^")):
    ax.plot(s.fa_per_day,s[v],marker=m,color=col,lw=1.5,ms=4.5,label=lab,markeredgecolor="white",markeredgewidth=0.6)
ax.plot([d0],[0],marker="X",color="#444",ms=6,ls="none",label="PRISM, undefended (all attackers)")
for _,r in s.iterrows():
    if r.cap_ratio in (0,0.02):
        t={0:"$H_a$ cap 0 (D1)",0.02:"cap $0.02\\tau_f$"}[r.cap_ratio]
        ax.annotate(t,(r.fa_per_day,r.A1T),textcoords="offset points",xytext=(-2,5),fontsize=6.5,color="#333",ha="right" if r.cap_ratio==0 else "left")
ax.annotate("caps $\\geq0.1\\tau_f$ and no cap",(1.125,5.5),textcoords="offset points",xytext=(10,-2),fontsize=6.5,color="#333")
ax.set_xlim(0.6,5.3); ax.set_xlabel("false alerts per day, no attack (16 incidents, 256 h)"); ax.set_ylabel("attacks detected (of 10)")
ax.set_ylim(-0.6,10.8); ax.set_yticks([0,2,4,6,8,10]); ax.legend(fontsize=6.3,frameon=False,loc="upper center",bbox_to_anchor=(0.5,-0.25),ncol=2,handlelength=1.6,columnspacing=1.0)
fig.tight_layout(); fig.savefig("../paper/fig_poison.pdf"); fig.savefig("/tmp/claude-0/fig_poison.png",dpi=200)
print(s.to_string())

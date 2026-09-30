import os, sys, subprocess
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from cases import cases
BASE="http://archive.routeviews.org/bgpdata"
def urls(c):
    r=c["rib"]; L=[(f"{BASE}/{r:%Y.%m}/RIBS/rib.{r:%Y%m%d.%H%M}.bz2","rib.bz2")]
    t=r
    while t< c["t1"]:
        L.append((f"{BASE}/{t:%Y.%m}/UPDATES/updates.{t:%Y%m%d.%H%M}.bz2", f"upd.{t:%Y%m%d.%H%M}.bz2"))
        t+=timedelta(minutes=15)
    return L
def get(a):
    url,dst=a
    if os.path.exists(dst) and os.path.getsize(dst)>0: return 0
    r=subprocess.run(["curl","-sS","-f","--retry","3","-o",dst,url])
    return r.returncode
jobs=[]
for c in cases():
    d=f"data/{c['case']}"; os.makedirs(d,exist_ok=True)
    for u,f in urls(c): jobs.append((u,f"{d}/{f}"))
print(len(jobs),"files")
with ThreadPoolExecutor(16) as ex: rc=list(ex.map(get,jobs))
bad=[j for j,r in zip(jobs,rc) if r]
print("failed",len(bad)); [print(b) for b in bad[:50]]

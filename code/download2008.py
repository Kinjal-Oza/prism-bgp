import os,re,subprocess
from datetime import datetime,timedelta
from concurrent.futures import ThreadPoolExecutor
from cases import cases
BASE="http://archive.routeviews.org/bgpdata/2008.02"
lst={}
for k in ["UPDATES","RIBS"]:
    html=subprocess.run(["curl","-s",f"{BASE}/{k}/"],capture_output=True,text=True).stdout
    lst[k]=sorted(set(re.findall(r'(?:updates|rib)\.\d{8}\.\d{4}\.bz2',html)))
ts=lambda f: datetime.strptime(".".join(f.split(".")[1:3]),"%Y%m%d.%H%M")
jobs=[]
for c in cases():
    if c["t0"].year!=2008: continue
    d=f"data/{c['case']}"
    for f in os.listdir(d): os.remove(f"{d}/{f}")
    start=c["t0"]-timedelta(hours=24)
    ribs=[f for f in lst["RIBS"] if ts(f)<=start]; rib=ribs[-1]
    jobs.append((f"{BASE}/RIBS/{rib}",f"{d}/rib.bz2"))
    for f in lst["UPDATES"]:
        if ts(rib)-timedelta(minutes=15)<=ts(f)<c["t1"]: jobs.append((f"{BASE}/UPDATES/{f}",f"{d}/upd.{ts(f):%Y%m%d.%H%M}.bz2"))
    open(f"{d}/RIBTIME","w").write(rib)
print(len(jobs))
def get(a): return subprocess.run(["curl","-sS","-f","--retry","3","-o",a[1],a[0]]).returncode
with ThreadPoolExecutor(16) as ex: print("fail",sum(1 for r in ex.map(get,jobs) if r))

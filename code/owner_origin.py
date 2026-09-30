"""Owner-mode leak check: attach the origin AS to each NX flag in the test window by re-reading the
same UPDATE files, then count, per (origin AS, exporter, 5-min window), how many of that origin's
prefixes the exporter newly leaked. Output: out/<case>.nxorigin.parquet"""
import sys, glob, pandas as pd, bgpkit
from datetime import timezone
from cases import cases
from engine import clean_path
import evaluate as E
def run(case):
    c=[x for x in cases() if x["case"]==case][0]
    t0,t1=E.TS(c["t0"]),E.TS(c["t1"])
    f=pd.read_parquet(f"out/{case}.flags.parquet",columns=["ts","off","prefix","peer"],
                      filters=[("type","==","NX"),("ts",">=",t0),("ts","<",t1)])
    keys=set(zip(f.ts,f.prefix,f.peer)); org={}; active=set()
    for fn in sorted(glob.glob(f"data/{case}/upd.*.bz2")):
        from datetime import datetime
        st=datetime.strptime(fn.split("upd.")[1][:13],"%Y%m%d.%H%M").replace(tzinfo=timezone.utc).timestamp()
        if st<t0-1200 or st>=t1: continue
        for e in bgpkit.Parser(url=fn):
            ts=e.timestamp
            if ts<t0 or ts>=t1 or e.elem_type!="A": continue
            if ":" not in e.prefix and e.as_path:
                active.add(e.as_path.rsplit(" ",1)[-1])
            k=(ts,e.prefix,e.peer_asn)
            if k in keys:
                p=clean_path(e.as_path)
                if p: org[k]=p[-1]
    f["origin"]=[org.get(k,-1) for k in zip(f.ts,f.prefix,f.peer)]
    f.to_parquet(f"out/{case}.nxorigin.parquet"); print(case,len(f),(f.origin<0).sum())
    open(f"out/{case}.active_origins","w").write(str(len(active)))
if __name__=="__main__": run(sys.argv[1])

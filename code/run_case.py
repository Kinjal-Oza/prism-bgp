import sys, os
from cases import cases
from engine import run
ASREL={2008:"20080201",2015:"20150601"}
def asrel_for(c):
    t=c["t0"]
    m={(2008,2):"20080201",(2015,6):"20150601",(2017,4):"20170401",(2017,12):"20171201",
       (2018,4):"20180401",(2018,11):"20181101",(2019,6):"20190601",(2020,4):"20200401",
       (2008,2):"20080201",(2015,6):"20150601",(2017,11):"20171201",(2018,11):"20181101",(2019,6):"20190601",
       (2020,3):"20200401",(2017,4):"20170401",(2018,4):"20180401"}
    return f"asrel/{m[(t.year,t.month)]}.as-rel.txt.bz2"
if __name__=="__main__":
    os.makedirs("out",exist_ok=True)
    for c in cases():
        if c["case"] not in sys.argv[1:]: continue
        from datetime import timezone
        t0=c["t0"].replace(tzinfo=timezone.utc).timestamp(); t1=c["t1"].replace(tzinfo=timezone.utc).timestamp()
        print("CASE",c["case"],c["t0"],c["t1"],asrel_for(c),flush=True)
        run(f"data/{c['case']}",asrel_for(c),t0,t1,f"out/{c['case']}")

from datetime import datetime, timedelta
UTC=lambda s: datetime.strptime(s,"%Y-%m-%d %H:%M")
# Documented incidents (onset per public reporting; sources cited in paper)
INCIDENTS = [
 dict(id="PT2008", onset="2008-02-24 18:47", culprits=[17557], kind="subprefix-hijack"),
 dict(id="TM2015", onset="2015-06-12 08:43", culprits=[4788], kind="route-leak"),
 dict(id="RT2017", onset="2017-04-26 22:36", culprits=[12389], kind="origin-hijack"),
 dict(id="DV2017", onset="2017-12-12 04:43", culprits=[39523], kind="origin-hijack"),
 dict(id="AM2018", onset="2018-04-24 11:05", culprits=[10297], kind="subprefix-hijack"),
 dict(id="MO2018", onset="2018-11-12 21:10", culprits=[37282], kind="route-leak"),
 dict(id="DQ2019", onset="2019-06-24 10:30", culprits=[396531,33154], kind="route-leak"),
 dict(id="RT2020", onset="2020-04-01 19:28", culprits=[12389], kind="origin-hijack"),
]
WARM=timedelta(hours=24)
def cases():
    out=[]
    for inc in INCIDENTS:
        T=UTC(inc["onset"])
        out.append(dict(inc, case=inc["id"], label="incident", t0=T-timedelta(hours=2), t1=T+timedelta(hours=2)))
        C=T-timedelta(days=7)
        out.append(dict(case=inc["id"]+"_ctl", label="control", culprits=[], kind="none",
                        t0=C-timedelta(hours=6), t1=C+timedelta(hours=6), onset=None))
    for c in out:
        w=c["t0"]-WARM
        c["rib"]=w.replace(minute=0)-timedelta(hours=w.hour%2)   # route-views2 RIBs every 2h
    return out

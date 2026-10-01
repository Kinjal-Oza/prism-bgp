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
# Held-out incidents, fixed on 2026-09-30 BEFORE any of them was run. The detector, the scoring rule,
# the guard G and every operating point were frozen on the eight incidents above and are applied unchanged.
# Selection rule (same as above): a public report names the responsible AS and gives an onset to the
# minute; IPv4; not a forged-origin hijack (out of scope, see Limitations). Culprit sets follow the DQ2019
# rule: the AS(es) the report names as originating or leaking, not upstreams that failed to filter.
# Excluded before running: China Telecom 2010 (no minute-level onset we could verify) and
# Celer Bridge 2022 (forged-origin: the hijacker appended Amazon's AS16509 as origin).
HELDOUT = [
 dict(id="ID2011", onset="2011-01-14 12:19", culprits=[4761], kind="origin-hijack", asrel="20110101"),   # BGPmon
 dict(id="ID2014", onset="2014-04-02 18:26", culprits=[4761], kind="origin-hijack", asrel="20140401"),   # BGPmon
 dict(id="GO2017", onset="2017-08-25 03:22", culprits=[15169], kind="route-leak", asrel="20170801"),     # Dyn/CircleID
 dict(id="SH2019", onset="2019-06-06 09:44", culprits=[21217], kind="route-leak", asrel="20190601"),     # Oracle/APNIC
 dict(id="VI2021", onset="2021-04-16 13:48", culprits=[55410], kind="origin-hijack", asrel="20210401"),  # APNIC blog (13:48 UTC); date per MANRS. Pre-registered as 04-17 by a transcription error, corrected after the first run
 dict(id="KS2022", onset="2022-02-03 01:04", culprits=[9457], kind="subprefix-hijack", asrel="20220201"),# MANRS/S2W
 dict(id="TW2022", onset="2022-03-28 12:06", culprits=[8342], kind="origin-hijack", asrel="20220301"),   # MANRS
 dict(id="CF2024", onset="2024-06-27 18:51", culprits=[267613,262504], kind="origin-hijack+leak", asrel="20240601"), # Cloudflare
]
WARM=timedelta(hours=24)
def cases(): return _build(INCIDENTS)
def heldout_cases(): return _build(HELDOUT)
def all_cases(): return _build(INCIDENTS)+_build(HELDOUT)
def _build(incs):
    out=[]
    for inc in incs:
        T=UTC(inc["onset"])
        out.append(dict(inc, case=inc["id"], label="incident", t0=T-timedelta(hours=2), t1=T+timedelta(hours=2)))
        C=T-timedelta(days=7)
        out.append(dict(case=inc["id"]+"_ctl", label="control", culprits=[], kind="none",
                        t0=C-timedelta(hours=6), t1=C+timedelta(hours=6), onset=None, asrel=inc.get("asrel")))
    for c in out:
        w=c["t0"]-WARM
        c["rib"]=w.replace(minute=0)-timedelta(hours=w.hour%2)   # route-views2 RIBs every 2h
    return out

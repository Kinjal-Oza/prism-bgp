#!/bin/sh
# Idempotent driver: runs only what has no complete log.
ok(){ [ -f "$1" ] && tail -n1 "$1" | grep -q "$2"; }
ALL="PT2008_ctl TM2015_ctl RT2017_ctl DV2017_ctl AM2018 AM2018_ctl MO2018 MO2018_ctl DQ2019_ctl RT2020_ctl ID2011_ctl ID2014_ctl GO2017_ctl SH2019_ctl VI2021_ctl KS2022 KS2022_ctl TW2022 TW2022_ctl CF2024 CF2024_ctl"
A="TM2015 RT2017 DV2017 DQ2019 RT2020 ID2011 ID2014 GO2017 SH2019 VI2021"
for c in $ALL; do ok out2/$c.clean.log "^UPD" || echo $c; done | xargs -P2 -I{} sh -c 'python3 run2.py clean {} > out2/{}.clean.log 2>&1'
for c in $A; do ok out2/$c.attackq.log "^UPD" || echo $c; done | xargs -P2 -I{} sh -c 'python3 run2.py attackq {} > out2/{}.attackq.log 2>&1'
for c in $(python3 -c "from cases import cases,heldout_cases;print(' '.join(c['case'] for c in cases()+heldout_cases()))"); do ok out3/$c.log "alerts" || [ -f out3/$c.artemis.parquet ] || echo $c; done | xargs -P2 -I{} sh -c 'python3 artemis.py {} > out3/{}.log 2>&1'
echo ALL_DONE > out2/ALL_DONE

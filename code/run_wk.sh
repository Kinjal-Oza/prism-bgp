#!/bin/sh
# Week-long controls on route-views2: download, replay, owner-mode origins, units, then delete raw data.
for c in "$@"; do
  python3 download_case.py $c > out/$c.dl 2>&1 &&
  python3 run_case.py $c > out/$c.log 2>&1 &&
  python3 owner_origin.py $c > out/$c.own.log 2>&1 &&
  PRISM_DETS=PRISM-origin,PRISM-export python3 -c "import evaluate as E; from cases import all_cases; [E.case_units(x) for x in all_cases() if x['case']=='$c']" > out/$c.units.log 2>&1 &&
  rm -rf data/$c
done

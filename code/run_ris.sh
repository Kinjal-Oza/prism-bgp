#!/bin/sh
# Second collector: download, replay and score each case on RIPE RIS rrc00, then delete its raw data.
one() {
  c=$1
  if [ -f out/$c.units.parquet ]; then return 0; fi
  if ! grep -q "^UPD" out/$c.log 2>/dev/null; then
    python3 ../code/download_ris.py $c > out/$c.dl 2>&1 &&
    python3 ../code/run_case.py $c > out/$c.log 2>&1 || return 1
  fi
  PRISM_DETS=PRISM-origin,PRISM-export python3 -c "import sys; sys.path.insert(0,'../code'); import evaluate as E; from cases import all_cases; [E.case_units(x) for x in all_cases() if x['case']=='$c']" > out/$c.units.log 2>&1 &&
  rm -rf data/$c out/$c.flags.parquet
}
for c in "$@"; do one $c; done

#!/bin/sh
# Held-out replay: engine, then owner-mode origin attachment, for every held-out case (2 in parallel).
python3 -c "from cases import heldout_cases as h; print('\n'.join(c['case'] for c in h()))" | \
  xargs -P2 -I{} sh -c 'python3 run_case.py {} > out/{}.log 2>&1 && python3 owner_origin.py {} > out/{}.own.log 2>&1'
echo HELDOUT_DONE > out/HELDOUT_DONE

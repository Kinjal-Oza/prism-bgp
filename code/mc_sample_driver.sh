#!/bin/sh
# interim pre-registered sample (code/mc_sample15.txt); idempotent
MC_DL_THREADS=8 
export MC_DL_THREADS
tr ' ' '\n' < mc_sample15.txt | xargs -P2 -I{} sh -c 'python3 mc_run.py {} >> mc_log.txt 2>&1'
echo DONE > mc_out/SAMPLE_DONE

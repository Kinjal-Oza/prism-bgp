#!/bin/sh
# Multi-collector run. Usage: sh mc_driver.sh [PARALLEL]   (default: number of CPUs / 2; each job needs ~4-6 GB RAM)
# Idempotent: re-running skips finished cases (mc_out/<id>.json). Safe to stop and restart.
P=${1:-$(( $(nproc) / 2 ))}
python3 mc_run.py list | tr ' ' '\n' | xargs -P "$P" -I{} sh -c 'python3 mc_run.py {} >> mc_log.txt 2>&1'
python3 mc_eval.py | tee mc_summary.txt

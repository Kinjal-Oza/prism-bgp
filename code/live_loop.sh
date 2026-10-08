#!/bin/sh
# Restart-always wrapper for the live run (each restart repeats the 24 h warm-up; logged as a gap).
while true; do
  echo "start $(date -u +%FT%TZ)" >> live_out/restarts.log
  python3 live_prism.py --out live_out >> live_out/run.log 2>&1
  echo "exit $(date -u +%FT%TZ) rc=$?" >> live_out/restarts.log
  sleep 30
done

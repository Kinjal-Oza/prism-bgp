#!/bin/sh
# idempotent: skips events with ext_out/<id>.json
for i in $(python3 ext_run.py list); do echo $i; done | xargs -P2 -I{} sh -c 'python3 ext_run.py {} >> ext_log.txt 2>&1'
echo EXT_DONE > ext_out/EXT_DONE

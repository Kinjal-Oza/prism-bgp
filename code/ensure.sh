#!/bin/sh
# Idempotent keep-alive: swap, multi-collector driver, live loop.
cd /home/claude/prism/code
swapon --show | grep -q swapfile || swapon /swapfile 2>/dev/null
if [ ! -f mc_out/FULL_DONE ] && ! pgrep -f "^sh mc_driver.sh" >/dev/null; then
  rm -rf mc_data/* mc_flags/*
  (nohup sh -c 'sh mc_driver.sh 2 && touch mc_out/FULL_DONE' >> mc_full.log 2>&1 &)
  echo "mc restarted"
fi
mkdir -p live_out
if ! pgrep -f "^sh live_loop.sh" >/dev/null; then
  (nohup sh live_loop.sh >/dev/null 2>&1 &); echo "live restarted"
fi
echo "mc: $(ls mc_out/*.json 2>/dev/null | wc -l)/210 done, $(grep -l '"ok": false' mc_out/*.json 2>/dev/null | wc -l) failed"
tail -1 live_out/status.jsonl 2>/dev/null | cut -c1-160
cat live_out/restarts.log 2>/dev/null | tail -2
free -m | sed -n 2p

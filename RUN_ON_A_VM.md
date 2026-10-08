# Running the two long jobs on a rented machine

Both jobs were fixed in `HELDOUT_PREREGISTRATION.md` (addendum of 2026-10-07) before any result. Run them as written;
report every number, including failures.

## Machine

Any Linux VM works (AWS, GCP, Azure, Hetzner, DigitalOcean). No GPU is needed.

| Job | Suggested size | Disk | Expected time | Rough cost |
|---|---|---|---|---|
| 1. Multi-collector replay | 32 vCPU, 128 GB RAM (e.g. AWS `m7i.8xlarge`, Hetzner CCX63) | 300 GB SSD | 1.5-3 days | $60-150 |
| 3. Live deployment | 2 vCPU, 8 GB RAM (e.g. AWS `t3.large`, Hetzner CX32) | 30 GB | 22+ days (always on) | $15-40 for the month |

Job 1 is CPU- and download-bound: each case replays every RouteViews collector (10 in 2010, about 35 by 2024) for
36 hours. Each parallel job needs about 4-6 GB of RAM, so run about RAM/6 jobs at once (`sh mc_driver.sh 20` on
128 GB). Stop the VM as soon as `mc_summary.txt` appears.

## Setup (both jobs)

```bash
sudo apt-get update && sudo apt-get install -y python3-pip git curl tmux
git clone https://github.com/Kinjal-Oza/prism-bgp && cd prism-bgp/code
pip install --break-system-packages pybgpkit pandas pyarrow matplotlib websocket-client
```

## Job 1: multi-collector replay

```bash
cd prism-bgp/code
tmux new -s mc
sh mc_driver.sh 20          # 20 parallel cases; re-run the same command after any interruption, it resumes
```

Outputs: `mc_out/` (one JSON per case), `mc_summary.txt`, and `../results/multicollector/`
(`ours_ops.csv`, `benchmark_summary.json`, `benchmark_cases.csv`). Copy `results/multicollector/` and `mc_log.txt` back.

Check after the first hour: `grep -c . mc_log.txt` should be growing, and `grep False mc_log.txt` should be empty
or explainable (a collector with a corrupt archive file is logged as `WARN` and skipped, not dropped silently).

## Job 3: live deployment

```bash
cd prism-bgp/code
tmux new -s live
python3 live_prism.py --out live_out              # add --owner my_prefixes.txt to also run owner mode
```

The first ~10 minutes download and load the RIS rrc00 RIB; the next 24 hours are warm-up (no alerts). Leave it running
for at least 22 days (24 h warm-up + 21 days of alerting). `live_out/status.jsonl` gets a line every 5 minutes; its
`lag_s` should stay below a few minutes. If the process dies, restart it the same way (it bootstraps again; note the
gap in the paper).

At the end (or weekly, to watch progress):

```bash
export CF_API_TOKEN=...      # free Cloudflare account -> My Profile -> API Tokens -> any token
python3 live_verify.py --out live_out
```

This writes `verify_alerts.csv`, `verify_missed.csv` and `verify_summary.md`. For every alert without a Radar match,
fill the `class` column (confirmed / benign / unknown) from the alert's evidence in `alerts.jsonl` and public reports
(bgp.tools, RIPEstat, operator mailing lists). Do not change thresholds during the run.

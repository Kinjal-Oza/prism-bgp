# PRISM: History-Anchored, Relationship-Aware BGP Hijack & Route-Leak Detection

This is the code and results for the IEEE TNSM submission *"PRISM: History-Anchored, Relationship-Aware Detection and Attribution of BGP Hijacks and Route Leaks from Public Collector Data"* by Kinjal Vaishnav.

Everything here runs on **public data only**:

- RouteViews `route-views2` MRT archives.
- CAIDA serial-1 AS relationships.

The only synthetic traffic is the attacker's seed announcements in the poisoning study, injected from one labeled synthetic session into otherwise real streams. Every number in the paper is produced by the scripts below. The results they generated are in `results/`.

## Layout

| Path | What it is |
|---|---|
| `paper/` | LaTeX source (`main.tex` + `sec_*.tex`, `refs.bib`), figures, compiled `PRISM_TNSM_Paper.pdf` |
| `code/cases.py` | The 8 development incidents and the 8 held-out incidents (onset, culprit AS), each with a matched control window (same hour, 1 week earlier) |
| `code/download.py`, `code/download2008.py` | Fetch RIB + UPDATE files from archive.routeviews.org. 2008 files use irregular timestamps, so a separate script handles them. |
| `code/asrel.py` | CAIDA relationship loader, relationship queries and customer-cone lookups |
| `code/engine.py` | **The PRISM replay engine.** Per-prefix history, NO and NX tests, baseline and ablation flags. |
| `code/run_case.py`, `code/run_all.sh` | Run the engine on one case or on all cases |
| `code/evaluate.py` | Offender-adaptive scoring (Eq. 2, 60-min guard), detection and false-alert metrics |
| `code/report.py` | Builds every table: dataset, culprit ranks, week-before calibration, sweep, owner mode |
| `code/grid.py` | Two-threshold operating points (Table III) |
| `code/owner_origin.py` | Owner-mode leak analysis (attaches the origin AS to each NX flag) |
| `code/adjacency.py` | Vantage-adjacency post-filter (reported as a negative result) |
| `code/figures.py` | Figures 2 and 3 |
| `HELDOUT_PREREGISTRATION.md` | The 8 held-out incidents, fixed before any of them was run, and the one disclosed date correction |
| `code/download_case.py`, `code/run_heldout.sh` | Fetch and replay the held-out cases (same engine, unchanged) |
| `code/heldout.py`, `code/combined.py` | Held-out evaluation at the frozen operating points; development + held-out together |
| `code/download_ris.py`, `code/run_ris.sh`, `code/mc.py` | Second collector: replay all 32 cases on RIPE RIS rrc00 (run from a separate `ris/` work dir) and apply the pre-registered combination rules |
| `results/ris/` | RIS unit files and logs, `mc_ops.csv` (RV2 alone / RIS alone / Either / Corroborated), `mc_visibility.csv` |
| `code/run_wk.sh`, `code/wk.py`, `results/week/` | Four 7-day control windows and their false-alert rates |
| `results/heldout/` | Held-out tables (`heldout_*.csv`), `heldout.json`, `combined_ops.csv`, unit files, engine logs |
| `results/` | Result tables (`table_*.csv`), `results.json`, per-case unit files, engine logs |
| `code/engine2.py` | Multi-view replay engine for the poisoning study: D0 (the published engine, reproduced exactly on all 32 cases) and D1 (persistence-gated learning), with timestamp-merged injection |
| `code/run2.py`, `code/resume.sh` | Clean runs (D0+D1), seeding attacks (transient T, persistent P, D1-aware Q), driver |
| `code/artemis.py` | Re-implementation of ARTEMIS's owner-side detection rules on the same replays |
| `code/rpki.py` | Route-origin validation against RIPE NCC's archive of published ROAs (all five RIRs) |
| `code/eval_poison.py`, `code/fig_poison.py` | Verification, clean cost, attack outcomes, cap sweep, RPKI tier, guard sweep, ARTEMIS comparison; Fig. 4 |
| `results/poison/` | `verify_d0.csv`, `clean_ops.csv`, `attack.csv`, `cap_sweep_*.csv`, `rpki_tier.csv`, `guard_sweep.csv`, `artemis*.csv` |

## Reproduce

```bash
pip install pybgpkit pandas pyarrow matplotlib
cd code
mkdir -p asrel && for m in 20080201 20150601 20170401 20171201 20180401 20181101 20190601 20200401; do
  curl -sSfo asrel/$m.as-rel.txt.bz2 https://publicdata.caida.org/datasets/as-relationships/serial-1/$m.as-rel.txt.bz2; done
python3 download.py && python3 download2008.py      # ~5.1 GB, 2,122 MRT files
bash run_all.sh                                      # engine: 4-33 min per case, ~2 GB RAM each
python3 run_case.py MO2018                           # (run_all.sh omits MO2018, which was the development case)
for c in $(python3 -c "from cases import cases;print(' '.join(x['case'] for x in cases()))"); do
  python3 owner_origin.py $c; python3 adjacency.py $c; done
python3 report.py && python3 grid.py && python3 figures.py
```

Held-out test (frozen design, no retuning):

```bash
for m in 20110101 20140401 20170801 20190601 20210401 20220201 20220301 20240601; do
  curl -sSfo asrel/$m.as-rel.txt.bz2 https://publicdata.caida.org/datasets/as-relationships/serial-1/$m.as-rel.txt.bz2; done
python3 download_case.py $(python3 -c "from cases import heldout_cases as h;print(' '.join(c['case'] for c in h()))")   # 4.8 GB, 2,134 files
sh run_heldout.sh
python3 heldout.py && python3 combined.py ../results/dev_units   # dev units: unzip results/per_case_results_parquet.zip there
```

Engine flag files (`out/*.flags.parquet`, ~440 MB) are not included because they regenerate deterministically from the archives.

## Headline results (from `results/`)

- **Culprit ranking.** In 7 of 8 incidents, the documented culprit is the top-scoring AS in its 4-hour window.
- **Quiet operating point.** τ_o = 50, τ_x = 2000 detects 5/8 incidents with attribution at **0.56 false alerts/day**, with a median first-flag delay of 29 s (when the first offending route becomes visible; this is not thresholded alert latency).
- **Week-before calibration.** Thresholds are set from last week's control only, never from the incidents. This detects 5/8 incidents with 9 false alerts in 32 incident-window hours.
- **Held-out test.** Eight more incidents (2011-2024), listed before they were run, scored with every threshold frozen: 5/8 detected and attributed at the quiet point at 1.3 false alerts/day, median first-flag delay 59 s. These are all five held-out incidents involving more than a few dozen prefixes. Across all 16: 10/16 at 0.94 false alerts/day.
- **Second collector.** Run unchanged on RIPE RIS rrc00, PRISM detects 9 of the same 10 incidents (quiet point, 0.94 false alerts/day). Fusing the two collectors (rules fixed before any RIS data was run) did not lower false alerts below the better single collector.
- **Week-long controls.** Four 7-day quiet windows (672 h): 0.54 false alerts/day at the quiet point (95% 0.30-0.88).
- **Owner mode.** Origin alerts: 0.054% false alerts per prefix-day. Leak alerts: 0.65% per origin-AS-day at κ = 20. Owner mode catches YouTube 2008, Route 53 2018 and MainOne 2018.

## Poisoning study and added comparisons

Pre-registered in `HELDOUT_PREREGISTRATION.md` before any run (one later variant and the cap sweep are marked post hoc).

```bash
python3 run2.py clean <CASE...>      # D0 + D1, records culprit seed paths
python3 run2.py attack <CASE...>     # transient and persistent seeding attacks
python3 run2.py attackq <CASE...>    # D1-aware persistent attacker (post hoc)
python3 artemis.py <CASE...>
# ROAs: rpki/<YYYY-MM-DD>_<tal>.csv.xz from https://ftp.ripe.net/rpki/<tal>.tal/<YYYY/MM/DD>/roas.csv.xz
python3 eval_poison.py verify clean attack rpki guard artemis capsweep && python3 fig_poison.py
```

- Undefended PRISM: evaded in 10/10 detected incidents after 26-143 min of seeding.
- D1 (persistence-gated learning, T_adm = 60 min): transient attack detected 10/10, clean detection unchanged (10/16), false alerts 0.94 -> 4.9/day. Capped offender history (exploratory, r = 0.02): 1.3/day, 8/10 transient and 6/10 persistent attacks detected. A D1-aware persistent attacker evades D1 in 10/10 but must carry its routes live for an hour; owner mode flags its first seed 26-213 min before onset.
- Guard G: any value from 30 to 240 min gives the same 10/16 detections.
- RPKI tier: +1 detection (TW2022) at 15 false alerts/day; not used.
- ARTEMIS rules (re-implemented, public-data configuration): origin rules 12/16 at 0.10% false per prefix-day; all rules 15/16 at 3.5%. PRISM owner mode: 11/16 at 0.051% (origin), 15/16 with leak mode.

## Independent benchmark (RouteLLM, 178 events 2002-2024)

`code/ext_run.py`, `code/ext_driver.sh`, `code/ext_eval.py`; source list `code/ext/routellm_event.csv` (Apache-2.0, github.com/vvcode1/RouteLLM @1781c24); results in `results/external/`.
Pre-registered before any case was downloaded. Frozen quiet point, route-views2, 12-h window around the listed time.

- Observatory mode detects 11/178 (6.2%, 95% 3.5-10.7%); owner mode 11/178. BEAM, run by the benchmark's authors on all RouteViews collectors, reports 57.7% event-level accuracy (different setup).
- 121/178 events are not visible at route-views2 (no announcement of a listed prefix carried the attacker); 41 had the attacker already present a day earlier; of the 16 visible and new, owner mode flags 10 and observatory mode 4.
- False alerts over 2,136 benchmark hours: 1.2/day.

## Multi-scale defense (D2), multi-collector kit, live kit (2026-10-07)

- `code/d2.py`, `code/d2cap.py`, `run2.py attackq2`: 6-h offender scale on top of D1. Clean: 10/16 at 5.8 false alerts/day
  (2.5 with the exploratory cap). Detects the transient, persistent and D1-aware attackers in 10/10; a D2-aware attacker
  evades but needs 7.4-15.6 h of live seeding. Results: `results/poison/d2_*.csv`, `d2cap_*.csv`.
- `code/engine_multi.py`, `code/mc_run.py`, `code/mc_driver.sh`, `code/mc_eval.py`: all RouteViews collectors merged
  (pre-registered). Runs free on GitHub Actions (`.github/workflows/multicollector.yml`) - see `RUN_FREE.md`. A pre-registered 15-event sample is run separately.
- `code/live_prism.py`, `code/live_verify.py`: D2 on RIPE RIS Live, verified against Cloudflare Radar. Needs an
  always-on VM for 22+ days - free Oracle Cloud Always Free VM, see `RUN_FREE.md` and `live/prism-live.service`. Not yet run (a 45-min pilot confirmed it keeps up with the full
  RIS Live firehose, about 5,000 messages per second).

## Honest scope notes

- 16 incidents (8 development, 8 held out) and two collectors (route-views2; RIPE RIS rrc00 as a replication) are used. The results describe these cases; they are not population estimates.
- MO2018 was the development case. The 60-minute guard came from inspecting it, and both post-hoc filters came from inspecting control-window alerts. The paper discloses all of this.
- Control windows have no *reported* incident. One large control alert (AS49697, 2018-11-05) may be an unreported real leak.

## License

MIT (code). RouteViews and CAIDA data are subject to their own terms.

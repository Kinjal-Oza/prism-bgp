# PRISM: History-Anchored, Relationship-Aware BGP Hijack & Route-Leak Detection

This is the code and results for the IEEE TNSM submission *"PRISM: History-Anchored, Relationship-Aware Detection and Attribution of BGP Hijacks and Route Leaks from Public Collector Data"* by Kinjal Vaishnav.

Everything here runs on **public data only**:

- RouteViews `route-views2` MRT archives.
- CAIDA serial-1 AS relationships.

No synthetic traffic is used anywhere. Every number in the paper is produced by the scripts below. The results they generated are in `results/`.

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

## Honest scope notes

- 16 incidents (8 development, 8 held out) and two collectors (route-views2; RIPE RIS rrc00 as a replication) are used. The results describe these cases; they are not population estimates.
- MO2018 was the development case. The 60-minute guard came from inspecting it, and both post-hoc filters came from inspecting control-window alerts. The paper discloses all of this.
- Control windows have no *reported* incident. One large control alert (AS49697, 2018-11-05) may be an unreported real leak.

## License

MIT (code). RouteViews and CAIDA data are subject to their own terms.

# PRISM: History-Anchored, Relationship-Aware BGP Hijack & Route-Leak Detection

This is the code, results and paper for the IEEE TNSM submission *"PRISM: History-Anchored, Relationship-Aware Detection and Attribution of BGP Hijacks and Route Leaks from Public Collector Data"* by Kinjal Vaishnav.

Everything here runs on **public data only**:

- RouteViews `route-views2` MRT archives.
- CAIDA serial-1 AS relationships.

No synthetic traffic is used anywhere. Every number in the paper is produced by the scripts below. The results they generated are in `results/`.

## Layout

| Path | What it is |
|---|---|
| `paper/` | LaTeX source (`main.tex` + `sec_*.tex`, `refs.bib`), figures, compiled `PRISM_TNSM_Paper.pdf` |
| `code/cases.py` | The 8 documented incidents (onset, culprit AS) + 8 matched control windows (same hour, 1 week earlier) |
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

Engine flag files (`out/*.flags.parquet`, ~440 MB) are not included because they regenerate deterministically from the archives.

## Headline results (from `results/`)

- **Culprit ranking.** In 7 of 8 incidents, the documented culprit is the top-scoring AS in its 4-hour window.
- **Quiet operating point.** τ_o = 50, τ_x = 2000 detects 5/8 incidents with attribution at **0.56 false alerts/day**, with a median delay of 29 s.
- **Week-before calibration.** Thresholds are set from last week's control only, never from the incidents. This detects 5/8 incidents with 9 false alerts in 32 incident-window hours.
- **Owner mode.** Origin alerts: 0.054% false alerts per prefix-day. Leak alerts: 0.65% per origin-AS-day at κ = 20. Owner mode catches YouTube 2008, Route 53 2018 and MainOne 2018.

## Honest scope notes

- Only 8 incidents and a single collector (route-views2) are used. The results describe these cases; they are not population estimates.
- MO2018 was the development case. The 60-minute guard came from inspecting it, and both post-hoc filters came from inspecting control-window alerts. The paper discloses all of this.
- Control windows have no *reported* incident. One large control alert (AS49697, 2018-11-05) may be an unreported real leak.

## License

MIT (code). RouteViews and CAIDA data are subject to their own terms.

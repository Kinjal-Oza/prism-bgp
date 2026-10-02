# PRISM held-out evaluation: pre-registration (fixed 2026-09-30, before any held-out case was run)

Frozen on the eight development incidents and applied unchanged: engine (NO/NX tests), scoring s = c/(1+H), guard G = 60 min,
5-min windows, detection credit window [-10 min, +60 min], and the operating points
Quiet (tau_o=50, tau_x=2000), Quiet+2VP, Balanced (50, 200), Sensitive (5, 200); week-before calibration rule;
owner mode (every NO flag; NX aggregated per victim origin AS with kappa = 20).

Held-out incidents (onset UTC, culprit AS, source):
| ID | Event | Onset | Culprit | Type | Source |
|---|---|---|---|---|---|
| ID2011 | Indosat mass origination | 2011-01-14 12:19 | 4761 | origin hijack | BGPmon |
| ID2014 | Indosat 417k prefixes | 2014-04-02 18:26 | 4761 | origin hijack | BGPmon |
| GO2017 | Google leak to Verizon (Japan outage) | 2017-08-25 03:22 | 15169 | route leak | Dyn / CircleID |
| SH2019 | Safe Host leak via China Telecom | 2019-06-06 09:44 | 21217 | route leak | Oracle IIJ / APNIC blog |
| VI2021 | Vodafone Idea ~30k prefixes | 2021-04-16 13:48 (corrected, see below) | 55410 | origin hijack | APNIC blog |
| KS2022 | KLAYswap / Kakao /24 | 2022-02-03 01:04 | 9457 | sub-prefix hijack | MANRS, S2W |
| TW2022 | RTComm / Twitter /24 | 2022-03-28 12:06 | 8342 | origin hijack | MANRS |
| CF2024 | Eletronet + Nova / 1.1.1.1 | 2024-06-27 18:51 | 267613, 262504 | hijack + leak | Cloudflare |

Excluded before running: China Telecom 2010 (no verifiable minute-level onset), Celer Bridge 2022 (forged origin; out of scope).
Culprit rule (same as DQ2019): AS(es) the report names as originating or leaking; not upstreams that failed to filter.
Every held-out number will be reported, including misses.

## Correction made after the first run (disclosed)
VI2021 was first registered with onset 2021-04-17 13:48. That date was transcribed from the APNIC blog's local-date
wording; the blog's time (13:48 UTC) is correct, but the event happened on 2021-04-16 (MANRS "BGP Security in 2021"
lists April 16; BleepingComputer shows AS55410 announcements on 2021-04-16). The first run, on the wrong day, found no
AS55410 flags in the window; the AS55410 flags in its warm-up started at 2021-04-16 13:48:58. We corrected the date,
re-ran VI2021 and its control, and report the corrected run. No other onset, culprit, threshold or rule was changed.

# Addendum: second-collector corroboration (fixed 2026-10-01, before any RIPE RIS data was downloaded or run)

Collector 2: RIPE RIS rrc00. The PRISM engine, scoring, guard and thresholds run unchanged and independently on it
(own prefix history, own offender history), from the latest rrc00 bview at least 24 h before the test window.
All 32 cases (16 incidents, 16 controls) are run.

Combination rules, at the frozen operating points (tau_o, tau_x) of the paper:
- RIS alone: PRISM on rrc00 only.
- Either: a (family, AS, 5-min window) unit alerts if its score reaches tau_f at either collector; counted once.
- Corroborated: as Either, but an alert is kept only if the other collector also has a unit for the same family
  and AS in the same window or one window either side (any score).
Detection and false alerts are counted exactly as in the paper (per unique family, AS, window).
All four rules are reported for all 16 incidents, including any that get worse.

## Second-collector outcome (reported in the paper, Section "A second collector")
All 32 rrc00 cases ran (13,838 MRT files after integrity-checked re-downloads; 11 early cases were re-run because the first
download pass left truncated files). Quiet point, all 16 incidents: route-views2 10/16 at 0.94 FA/day; rrc00 alone 9/16 at 0.94;
Either 10/16 at 1.6; Corroborated 10/16 at 1.1. No combination rule beat the better single collector.

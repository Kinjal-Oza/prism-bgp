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

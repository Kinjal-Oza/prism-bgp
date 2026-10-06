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

# Addendum: week-long controls (fixed 2026-10-02, before being run)
To measure false alerts over longer quiet periods, four 7-day control windows on route-views2, each ending 24 h before
the reported onset of TM2015, DQ2019, VI2021 and CF2024 (two development, two held-out incidents). Same engine,
24 h warm-up, frozen operating points and owner-mode rules. Every alert in these windows counts as a false alert.

## Week-long control outcome
All four 7-day windows ran (no download failures). Quiet point: 15 alerts in 672 h = 0.54/day (Poisson 95% 0.30-0.88);
Balanced 1.5/day; Sensitive 7.8/day. Owner mode: 0.036% false origin flags per prefix-day; 0.33% leak alerts per origin-AS-day (kappa 20).

# Addendum: history poisoning (fixed 2026-10-06, before any attack or defense run)

Purpose: measure the weakness stated in the Discussion ("an attacker who announced a target prefix with the future
hijacking origin a day earlier would make the hijack look familiar") and test one defense. Every number is reported,
including attacks that fail and defense costs that are large.

## Threat model
White-box attacker in control of the culprit AS(es) of a real incident. It knows the PRISM code, the Quiet operating
point (tau_o=50, tau_x=2000), the 5-min window and the 60-min guard G, and it can watch public collectors.
Goal: the incident, exactly as it happened in the archive, raises no observatory-mode alert naming a culprit AS.
Means (poisoning): before the onset, announce the (prefix, origin) and (prefix, exporter) pairs that the incident will
later flag, so they are already in PRISM's history when the incident starts; the same announcements also raise the
culprit's offender history H_a.

## Attacked incidents
The 10 incidents detected at the Quiet point (TM2015, RT2017, DV2017, DQ2019, RT2020, ID2011, ID2014, GO2017, SH2019,
VI2021). Undetected incidents cannot be made less detected and are not attacked.

## Seed set and schedule
- Seed items: every distinct (family, prefix, culprit) of NO/NX flags naming a culprit AS with first-flag time in the
  detection credit window [onset-10 min, onset+60 min] of the clean run. Each seed announcement reuses the AS path of
  that item's first flagged announcement in the clean run. One announcement per prefix where one path covers all of
  the prefix's items; extra announcements otherwise.
- Pacing: greedy in 5-min windows. In window k the attacker adds announcements while, for every (family, culprit AS)
  they touch, its own count stays <= floor(0.8 * tau_f * (1 + H_k)), where H_k is the attacker's own maximum count in
  windows <= k-12 (the attacker's model of Eq. 2). Announcements in a window are spread evenly over it.
- Injection: seed announcements come from one synthetic collector session (the only synthetic data in the study),
  merged by timestamp into the otherwise unmodified real stream of the incident case.
- Two attacker variants:
  T (transient): each seed is withdrawn 1 s after it is announced. Seeding ends at onset-15 min.
  P (persistent): seeds stay announced to the end of the run. Seeding ends at onset-75 min, so every seed has been up
    for 60 min before the credit window opens. This attacker carries the bogus routes live before the incident.
- If the schedule would start before the first update file of the case (the RIB time), the attack is reported as not
  representable in the replay rather than shortened.

## Defense D1: persistence-gated learning (T_adm = 60 min, set equal to G a priori; not tuned)
- A (prefix, origin) or (prefix, non-cone exporter) pair enters history only after at least one collector session has
  carried it continuously for T_adm. Announcements in the RIB snapshot are admitted at once. Withdrawals and route
  replacements end a session's carriage. Sessions are identified by peer IP.
- While a pair is pending, the NO/NX test is applied at the start of each presence episode (the first session to carry
  it after none did), against admitted history only.
- Offender history H_a counts, per 5-min window, only flagged pairs that were later admitted, and such a count enters
  H_a no earlier than max(window + G, admission time). c(a,w) still counts every flag.
- Ablation (same runs): D1-hist, history gating without the change to H_a.

## Runs and metrics
1. Clean runs, all 32 cases (16 incidents, 16 controls), D0 (current PRISM) and D1 in one pass. D0 must reproduce the
   published PRISM-origin and PRISM-export units exactly; any mismatch is reported.
2. Clean cost of D1 (and D1-hist): detection, false alerts/day and median first-flag delay at the four frozen operating
   points (Quiet, Quiet+2VP, Balanced, Sensitive), development, held-out and all 16, scored exactly as in the paper.
3. Attack runs, 10 incidents: D0 under T/P (identical for D0, which ignores withdrawals), D1 under T, D1 under P.
   Attack succeeds iff no alert at the Quiet point names a culprit AS from seeding start to onset+60 min.
   Also reported: seeding lead time and number of seed announcements, whether the seeding itself raises an alert, and
   the time of the first owner-mode origin flag on a seeded prefix (owner mode alerts on every NO flag).

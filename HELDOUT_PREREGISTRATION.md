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

# Addendum: owner-side baseline, RPKI tier, guard sensitivity (fixed 2026-10-06, before any of them was evaluated)

## ARTEMIS-style baseline (owner mode)
Re-implementation of ARTEMIS's detection rules (Sermpezis et al., ToN 2018), code/artemis.py. Every prefix owner is
given the most generous configuration public data allows: all origins and first-hop neighbours seen for the prefix in
the RIB snapshot and the 24-h warm-up (the same information PRISM has). Alert types E|0, E|1, S|0, S|1, S|-.
Reported for all 32 cases, in two variants: ARTEMIS-origin (E|0, S|0; comparable to PRISM owner origin mode) and
ARTEMIS-full (all five types). Metrics exactly as for PRISM owner mode: an incident is detected if an alert naming a
culprit (hijacker AS, or origin for S|-) falls in [onset-10 min, onset+60 min]; false alerts are distinct prefixes
alerted with a non-culprit hijacker, per prefix-day of exposure (RIB prefixes x test-window days), pooled over cases.
BEAM is not re-run (see paper); RADBench data were not found publicly.

## RPKI tier
For cases whose test window starts on or after 2018-04-05 (all five RIR trust anchors archived by RIPE NCC from then
on: AM2018, MO2018, DQ2019, RT2020, SH2019, VI2021, KS2022, TW2022, CF2024 and their controls), each PRISM NO flag in the
test window is validated against the union of the five RIRs' published ROAs for the day the test window starts
(ftp.ripe.net/rpki). Tier rule, fixed now: a (culprit/offender AS, 5-min window) unit alerts if it reaches the Quiet
threshold OR contains at least one RPKI-invalid NO flag. Reported: detection and false alerts/day for these 9 incidents
and 9 controls, with and without the tier; also under the poisoning attacks for the attacked incidents in this range.

## Guard sensitivity
G in {0, 5, 15, 30, 60, 120, 240} min, all 16 incidents and 16 controls, at the frozen Quiet point (D0 flags). Every
value is reported; the paper's G = 60 min is not re-selected.

# Addendum: D1-aware persistent attacker (added 2026-10-06 AFTER seeing the TM2015 and RT2017 attack results)
Disclosed as post hoc. In TM2015 the pre-registered attackers, which pace against Eq. 2, were caught under D1 because D1
admits a seed into H_a only after T_adm, one window later than the attacker's model assumed. A white-box attacker would
know D1. Variant Q: the persistent attacker (P) paces with its own windows entering H only 13 windows later instead of
12; seeding still ends at onset-75 min. Run under D1 for all 10 attacked incidents; success defined as before. Every
result is reported next to the pre-registered T and P results, not instead of them.

# Addendum: external benchmark (fixed 2026-10-07, before any external case was downloaded or run)
Source: RouteLLM benchmark (Liu et al., arXiv:2608.22812, Apache-2.0), github.com/vvcode1/RouteLLM,
event_collector/events/event.csv at commit 1781c24: 232 expert-validated incidents mined from operator mailing lists,
with time, attacker AS, victim AS, prefixes and category. An independent team selected these incidents, and it reports
BEAM's official implementation at 57.67% event-level accuracy on the full benchmark (Table II of that paper).

Cases: every event with time on or after 2002-01-01 (route-views2 coverage) - 178 events, all three categories
(prefix hijacking, route leak, path hijacking), no other exclusion. Events that coincide with our 16 incidents are
flagged and reported both with and without them.
Replay: route-views2, RIB at least 24 h before the test window, test window [T-6h, T+6h] around the listed time T
(the benchmark's times are partly approximate, some fall back to e-mail timestamps; the 12-h window is fixed for that
reason). CAIDA serial-1 relationships of the latest available month not after T. Frozen PRISM (D0), Quiet point.
Metrics (fixed now):
- Observatory detection: some Quiet-point alert names an attacker AS with first flag in the test window.
- Owner detection: some NO or NX flag names an attacker AS on a listed prefix or a more-specific of one, in the window.
- False alerts: Quiet-point alerts not naming an attacker AS, per day of test-window exposure.
- Reported per category and per period, with Wilson intervals; compared with the published BEAM figure, noting the
  differences in setup (BEAM: all RouteViews collectors, +-12 h, its own event-level definition, all 232 events).
No threshold, window or rule is changed after the first external result. Failures to download or parse are reported.

# Addendum: multi-scale defense, multi-collector replay, live deployment (fixed 2026-10-07, before any of them was run)

## D2: multi-scale offender score (on top of D1)
- Slow scale L = 6 h, evaluated at every 5-min window w: c6(a,w) = distinct prefixes flagged for AS a (per family) in
  the 72 windows ending at w. H6(a,w) = max of c6 computed from later-admitted flags only (D1 convention), over windows
  ending at least 72 + 12 windows before w, entering no earlier than the admissions involved.
  s6 = c6 / (1 + H6); same thresholds tau_f as the 5-min score (Quiet: 50 / 2000).
- An s6 episode is a maximal run of consecutive windows with s6 >= tau_f for the same (family, AS); it counts once, at
  the first window of the run. D2 alerts = D1 5-min alerts plus s6 episodes.
- Detection and false alerts exactly as before (an s6 episode naming a culprit counts as a culprit alert, any other
  episode as one false alert). Reported at the Quiet point on all 16 incidents and 16 controls, and for the existing
  T, P and Q attack runs.
- D2-aware attacker (Q2): persistent; paces so that, for every (family, AS) it touches, the 5-min count stays
  <= 0.8 tau (1 + H5) with its windows entering H5 13 windows later, AND its trailing 72-window count stays
  <= 0.8 tau (1 + H6) with its windows entering H6 72 + 13 windows later. Seeding ends at onset - 75 min. Run under D2
  on the 10 attacked incidents; report detection and the lead time it needs. If the lead exceeds the warm-up available
  in the replay, the attack is reported as not representable.

## Multi-collector replay (kit for a larger machine; results reported only when run)
- Collectors: every RouteViews collector that has a RIB at or before (test window start - 24 h) and UPDATE files
  covering the window, as listed by the BGPKIT broker (the BEAM benchmark run used all RouteViews collectors).
- One merged, time-ordered stream; history is the union over collectors; sessions are (collector, peer IP); vantage
  points are (collector, peer AS).
- Frozen PRISM (D0) at the Quiet point, no retuning; also the four frozen operating points.
- Cases: the 178 RouteLLM events (protocol of the external-benchmark addendum) and our 16 incidents + 16 controls.
- Same metrics and visibility diagnostics as the single-collector runs.

## Live deployment (kit; results reported only when run)
- Input: RIPE RIS Live (all RIS collectors), IPv4 announcements and withdrawals. Bootstrap: latest RIS rrc00 bview and
  the CAIDA serial-1 snapshot of the latest available month; 24 h of live warm-up with no alerting.
- Detector: D2 (D1 + multi-scale) at the Quiet point, plus owner-mode flags for a user-supplied prefix list.
- Duration: at least 21 days of alerting. Every alert is logged with its evidence (prefixes, paths, vantage points).
- Verification: each alert is matched (same AS within +-2 h) against Cloudflare Radar's BGP hijack and route-leak event
  feeds; unmatched alerts are classified by hand from the evidence and public reports into confirmed / benign /
  unknown. Radar events with confidence >= 8 that PRISM did not alert on are listed as misses. All alerts are reported.
  failed, not dropped.
- Interim sample, run in the authors' 2-CPU workspace while the full run is pending: 15 benchmark events drawn with
  Python random.Random(20261008).sample over the 178 event ids (code/mc_sample15.txt). Reported as a sample, next to the
  single-collector result for the same 15 events, and superseded by the full run when it exists.
- Live deployment: an Oracle Cloud "Always Free" Ampere A1 VM (personal account), otherwise as pre-registered.

# Addendum: execution venue change (fixed 2026-10-08, before any case of the full multi-collector run and before the live run)
Pushing to GitHub is not possible from the authors' workspace, so the two long jobs run there instead. No protocol,
threshold or metric changes.
- Full multi-collector run: all 210 cases in the authors' 2-CPU workspace with the same code (code/mc_driver.sh,
  idempotent). The 15 interim-sample cases already run with the identical code and protocol are reused, not re-run.
  A case that fails (download error, out of memory or disk) is reported as failed, not dropped. The GitHub Actions
  workflow remains an equivalent alternative.
- Live deployment: runs in the same workspace from the time it starts. Any interruption (workspace restart, network
  loss) restarts the process with a fresh 24 h warm-up; every gap is reported, and the >=21 days of alerting are
  counted excluding warm-ups and gaps. Verification as pre-registered (Cloudflare Radar, +-2 h, same AS).

# Addendum: attribution-free fields for the BEAM comparison (fixed 2026-10-08, before any benchmark case of the full multi-collector run)
RouteLLM (Sec. IV-A) defines event-level accuracy only as "whether an incident is detected", with BEAM retrained on
data from the evaluation period and run on +-12 h; it does not require naming the attacker. To give a number closer to
that definition, the full multi-collector run also records, per benchmark event, in the same pre-registered +-6 h window:
- pfx_detected: some Quiet-point alert (any AS) whose flags in its alerting window include a listed prefix or a
  more-specific of one.
- pfx_owner: some NO or NX flag (any AS) on a listed prefix or a more-specific of one.
- any_alert: some Quiet-point alert at all in the window (reported only as the chance reference: it says nothing about
  the event).
The pre-registered metrics (attacker-attributed detection and owner detection) stay the headline. The new fields are
reported next to them with Wilson intervals, as descriptive. The 15 interim-sample events are re-run so that they carry
the fields; the earlier sample results stay as reported.

# Addendum: final execution venues (fixed 2026-10-08, before the GitHub Actions run and before the live VM exists)
The authors' workspace stops a few minutes after it goes idle: the live process started there at 19:24 UTC died at about
19:40 UTC, still in warm-up (no alerting window), and the multi-collector driver had finished 3 cases. Both attempts are
discarded. The runs go back to the venues of the first venue addendum, with the protocol, the attribution-free fields
and the retry rule unchanged:
- Full multi-collector run: GitHub Actions on the public repository, all 210 cases (the 3 workspace cases are re-run).
  The workflow also starts on the push that adds it. Only transient network failures are retried (inside a job); a
  case that still fails is reported as failed.
- Live deployment: Oracle Cloud Always Free VM, as pre-registered. Verification with a Cloudflare API token.

# Addendum: live VM shape (fixed 2026-10-08, before the live run's warm-up ended)
The Always Free Arm shape (VM.Standard.A1.Flex) was out of capacity in the home region (us-sanjose-1, one availability
domain) for over an hour of automatic retries. The live run therefore uses an Oracle VM.Standard.E5.Flex (x86, 2 OCPU,
12 GB) paid from the account's free-trial credit, with no other change. The service started 2026-10-08 22:40 UTC
(bootstrap done 22:45 UTC); alerting begins after the 24 h warm-up, and restarts are logged in live_out/restarts.log.

# Addendum: age of already-present attacker routes (fixed 2026-10-11, before any of these RIBs was examined beyond one test case)
Real data only. For the 41 RouteLLM benchmark events in class "visible, attacker already present" (route-views2), take
the latest route-views2 RIB at or before 1, 7, 30 and 90 days before the listed time, and record the number of routes
to a listed prefix (or a more-specific) whose AS path contains a listed attacker AS (code/presence_age.py). One event
(X008) was run as a test of the code before this addendum was written; its result is kept. Reported: for each event,
the oldest look-back at which the attacker's routes were already present, grouped as < 7 days, 7-30 days, 30-90
days, >= 90 days, and failures. Interpretation fixed now: routes that appeared within days before an event are what a
history-poisoning attacker would produce, and only they could be recovered by a longer admission delay; long-standing
routes cannot be told apart from normal routing by any history-based detector. No detector threshold is involved.

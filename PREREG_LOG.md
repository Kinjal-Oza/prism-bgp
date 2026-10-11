# Pre-registration log

Every addendum in `HELDOUT_PREREGISTRATION.md` was written and committed before the analysis it describes was run,
except where the addendum itself says otherwise (the D1-aware attacker, added after the first attack results).
Commit times are as recorded by git (UTC); the public GitHub history shows when each commit was pushed.

| Addendum | Commit | Committed (UTC) |
|---|---|---|
| Held-out incident list (8 incidents), frozen design | 48bc1f6 | 2026-09-30 20:50 |
| Second collector (RIPE RIS rrc00) and fusion rules | caa8e49 | 2026-10-02 10:25 |
| Week-long controls | 013154a | 2026-10-02 14:30 |
| History poisoning: attacks and persistence-gated defense | 201495f | 2026-10-06 20:23 |
| ARTEMIS-style baseline, RPKI tier, guard sensitivity | 0e4d212 | 2026-10-06 20:38 |
| D1-aware attacker (post hoc, disclosed) | 7716bbd | 2026-10-06 22:04 |
| External benchmark (RouteLLM events) | 55f48a8 | 2026-10-07 06:09 |
| Multi-scale defense (D2), multi-collector replay, live deployment | 7dde742 | 2026-10-08 02:19 |
| Execution venues and interim sample | cf30713 | 2026-10-08 04:32 |
| Venue change | ec2e19b | 2026-10-08 18:52 |
| Attribution-free fields for the BEAM comparison | 566a524 | 2026-10-08 18:58 |
| Final venues | e726505 | 2026-10-08 19:51 |
| Live VM shape | c23028e | 2026-10-08 22:53 |
| Age of already-present attacker routes | 6ce774c | 2026-10-11 01:05 |
| Held-back validation of the capped defense | e566099 | 2026-10-11 01:57 |
| BEAM head-to-head on three held-out incidents | 1eba976 | 2026-10-11 02:02 |
| BEAM detection execution and BEAM poisoning stress test | (this commit) | 2026-10-11 |

Implementation fixes that do not change any protocol (re-aggregation of the multi-collector run after the first
aggregation missed files; broker retries; faster live client) are in the ordinary commit history.

# Ruling map

One row per owner ruling 1-154 on #6854, and one per owner record that set a rule, showing what each
became: the [`rules.md`](../rules.md) rule (`UR-n`), `one-off` (one PR, row, fold or order, now
history), `package <id>` (binds only while that package is open; its text is in `packages/` or
`packages-done.md`), or `superseded by <n>`. A ruling with several parts lists each. Rulings 118 and
119 are coordinator decisions C-118 and C-119. Pass 2 merged rules that said the same thing into the
lower number; the ruling and record rows name the rule that now holds each one, and "Merged rules"
lists every number that left `rules.md`. The owner design session of 2026-10-12 is ruling 147; a
package tagged `[rNNN]` is a fix that ruling NNN ordered.

## Rulings

| ruling | became                                                                                                                                                                                            |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | UR-33 (monitoring denied when exposed); package O1.11 (done, `awaiting real tier`)                                                                                                                |
| 2      | UR-30                                                                                                                                                                                             |
| 3      | one-off (O1.9 deletes `rollback.yml`; #6875)                                                                                                                                                      |
| 4      | one-off (#6875); its derived rule is UR-99                                                                                                                                                        |
| 5      | one-off (#6861 approved)                                                                                                                                                                          |
| 6      | one-off (#6864 approved)                                                                                                                                                                          |
| 7      | superseded by 40 (UR-47)                                                                                                                                                                          |
| 8      | one-off (F1.1 questions to R2); its derived rule is UR-99                                                                                                                                         |
| 9      | UR-119 (one required check); rest one-off (#6870)                                                                                                                                                 |
| 10     | one-off (`VlmRequestErrors`, waits with B1.1); its derived rule is UR-99                                                                                                                          |
| 11     | one-off (#6884 not owner-tier); its derived rule is UR-99                                                                                                                                         |
| 12     | UR-37 (hooks in the gate); package O1.12 (done)                                                                                                                                                   |
| 13     | one-off (#6867 approved)                                                                                                                                                                          |
| 14     | one-off (#6898 approved)                                                                                                                                                                          |
| 15     | UR-108 (owner PRs auto-merge and queue); queue order one-off                                                                                                                                      |
| 16     | one-off (#6904 approved)                                                                                                                                                                          |
| 17     | UR-29, UR-166 (as amended by the 2026-10-12 merge-comment decision)                                                                                                                               |
| 18     | superseded by 40 (UR-47); `owner` label removal one-off                                                                                                                                           |
| 19     | UR-102, UR-166                                                                                                                                                                                    |
| 20     | one-off (#6908 approved)                                                                                                                                                                          |
| 21     | UR-104 (oldest ready first); queue order one-off                                                                                                                                                  |
| 22     | UR-133, UR-140; B1.4 routing one-off                                                                                                                                                              |
| 23     | one-off (B1.1 owner run deferred)                                                                                                                                                                 |
| 24     | UR-123; #6913 slot one-off                                                                                                                                                                        |
| 25     | one-off (ruling 13 covers #6867)                                                                                                                                                                  |
| 26     | UR-104 (named place), UR-106 (ready time, as amended 2026-10-12)                                                                                                                                  |
| 27     | UR-102                                                                                                                                                                                            |
| 28     | one-off (heavy queue reordered; executed)                                                                                                                                                         |
| 29     | UR-25; batch 8 catch-up one-off                                                                                                                                                                   |
| 30     | one-off (#6924 approved; prompt programme resumed)                                                                                                                                                |
| 31     | one-off (#6921 approved)                                                                                                                                                                          |
| 32     | superseded by 40 (UR-47)                                                                                                                                                                          |
| 33     | one-off (#6920 approved); package W3.2 (caps baseline, `synthbench/commands` exception)                                                                                                           |
| 34     | one-off (#6922 approved)                                                                                                                                                                          |
| 35     | package B-1 follow-up (done, #6927)                                                                                                                                                               |
| 36     | one-off (alloy ports in #6925)                                                                                                                                                                    |
| 37     | one-off (#6925 approved)                                                                                                                                                                          |
| 38     | one-off (#6923 approved)                                                                                                                                                                          |
| 39     | UR-53 (item M), UR-91 (item G), UR-37 (item E); small packages C, D, I, J, L-i, L-ii one-off                                                                                                      |
| 40     | UR-47, UR-92, UR-98                                                                                                                                                                               |
| 41     | UR-66; W3.1 parking one-off                                                                                                                                                                       |
| 42     | superseded by 49                                                                                                                                                                                  |
| 43     | UR-64; package backend entry-point trace (done, #6935)                                                                                                                                            |
| 44     | UR-179; package no-API-key-in-browser (done, #6936)                                                                                                                                               |
| 45     | UR-95; #6937 approval one-off                                                                                                                                                                     |
| 46     | one-off (#6909 approved)                                                                                                                                                                          |
| 47     | package R47 (done, #6943)                                                                                                                                                                         |
| 48     | UR-96; #6929/#6930 conditions one-off                                                                                                                                                             |
| 49     | UR-142 (no copying stores); ruling 42 reversal one-off                                                                                                                                            |
| 50     | UR-59; F2.2 move one-off                                                                                                                                                                          |
| 51     | one-off (F2.2 Files line)                                                                                                                                                                         |
| 52     | one-off (banner spec red-main fix)                                                                                                                                                                |
| 53     | UR-59; assignments one-off                                                                                                                                                                        |
| 54     | UR-67, UR-166; W3.3 parking one-off                                                                                                                                                               |
| 55     | UR-106 (approval across a merge-only head); R55 package one-off (done, #6950)                                                                                                                     |
| 56     | UR-10 (contract rule 2), UR-156                                                                                                                                                                   |
| 57     | UR-142; B1.2 count source one-off                                                                                                                                                                 |
| 58     | one-off (#6945 widened)                                                                                                                                                                           |
| 59     | UR-106 (approval across update-branch), UR-152 (half-built at the UI end); #6941 approval one-off                                                                                                 |
| 60     | package R60 API-key scopes (done, #6959)                                                                                                                                                          |
| 61     | one-off (#6947 approved; `braces` exemption); package R61 (done, #6960)                                                                                                                           |
| 62     | one-off (OD-36-38 to the R2 sheet; small findings routed)                                                                                                                                         |
| 63     | dropped (pass 2 Q7: no wait for `main`'s run); #6955 one-off                                                                                                                                      |
| 64     | UR-38, UR-162, UR-163                                                                                                                                                                             |
| 65     | one-off (#6957 approved; heartbeats issue created)                                                                                                                                                |
| 66     | UR-136                                                                                                                                                                                            |
| 67     | one-off (OD-39 added to the R2 sheet)                                                                                                                                                             |
| 68     | package B2.2 (done, parked)                                                                                                                                                                       |
| 69     | one-off (#6961 approved)                                                                                                                                                                          |
| 70     | package W3.3 (repo slug exemption)                                                                                                                                                                |
| 71     | package r71 (done, #6968)                                                                                                                                                                         |
| 72     | package `[r72]` coverage-gate timeout wrapper (done, #6971)                                                                                                                                       |
| 73     | package O2.3b (done, #6973)                                                                                                                                                                       |
| 74     | superseded by 93 (UR-125)                                                                                                                                                                         |
| 75     | one-off (B1.6 real tier: branch 1)                                                                                                                                                                |
| 76     | package `[r76]` npm-audit alias fix (done, #6966)                                                                                                                                                 |
| 77     | UR-38; owner PR #6965 one-off                                                                                                                                                                     |
| 78     | one-off (#6967 approved)                                                                                                                                                                          |
| 79     | one-off (#6959 approved)                                                                                                                                                                          |
| 80     | one-off (#6969 approved; ORCHESTRATOR-01)                                                                                                                                                         |
| 81     | UR-162, UR-166, UR-168                                                                                                                                                                            |
| 82     | UR-54, UR-63                                                                                                                                                                                      |
| 83     | UR-104, UR-111, UR-112, UR-25                                                                                                                                                                     |
| 84     | UR-101                                                                                                                                                                                            |
| 85     | UR-38, UR-173                                                                                                                                                                                     |
| 86     | UR-66, UR-67, UR-148                                                                                                                                                                              |
| 87     | UR-83 (inventory hot-file row); package F2.3 (in progress)                                                                                                                                        |
| 88     | UR-160, UR-174                                                                                                                                                                                    |
| 89     | UR-86 (OD-39), UR-87 (OD-33); R2a record one-off (#6980); package Phase 4 priority tiers                                                                                                          |
| 90     | one-off (#6970 approved; heavy agents pause)                                                                                                                                                      |
| 91     | one-off (#6980 approved)                                                                                                                                                                          |
| 92     | one-off (F2.2 follow-up to frontend)                                                                                                                                                              |
| 93     | UR-125; package real-sleep gate (done, #6972)                                                                                                                                                     |
| 94     | package `[r94]` `setup.py` re-runs and `--convert-monitoring-key` (done, #7038)                                                                                                                   |
| 95     | package `[r95]` monitoring-key gaps S1, S4 (open; `packages/backend.md`)                                                                                                                          |
| 96     | item 8: package dead CI failure guards (done, #6993); item 11: package `[r96i11]` (open; `packages/ops.md`)                                                                                       |
| 97     | UR-56 (F2.3 claim PR), UR-107 (never combine queued PRs); package draft-skip workflows (done, #6989)                                                                                              |
| 98     | superseded by 101                                                                                                                                                                                 |
| 99     | one-off (ops-b work order)                                                                                                                                                                        |
| 100    | package G2 nightly moves (done, #6992); G3 part superseded by 101                                                                                                                                 |
| 101    | UR-104 (UR-103 part dropped, pass 2 Q7); #6994/#6997 one-off                                                                                                                                      |
| 102    | package golden step `npm ci` (done); superseded by 143                                                                                                                                            |
| 103    | package F2.3 (row lifecycle)                                                                                                                                                                      |
| 104    | package F2.3 (batch file rule)                                                                                                                                                                    |
| 105    | package feature check in `CI Gate` (done, #7004)                                                                                                                                                  |
| 106    | one-off (B2.2 parked)                                                                                                                                                                             |
| 107    | UR-85; packages O2.4, B2.3                                                                                                                                                                        |
| 108    | one-off (F-017, F-020 demoted); its derived rule is UR-99                                                                                                                                         |
| 109    | UR-116; package `[r109]` (done, #7003)                                                                                                                                                            |
| 110    | superseded by 112                                                                                                                                                                                 |
| 111    | package F2.3 (`backend/tests/golden/__init__.py`)                                                                                                                                                 |
| 112    | UR-175                                                                                                                                                                                            |
| 113    | UR-115; package `[r109b]` (done, #7006)                                                                                                                                                           |
| 114    | UR-128; package `[r114]` (done, #7014); interim flip rule one-off                                                                                                                                 |
| 115    | package OB.4 (trigger)                                                                                                                                                                            |
| 116    | package `[r116]` (done, #7012); superseded by 143 (UR-131 keeps its firewall clause)                                                                                                              |
| 117    | UR-10 (contract rule 5)                                                                                                                                                                           |
| 118    | coordinator decision C-118 (not an owner ruling); half kept by 120                                                                                                                                |
| 119    | coordinator decision C-119 (not an owner ruling); stands per 120                                                                                                                                  |
| 120    | UR-45, UR-48, UR-151; C-118/C-119 disposition one-off                                                                                                                                             |
| 121    | UR-81                                                                                                                                                                                             |
| 122    | UR-125, UR-126; package `[r122]` (open, #7027 merged; `packages/backend.md`)                                                                                                                      |
| 123    | UR-128; spec fix one-off                                                                                                                                                                          |
| 124    | one-off (R2 sheet face-events row)                                                                                                                                                                |
| 125    | UR-114, UR-128; quarantine of F-022, F-007, F-235 one-off                                                                                                                                         |
| 126    | UR-48, UR-129                                                                                                                                                                                     |
| 127    | UR-148, UR-10, UR-153                                                                                                                                                                             |
| 128    | package Phase 4 Monitoring page                                                                                                                                                                   |
| 129    | package `[r129]` (open, #7031 merged; `packages/backend.md`)                                                                                                                                      |
| 130    | packages `[r130b]` (open; `packages/backend.md`) and `[r130f]` (#7039; `packages/frontend.md`)                                                                                                    |
| 131    | package Phase 4 Trash delete action                                                                                                                                                               |
| 132    | package Phase 3 rate-limit countdown retirement                                                                                                                                                   |
| 133    | package Phase 3 PWA install prompt retirement                                                                                                                                                     |
| 134    | package Phase 3 batch-statistics history views retirement                                                                                                                                         |
| 135    | UR-66 (R2b-round Phase 3 start), UR-149; round 1 record #7030 (merged); round 1 tiers one-off                                                                                                     |
| 136    | UR-78; #7026 fold one-off                                                                                                                                                                         |
| 137    | UR-121; #7022/#7023/#7025 one-off                                                                                                                                                                 |
| 138    | UR-144                                                                                                                                                                                            |
| 139    | package R2a alert-rules (schedule end minute)                                                                                                                                                     |
| 140    | UR-124; package W3.3 (Done-when gains the citation gate)                                                                                                                                          |
| 141    | one-off (O3.8 target met; `timeout(30)`); package `[r141]` follow-up                                                                                                                              |
| 142    | UR-130; verdict-spread check one-off                                                                                                                                                              |
| 143    | UR-131, UR-176; package `[r143]` (open, #7034 merged; `packages/ops.md`)                                                                                                                          |
| 144    | package O2.5 (not started; `packages/ops.md`); UR-10 (contract rule 5: does not gate Phase 2's exit)                                                                                              |
| 145    | UR-94, UR-29, UR-113, UR-122; freeze lift one-off; package `[r141]` follow-up                                                                                                                     |
| 146    | UR-39, UR-42, UR-155; the `rules.md` ledger itself superseded by the plan rewrite (record 6128714278)                                                                                             |
| 147    | the plan rewrite (owner design session 2026-10-12; see "Owner records")                                                                                                                           |
| 148    | packages `[r148a]`, `[r148b]`, `[r148c]`; F-278 under UR-153 one-off (record 6136930446)                                                                                                          |
| 149    | UR-106, UR-91, UR-116; packages `[r149b]`, `[r149d]`, `[r149e]`, `[r149f]` (record 6146380050)                                                                                                    |
| 150    | packages `[r132]`, `[r133]`, `[r134]`; ops F2.3 batches; `OB.3` (record 6147963319)                                                                                                               |
| 151    | UR-125 (integration re-run); package `[r151]` (record 6149020713)                                                                                                                                 |
| 152    | `scripts/uplevel/coordinator_snapshot.py` and the tick steps, PR #7078 (record 6149140632)                                                                                                        |
| 153    | UR-92 (owner tier only for UR-47's owner kinds) (record 6151644378)                                                                                                                               |
| 154    | real-tier run owners for B1.1, F1.2, O1.11, O2.2, O2.4; `O2.5`'s Done-when (record 6152457996)                                                                                                    |
| 155    | package `[r132]` pill text and nginx-429 note; ruling 125's quarantine ends (6153625662)                                                                                                          |
| 156    | UR-23, UR-92, UR-102, UR-108, UR-38, UR-25 (lane auto-merge; record 6154557279)                                                                                                                   |
| 157    | package `[r157]` (O2.4 parity diagnosis; record 6154665161)                                                                                                                                       |
| 158    | F2.3 batch identity: the split post, not plan text (6154948109)                                                                                                                                   |
| 159    | package `[r157]`'s committed real-tier runner (record 6154999327)                                                                                                                                 |
| 160    | dependabot split; packages `[r160a]`, `[r160b]` (record 6155111397)                                                                                                                               |
| 161    | lane.md "Self-review": ready when code is complete (6156907393)                                                                                                                                   |
| 162    | `O2.5`'s spike blockers; package `[r162]` (record 6156947315)                                                                                                                                     |
| 163    | lane.md, operator.md tick step 1: read BINDING NOW records (6156999669)                                                                                                                           |
| 164    | UR-10, UR-21, UR-102, UR-179; package `[r164a]` (record 6157102381)                                                                                                                               |
| 165    | packages `[r165a]`, `[r165b]`: quarantine cures (record 6167988837)                                                                                                                               |
| 166    | flaky golden specs published, not failed (record 6168002797)                                                                                                                                      |
| 167    | F-034: frontend `/events/:id` redirect (record 6168022059)                                                                                                                                        |
| 168    | package `[r168]` and `[r130b]`'s fast-path flag (record 6168040085)                                                                                                                               |
| 169    | `[r96i11]` accepted as built; #7052 approved (record 6168049984)                                                                                                                                  |
| 170    | lane.md, operator.md step 1: every live record (6168081817)                                                                                                                                       |
| 171    | reviewer auto-merge may merge at once (record 6168101206)                                                                                                                                         |
| 172    | package `[r172]`: per-module import budget (record 6168112919)                                                                                                                                    |
| 173    | package `[r173]`: golden skips in the registry (record 6168125268)                                                                                                                                |
| 174    | compose-render entry leaves `tpa_slow_list` (record 6168142239)                                                                                                                                   |
| 175    | lane.md roster: `F2.3` rebalanced (FE-4 to docs, OP-3 to ops-b) (record 6168756268)                                                                                                               |
| 176    | UR-180: sandbox disks under 90%, targeted cleanup (record 6172107453)                                                                                                                             |
| 177    | lane.md, operator.md step 1: uncarried records, filtered (record 6172198207)                                                                                                                      |
| 178    | lane.md beat before long steps; coordinator.md step 5 (record 6172424097)                                                                                                                         |
| 179    | UR-155 600-char heartbeats; UR-181 evidence cells (record 6172543400)                                                                                                                             |
| 180    | package `[r157]`: independent builds, `--plan-timeout` (record 6173140800)                                                                                                                        |
| 181    | package `[r181]`: lane-tick digest, activity snapshot; `BLOCKER:` line (record 6173920972)                                                                                                        |
| 182    | UR-182: RTX VSS positioning, Easy/Advanced modes; seven rows kept (record 6174228588)                                                                                                             |
| 183    | package B3.2: scene-change vertical kept, R2a row 24 over OD-28 (record 6175205677)                                                                                                               |
| 184    | heavy agents renamed heavy-a/-b; FE-4 and OP-1 batches; UR-59 label (record 6177514438)                                                                                                           |
| 185    | `O2.5`'s prod-shape run on maui, run by the owner (record 6181352718)                                                                                                                             |
| 186    | package `[r162]`: backend's socket only; alloy keeps its mount (record 6181436641)                                                                                                                |
| 187    | F2.3's seeded CI project to heavy-b, ops-b reviews (record 6182863643)                                                                                                                            |
| 188    | `O2.4` and `O2.5` move to the operator: agent-gpu venue, in-sandbox store (record 6182950505)                                                                                                     |
| 189    | package `[r189]`: the golden leg's cap follows measured time (record 6191177913)                                                                                                                  |
| 190    | heavy-b out of service; heavy-a takes #7155, OP-1's seeded rows, B2.3 (record 6191930218)                                                                                                         |
| 191    | docs flips F-256, specs F-254, F-278; frontend FE-3's six after #7145 (record 6192225830)                                                                                                         |
| 192    | routes F-028 (frontend), F-012's disk seed (heavy-a), F-234 (docs) (record 6192470752)                                                                                                            |
| 193    | package `[r193]`: lanes wake on GitHub events; ticks become a fallback (record 6195149856)                                                                                                        |
| 194    | F-234: docs sets `channel: 'chromium'` in permission.spec.ts only (record 6197728882)                                                                                                             |
| 195    | O2.5 runs on maui after package `[r195]` (host-login harness) (record 6197833896)                                                                                                                 |
| 196    | packages `[r196a]` frontend, `[r196b]` docs, `[r196c]` ops-b: last F2.3 rows (record 6198072340)                                                                                                  |
| 197    | `[r197]`, owner's session: plan lint, footers, `--beat` (records 6198161166, 6198199744)                                                                                                          |
| 198    | one review per PR, the author's UR-89 subagent; author arms auto-merge (record 6198314579)                                                                                                        |
| 199    | package `[r199]`: analysis acks follow a stored event or a terminal failure (record 6198662741)                                                                                                   |
| 200    | package `[r200]`: one owner for the running pipeline workers (record 6198757258)                                                                                                                  |
| 201    | `[r184]` gets its block: the launcher prints the heavy pi start line (record 6198825479)                                                                                                          |
| 202    | one-GPU installs wait for Phase 4 as `O4.1`; no lane now (record 6198876496)                                                                                                                      |
| 203    | B3.3 owns schema upgrades; B3.1 drops tables as its upgrades (record 6198942052)                                                                                                                  |
| 204    | package `[r204]`: one realtime connection owner in the frontend (record 6199283332)                                                                                                               |
| 205    | package `[r205]`: no status is not healthy; health is not an alert count (record 6199725340)                                                                                                      |
| 206    | OD-31 stands; F-236's design also settles what an event sends on (record 6199786907)                                                                                                              |
| 207    | real tier is real VLM, fake detector; `[r207]` holds detector rows back (record 6199844401)                                                                                                       |
| 208    | owner's session measures record repair; result 6200252063 (record 6199979513)                                                                                                                     |
| 209    | claim drafts that hold nothing close: #7072 now, #6996 after `[r196b]` (record 6200064485)                                                                                                        |
| 210    | R2b round 2: R2 §3 approved as a rule; export tooling stays; spikes go (record 6200282082)                                                                                                        |
| 211    | R2b: F-048 complete, P1, fix now; `[r211b]` backend, `[r211f]` frontend (record 6200331506)                                                                                                       |
| 212    | R2b: F-061, F-062 complete, P1, fix now; `[r212]` frontend (record 6200384247)                                                                                                                    |
| 213    | R2b: F-060 split, labelling fix-now `[r213]`; learning retired with F-131 (record 6200455263)                                                                                                     |
| 214    | R2b: F-213, F-277 complete, P1, fix now; `[r214]` frontend (record 6200676782)                                                                                                                    |
| 215    | R2b: F-278 by a seeded test-only face vector; `[r215a]`, `[r215d]` (record 6200719567)                                                                                                            |
| 216    | the owner's session writes R2b round 2's record; UR-149 amended once (record 6200852082)                                                                                                          |
| 217    | ops-b claims `[r196c]` now; UR-52 waived while `[r157]` waits (record 6200901387)                                                                                                                 |
| 218    | package `[r218]`: CI checks inventory status against the golden run (record 6201875149)                                                                                                           |
| 219    | F-033 split; its summary-push clause is F-295, real tier, not gating (record 6203806645)                                                                                                          |
| 220    | the 7 expired flaky skips go; CI's suppression ratchet turns green (record 6205451631)                                                                                                            |
| 221    | frontend inverts F-048's search fixture on #7187, ahead of `[r196a]` (record 6205729827)                                                                                                          |
| 222    | F-059 split; its video and two-detection clauses become F-296, routed to O2.5 (record 6205769421)                                                                                                 |
| 223    | package `[r223]`: the developer tools' seed and clear refresh the caches (record 6205796977)                                                                                                      |
| 224    | heavy-a takes `[r212]`, `[r213]`, `[r214]` from frontend now, ahead of B2.3 (record 6205825842)                                                                                                   |
| 225    | the dispatcher stops a coordinator tick at 60 minutes, not 30 (record 6205915207)                                                                                                                 |
| 226    | heavy-a takes F-012 and F-064 from `[r196a]`; docs claims `[r215d]` now (record 6206280092)                                                                                                       |
| 227    | ops-b arms #7189; the seeded-only rows' route to works goes to R2b's last round (record 6215786871)                                                                                               |
| 228    | package `[r228]`: one cache key shape, before `[r223]` (record 6215814018)                                                                                                                        |
| 229    | the second session in frontend's sandbox ends; `fe3-f064-draft` is deleted (record 6215872590)                                                                                                    |
| 230    | no rows for docs' unrowed paths; three client-less endpoints go to R2b's last round (record 6215912535)                                                                                           |
| 231    | package `[r231]`: ruling 207 covers every model family the real tier fakes (record 6215981513)                                                                                                    |
| 232    | the dispatcher starts each tick's subagent without a name; stacking diagnosis runs (record 6216022003)                                                                                            |
| 233    | R2b last round: F-045 complete, P1, fix now, carried by `[r211f]` (record 6216193689)                                                                                                             |
| 234    | R2b last round: F-052 complete, P1, fix now, `[r234]` for heavy-a (record 6216216005)                                                                                                             |
| 235    | R2b last round: seeded-only rows reach works on `--real --seeded`, `[r235]` (record 6216273821)                                                                                                   |
| 236    | R2b last round: `/api/reid/search` retires; two endpoints become External rows (record 6216306194)                                                                                                |
| 237    | Phase 2 exits: F2.3 excepts the O2.5 rows; R2b's last round closed (record 6216370633)                                                                                                            |
| 238    | package `[r238]`: heavy-a flips F-057's read-back leg after `[r234]` (record 6216702824)                                                                                                          |
| 239    | coordinator loop `/loop 30m`; UR-162 raises past 90 minutes, `[r239]` for ops-b (record 6217014151)                                                                                               |
| 240    | package `[r240]`: two shards; superseded by `[r264]`, retired by ruling 266 (record 6217450751)                                                                                                   |
| 241    | heavy-a takes `B3.1` with `F3.1` ahead of `B2.3`; Phase 3 blocks gain `**PR:**` (record 6217824144)                                                                                               |
| 242    | package `[r242]`: plan_lint checks every roster row again; owner PR, ops-b reviews (record 6221764225)                                                                                            |
| 243    | package `[r243]`: prod.yml's engine-socket condition renders on every Compose, ops-a (record 6222454848)                                                                                          |
| 244    | package `[r244]`: the monitoring key gets no recommendation prose, backend (record 6222984876)                                                                                                    |
| 245    | UR-36/UR-38 cadence once `[r193]` lands; `[r239]`'s interval table (record 6223117374)                                                                                                            |
| 246    | one-off: §8's no-failing-path demotion only for ruling 207/`[r231]` families (record 6223337228)                                                                                                  |
| 247    | package `[r247]`: a host-side supervisor runs the coordinator's ticks, ops-b (record 6223821495)                                                                                                  |
| 248    | UR-183: a package PR writes its own `**PR:**` number; package `[r248]` (record 6223962176)                                                                                                        |
| 249    | UR-98: a plain `B3.1`/`F3.1` retirement is lane-tier (record 6224222541)                                                                                                                          |
| 250    | UR-89, UR-91: from round 2 only blocking findings change the head (record 6224354057)                                                                                                             |
| 251    | package `[r251]`: the inventory's §2 is computed, not stored; owner PR (record 6224408012)                                                                                                        |
| 252    | package `[r252]`: re-ID's ONNX→TensorRT plan-build root cause, ahead of B2.3 (record 6235589555)                                                                                                  |
| 253    | UR-181: re-anchoring a cite a merge or a file move shifted is not a row edit (record 6242299001)                                                                                                  |
| 254    | package B3.3: the fourth box per R2a row 27; four models leave by recorded upgrade (record 6244092557)                                                                                            |
| 255    | package B3.1/F3.1: one R2a row per PR, amending 241 item 1 (record 6244403809)                                                                                                                    |
| 256    | package O2.5, `[r195]`: O2.5 splits by venue, sandbox run then maui run (record 6250363327)                                                                                                       |
| 257    | package F3.2, O3.4: knip's exit 0 reads against F3.2's recorded baseline (record 6250472120)                                                                                                      |
| 258    | packages O3.6, B2.3: heavy-b in service again; heavy-a keeps B3.1/F3.1, B3.2 (record 6250529550)                                                                                                  |
| 259    | package `[r247]`: the supervisor's tick runs with the pane's launch flags (record 6253915725)                                                                                                     |
| 260    | packages O3.1, O3.2, O3.3: from ops-a's queue to heavy-b (record 6254983272)                                                                                                                      |
| 261    | one-off: #7246 re-pins the frontend coverage floors; UR-69 stands (record 6256508661)                                                                                                             |
| 262    | package `[r262]`: docs audits the Qwen-era merges' code on main; owner rules each item (record 6257468143)                                                                                        |
| 263    | one-off: #7258's merge stands; its auth-path test edits count as mechanical (record 6257521861)                                                                                                   |
| 264    | package `[r264]`: golden suite in shards on separate stacks; ops-a beside #7231 (record 6257854715)                                                                                               |
| 265    | UR-184: the hooks and three Collection Sanity checks run before each push (record 6266412276)                                                                                                     |
| 266    | one-off: `[r240]` retired, superseded by `[r264]` (record 6266823796)                                                                                                                             |
| 267    | packages `[r267a]`, `[r267b]`: audit batch 1's Q-001 and Q-004; lows later (record 6266846674)                                                                                                    |
| 268    | UR-102: `strict: true` stays; the coordinator updates one PR at a time (record 6270622374)                                                                                                        |
| 269    | UR-52 and package `[r269]`: a waiting PR's author may claim the next, at most two (record 6275028285)                                                                                             |
| 270    | package `[r270]`: the snapshot's merge legs read for strict mode, ops-b (record 6276943371)                                                                                                       |
| 271    | packages `[r271a]`, `[r271b]`, `[r271c]`: audit batch 2's fixes; lows later (record 6277412644)                                                                                                   |
| 272    | UR-102, package `[r272]`: the queue-update workflow and the queue line (records 6282551725, 6290019383)                                                                                           |
| 273    | package `[r273]`: one PR for every open Dependabot PR, heavy-b (record 6282749517)                                                                                                                |
| 274    | package `[r274]`: `up --no-build` after a prebuild only (records 6282871050, 6290084892)                                                                                                          |
| 275    | one-off: #7246's coverage floors at the lowest printed value; UR-69 stands (record 6290039971)                                                                                                    |
| 276    | one-off: `O2.5` on both venues; the operator re-probes with cgroups disabled (record 6290063282)                                                                                                  |
| 277    | packages `[r277a]`, `[r277b]`: audit batch 3's fixes; lows later (record 6291992942)                                                                                                              |
| 278    | UR-106's subset carry and package `[r278]`, ops-b (record 6293203635)                                                                                                                             |
| 279    | package `[r279]`: three flaky CI checks made deterministic, heavy-b (record 6293490330)                                                                                                           |
| 280    | `O2.5`: both runs from the owner's maui login; the sandbox venue closed (record 6293639903)                                                                                                       |
| 281    | UR-98, UR-99, UR-100, `roles/owner-partner.md`: delegated approval (record 6293911155)                                                                                                            |
| 282    | package `[r282]`: golden shards balanced by measured duration, ops-a (record 6294042743)                                                                                                          |
| 283    | UR-47 and `roles/lane.md` "Closing": bookkeeping rides the package PR (record 6294043011)                                                                                                         |
| 284    | `roles/coordinator.md` "Assigning a package": the weekly Dependabot combine (record 6294043265)                                                                                                   |
| 285    | package `[r285]`; F-182 under ruling 182 (records 6300916398, 6301639831, 6302995876)                                                                                                             |
| 286    | one-off, delegated: red-`main` fixes for `certifi` and Pillow (records 6301229929, 6302966882)                                                                                                    |
| 287    | `O2.5` item 2's pass and venue fixes; package `[r287b]` (record 6302941592)                                                                                                                       |
| 288    | one-off, delegated: `[r272]`'s red-`main` read, #7314, #7311's F-254 (record 6303093964)                                                                                                          |
| 289    | one-off, delegated: Phase 3 rebalance; O3.4, O3.5 to heavy-b; B3.3's box 4 (record 6303414416)                                                                                                    |
| 290    | UR-47 (283 amended) and package `[r290]`: the coordinator proposes balance moves (record 6303479997)                                                                                              |
| 291    | UR-185 and package `[r291]`: the gate audits only what a change adds (record 6304527940)                                                                                                          |
| 292    | one-off: ops-a claims `O2.5`'s venue fixes while #7310 is open, a UR-52 exception (record 6304623987)                                                                                             |
| 293    | one-off, delegated: the `certifi` red-`main` route and its correction (records 6307149057, 6307222499)                                                                                            |
| 294    | UR-185 and package `[r294]`: Trivy's scans fail a change only on what it adds (record 6307203645)                                                                                                 |
| 295    | one-off: pip's bundled `certifi` exempted; package `[r295]`: pip leaves the image (record 6307239846)                                                                                             |
| 296    | package `[r262]`: rows only for bugs and medium+ from batch 7; a cite checker scoped (record 6307432184)                                                                                          |
| 297    | package `[r282]` closed on its measured gain; package `[r297]`: the shard fixed cost (record 6315692389)                                                                                          |
| 298    | one-off: heavy-b claims `O3.7` from ops-b's queue, ahead of `O3.2` and `B2.3` (record 6321095724)                                                                                                 |
| 299    | package `[r299]`: the E2E setup's tour keys; `[r262]` batches 4–6 ruled (record 6321779954)                                                                                                       |
| 300    | package `W3.1`: to heavy-a, one PR per lane as each lane's Phase 3 is done (record 6322983128)                                                                                                    |
| 301    | package Monitoring (`F4.*`): the zone panels drop; F-117 stays complete (record 6323705324)                                                                                                       |
| 302    | UR-86 (OD-39): Triton stays; no measure-first package (record 6323705569)                                                                                                                         |
| 303    | package `[r303]`: RF-DETR tested against YOLO26-M (record 6323705837)                                                                                                                             |
| 304    | UR-186: a scope canary moves down only with an authorized retirement (record 6323706092)                                                                                                          |
| 305    | package `[r305]`: three weak tests and 15 prose rows of `[r262]` batches 4–6 (record 6323706301)                                                                                                  |
| 306    | UR-85; packages `[r306a]`, `[r306b]`; `[r252]`'s proving run now (record 6323748868)                                                                                                              |
| 307    | UR-86; packages `[r307a]`–`[r307d]`: small models in Triton, fast-alpr out (record 6323846997)                                                                                                    |
| 308    | P1 packages `B4.1`–`B4.6`, `F4.1`–`F4.4`, `[r308a]`, `[r308b]`, spread (record 6326364266)                                                                                                        |
| 309    | package `[r309]`: real stills for `[r303]`, which goes to heavy-b (record 6327202214)                                                                                                             |
| 310    | #7336 (F-246's outbound webhooks) fixed inside `B4.2` (record 6327324775)                                                                                                                         |
| 311    | arming: `B4.7`, `B4.8`, `F4.5`, `[r311a]`, `[r311b]`; sensitivity leaves MQTT (record 6328311780)                                                                                                 |
| 312    | UR-187; packages `[r312a]`, `[r312b]`; amended: #7343 merges on its smoke (records 6329693164, 6331303299)                                                                                        |
| 313    | package `[r313]`: the npm audit checker fails closed; corrected (records 6332025973, 6332789646)                                                                                                  |
| 314    | packages `[r314a]`, `[r314b]`: UR-187's two follow-ups to heavy-b (record 6342032031)                                                                                                             |
| 315    | `O2.5` item 2 runs again with its peak sampled, at item 1's pin (record 6345740728)                                                                                                               |
| 316    | docs closes `[r262]`; `W3.2` and `W3.3` first on its queue (record 6346660761)                                                                                                                    |
| 317    | P2 designs (scene changes, exports, status); `B4.9`–`B4.11`, `F4.6`–`F4.8` (record 6347331324)                                                                                                    |
| 318    | owner-partner: red `main` (real-sleep gate) to backend; fixed by #7368 (record 6349548111)                                                                                                        |
| 319    | OD-36 keep, admin-only: every `/api/debug/*` route behind the admin session (record 6349900914)                                                                                                   |
| 320    | `[r320]`: Q-192 to heavy-a; moot, its spec left `main` in #7311 (records 6354896020, 6355421498)                                                                                                  |
| 321    | modes and debug tools designs; `F4.9`, `B4.12`, `F4.10`; `F4.8` owner tier (record 6355356496)                                                                                                    |
| 322    | owner-partner: red `main` (PG 18 client vs PG 16) to ops-a; fixed by #7379 (record 6356617873)                                                                                                    |
| 323    | `O2.5` is item 2 alone; item 1 and its VLM relay dropped; `[r323a]`, `[r323b]` (record 6356971214)                                                                                                |
| 324    | owner-partner: the nightly's PG client drift to ops-a; fixed by #7389 (record 6362943411)                                                                                                         |
| 325    | Q-193: `O2.4` done on `[r312a]`'s Run 2; `[r325a]` (record 6364638047)                                                                                                                            |
| 326    | one-off: the operator stages B4.4's store in its workspace for the owner (UR-142; record 6372335619)                                                                                              |
| 327    | no revert of #7370; frontend reviews the post-approval delta only (record 6377661937)                                                                                                             |
| 328    | O3.2: two compose bases stay + a pin test; box 3 dropped, the seven container_names stay (record 6378106167)                                                                                      |
| 329    | heavy-a takes r306a, r306b, r307b from backend's queue, in that order (record 6378113072)                                                                                                         |
| 330    | autovlm: docs/auto-vlm-research/ + docs/superpowers/2026-10-23-autovlm/ are a design record, docs skips their drift audits but not their broken links (record 6378138172)                         |
| 331    | [r297] (#7356) unparked; ops-a resumes it after #7408 (record 6378198868)                                                                                                                         |
| 332    | owner-partner: main's red on the stale inventory cites (F-070/F-167/F-168) to frontend, its own red-main PR (record 6380955597)                                                                   |
| 333    | B2.3 answered: 150-200 neutrally pre-grouped crops; challengers CLIP-ReID ViT-B/16 + NVIDIA ReID-Transformer, PersonViT out; SHA-256-pinned no-login install rule (record 6383476260)             |
| 334    | [r334] (ops-a, after [r297]): the installer fetches both default model pairs itself, ruling 333's rule applied to what ships today; docs updates the install pages under UR-9 (record 6383489716) |

## Owner records

| record                          | became                                                                                                                                                                                                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 6074248201                      | UR-52                                                                                                                                                                                                                                      |
| 6083435595                      | UR-52                                                                                                                                                                                                                                      |
| 6103795550                      | UR-160                                                                                                                                                                                                                                     |
| 6109277356                      | superseded by 138 (UR-144)                                                                                                                                                                                                                 |
| 6114826605                      | UR-43                                                                                                                                                                                                                                      |
| 6116458014                      | UR-138                                                                                                                                                                                                                                     |
| 6116476010                      | package B1.1 tail measurement                                                                                                                                                                                                              |
| 6123811294                      | superseded by 143 (UR-176)                                                                                                                                                                                                                 |
| 6126535946                      | one-off (#7029 approved head); amended by 6128195816                                                                                                                                                                                       |
| 6128195816                      | UR-106, UR-29                                                                                                                                                                                                                              |
| 6128714278                      | PROGRAMME PAUSE record; supersedes ruling 146's ledger by this rewrite                                                                                                                                                                     |
| 6135991251                      | UR-102 (merge without update-branch when safe; superseded by ruling 268, strict stays on)                                                                                                                                                  |
| 6146755754                      | `roles/coordinator.md` (each tick runs in a fresh subagent)                                                                                                                                                                                |
| 6148551105                      | `roles/coordinator.md` (tick reads from a cursor; dispatcher only dispatches)                                                                                                                                                              |
| owner design session 2026-10-12 | ruling 147. Pass 1: UR-39, UR-40, UR-41, UR-106, UR-29, UR-162, UR-163; corrected lines in UR-45, UR-66, UR-10, UR-121, UR-144. Pass 2: UR-24, UR-52, UR-59, UR-63, UR-25, UR-166, UR-168, UR-98, UR-125, UR-126, UR-151; package `[r147]` |
| 6135935339                      | UR-166 (status comment shows current state only, about 4,000 characters)                                                                                                                                                                   |

## Merged rules

Numbers removed from `rules.md` in pass 2 because a lower-numbered rule said the same thing. Each
number stays retired; it is never reused.

| rule   | became                                                                       |
| ------ | ---------------------------------------------------------------------------- |
| UR-49  | merged into UR-22                                                            |
| UR-57  | merged into UR-52                                                            |
| UR-71  | merged into UR-10 (contract rule 1)                                          |
| UR-72  | merged into UR-10 (contract rule 2)                                          |
| UR-73  | merged into UR-10 (contract rule 3)                                          |
| UR-74  | merged into UR-10 (contract rule 4)                                          |
| UR-75  | merged into UR-10 (contract rule 5)                                          |
| UR-80  | merged into UR-9                                                             |
| UR-90  | merged into UR-32                                                            |
| UR-97  | merged into UR-23                                                            |
| UR-109 | merged into UR-94                                                            |
| UR-110 | merged into UR-29                                                            |
| UR-117 | merged into UR-34                                                            |
| UR-118 | merged into UR-34                                                            |
| UR-120 | merged into UR-37                                                            |
| UR-139 | merged into UR-30                                                            |
| UR-145 | merged into UR-46                                                            |
| UR-150 | merged into UR-10                                                            |
| UR-158 | merged into UR-38                                                            |
| UR-159 | merged into UR-38                                                            |
| UR-161 | merged into UR-38                                                            |
| UR-164 | merged into UR-36                                                            |
| UR-165 | merged into UR-25                                                            |
| UR-167 | merged into UR-25                                                            |
| UR-169 | merged into UR-28                                                            |
| UR-171 | merged into UR-26                                                            |
| UR-172 | merged into UR-30                                                            |
| UR-50  | merged into UR-24 (pass 2 Q3, Q4)                                            |
| UR-58  | merged into UR-52 (pass 2 Q4)                                                |
| UR-60  | merged into UR-59 (pass 2 Q4)                                                |
| UR-61  | merged into UR-59 (pass 2 Q4)                                                |
| UR-62  | merged into UR-52 (pass 2 Q4)                                                |
| UR-93  | merged into UR-91 (pass 2 Q7)                                                |
| UR-103 | dropped by the owner: no wait for `main`'s own run after a merge (pass 2 Q7) |
| UR-105 | merged into UR-104 (pass 2 Q7)                                               |
| UR-132 | merged into UR-15 (pass 2 Q3)                                                |

## Retired rules

Rules carried out or lapsed, removed from `rules.md` in pass 2 (owner design session 2026-10-12).
Their numbers stay reserved, and code comments that cite them still resolve here. Reversing one is a
ruling (UR-44; README "Considered and rejected" guards UR-8, UR-11, UR-17 and UR-19).

| rule  | original text                                                                                                                              | state                                                                       |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| UR-8  | Targeted pause: VLM prompt and threshold selection waits for replay parity; synthbench continues; all other agents move to this programme. | lapsed: lifted with `B1.2` (#6924)                                          |
| UR-11 | One plan per lane; seams are designed when reached.                                                                                        | carried out: the plan files are per lane; README states the seams principle |
| UR-17 | The ghcr install path is retired; local build plus the prod compose file is the one supported install.                                     | carried out: `O1.2` (#6907)                                                 |
| UR-19 | `archive/` and `docs/archive/` are deleted; the two `setup.py` test files return to the live suite; git history is not rewritten.          | carried out: `O1.5`                                                         |
| UR-20 | A fourth lane, docs, owns the documentation and makes it true: Phase 1 stops active misdirection, Phase 3 rewrites after the deletions.    | carried out: the docs lane exists (README "Lanes and ownership")            |

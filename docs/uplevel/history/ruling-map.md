# Ruling map

One row per owner ruling 1-146 on #6854, and one per owner record that set a rule, showing what each
became: the [`rules.md`](../rules.md) rule (`UR-n`), `one-off` (one PR, row, fold or order, now
history), `package <id>` (binds only while that package is open; its text is in `packages/` or
`packages-done.md`), or `superseded by <n>`. A ruling with several parts lists each. Rulings 118 and
119 are coordinator decisions C-118 and C-119. Pass 2 merged rules that said the same thing into the
lower number; the ruling and record rows name the rule that now holds each one, and "Merged rules"
lists every number that left `rules.md`.

## Rulings

| ruling | became                                                                                                      |
| ------ | ----------------------------------------------------------------------------------------------------------- |
| 1      | UR-33 (monitoring denied when exposed); package O1.11 (done, `awaiting real tier`)                          |
| 2      | UR-30                                                                                                       |
| 3      | one-off (O1.9 deletes `rollback.yml`; #6875)                                                                |
| 4      | one-off (#6875); its derived rule is UR-99                                                                  |
| 5      | one-off (#6861 approved)                                                                                    |
| 6      | one-off (#6864 approved)                                                                                    |
| 7      | superseded by 40 (UR-47)                                                                                    |
| 8      | one-off (F1.1 questions to R2); its derived rule is UR-99                                                   |
| 9      | UR-119 (one required check); rest one-off (#6870)                                                           |
| 10     | one-off (`VlmRequestErrors`, waits with B1.1); its derived rule is UR-99                                    |
| 11     | one-off (#6884 not owner-tier); its derived rule is UR-99                                                   |
| 12     | UR-37 (hooks in the gate); package O1.12 (done)                                                             |
| 13     | one-off (#6867 approved)                                                                                    |
| 14     | one-off (#6898 approved)                                                                                    |
| 15     | UR-108 (owner PRs auto-merge and queue); queue order one-off                                                |
| 16     | one-off (#6904 approved)                                                                                    |
| 17     | UR-29, UR-166 (as amended by the 2026-10-12 merge-comment decision)                                         |
| 18     | superseded by 40 (UR-47); `owner` label removal one-off                                                     |
| 19     | UR-102, UR-166                                                                                              |
| 20     | one-off (#6908 approved)                                                                                    |
| 21     | UR-104 (oldest ready first); queue order one-off                                                            |
| 22     | UR-133, UR-140; B1.4 routing one-off                                                                        |
| 23     | one-off (B1.1 owner run deferred)                                                                           |
| 24     | UR-123; #6913 slot one-off                                                                                  |
| 25     | one-off (ruling 13 covers #6867)                                                                            |
| 26     | UR-105 (named place), UR-106 (ready time, as amended 2026-10-12)                                            |
| 27     | UR-102                                                                                                      |
| 28     | one-off (heavy queue reordered; executed)                                                                   |
| 29     | UR-25; batch 8 catch-up one-off                                                                             |
| 30     | one-off (#6924 approved; prompt programme resumed)                                                          |
| 31     | one-off (#6921 approved)                                                                                    |
| 32     | superseded by 40 (UR-47)                                                                                    |
| 33     | one-off (#6920 approved); package W3.2 (caps baseline, `synthbench/commands` exception)                     |
| 34     | one-off (#6922 approved)                                                                                    |
| 35     | package B-1 follow-up (done, #6927)                                                                         |
| 36     | one-off (alloy ports in #6925)                                                                              |
| 37     | one-off (#6925 approved)                                                                                    |
| 38     | one-off (#6923 approved)                                                                                    |
| 39     | UR-53 (item M), UR-93 (item G), UR-37 (item E); small packages C, D, I, J, L-i, L-ii one-off                |
| 40     | UR-47, UR-92, UR-98                                                                                         |
| 41     | UR-66; W3.1 parking one-off                                                                                 |
| 42     | superseded by 49                                                                                            |
| 43     | UR-64; package backend entry-point trace (done, #6935)                                                      |
| 44     | UR-179; package no-API-key-in-browser (done, #6936)                                                         |
| 45     | UR-95; #6937 approval one-off                                                                               |
| 46     | one-off (#6909 approved)                                                                                    |
| 47     | package R47 (done, #6943)                                                                                   |
| 48     | UR-96; #6929/#6930 conditions one-off                                                                       |
| 49     | UR-142 (no copying stores); ruling 42 reversal one-off                                                      |
| 50     | UR-59; F2.2 move one-off                                                                                    |
| 51     | one-off (F2.2 Files line)                                                                                   |
| 52     | one-off (banner spec red-main fix)                                                                          |
| 53     | UR-60; assignments one-off                                                                                  |
| 54     | UR-67, UR-166; W3.3 parking one-off                                                                         |
| 55     | UR-106 (approval across a merge-only head); R55 package one-off (done, #6950)                               |
| 56     | UR-10 (contract rule 2), UR-156                                                                             |
| 57     | UR-142; B1.2 count source one-off                                                                           |
| 58     | one-off (#6945 widened)                                                                                     |
| 59     | UR-106 (approval across update-branch), UR-152 (half-built at the UI end); #6941 approval one-off           |
| 60     | package R60 API-key scopes (done, #6959)                                                                    |
| 61     | one-off (#6947 approved; `braces` exemption); package R61 (done, #6960)                                     |
| 62     | one-off (OD-36-38 to the R2 sheet; small findings routed)                                                   |
| 63     | UR-103 (wait for `main`'s run after a merge); #6955 one-off                                                 |
| 64     | UR-38, UR-162, UR-163                                                                                       |
| 65     | one-off (#6957 approved; heartbeats issue created)                                                          |
| 66     | UR-136                                                                                                      |
| 67     | one-off (OD-39 added to the R2 sheet)                                                                       |
| 68     | package B2.2 (done, parked)                                                                                 |
| 69     | one-off (#6961 approved)                                                                                    |
| 70     | package W3.3 (repo slug exemption)                                                                          |
| 71     | package r71 (done, #6968)                                                                                   |
| 72     | package `[r72]` coverage-gate timeout wrapper (done, #6971)                                                 |
| 73     | package O2.3b (done, #6973)                                                                                 |
| 74     | superseded by 93 (UR-125)                                                                                   |
| 75     | one-off (B1.6 real tier: branch 1)                                                                          |
| 76     | package `[r76]` npm-audit alias fix (done, #6966)                                                           |
| 77     | UR-38; owner PR #6965 one-off                                                                               |
| 78     | one-off (#6967 approved)                                                                                    |
| 79     | one-off (#6959 approved)                                                                                    |
| 80     | one-off (#6969 approved; ORCHESTRATOR-01)                                                                   |
| 81     | UR-162, UR-166, UR-168                                                                                      |
| 82     | UR-54, UR-63                                                                                                |
| 83     | UR-104, UR-111, UR-112, UR-25                                                                               |
| 84     | UR-101                                                                                                      |
| 85     | UR-38, UR-173                                                                                               |
| 86     | UR-66, UR-67, UR-148                                                                                        |
| 87     | UR-83 (inventory hot-file row); package F2.3 (in progress)                                                  |
| 88     | UR-160, UR-174                                                                                              |
| 89     | UR-86 (OD-39), UR-87 (OD-33); R2a record one-off (#6980); package Phase 4 priority tiers                    |
| 90     | one-off (#6970 approved; heavy agents pause)                                                                |
| 91     | one-off (#6980 approved)                                                                                    |
| 92     | one-off (F2.2 follow-up to frontend)                                                                        |
| 93     | UR-125; package real-sleep gate (done, #6972)                                                               |
| 94     | package `[r94]` `setup.py` re-runs and `--convert-monitoring-key` (open; `packages/backend.md`)             |
| 95     | package `[r95]` monitoring-key gaps S1, S4 (open; `packages/backend.md`)                                    |
| 96     | item 8: package dead CI failure guards (done, #6993); item 11: package `[r96i11]` (open; `packages/ops.md`) |
| 97     | UR-56 (F2.3 claim PR), UR-107 (never combine queued PRs); package draft-skip workflows (done, #6989)        |
| 98     | superseded by 101                                                                                           |
| 99     | one-off (ops-b work order)                                                                                  |
| 100    | package G2 nightly moves (done, #6992); G3 part superseded by 101                                           |
| 101    | UR-103, UR-105; #6994/#6997 one-off                                                                         |
| 102    | package golden step `npm ci` (done); superseded by 143                                                      |
| 103    | package F2.3 (row lifecycle)                                                                                |
| 104    | package F2.3 (batch file rule)                                                                              |
| 105    | package feature check in `CI Gate` (done, #7004)                                                            |
| 106    | one-off (B2.2 parked)                                                                                       |
| 107    | UR-85; packages O2.4, B2.3                                                                                  |
| 108    | one-off (F-017, F-020 demoted); its derived rule is UR-99                                                   |
| 109    | UR-116; package `[r109]` (done, #7003)                                                                      |
| 110    | superseded by 112                                                                                           |
| 111    | package F2.3 (`backend/tests/golden/__init__.py`)                                                           |
| 112    | UR-175                                                                                                      |
| 113    | UR-115; package `[r109b]` (done, #7006)                                                                     |
| 114    | UR-128; package `[r114]` (done, #7014); interim flip rule one-off                                           |
| 115    | package OB.4 (trigger)                                                                                      |
| 116    | package `[r116]` (done, #7012); superseded by 143 (UR-131 keeps its firewall clause)                        |
| 117    | UR-10 (contract rule 5)                                                                                     |
| 118    | coordinator decision C-118 (not an owner ruling); half kept by 120                                          |
| 119    | coordinator decision C-119 (not an owner ruling); stands per 120                                            |
| 120    | UR-45, UR-48, UR-151; C-118/C-119 disposition one-off                                                       |
| 121    | UR-81                                                                                                       |
| 122    | UR-125, UR-126; package `[r122]` (open, #7027; `packages/backend.md`)                                       |
| 123    | UR-128; spec fix one-off                                                                                    |
| 124    | one-off (R2 sheet face-events row)                                                                          |
| 125    | UR-114, UR-128; quarantine of F-022, F-007, F-235 one-off                                                   |
| 126    | UR-48, UR-129                                                                                               |
| 127    | UR-148, UR-10, UR-153                                                                                       |
| 128    | package Phase 4 Monitoring page                                                                             |
| 129    | package `[r129]` (open, #7031; `packages/backend.md`)                                                       |
| 130    | packages `[r130b]` (open; `packages/backend.md`) and `[r130f]` (open; `packages/frontend.md`)               |
| 131    | package Phase 4 Trash delete action                                                                         |
| 132    | package Phase 3 rate-limit countdown retirement                                                             |
| 133    | package Phase 3 PWA install prompt retirement                                                               |
| 134    | package Phase 3 batch-statistics history views retirement                                                   |
| 135    | UR-66 (R2b-round Phase 3 start), UR-149; round 1 record #7030 (open); round 1 tiers one-off                 |
| 136    | UR-78; #7026 fold one-off                                                                                   |
| 137    | UR-121; #7022/#7023/#7025 one-off                                                                           |
| 138    | UR-144                                                                                                      |
| 139    | package R2a alert-rules (schedule end minute)                                                               |
| 140    | UR-124; package W3.3 (Done-when gains the citation gate)                                                    |
| 141    | one-off (O3.8 target met; `timeout(30)`)                                                                    |
| 142    | UR-130; verdict-spread check one-off                                                                        |
| 143    | UR-131, UR-176; package `[r143]` (open, #7034 draft; `packages/ops.md`)                                     |
| 144    | package O2.5 (not started; `packages/ops.md`); UR-10 (contract rule 5: does not gate Phase 2's exit)        |
| 145    | UR-94, UR-29, UR-113, UR-122; freeze lift one-off                                                           |
| 146    | UR-39, UR-42, UR-155; the `rules.md` ledger itself superseded by the plan rewrite (record 6128714278)       |

## Owner records

| record                          | became                                                                                                     |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 6074248201                      | UR-62                                                                                                      |
| 6083435595                      | UR-62                                                                                                      |
| 6103795550                      | UR-160                                                                                                     |
| 6109277356                      | superseded by 138 (UR-144)                                                                                 |
| 6114826605                      | UR-43                                                                                                      |
| 6116458014                      | UR-138                                                                                                     |
| 6116476010                      | package B1.1 tail measurement                                                                              |
| 6123811294                      | superseded by 143 (UR-176)                                                                                 |
| 6126535946                      | one-off (#7029 approved head); amended by 6128195816                                                       |
| 6128195816                      | UR-106, UR-29                                                                                              |
| 6128714278                      | PROGRAMME PAUSE record; supersedes ruling 146's ledger by this rewrite                                     |
| owner design session 2026-10-12 | UR-39, UR-40, UR-41, UR-106, UR-29, UR-162, UR-163; corrected lines in UR-45, UR-66, UR-10, UR-121, UR-144 |

## Merged rules

Numbers removed from `rules.md` in pass 2 because a lower-numbered rule said the same thing. Each
number stays retired; it is never reused.

| rule   | became                              |
| ------ | ----------------------------------- |
| UR-49  | merged into UR-22                   |
| UR-57  | merged into UR-52                   |
| UR-71  | merged into UR-10 (contract rule 1) |
| UR-72  | merged into UR-10 (contract rule 2) |
| UR-73  | merged into UR-10 (contract rule 3) |
| UR-74  | merged into UR-10 (contract rule 4) |
| UR-75  | merged into UR-10 (contract rule 5) |
| UR-80  | merged into UR-9                    |
| UR-90  | merged into UR-32                   |
| UR-97  | merged into UR-23                   |
| UR-109 | merged into UR-94                   |
| UR-110 | merged into UR-29                   |
| UR-117 | merged into UR-34                   |
| UR-118 | merged into UR-34                   |
| UR-120 | merged into UR-37                   |
| UR-139 | merged into UR-30                   |
| UR-145 | merged into UR-46                   |
| UR-150 | merged into UR-10                   |
| UR-158 | merged into UR-38                   |
| UR-159 | merged into UR-38                   |
| UR-161 | merged into UR-38                   |
| UR-164 | merged into UR-36                   |
| UR-165 | merged into UR-25                   |
| UR-167 | merged into UR-25                   |
| UR-169 | merged into UR-28                   |
| UR-171 | merged into UR-26                   |
| UR-172 | merged into UR-30                   |

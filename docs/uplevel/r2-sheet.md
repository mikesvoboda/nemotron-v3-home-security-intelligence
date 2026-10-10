# R2 Ruling Sheet — session date TBD by the owner

> Created early by `W2.2` (docs lane), before `F2.2` runs. The template
> (`templates/r2-sheet.md`) says `F2.2` copies it here and fills it; `W2.2`'s Done-when needs its
> three rows committed before the owner's ruling session, so this file starts with only the docs
> rows (§2b) and nothing else. **`F2.2`: fill §1, §2 and §3 around §2b — do not rewrite or
> renumber this section.** The §2b OD numbers (`OD-33`…`OD-35`) are assigned; register rows run to
> `OD-32` today, so continue from `OD-36` if new decisions surface.
>
> Every row is written so it can be ruled from the row alone, without opening code. Facts were first
> measured at `1d847a6a` (2026-10-08, 23:48 -0400 — the header said 2026-10-09, which is the calendar
> day the sheet was written, not the commit's date; corrected in the third round) and **re-measured at
> every revision of this branch since** (the first being `10ab08e8`) by the commands named in each row.
> Every revision that touched this file differs from the last only in this file, with three exceptions:
> the merge `10ab08e8`, which brings in `origin/main` (39 paths) and does not touch this file at all
> (its sheet blob is byte-identical to the draft's, so at the merge the sheet's _text_ still carried
> the draft numbers); the row-flip commit `cdd0ca95`, which touches only README's status table; and
> the merge `2a558bdb`, which is the first revision that both brings in `origin/main` (22 paths) _and_
> moves numbers this file prints — the fifth-round corrections below are what that move forced —
> so a number printed here is checkable at any of them (the merge's tree was checked for the census
> and ERR legs in the fourth round; every moved number was re-measured at the fifth round's head) —
> including the ERR count's two legs,
> which are the one pair measured in two different trees (the `1d847a6a` leg, 216 ERR / 169 OK, re-run
> in a detached worktree at that commit; this branch's leg, 222 / 163, at head — not remembered; the
> third round re-ran every two-commit pair in a detached worktree at each leg's own baseline — ERRs,
> register lines, the 24-citer split — none carried over). Forty-three claims did not survive that
> re-measurement, a fresh-context review of the sheet, the re-measurement at the second merge head, or a
> fresh-context verification pass on the fifth round's own wording — the count now runs through four review
> rounds and a merge-head re-measurement, the third, fourth and sixth from a separate agent, and it grew each time because those rounds'
> findings, re-measured here, confirmed claims earlier rounds had asserted without measuring; the fifth
> round's thirteen came not from a reviewer but from `origin/main` moving under the branch again, found
> by this lane re-measuring at the new head before pushing; the sixth round's two sit in that round's own
> sentences — and
> the bullets say where each came
> from:
> thirteen were wrong in the draft as first committed (one of them this header's own date label), fifteen
> were true at the measured commit and went
> stale when `origin/main` merged (two at the first merge, thirteen at the second — first bullet), and fifteen were introduced _by the corrections_ —
> three found by the second round, six by the third, four by the fourth, two by the sixth (last bullet). Every one is corrected in place
> and the row names the draft's wording at the correction, so an owner reading one row sees what changed
> rather than a silently tidied fact — the corrections sit inside the Facts prose, not at the row end:
>
> - **moved with a merge** (15 — two at `10ab08e8`, thirteen at `2a558bdb`, counted as stale printed
>   facts, one per fact wherever the sheet prints it twice): `docs/plans`' level-1 ERR 216 → **222**
>   (OD-33) — which arrived as evidence, not just a number, because the tree itself had zero changed
>   paths; and the register's line count, which has moved twice, 8,485 → 8,518 → **8,565**, with its
>   staleness delta 373 → **420** (the plan text's 8,145 did not move) (OD-34). The thirteen at the
>   second merge: the four page-count facts of OD-33's nav row and their echo inside this header —
>   600 → **601** pages, 599 → **600** `index.html`, home 148 → **149** nav links, busiest 316 →
>   **317**, and the header's own "148–316 of 600" → **149–317 of 601** is the same four facts at a
>   second location, counted once — all four from one cause: `mkdocs.yml` gained exactly one nav entry
>   (`developer/agents-md-standard.md`) and `awesome-pages` rides every nav entry on every page's
>   sidebar; the invariant the row argues — no page links into the trees — survives it, verified over
>   all 601. Seven line-number cites: the `ci.yml` citation-job cite :229 → **:230** — a re-anchor, not
>   same-line drift (the draft's :229 pointed inside the step's run block even at the draft commit;
>   OD-33's row carries the decomposition); `docs/uplevel/40-docs.md:176` →
>   **:156** (W2.1 rewrote that file); `README.md:243` → **:246** (same rewrite); the validator's `≥2`
>   test `agents_md_validator.py:619` → **:702** (W2.1 grew the validator +186/−6); and inside the
>   register itself, `## Intake log` 7096 → **7143**, OD-24's log line L7150 → **L7197**, "§5 … at
>   708" → **744** — those three moved by prefix-sum arithmetic, not page counts: main's B1.2 hunks
>   added +36 lines at 708 and +11 at 3232, so everything below 708 held (the `Ruled 2026` hits at
>   578–603 did not move) while §5 moved +36 and the log moved +47. Two of these are the lesson of the
>   round: `docs-scan-findings.md:311` was re-checked and _did not_ move (blob `e4597283` identical at
>   both commits) — a line cite is only as stable as the merge above it, and you cannot tell which
>   without opening both. The second merge moved no other number: the census (11/12/1 + 44/36/32,
>   136 mentions / 104 citers), the tree counts (93/37/26), the ERR leg re-run at this head (385
>   checked / 163 OK / **222** ERR — the number the row prints is now verified here, not inherited),
>   the 154 published pages (91+37+26 in the fresh build), the register's 32 rows and 5-markup
>   findings, and OD-35's family (26 files / **8,314** lines re-summed at this head from
>   `git cat-file`, not remembered) all re-measured unchanged — disclosed because a held claim
>   verified is a different thing from a claim never re-checked.
> - **wrong at every commit** (11): this header's own "(2026-10-09)" date label for `1d847a6a`, which
>   commits 2026-10-08 23:48 -0400; OD-33's "~91 citing files" (an arithmetic slip) and its per-tree
>   columns (45/35/31, which match no instrument — the first replacement kept them verbatim and was
>   wrong too, last bullet); its "0 nav entries" (true of the nav, false of
>   publication); OD-34's "7 bolded
>   rulings" and "5 more only in the intake log" (both miscounts of the same 12 decisions — and the
>   miscount mechanism is now the row's argument for the column it asks for); OD-35's quoted provenance
>   header, "~200–250 lines each", "one per architecture doc", "they cross-cite each other" (one-way),
>   and "2 external referrers to re-aim" (both are prose mentions, not citations).
> - **a ruling this sheet had not read** (1, and the most serious): OD-35 recommended moving the family
>   into `docs/archive/`, which **UR-19** has already ruled deleted and **`O1.5`** executes — and README's
>   "Considered and rejected" table rejects that exact move. OD-35's options and recommendation are
>   rewritten around that; nothing in the draft mentioned UR-19.
> - **a command that ran but measured nothing** (1): OD-35's transcribed `git ls-files` passed both stems
>   inside one quoted argument, which matches no path and returns **0** — the printed 26 came from a
>   different invocation than the one the row showed a reviewer. Fixed to two pathspecs.
> - **first corrections that were themselves wrong** (15 — three found by the second review round,
>   six by the third, four by the fourth, two by the sixth, each named where it sits): (a) OD-33's — the first re-measurement
>   replaced "~91 citing files" with "97 distinct across 135 mentions", and re-running its own printed
>   commands shows its columns (45/35/31) reproduce under no instrument (the nearest prints 44/36/31,
>   ±1 twice in opposite directions inside the 111 the sum carried), and its 97 silently mixed two
>   scopes — AGENTS citers counted repo-wide, docs citers counted only inside the grep's search
>   directories. One whole-repo rule now, transcribed as one command per column: 11/12/1 + 44/36/32 =
>   **136** mentions across **104** distinct citers; the re-aim cost the recommendation quotes moves
>   97 → 104. (b) OD-35's — the same pass printed "median 315" for the family's sizes, which is no
>   median under any convention: the probe averaged the two middle files (313, 318 → 315.5) and `int()`
>   truncated it. OD-35's row now prints the straddle. (c) OD-33's nav note — the same pass printed
>   "296 nav links on a page", a single-page string count that is neither rerunnable nor stable across
>   pages (`md-nav__link` rides `<label>`s as well as anchors; real anchor counts run 149–317 of 601
>   built pages at the fifth round's head — the 148–316-of-600 form was the measurement at the revision
>   before it, and the merge moved it). The row now
>   prints the invariant the argument needs: none of the 601 built pages carries a nav link into the
>   three trees. (d)–(i) are the third round's six, each confirmed here
>   by re-measurement before being fixed: OD-33's citation passage said the 24 out-of-scope citers
>   include "the 6 doc files **under the 4 paths** the draft's grep listed" — the inverse of what the
>   enumeration shows (all 6 sit _outside_ those paths; they are now named). OD-34 said "2 of the 11
>   mention the ruling in a second cell" (strict count **5**; the correction named only OD-1's Source
>   and OD-30's Unblocks), and "3 rows carry the Intake-log pointer from their options cell" (only
>   OD-1's is in the options cell; OD-31's and OD-32's are in Source). OD-35 said api-reference
>   "carries both of the last two" date fields (it carries `**Revalidation Date:**` +
>   `**Original Validation Date:**`; `**Re-Validation Date:**` is observability's alone), that "the
>   other 6 … carry `**Hub:**` instead" (5 files name no area; exactly 2 carry `**Hub:**`), and — my
>   own second-round re-measurement, same class — that the families "name the same 10 areas
>   (identical sets)" (they are one apart: revalidation also names `data-model`). The first two of
>   these six came from prose a correction wrote about _counts_ without re-reading the underlying
>   cells/files; the OD-35 area claim came from trusting the earlier residue list after the counts
>   next to it were fixed. (j)–(m) are the fourth round's four, same reviewer, each confirmed by
>   re-measurement: OD-35's _recommendation_ still read "~10 architecture areas covered twice over"
>   after the Facts above moved to ~11/almost — the correction never propagated to the second place
>   the number lived (a phrase the correction round itself introduced). OD-33's census-correction said
>   the first correction's census "printed 44 / 36 / 31" — it printed the draft's 45 / 35 / 31
>   verbatim; 44 / 36 / 31 is what re-running _its instrument_ yields (both verified at its own commit
>   and at head) — the sentence asserted the correction both kept and replaced the columns. The
>   header's file-hygiene claim named one exception but the merge `10ab08e8` is a second (39 paths,
>   sheet untouched — now both exceptions are named). And OD-34's "`Ruled 2026` finds 5 and misses 6"
>   had "those 12" as its object while 6 is the count against the 11 table rows — now "misses 6 of the
>   11 table rows (7 of the full 12)". (n)–(o) are the sixth round's two, same reviewer, found
>   verifying the fifth round's new wording rather than the repo: (n) OD-33's new `ci.yml` sentence
>   claimed the cite had "shifted by one" at the merge — false twice over: the step-name line was :226
>   at `a0b4ca31` (:229 was the step's loop line there), and the merge's two insert hunks (+3 after
>   old 195, +1 after old 217) shift every line from 218 down by four, so the :229 → :230 pair is a
>   re-anchor, not drift (verified at
>   both commits with `sed -n '226p;229p'` and the `-U0` hunk headers — the row now carries the full
>   history, which is worse than the reviewer filed: :229 was never the name line even at the draft);
>   (o) the header's moved-facts bullet opened "the six page-count facts" and then enumerated four
>   pairs — the totals only close on four, so "six" contradicted its own sentence (the kind-cut
>   13 = 11+1+1, the merge-split 15 = 2+13 and the census 43 all require four). The lesson compounds
>   again: a corrected number has to be chased into every sentence that quotes it, including the
>   recommendation, "printed" is a claim about an artifact you can open, not about an instrument you
>   re-ran, and a correction sentence written to explain a drift is itself a drift claim — the fix
>   for a wrong cite has to open the file at both commits before it says which line moved by how much.
>
> Everything else measured identically at the first commit, at every revision of this branch since, and
> — for the claims this header names as held — in a detached worktree at the second merge head.

**`F2.2`'s part** (frontend lane, 2026-10-09): §1, §2 and §3 below, drafted from
[`docs/reference/feature-inventory.md`](../reference/feature-inventory.md); §2b above is `W2.2`'s
and is unchanged. `F2.3` finalises §1 and §3: rows its golden paths demote to **half-built** join
§1, and §3 takes `O2.3`'s Python list.

Each §1 row is one **cause** and lists every inventory row it settles; ruling the row rules all of
them, unless the owner names an id in the ruling cell to rule it apart. Sizes are estimates: **S** — one lane, a few files, about a day; **M** — two lanes or a new
wiring path, a few days; **L** — a new pipeline stage or producer, a week or more. The
recommendation is the drafting agent's; the ruling is the owner's.

## 1. Features to rule

The inventory's 128 **half-built** and **leftover** rows, in 45 rows by cause. Core-loop
rows first.

<!-- prettier-ignore -->
| id | feature | status | what the user sees | evidence | core loop | privacy | to complete | to retire | recommendation | ruling | priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-216, F-217 | Alert rules (create, edit, enable) | half-built | rules save and toggle, but no rule ever raises an alert or a notification | `AlertRuleEngine.evaluate_event` and `create_alerts_for_event` have no production caller (`backend/services/alert_engine.py:166`, `:1039`); OD-1 parked the rules engine on 2026-10-05 | yes | none | M — call the engine from the post-verdict path and deliver its channels; backend (alert_engine, the VLM persist path), frontend golden path | M — `alert_rules`, the rules page, `alert_engine.py`; F-220's conditions and F-263's loitering threshold go with it | **complete** — rule-based alerting is the core loop's last step; OD-1 parked it, so this ruling re-opens OD-1's option (c) | | |
| F-050, F-079 | Snooze an event or alert | half-built | the snooze badge appears; nothing is suppressed | `snooze_until` is written (`backend/api/routes/events.py:1997`) but `Event.is_snoozed` (`backend/models/event.py:310`) has no caller | yes | none | S — the notification decision reads `snooze_until`; backend | S — the snooze controls and `events.snooze_until` | **complete** — a one-line read in the notify path makes an existing control honest | | |
| F-044 | Timeline confidence filter | half-built | the filter counts as active; the list does not change | only the sort is applied (`frontend/src/components/events/EventTimeline.tsx:523`) | yes | none | S — apply the filter client-side or pass it to `GET /api/events`; frontend | S — remove the control | **complete** — small, and review is the core loop | | |
| F-055 | Event detail: detected objects and threat boxes | half-built | an empty objects list and no boxes in the event modal | the timeline hands the modal `detections: []` (`frontend/src/components/events/EventTimeline.tsx:1082`) | yes | none | S — pass the event's detections (the modal already fetches them for other panels); frontend | S — remove the list and overlay | **complete** — the reviewer needs to see what was detected | | |
| F-058 | Flag an event for follow-up | half-built | a success toast; nothing is saved | `update_event` handles only `reviewed` (`backend/api/routes/events.py:1987`); the schema accepts `flagged` (`backend/api/schemas/events.py:312`) | yes | none | S — persist `flagged` and filter on it; backend and frontend | S — remove the button and the schema field | **retire** — mark-reviewed and notes already cover follow-up; a false success is worse than no button | | |
| F-078 | Dismiss on the Alerts page | half-built | dismissed alerts stay on the Alerts page | the write lands (the timeline's reviewed filter reads it), but the Alerts list sends only `risk_level`, `limit` and `cursor` (`frontend/src/hooks/useAlertsQuery.ts:155-158`) | yes | none | S — the Alerts query passes `reviewed=false`; frontend | — | **complete** — one query parameter; dismissing is the Alerts page's main action | | |
| F-290 | Inbound webhooks (alert, arm, disarm, mode) | half-built | every call answers 501 | `_reject_unimplemented` raises 501 (`backend/api/routes/inbound_webhooks.py:192`) | yes (arming) | none | L — the arming module with webhook and MQTT adapters (UR-12, Phase 4) | — | **already ruled: complete (UR-12)** — listed for the record; no ruling needed | complete (UR-12) | |
| F-291 | MQTT commands (zone arm/disarm, system mode, alert ack, camera sensitivity/PTZ) | half-built | commands published to the topics are never received | the handler logs and records success without acting, and is constructed only in its own docstring (`backend/services/mqtt_command_handler.py:232`) | yes (arming) | none | L — the arming commands are UR-12's MQTT adapter; alert ack and camera sensitivity/PTZ would be added to it | M — the handler, the unstarted MQTT client and its consumers; arming over MQTT then comes only with UR-12's adapter | **complete** the arming commands with UR-12's adapter (UR-12 names an MQTT adapter); **retire** alert ack and camera sensitivity/PTZ until a package needs them | | |
| F-009, F-292, F-293 | Infrastructure (Prometheus) alerts in the header | half-built | the header's infrastructure-alert badge never lights | the receiver Alertmanager calls sends `infrastructure_alert` (`backend/api/routes/webhooks.py:36`); the header listens for `prometheus.alert` on `/ws/system` (`frontend/src/hooks/usePrometheusAlertWebSocket.ts:197`, `:404`); the second receiver has no caller | no | none | S — align the message type and socket; delete the unused `/api/v1/alertmanager/webhook` receiver and `prometheus_alerts` | S — the badge, drawer and both receivers' broadcasts | **complete** — one type name joins a working receiver to a working badge | | |
| F-010, F-036 | Recent-threats indicator and dashboard threat banner | half-built | neither ever shows a threat | nothing publishes `threat_detected` (`frontend/src/hooks/useRecentThreats.ts:53`); the banner's only feed is discarded (`frontend/src/components/dashboard/DashboardPage.tsx:107`) | yes | none | M — depends on OD-7's immediate-alert path (§2) | S — the indicator, the banner and `useThreatDetection` | **retire** — unless OD-7 rules for an immediate-alert path, which would re-add them with a real feed | | |
| F-131 | Risk-threshold calibration | half-built | thresholds save; event severity does not change | the only reader, `SeverityService.classify_risk` (`backend/services/severity.py:222`), has no production caller | yes | none | M — the verdict path classifies with the saved thresholds; conflicts with OD-29's per-camera floor | S — the page, `CalibrationService`, its table | **retire** — OD-29 ruled the alert operating point as the per-camera floor; two threshold mechanisms would disagree | | |
| F-236 | Notification history | half-built | always "no notifications" | the handler returns a literal empty list (`backend/api/routes/notification.py:412`) | yes | none | M — a delivery-log table written where notifications are sent (ISS-001's path) | S — the panel and route | **complete** — the owner needs to see what was sent; delivery now exists (ISS-001 done) | | |
| F-051, F-098, F-099 | Exports: download, type, cancel (`/data` and the timeline's export modal) | half-built | the export button's Download link 404s; "Alerts"/"Full Backup" exports contain events; a cancelled export finishes anyway | download path is the status route (`backend/services/export_service.py:888`); type is never passed (`backend/api/routes/exports.py:119`); cancel only flips the row (`backend/api/routes/exports.py:453`, `:181`) | no | the export holds event data | S — serve the file, drop or implement the two types, check cancel in the task; backend | M — the export jobs stack; the CSV/JSON export modal (unverified) would remain | **complete** — each fix is small and exporting is a stated feature | | |
| F-088 | Trash: delete permanently | half-built | "Delete permanently" fails or re-trashes | the route ignores `soft_delete: false` and soft-deletes again (`backend/api/routes/events.py:2713`) | no | retained events | S — honour hard delete for trashed events; backend | M — the trash page and soft delete | **complete** — a privacy control that does not delete is a defect | | |
| F-202 | Deleted cameras (trash view) | half-built | the deleted-cameras list is always empty | delete is hard (`backend/api/routes/cameras.py:978`); `Camera.soft_delete` (`backend/models/camera.py:240`) has no caller | no | none | S — make camera delete soft | S — the trash view and restore route | **retire** — hard delete is the shipped behaviour | | |
| F-101 | Restore from backup | half-built | restore succeeds; camera baselines are silently lost | restore iterates only a `baselines` entry (`backend/services/restore_service.py:54`) while backups write `activity_baselines` and `class_baselines` (`backend/services/backup_service.py:146`, `:147`) | no | none | S — restore the two baseline tables; backend | — | **complete** — a backup that drops data on restore is a defect | | |
| F-091, F-092, F-093, F-094, F-095, F-096 | Job controls, history and live logs | half-built | the live log viewer stays empty; cancel, abort, retry, delete and history were built but no page shows them | no production log publisher (`backend/services/job_log_emitter.py:165`); `JobActions` and `JobHistoryTimeline` are rendered by no component; retry has no route | no | none | M — mount the actions, add a retry route, make delete delete, publish logs; backend and frontend | S — the unmounted components, the log socket's client, the retry client call | **retire** — jobs are short exports and audits; the controls never shipped | | |
| F-035 | Dashboard summary export buttons | half-built | the buttons do nothing | the dashboard mounts the panel without `onExport` (`frontend/src/components/dashboard/ExpandableDetailPanel.tsx:242`) | no | none | S — wire `onExport` to the summary export route (whose PDF is a skeleton, backend trace Dead Marks (e)) | S — the buttons | **retire** — the export it would call emits a placeholder PDF | | |
| F-065, F-066, F-067, F-081, F-082, F-083, F-084, F-085, F-086 | Entities and re-ID (entity list, trust, re-ID dashboard, event re-ID panels) | half-built | empty pages and panels | `entities` has no production writer since R8 S2b removed the enrichment pipeline (`backend/services/entity_clustering_service.py:265`, `backend/services/hybrid_entity_storage.py:233`); entity-matches has no route | no | person re-ID embeddings | L — persist the re-ID matches the VLM specialists already compute (`backend/services/vlm_specialists.py:723`); backend, frontend; ties to OD-17 | M — `entities`, Redis `entity_embeddings:*`, the entities/reid routes and pages, the event panels | **retire** — no writer since R8, it stores biometric-like embeddings, and OD-17 may drop the re-ID model; complete only if cross-camera tracking is a product goal | | |
| F-276, F-279, F-280, F-281, F-282, F-283, F-284, F-285, F-118 | Face events, appearances and face actions | half-built | the known-persons gallery works; face events, appearances and stranger alerts are always empty; Delete, Enroll, Identify and link-to-member do nothing | `record_face_detection` has no caller (`backend/services/face_recognition_service.py:588`); TODO handlers (`frontend/src/pages/FaceRecognitionPage.tsx:79`, `:120`); no `face_detection` publisher | no | faces | M — write face events where faces are detected, publish them, wire the buttons; backend and frontend | M — `face_detection_events`, the events tab, the unmounted modals, the stranger alerts (the gallery could stay) | **complete** — the gallery and enrollment work; one missing write and four handlers make the rest real | | |
| F-272, F-273, F-274 | Household links, member detections, property/area editor | half-built | a member↔person link that nothing uses; the other two were built but no page shows them | the link's consumer is unreachable (`backend/services/unified_embedding_service.py:548`); the detection routes do not exist; `PropertyManagement` is unreachable | no | faces, person re-ID embeddings | M — backend routes, mount the components, a consumer for the link | S — the unmounted components, the hierarchy property/area routes and tables, the link field | **retire** — none of the three ever reached a user | | |
| F-268, F-269 | Plate reads | leftover, half-built | an empty list; stats cards fail | plate OCR retired in R8 S3 (`backend/services/alpr_service.py:559`); `/stats` vs `/statistics` (`backend/api/routes/plate_reads.py:89`) | no | plates | L — a new OCR model | M — `plate_reads`, the routes, the page, the ALPR service | **retire** — its model was retired; F1.1's one-word `/stats` fix is moot | | |
| F-257, F-259, F-260, F-261, F-262, F-263, F-264, F-265, F-266, F-267, F-212, F-214 | Zone analytics (crossings, dwell, loitering, anomalies, comparison, trust violations, health) | half-built | empty cards and charts; every zone "healthy" | no production writer for `dwell_time_records`, line/polygon counters or `zone_anomalies` (`backend/services/dwell_time_service.py:95`, `backend/services/line_zone_service.py:212`, `backend/services/zone_anomaly_service.py:284`); no UI creates line or polygon zones | no | location (movement within the property) | L — a zone tracker in the pipeline feeding dwell, crossings and anomalies; UI to create analytics zones | L — the analytics-zones routes and tables, zone anomalies, the Zones analytics tabs; camera zones (analyzer context) stay | **retire** — none of it has ever had data; camera zones, which the analyzer uses, are unaffected | | |
| F-008, F-030, F-208, F-287, F-288 | Scene-change (camera tamper) detection | half-built | no scene changes, ever | `scene_changes` has no production writer (`backend/services/scene_change_detector.py:307`) | yes (camera health) | none | M — run the detector on frames in the pipeline and emit the event; backend | M — the table, routes, page, header alerts, dashboard indicator | **complete** — a blocked or moved camera is a security event and the detector exists | | |
| F-286 | Movement heatmaps | half-built | an empty heatmap | `HeatmapService.add_detection` has no production caller (`backend/services/heatmap_service.py:197`) | no | location | M — feed detections into the accumulator | S — the page, routes, `heatmap_data` | **retire** — not part of the core loop and never had data | | |
| F-289 | Object tracks | half-built | no tracks | `TrackService.create_or_update_track` has no caller (`backend/services/track_service.py:78`) | no | location | L — a tracker in the pipeline | S — the page, routes, `tracks` | **retire** — needs a tracker the product does not run | | |
| F-109, F-110, F-111, F-113, F-120, F-122, F-123, F-124, F-112, F-121 | Prompt management and the prompt playground | half-built, leftover | prompts save, version, test and import; the VLM never reads them; four editors are for retired models | nothing outside the prompt routes reads `prompt_versions` (`backend/api/routes/prompt_management.py:42`); the shipped prompt is inline (`backend/services/vlm_analyzer.py:649`); this answers ISS-084 | no | none | M — the VLM reads the active prompt version; would bypass the replay-measured prompt selection (UR-8, OD-29) | M — the prompt routes, service, `prompt_versions`, both pages (OD-25 option (a)) | **retire** — prompts are chosen on replay numbers (OD-29); an editable store the VLM ignores misleads | | |
| F-114 | Automatic AI-audit evaluation | half-built | nothing; audits appear only from a manual batch | `EvaluationQueue.enqueue` has no production caller (`backend/services/evaluation_queue.py:45`); the evaluator starts by default (`backend/main.py:1070`) | no | none | S — enqueue events as they close; costs GPU time beside the verdict | S — stop starting it and delete the queue (the audit's D7); manual audit stays | **retire** — the manual batch audit covers the need without GPU contention | | |
| F-105, F-130, F-127, F-128 | Model Zoo latency chart, management panel, load/unload | half-built | an empty latency chart; a panel with wrong fields; load/unload fail | `record_model_zoo_latency` has no caller (`backend/core/metrics.py:2223`); load/unload end in 501 (`backend/api/routes/model_management.py:751`, `:784`) | no | none | M — latency recording in the gateway; the panel's shape; load/unload cannot exist under `--model-control-mode=none` | S — the chart, the buttons and their routes; fix or drop the panel | **retire** — the read-only cards (unverified) keep what works | | |
| F-011, F-015, F-037, F-126, F-139, F-140, F-173 | Status displays keyed on retired models (RT-DETRv2, Nemotron, Florence, CLIP) | leftover, half-built | badges, cards and charts stuck on "unknown" or empty | the UI reads `rtdetr`/`nemotron` keys; the backend reports `yolo26`/`ai-vlm` (`backend/api/routes/system.py:1062-1063`) | no | none | S — re-key to `yolo26` and `ai-vlm`; frontend | S — remove the stale badges and cards | **complete** — re-keying gives the owner live status for the two engines that run | | |
| F-103, F-116, F-119, F-107, F-063 | Retired-model analytics: Grafana panels, model contribution chart, LLM reasoning tab | leftover | panels and tabs that stay empty | Florence-2, the attribute zoo and X-CLIP retired (`backend/services/model_zoo.py:18-19`, `backend/api/routes/action_events.py:10`); `llm_interactions` lost its writer in R8 S2b | no | none | — | S — the panels (ops: `monitoring/`), the chart, the tab and `llm_interactions` | **retire** — their models are gone | | |
| F-068, F-069, F-220 | Action events, pose overlay, pose/action/threat/smoke rule conditions | leftover | an empty panel, no overlay, conditions the UI already hides | X-CLIP and ST-GCN++ archived/deleted (`backend/models/action_event.py:10`, R8 `602379e29`); pose rows deleted in R8 S3 | no | none | — | S — the panel, overlay, `action_events`, the four condition fields | **retire** — their models are gone | | |
| F-136, F-144, F-041 | Live queue and worker panels | half-built | queue and worker panels that never update; a dashboard widget showing literal zeros | no production emitter for `queue.status`/`pipeline.throughput` (`backend/core/websocket/event_types.py:248`); `broadcast_worker_event` gets no emitter (`backend/services/pipeline_workers.py:104`); zeros at `frontend/src/components/dashboard/DashboardPage.tsx:531` | no | none | S — wire the emitter or read the REST queue endpoint the other panels use | S — the WS-only panels and the widget | **retire** — the REST-fed operations panels (unverified) already show queues and workers | | |
| F-151, F-152, F-153, F-157 | Profiling and recording developer tools | half-built | profiling status and download 404; Start/Stop shows the wrong state; Clear all fails | client paths `/api/debug/profile` and `/download` are not served (`backend/api/routes/debug.py:925`); `DELETE /api/debug/recordings` answers 405 (`backend/api/routes/debug.py:1405`) | no | request recordings may hold request bodies | S — point the client at `/profile/stats`, add a download route or drop the button, delete per recording | S — the panels; the debug routes stay for the API | **complete** — client-side fixes; follows **OD-36** (§2): retired with the debug tooling if OD-36 retires it | | |
| F-168 | Tracing: open Jaeger | half-built | a link to a Jaeger UI that does not exist | prod compose runs Tempo, no Jaeger (`docker-compose.prod.yml:989`) | no | none | S — link to Grafana's Tempo explore | S — remove the link | **complete** — one URL | | |
| F-177, F-179, F-180, F-181, F-183 | GPU assignment (rescan, assign, apply, import, rollback) | half-built | assignments save and "apply" reports success; nothing restarts; health is always "healthy" | apply is simulated (`backend/api/routes/gpu_config.py:926`, `:943`); health hardcoded (`:1280-1281`); the only assignable service is the retired `ai-yolo26` container | no | none | L — real container recreation; overlaps the orchestrator scoping (`B1.6`, D11) | M — the GPU settings page, `gpu_config` routes, `gpu_configurations`/`gpu_devices` | **retire** — its only target is retired, and recreating containers from the backend is what D11 removed | | |
| F-188, F-189 | Admin feature toggles: Vision Extraction, Re-ID, Scene Change, Image Quality | leftover, half-built | toggles save; nothing changes | Florence retired (`backend/ai_contract/providers.py:53`); the other three settings have no reader outside the settings route | no | none | — (follows the scene-change and re-ID rulings above) | S — the four toggles and their settings fields | **retire** — re-add a toggle only with the feature it controls | | |
| F-193 | Admin: flush queues | half-built | "flushed"; the queues are untouched | it clears prefixed keys (`backend/api/routes/admin.py:1264`); the pipeline uses unprefixed `detection_queue` (`backend/services/file_watcher.py:405`) | no | none | S — use the pipeline's key names | S — the button | **complete** — an operator tool reporting a false success | | |
| F-227, F-210 | Camera anomaly detection (config and timeline) | half-built | a config that resets on restart; an anomaly timeline that is always empty | `get_recent_anomalies` returns `[]` (`backend/services/baseline.py:966`); the threshold lives in memory only (`backend/services/baseline.py:1090`) | no | none | M — compute and store anomalies against the activity baselines | S — the config panel, the timeline, the anomaly half of `baseline.py` | **retire** — baselines (unverified) stay; anomalies were never computed | | |
| F-239 | Ambient audio and desktop-notification toggles | half-built | toggles save; nothing reads them | the provider reads only `ambientEnabled` and `faviconBadgeEnabled` (`frontend/src/components/common/AmbientStatusProvider.tsx:82`) | no | none | S — implement the sound and desktop notification | S — the toggles | **retire** — the notification settings page already owns desktop and sound | | |
| F-244 | Detector switching | half-built | nothing: no page renders it | `DetectorSettings` is imported by nothing; the router is mounted without `/api` (`backend/main.py:1618`) | no | none | S — mount the router under `/api` and render the panel | S — the component, hook, client and router | **retire** — one detector (YOLO26) ships | | |
| F-246 | Outbound webhook event types that never fire | half-built | a webhook subscribed to, say, `event_created` saves and never receives anything | of the eleven types the form offers (`frontend/src/types/webhook.ts:34-46`), `backend/` triggers only the `alert_*` types and `entity_discovered` (`backend/services/entity_clustering_service.py:327`, itself unreached) | no | none | M — fire `event_created`, `anomaly_detected`, `system_health_changed` and the batch types where those things happen; backend | S — drop the seven types from the form and the enum | **retire** the seven types — `alert_*` covers the core loop; re-add a type with its producer | | |
| F-252, F-253, F-255 | Scheduled reports | half-built | reports save with a "next run"; none ever runs; Run now 404s | nothing reads `next_run_at`/`is_due` (`backend/models/scheduled_report.py:134`, `:170`); `/run` answers "queued" and queues nothing (`backend/api/routes/scheduled_reports.py:419`, `:433`) | no | none | L — a scheduler, a report generator and delivery | S — the page, routes and `scheduled_reports` | **retire** — no generator exists; the summaries cover the reporting need | | |
| F-019 | Command palette "System" entry | half-built | the 404 page | it targets `/system`; the page moved to `/operations` (`frontend/src/App.tsx:275`) | no | none | S — point it at `/operations` | S — remove the entry | **complete** — one path | | |
| F-076 | Cost analytics | half-built | zero cost and tokens | `track_llm_usage` (`backend/services/cost_tracker.py:199`) is fed by nothing since the LLM tier left | no | none | M — record VLM token usage | M — the cost view, routes and tracker | **retire** — the VLM runs locally; token cost is not a product number | | |

## 2. Open owner decisions

### OD-7 — threat specialist, immediate-alert fast paths, alerts surface for unverified events

**Facts the inventory found.**

- No immediate-alert path runs: the threat fast path builds `ThreatMonitorService(session=None)` and
  raises on every call, and the smoke/fire path only updates a tracker; no production caller passes
  a threat or smoke/fire type, so neither branch fires (register ISS-021, re-read 2026-10-09).
- The UI surfaces built for that path never receive data: the header's recent-threats indicator
  waits for `threat_detected`, which nothing publishes (F-010); the dashboard's threat banner has no
  feed (F-036); the alert-rule threat and smoke/fire conditions are hard-coded off (F-220).
- The threat specialist is off by default: `GATEWAY_ENABLE_THREAT` defaults to `false`
  (`docker-compose.prod.yml:394`), so the gateway's resident set is `yolo26` and `reid`
  (`ai/gateway/residency.py:60`).
- The Alerts page lists events by risk level (high and critical), not the `alerts` table (F-077,
  F-078); the rules engine that would write `alerts` does not run (§1, F-216).

**Facts added by ruling 67** (re-read at `main` `28770b3d8`):

- The gateway's `threat` model is a YOLOv8n fine-tune for weapons. Its weights are
  `threat-detection-yolov8n/weights/best.pt` (`ai/gateway/export/export_yolo_threat.py:5`), from
  the Hugging Face repo `Subh775/Threat-Detection-YOLOv8n` (`models.yml:197`). Nothing pins a
  revision.
- **Provenance and license.**
  - The model card declares MIT and names `Ultralytics/YOLOv8` as the base model.
  - Its training config starts from `yolov8n.pt` and the Kaggle dataset `threat-detection-3849`.
    The card credits Roboflow for the dataset and gives no license for it.
  - The card does not record the license of the `yolov8n.pt` weights. The `ultralytics` package
    the repo installs (`8.4.173`) declares AGPL-3.0 for its code. Whether that license covers the
    base weights, and so this fine-tune, is open.
  - So the MIT claim is the uploader's, and the base weights' and dataset's licenses are
    unrecorded.
- **The class labels do not match.** The gateway names the four outputs `knife`, `pistol`,
  `rifle` and `threat_object` (`ai/gateway/adapters/enrichment_light.py:84`). The model card lists them as
  Gun, Explosive, Grenade and Knife; its "Explosive" class covers "fire, explosion scenarios, and
  explosive devices". Which gateway label a detection gets is unverified until someone reads the
  checkpoint's own `names`.
- **Trigger source.** The recommendation below says a fast path has no trigger source. For weapons,
  this model is one. For smoke there is none. For fire, the ruling's facts say there is
  none, and this refines that: the only candidate is the card's "Explosive" class. The gateway
  does not name that class as such, and the card reports 49.7 % test precision for it.
- Nothing calls the gateway's `/enrich-lt/threat-detect`
  (`ai/gateway/adapters/enrichment_light.py:130`) today; turning the model on also needs a backend
  caller.

**Options, as the register states them** (`docs/vss-integration/17-action-plan.md`, OD-7):
`GATEWAY_ENABLE_THREAT` on (re-measure S1) or off; delete the fast-path stubs or specify a
trigger; show unverified events or keep high/critical only.

**Rows each option affects.** Threat on with a trigger specified: F-010 and F-036 are completed
against it, and F-220's threat condition returns. Stubs deleted: F-010, F-036 and F-220 retire with
them (§1 recommends this). Alerts surface: F-077 and F-078.

**Recommendation.** Keep the threat specialist off and delete both fast-path stubs, with F-010,
F-036 and F-220; keep the Alerts page on high/critical events. The verdict path is the one alert
path that works, and a second, seconds-fast path needs a trigger source the detector does not
have (COCO classes carry no weapon, fire or smoke). Ruling 67's facts change that premise
for weapons: the gateway's `threat` model is a trigger source. The recommendation stands until its labels and its
license are settled. A weapons fast path would need both, plus a backend caller for
`/enrich-lt/threat-detect`.

**Ruling:**

### OD-17 — the Triton `reid`/`threat` lane and `ai-llm-vllm`

> **The re-ID half is ruled (ruling 68, 2026-10-10).** The backend's person re-ID moves to the
> gateway's `reid` model on the GPU, as package `B2.2` (`uplevel-heavy-2`). What stays open here is
> the rest of OD-17: the entity and re-ID surfaces, and `ai-llm-vllm`. The facts and options below
> are kept as the inventory wrote them; the re-ID option they weigh is settled.

**Facts the inventory found.**

- Re-ID runs in the backend, not the gateway: the specialists embed crops with the resident OSNet
  handle (`backend/services/vlm_specialists.py:723`); no backend code calls the gateway's
  `/enrich-lt/person-reid` (register ISS-050).
- What re-ID computes is not persisted: `entities` has no production writer since R8 S2b, so every
  entity and re-ID surface is empty (§1, F-065, F-081 to F-086).
- `ai-llm-vllm` (compose profile `vllm`, `docker-compose.prod.yml:283`) backs no UI row; no
  inventory row's chain reaches it.
- The Model Zoo cards (F-104, F-129, **unverified**) read the live model manager; neither option
  changes them.

**Facts added by ruling 67** (re-read at `main` `28770b3d8`):

- **The gateway's `reid` is the backend's model:** the same network and weights, OSNet-AIN x1.0
  trained on MSMT17 (`ai/gateway/export/export_reid.py:2-21`). The export script is a standalone
  port of torchreid's network. `ai/gateway/tests/test_export_reid.py` checks it against torchreid
  itself.
- **The backend's copy runs on the CPU.** Its torch is the CPU wheel (`uv.lock:4430`,
  `torch 2.14.0+cpu`), and the backend has a 2-CPU limit (`docker-compose.prod.yml:685`), although
  compose reserves a GPU for it (`docker-compose.prod.yml:690`-`693`). The backend embeds person
  crops on every event that has them (`backend/services/vlm_specialists.py:754`).
- **The gateway's copy is resident on the GPU** (`ai/gateway/residency.py:60`), served at
  `/enrich-lt/person-reid` (`ai/gateway/adapters/enrichment_light.py:172`), and nothing calls it.

**Options, as the register states them** (OD-17): the backend calls `/enrich-lt/person-reid`, or
drop `reid` from the residency sets; pin or remove `ai-llm-vllm`.

**Rows each option affects.** Either re-ID option leaves the entity and re-ID rows (§1) empty
unless they are also completed; dropping `reid` from the gateway changes no UI row; removing
`ai-llm-vllm` changes no UI row.

**Recommendation.** For the half still open: remove `ai-llm-vllm`, and retire the entity and
re-ID surfaces with §1's row. If cross-camera tracking is wanted, complete that row against the
gateway's `reid` that B2.2 moves re-ID to. The inventory's original recommendation was to drop
`reid` from the gateway and keep the backend's OSNet. Ruling 68 decided the opposite, so that
recommendation is superseded.

**Ruling:**

### OD-36 — debug tooling in production

Added by ruling 62 (issue #6854). Facts read at `main` `523584583`.

**What the user sees.** `/operations` always shows a **Developer Tools** section: profiling, request
recording and replay, a configuration inspector, log-level control and test-data seeding
(`frontend/src/components/system/SystemMonitoringPage.tsx:695`, no condition around it). On
`/settings/admin`, Raw Settings and the seed/clear tools appear only in debug mode
(`frontend/src/components/settings/AdminSettings.tsx:787`, `:805`), but Logging Settings, which reads
and sets the log level through `/api/debug`, always shows (`:775`). Behind all of them, every
`/api/debug/*` route answers whether or not the backend runs in debug mode.

**Evidence.**

- The guard all 22 debug routes depend on does nothing: `require_debug_mode`
  (`backend/api/routes/debug.py:57`) promises a 404 when debug is off, and its body is `pass` under
  "Debug endpoints always available in this deployment" (`backend/api/routes/debug.py:72`).
  `settings.debug` defaults to `False` (`backend/core/config.py:816`), so on a default deployment the
  guard's own premise says these routes should be hidden.
- Ten of the 22 change state: log level, profiling start/stop, garbage collection, tracemalloc
  start/stop, replaying a recorded request against the live app (`backend/api/routes/debug.py:1522`),
  deleting a recording, injecting a detection into the batch aggregator (`/batch/add-detection`) and
  resetting batch metrics.
- Who can reach them: with `EXPOSE_LAN` unset the app listens on loopback and the auth gate passes
  every request (`backend/api/middleware/auth.py:381`); with `EXPOSE_LAN=true`, any logged-in
  session or API key reaches them — there is no admin check.
- Not every caller is a developer tool. Logging Settings on `/settings/admin` (F-195) reads
  `GET /api/debug/config` and reads and sets `/api/debug/log-level`, with no debug condition; the
  `/operations` Databases section reads `GET /api/debug/redis/info` for Redis INFO (F-145). A
  working guard turns both off on a default deployment.
- The guard covers `/api/debug/*` only. The seed and clear routes of OD-37 sit under `/api/admin`,
  gated by `ADMIN_ENABLED` alone, which "does NOT consult DEBUG" (`backend/core/config.py:826`).

**To complete — M** (backend and frontend). The guard raises 404 unless `settings.debug`; the
`/operations` Developer Tools section renders only when the backend reports debug available, as
`/settings/admin` already does. Logging Settings' config and log-level calls move to a route outside
the debug router (or are exempted from the guard), so F-195 keeps working with debug off. A test pins
a debug route at 404 with debug off. §1's profiling row (F-151–F-153, F-157) keeps its own S client
fixes.

**To retire — M.** The 22 routes in `backend/api/routes/debug.py`, the five `/operations` panels
and the `/settings/admin` developer tools, with their hooks and tests; profiling, replay and the
config inspector go with them. §1's profiling row retires with this. Logging Settings (F-195) loses
its backend unless its calls move first, and F-145 loses its Redis INFO block.

**Rows it settles.** F-133, F-145, F-151–F-159, F-195; §1's profiling row (F-151–F-153, F-157)
follows this ruling. The test-data rows (F-160–F-162, F-197) are ruled in OD-37, which wins for
them.

**Recommendation.** **Complete.** The tools are useful in development and the fix is the guard
the code already describes; turning it on closes the `/api/debug` routes on every default
deployment, once Logging Settings has its own route. Retire only if no one uses them.

**Ruling:**

### OD-37 — "Clear All Test Data" deletes all data

Added by ruling 62. Facts read at `main` `523584583`.

**What the user sees.** Three buttons call one route, `DELETE /api/admin/seed/clear`:

- `/settings/admin` (debug mode only): **Clear Test Data**, "Delete all cameras, events, and
  detections" (`frontend/src/components/settings/AdminSettings.tsx:900`, `:903`), confirmed in a
  dialog titled "Clear All Test Data" (`:983`) — F-197.
- `/operations` → Developer Tools → Test Data: **Delete All Events**, "Permanently deletes all events
  and detections from the database" (`frontend/src/components/developer-tools/TestDataPanel.tsx:203`,
  `:204`), and **Full Database Reset** (`:211`) — F-162. "Delete All Events" sends the same request
  (`:110`), so it deletes every camera too: its description is false.

**Evidence.** The route (`backend/api/routes/admin.py:658`, `clear_seeded_data` at `:671`) needs
`ADMIN_ENABLED` — which defaults to `True` (`backend/core/config.py:836`) — and the body
`{"confirm": "DELETE_ALL_DATA"}`, then runs `delete(Event)`, `delete(Detection)` and
`delete(Camera)` on every row (`backend/api/routes/admin.py:714`, `:716`). Nothing marks a seeded
row: the seeded cameras use ordinary ids (`front-door`, `garage`, `backend/api/routes/admin.py:172`)
and the models carry no seed flag. Seeding cameras with "clear existing" also deletes every camera
first (`backend/api/routes/admin.py:331`). Deleting a camera cascades: 16 model files hold a
`cameras.id` foreign key with `CASCADE` (`rg -l 'ForeignKey\("cameras\.id".*CASCADE' backend/models`,
less `AGENTS.md`) — zones, baselines, calibration, notification preferences, tracks, plate reads,
face identities, heatmaps, dwell time, scene changes, package events and others — so the reset also
deletes every camera's configuration and analytics history.

**Options.**

- **Rename — S** (frontend): every label says what happens ("Delete all cameras with their
  settings, events and detections"); "Delete All Events" either deletes only events or goes.
- **Restrict to seeded rows — M** (backend schema and frontend): add a seed marker to cameras and
  events, write it when seeding, delete only marked rows; existing seeded rows stay unmarked.
- **Retire the seed tools — S**: the clear route, the Test Data panel and the admin section. The
  seed routes stay: `scripts/seed-events.py:3337` posts to `/api/admin/seed/pipeline-latency`, and
  the k6 load tests seed through `/api/admin/seed/cameras` and `/events`
  (`tests/load/mutations.js:197`, `:230`), run by `.github/workflows/load-tests.yml`.

**Rows it settles.** F-160, F-161, F-162, F-197.

**Recommendation.** **Rename, and require debug mode for the seed and clear routes — S each**
(frontend labels; backend: the `/api/admin/seed/*` routes check `settings.debug` as well as
`ADMIN_ENABLED`, since OD-36's guard does not reach them, and the load-test workflow sets
`DEBUG=true`). A full reset is a legitimate development tool; what is wrong is a label that calls it
test data, a button that says "events" and deletes cameras, and its presence on a default
deployment. If OD-36 retires debug tooling, retire the UI with it.

**Ruling:**

### OD-38 — two orphan cleaners side by side

Added by ruling 62. Facts read at `main` `523584583`.

**What the user sees.** Two "clean up orphaned files" controls, on two pages, with different
safety rails:

- `/settings/storage`: a preview headed "N Orphaned Files Found", then **Clean Up**, with no
  confirm step (`frontend/src/components/system/FileOperationsPanel.tsx:289`, `:308`) — F-184,
  F-186. Also on `/operations` (F-163).
- `/settings/admin` → Maintenance: an orphan cleanup panel with a minimum-age slider (1–720 h,
  default 24), a size cap and a preview (`frontend/src/components/settings/AdminSettings.tsx:712`)
  — F-194.

**Evidence. They delete different files.**

- The storage cleaner (`run_orphaned_file_cleanup`, `backend/api/routes/system.py:3403`) scans the
  **thumbnails and clips** directories (`backend/services/cleanup_service.py:763`, `:768`): derived
  files whose `Detection` or `Event` row is gone. No age or size limit. Guarded by `verify_api_key`
  (`backend/api/routes/system.py:3401`), which passes everyone while `API_KEY_ENABLED` is off, its
  default.
- The admin job (`cleanup_orphans`, `backend/api/routes/admin.py:785`) scans the **camera upload
  folder**, `foscam_base_path` (`backend/services/orphan_scanner_service.py:144`, `:365`), and
  deletes files no `Detection.file_path` names, older than 24 h by default and up to 10 GB a run
  (`backend/jobs/orphan_cleanup_job.py:36`, `:37`). A camera image in which the detector finds
  nothing gets no `Detection` row — rows are created per detected object above the threshold
  (`backend/services/detector_client.py:1184`, `:1194`, `:1281`) — so this job deletes every
  capture with no detection once it is a day old. That is a retention policy for raw captures,
  presented as orphan cleanup.
- Two more cleaners exist and never run: `OrphanCleanupScheduler`
  (`backend/jobs/orphan_cleanup_job.py:328`, recorded dead in
  `docs/reference/backend-entry-points.md:1430`) and `OrphanedFileCleanupService`
  (`backend/services/orphan_cleanup_service.py:88`; its factory `get_orphan_cleanup_service` has no production caller). Every option below
  removes them.

**Options.** Keep the storage cleaner (derived files only) and retire the admin job — **S**; keep
the admin job and retire the storage cleaner — **S**, but raw-capture deletion then becomes the only
cleaner; or merge them into one cleaner with the admin job's age and size rails and the storage
cleaner's directories — **M**.

**Rows it settles.** F-163, F-184, F-186, F-194.

**Recommendation.** **Merge into one cleaner over the derived directories, with the admin job's
age and size rails, and retire the scan of the camera folder.** Whether raw captures with no
detection should be deleted is a retention decision, and today no retention rule covers them: the
retention cleanup deletes images only through their `Detection` rows
(`backend/services/cleanup_service.py:377`). If the owner wants them deleted, that is a retention
setting with its own name, not an "orphan" button.

**Ruling:**

### OD-39 — Triton's future

Added by ruling 67 (issue #6854), which puts it on the R2 sheet to be ruled together with OD-7 and
OD-17. Nothing changes in code now; any replacement would be a Phase 4 package that measures
latency and VRAM first. Facts read at `main` `28770b3d8`.

This entry is written from ruling 68's state: `yolo26` and `reid` are both in use. Today, until
B2.2's switch merges, nothing calls `reid`.

**What Triton serves today.** The `ai-gateway` container runs Triton behind a FastAPI gateway. Its
model repository holds three models, all ONNX Runtime on the GPU
(`ai/triton/model_repository/reid/config.pbtxt:33`, `KIND_GPU`; the other two match):

- `yolo26`, the object detector. The backend calls it for every frame through
  `/yolo26/detect`: the `/yolo26` base URL is at `backend/core/config.py:1065`, and the `/detect`
  call at `backend/services/detector_client.py:668`.
- `reid`, the OSNet-AIN x1.0 re-ID model. Ruling 68 makes it the backend's re-ID path (B2.2);
  until B2.2's switch merges, nothing calls it.
- `threat`, the weapons detector. It is off by default (`docker-compose.prod.yml:394`), and nothing
  calls it.

The residency set is `yolo26` and `reid`, plus `threat` only when `GATEWAY_ENABLE_THREAT` is on
(`ai/gateway/residency.py:60`; `GATEWAY_ENABLE_THREAT` is read at `:96`).

**What it would serve under each outcome of OD-7 and OD-17.**

| Outcome                                          | Triton serves                                                                          |
| ------------------------------------------------ | -------------------------------------------------------------------------------------- |
| OD-7: threat off (its recommendation)            | `yolo26`, `reid`                                                                       |
| OD-7: threat on with a trigger                   | `yolo26`, `reid`, `threat`, plus a backend caller for `threat` that does not exist yet |
| OD-17, the re-ID half (ruled by 68)              | `reid` in use. If B2.2 is reverted, `reid` is resident and uncalled again              |
| OD-17, the rest (entity surfaces, `ai-llm-vllm`) | no change: neither touches Triton                                                      |

**What Triton costs.**

- **The image.** It is built on `nvcr.io/nvidia/tritonserver:26.01-py3` (`ai/gateway/Dockerfile:1`).
  On top of that it installs the export toolchain: `torch`, `transformers`, `ultralytics`, `onnx`,
  `onnxscript`, `onnxruntime-gpu`, `open_clip_torch`, `timm` and `einops`
  (`ai/gateway/Dockerfile:19`-`35`). There are 12 export scripts (`ai/gateway/export/export_*.py`);
  `export_all.sh` runs three of them (threat, `yolo26`, `reid`;
  `ai/gateway/export/export_all.sh:113`, `:123`, `:137`).
- **Start-up machinery,** all of it run before Triton starts:
  - per-model config patching from `models.yml` (`ai/gateway/entrypoint.sh:87`);
  - linking the exported files from the cache into the repository (`:110`);
  - pruning the repository to the residency set (`:131`).

  Triton then runs with `--model-control-mode=none` (`:147`), so it has no load API; F-128's
  buttons return 501 for that reason.

- **Volumes:**
  - the model cache, `${AI_MODELS_PATH}/triton` (`docker-compose.prod.yml:374`);
  - two named caches, `triton-kernel-cache` (`:377`) and `triton-tmp-cache` (`:379`);
  - the Hugging Face cache (`:381`).
- **Resources:** a limit of 8 CPUs and 20 GB, with 10 GB of memory and one GPU reserved
  (`docker-compose.prod.yml:417`-`423`).
- **The real-tier gap.** The `agent-gpu` library holds no Triton models (ruling 67, citing ruling
  66). `O2.2`'s `--real` serves only the VLM and keeps the fake detector, so no agent run exercises
  `yolo26`, `reid` or `threat`. B2.2's parity check is an owner run on the host for that reason.
  Neither option below closes the gap by itself: a real-tier run of either server needs its ONNX
  files in the library.

**What Triton provides beyond running ONNX Runtime:**

- a shared rate limiter that serialises GPU work across the three models, with priorities
  (`ai/triton/model_repository/reid/config.pbtxt:35`, `:39`);
- dynamic batching for `reid`, with a queue delay of up to 100 ms (`:44`-`46`);
- the `nv_inference_*` and `nv_gpu_*` metrics on port 8002.

**What would replace its metrics.** Prometheus scrapes Triton at `ai-gateway:8002`
(`monitoring/prometheus.yml:136`, `:142`). The `nv_*` series feed:

- the `GPUInferenceFailures` alert (`monitoring/ai-pipeline-alerts.yml:51`);
- the recording rule `job:triton_inference_latency:avg5m`
  (`monitoring/profiling-recording-rules.yml:191`);
- four Grafana dashboards: `ai-services.json` (F-102, F-115), `consolidated.json` (F-164),
  `tracing.json` (F-167) and `ai-service-health.json`;
- the list of `nv_*` names in `scripts/audit_grafana_queries.py:256`-`258`.

The gateway's own scrape job drops `nv_.*` (`monitoring/prometheus.yml:175`) so that the series
are not counted twice; that drop rule goes with them.

The gateway already exports its own per-endpoint metrics:
`hsi_ai_inference_duration_seconds` and `hsi_ai_inference_errors_total` (`ai/gateway/main.py:83`,
`:90`). The GPU-memory alerts already read the `hsi_gpu_*` exporter
(`monitoring/ai-pipeline-alerts.yml:69`), not Triton. A slim service would re-point the failure
ratio and latency panels to the `hsi_ai_inference_*` series, and the GPU panels to `hsi_gpu_*`.

**Options.**

- **Keep Triton as the one model server — no new work.** Route re-ID through it (B2.2, already
  ruled), and threat too if OD-7 turns it on. The costs above stay as they are.
- **A slim detector service — L** (ops and backend). It is L rather than M because it replaces a
  production service and must measure before it switches. A FastAPI service runs ONNX Runtime on the
  GPU, loads the same three `.onnx` files and exports the app's own metrics.
  - No model needs re-exporting: Triton already runs each one through its ONNX Runtime backend.
  - It removes the Triton base image, the patching, linking and pruning steps, and the `nv_*`
    metrics.
  - It must replace the rate limiter and `reid`'s dynamic batching, or show by measurement that
    they aren't needed.
  - B2.2's client and parity gate move with it.
  - Per ruling 67, it is a Phase 4 package that measures latency and VRAM before it switches
    anything.

**Rows each option affects.**

- **Keep:** none.
- **Slim service:**
  - F-102, F-115, F-164 and F-167: their dashboards' `nv_*` panels are re-pointed.
  - F-125: its readiness source, the gateway's health, keeps the same shape.
  - F-128: there is still no load API; the reason changes from Triton's control mode to the
    service having none.
- **Under either option:** OD-7's threat rows (F-010, F-036, F-220) follow OD-7, not this decision.

**Recommendation.** **Keep Triton now, and approve the Phase 4 measure-first package. Triton stays
unless the slim service matches it on latency and VRAM.** A ruling of "keep" alone would leave
that package unapproved, so this recommendation asks for both.

- Triton costs more than it serves today: two resident ONNX Runtime models (three with `threat`)
  carry a full Triton image, the export toolchain and three start-up steps.
- But B2.2 is about to rely on its GPU rate limiting, and on its batching across concurrent events:
  `/person-reid` takes one crop per request (`ai/gateway/adapters/enrichment_light.py:172`). And
  B2.2's parity gate is written against the gateway path.
- A replacement decided before those numbers exist would be a guess. The Phase 4 package measures
  per-request latency, VRAM and image size for both servers with the same ONNX files, and the
  slim service replaces Triton only if it matches on latency and VRAM.

**Ruling:**

## 2b. Docs-lane rulings (`W2.2`)

### OD-33 — one home for future plans and specs

**The question** (`40-docs.md` W2.2): VSS material is split across `docs/plans/`,
`docs/superpowers/` and `docs/vss-integration/` today. Where do future plans and specs go?

**Facts.** `git ls-files docs/plans/ docs/superpowers/ docs/vss-integration/` — all extensions; an
`--include='*.md'` variant loses 2 `.json` design files and reports 91 files / 56 dated, which is the
wrong census: `docs/plans/` **93** files (**57** dated-named, span 2025-01-23 → 2026-10-04 — still
live: the AGENTS.md validator's own design doc lives here); `docs/superpowers/` **37** files, ALL
dated, span 2026-09-12 → 2026-10-07 (the VSS specs — the tree the programme is actively writing into);
`docs/vss-integration/` **26** files (5 dated; the register and its companions). None of the three
trees appears in `mkdocs.yml`'s nav — 0 explicit entries each, which is what the draft said and is true
of the nav, and the built site agrees: `uv run mkdocs build --site-dir <tmp>` at this head emits 601
pages (600 `index.html` + Material's `404.html`) — 600/599 at every revision before the `2a558bdb`
merge, which added one nav entry and moved the pair — and **none of the 601
carries a nav link into the three trees** (parsed `<a … md-nav__link …>` tags quote-agnostically —
`minify` strips the quotes, so a `href="…"` regex matches nothing; the home page runs 149 such links
at this head (148 before the merge), the busiest page 317 (was 316 — same system-ops page, and the
delta is the one new nav entry, which every page's sidebar carries); counting the raw string
`md-nav__link` over-counts because Material puts it on
`<label>`s too, and an earlier revision of this sheet quoted one such count, "296", as if it were a
page property — it is neither rerunnable nor stable across pages) — but the draft's "(0 entries
each)" invites the inference that these trees are not on the site, and they are: **154 pages built and
URL-reachable**, `site/plans/` 91 + `site/superpowers/` 37 + `site/vss-integration/` 26, because
`mkdocs.yml` loads `awesome-pages` and there are zero `.pages`
files repo-wide to exclude anything. So "not in the nav" is not "not published" — it is published
unlinked — which is what `W3.3` (rebuild the nav to cover every living doc) actually has to fix, and it
constrains any freeze rule phrased in terms of the nav. A move is citation-cheap in one direction and
expensive in the other. Files _outside_ the cited tree that name it, one rule stated as a command:
`git grep -l -- '<tree>/' -- '**/AGENTS.md' 'AGENTS.md'` for the AGENTS column, and `git grep -l --
'<tree>/' -- '*.md' ':(exclude)<tree>/' ':(exclude)docs/uplevel/r2-sheet.md'
':(exclude,glob)**/AGENTS.md'` for the docs column (this sheet excludes itself — its mentions are this
ruling's subject text, not a path to re-aim; the template's one mention of `docs/vss-integration/` at
line 51 is an instruction that a move would have to re-aim, so it counts). Result at both the first
measured commit and this one: **11 / 12 / 1** `AGENTS.md` and **44 / 36 / 32** other docs. Per-tree
counts overstate: **136** mentions across **104 distinct files** — the double-count is 32 entries from
**29 multi-tree citers** (28 docs + 1 `AGENTS.md` name two or three trees; 26 name two, 3 name all
three). What is being corrected, precisely, and by whom: the draft printed the columns **45 / 35 / 31**
and "~91 citing files", and the first re-measurement of this sheet replaced the 91 with "**135** mentions
across **97** distinct" plus a five-files-in-both-columns mechanism — while keeping the draft's columns
verbatim. Re-running that first correction's own commands at this commit shows they never reproduced
either — including the columns it kept: its census commands print **44 / 36 / 31** (verified at the
correction's own commit and at head), not the 45 / 35 / 31 it printed — the same whole-repo rule as
above, except it excluded this sheet by _basename_, and that basename exclusion silently dropped
`docs/uplevel/templates/r2-sheet.md` with it. The template is a real citer: line 51 instructs the
record PR to write rulings into `docs/vss-integration/17-action-plan.md`, so a move must re-aim it and
it belongs in the column. The printed 45 / 35 / 31 and the re-run's 44 / 36 / 31 agree in sum
(111) and disagree file by file (±1 twice, in opposite directions) — a reader checking the total would
never see the split; excluding by full path instead of basename gives the honest docs column, 44 / 36 /
**32**. And that correction's 97 silently mixed scopes — 23 `AGENTS.md` citers counted repo-wide + 74
docs citers counted only inside `docs scripts .github README.md` (23 + 74 = 97 exactly; 24 citers live
outside those search dirs). Its "five files sit in both columns" mechanism was real _for the draft's
grep_ — `--include='*.md'` matches `AGENTS.md` basenames, so
`docs/architecture`, `docs/benchmarks`, `docs/decisions`, `docs/synthbench` and `docs/vss-integration`
`/AGENTS.md` each land in both columns — an artifact of the instrument, not the repo; the rule above
splits columns by basename, so the overlap is 0 by construction. Counting every tracked `.md`
whole-repo, the citers outside the draft's docs-scope (`docs scripts .github README.md`) are **24** —
18 `AGENTS.md` files (root, `ai/`, `backend/`, `frontend/`, `synthbench/` subtrees) the draft's
repo-wide AGENTS grep already caught anyway, + the 6 doc files that sit **only** outside the 4 listed
paths: `.claude/skills/synthbench-generation/SKILL.md` and `reference.md`,
`ai/gateway/export/README.md`, `archive/wp25-feed/HANDOFF-WP43.md` and its
`memory/sandbox-recreate-vs-reboot.md`, `backend/tests/plugins/README.md`. (This clause said "the 6
doc files under the 4 paths it listed" — the inverse of what the enumeration shows: a path under
those 4 dirs is by definition inside the scope, so 6 files that all sit outside it cannot be "under"
them.) And **no CI gate would catch a mis-move**: the
level-1 citation job (`ci.yml:230` at this head — the step's name line; the draft cited `:229`, which
was never the name line at any measured commit: it was :225 at the draft (the first merge's +1 hunk
made it :226, this merge's +3/+1 hunks made it :230) and :229 sat inside the step's own run block,
4 lines below the name — so this cite is now correct for the first time, by re-anchoring, not drift;
the prose name + the step's `run:` block are the stable way to re-find it), "Docs citation existence")
validates citations _authored inside_
exactly `docs/decisions deployment getting-started operations ui` — 43 citations across all five, every
one ERR-free today — and of the citers **exactly 2 sit inside those five directories**
(`docs/decisions/2026-01-12-docs-reorganization-design.md`, `docs/decisions/AGENTS.md`); the other 102 of
104 are outside its reach. `docs/plans` itself carries **222 level-1 ERR
citations** (`python -m
scripts.validate_docs docs/plans --no-ast --no-code-match --no-cross-ref --no-staleness`; 385 checked,
163 OK), up from 216/169 at `1d847a6a` with **zero changed paths under `docs/plans/`** — the +6 came in
on a neighbour's merge (`O1.2` deleted `docker-compose.ghcr.yml`, cited by 7 files here, and shrank
`setup_lib/image_pull.py` 379 → 103 lines). So the decay is already running, ungated: the tree that
most needs consolidation is the one whose citations no gate watches. `docs/superpowers/` is citation-
gated by nothing but is the only tree with a uniform naming discipline (100% dated names).

**Options as the register states them.** (a) consolidate the three trees into one directory now;
(b) name one home for FUTURE material and freeze the others as history; (c) keep the split and
record each tree's role.

**Recommendation: (b)**, home = `docs/superpowers/<date>-<slug>/` — the discipline is already proven
there (37/37 dated names, current spans), it moves zero files, and it makes the freeze testable by eye:
a dated file outside `docs/superpowers/` after this ruling is the violation. (a) is the worst option on
the evidence: **104 citing files** to re-aim, of which a gate re-checks 2. One caveat so (b) is not
chosen for the wrong reason: moving nothing removes the _re-aim_ risk, not the _decay_ — the 222 rose
from 216 without an edit to `docs/plans`, when `O1.2` retired a file seven of them cite. (b) leaves
that ungated either way; closing it is a separate decision (extend the level-1 job's dir list, or gate
`docs/plans` on a no-new-ERR bar), and it is not what OD-33 is asking. Under (b), `docs/plans/` and
`docs/vss-integration/` stay where their citations point; `docs/vss-integration/` remains the
register's home (it is live, not history).

**Ruling:**

### OD-34 — the register's OD table and its closed issues

**The question** (`40-docs.md` W2.2): the register gains a ruling column — rulings are inline in the
options column today, "which is how three rulings were misread during the audit" — and closed issues
move to a history file.

**Facts.** `docs/vss-integration/17-action-plan.md` is **8,565 lines** (`wc -l` at this head — this
file's count has moved twice since the draft: 8,485 → 8,518 → 8,565, each move a merge of
`origin/main`, never an edit by this branch) — the plan text says
8,145, stale by **420** lines, about one Phase 1's growth (the first merge added 44 lines and removed 11
per `git diff --numstat`; the second brought +47/−0 in two hunks, +36 at 708 and +11 at 3232, from
`B1.2`'s replay-parity material). The plan-text edit belongs in whichever PR touches it first, or the owner's
next plan edit. Its OD table has **32 rows** (`grep -cE '^\| *OD-[0-9]+'`), 5 columns each.

**Where the rulings actually are.** **11 of the 32 rows record their ruling inside the options cell, and
they do it in three different markups** — which is the finding, and the argument for the column: **10
bolded** clauses, of which only 5 begin `**Ruled 2026…` (OD-3/12/15/20/28) while 5 use other wording
(OD-1 `**Follow-up scope ruled…**`, OD-8 `**Acceptance half ruled…**`, and OD-30/31/32 lowercase
`**ruled 2026-10-05 (a):**`), plus **1 unbolded** ruling at OD-29 (`ruled 2026-10-05 (a): the arm B
rubric text …`, plain text in the options cell). Even "which cell names the ruling" is not single-valued:
**5 of the 11 mention it in a second cell** — OD-1's Source is a pointer ("follow-up ruled in the
2026-10-05 Intake log"), OD-29's and OD-30's Source each read "owner ruling 2026-10-05, Intake log",
OD-30's Unblocks argues with it ("the ruling reached (c) only"), OD-31's Decision names "the same-day
smallest-slice ruling", and OD-31's and OD-32's Source each read "17 Intake log entry 2026-10-05".
(The first correction of this sentence said "2 of the 11", naming only OD-1's Source and OD-30's
Unblocks — it missed OD-29's and OD-32's Source pointers and both of OD-31's second cells.)
**1 more ruling, OD-24, exists nowhere in the table** —
only as an intake-log line ("OD-24 ruled by the owner [O]", L7197 at this head — the register's
internal line cites below moved +36 to +47 with the merge's two hunks, re-anchored here); that is the _only_ log-only ruling,
and 3 rows (OD-1/31/32) carry an explicit "(Intake log entry 2026-10-05)" pointer — OD-1's **from the
options cell**, OD-31's and OD-32's **from the Source cell**. An earlier draft of this row said "7 bolded rulings, 5 more only in the intake log"; both halves
were wrong, and wrong in the instructive way. The 7 came from one grep vocabulary
(`**Ruled` + `**Both floors` + `**Follow-up scope ruled`), which **misses 5 real rulings** (OD-8,
OD-29/30/31/32 — casing and wording variance, exactly the misreading hazard the package text cites)
**and includes 1 non-ruling**: OD-2's bold clause is "**Both floors are measured as of 2026-10-05**",
and OD-5's says out loud "**Input landed 2026-10-05, not a ruling:**". The "5 more in the intake log"
were the `Ruled 2026` grep hits at lines 578–603 (unchanged at this head — both incoming hunks land
below 707) — those lines are _inside_ §4's own table (OD-3/12/15/
20/28), a strict subset of the 7 already counted, and the Intake log (`## Intake log`, line 7143 at
this head, 7096 before the merge — it is
unnumbered; §5 is "The register", at 744, was 708) contains **0** occurrences of that string. So the corrected
total is **12 ruled decisions across table and log**, of which 11 are in the table in 3 markups and 1 is
log-only. No grep returns those 12 as a clean set — that is the machine-checkable form of "three rulings
were misread during the audit": `Ruled 2026` finds **5** and misses 6 of the 11 table rows (7 of the
full 12 — OD-24 is log-only); a bold-clause grep returns **12
rows** of which only **10** are rulings (it wrongly takes in OD-2 and OD-5, and still misses the unbolded
OD-29); case-insensitive `[Rr]uled` catches all 11 table rows but adds OD-5's disclaimer and, in the log,
surfaces OD-24 only as one of 22 log lines that use the word at all.

The register's own status vocabulary (§1) already requires a dated closure note and says "A closed issue
is never deleted" — so a history-file move conflicts with the file's stated doctrine unless the moved
line leaves a dated pointer in place. The
OD table is 5 columns × 32 rows: a 6th "ruling" column re-lays in one mechanical commit.

**Options.** (a) as the package text proposes: ruling column + closed issues to a history file;
(b) ruling column only, closed issues stay; (c) status quo, fix the reading discipline instead.

**Recommendation: (a) with one amendment** — the history file keeps the text (so "never deleted"
survives) but every moved issue leaves a one-line dated pointer at its original position, matching
the register's existing closure-note convention; the ruling column is the part the misreading hazard
actually justifies, and it converts **12 ruled decisions in 3 markups** (10 bold + OD-29 unbolded +
OD-24 log-only) into one column that greps. Cost, measured, and it is not the zero-cost edit the draft
implied: the re-lay itself is one mechanical commit (5→6 columns × 32 rows), but **the extraction cannot
be a grep** — the draft's own vocabulary misses 5 of the 11 table rulings and a bold-only read misses
OD-29, so populating the column honestly costs a human read of all 32 rows plus one log-only ruling
(OD-24) recovered from §Intake log. Budget that read; do not let the history-file half block the column
half — they are separable commits.

**Ruling:**

### OD-35 — the 26 image-(re)validation plans: history or gone

**The question** (`40-docs.md` W2.2): whether the near-identical `docs/plans/image-(re)validation-*`
plans stay as history or go.

**Facts.** The plan text says 28; **the tree holds 26** (`git ls-files 'docs/plans/image-validation-*' 'docs/plans/image-revalidation-*'` — two pathspecs; the single quoted argument `'…-* …-*'` the draft transcribed matches nothing and returns **0**): 12 `image-revalidation-*` + 14 `image-validation-*`, both families dated
2026-01-24 — **all 26 carry that date in their first 15 lines**, which is the provenance fact that
matters, and it is uniform. What is _not_ uniform is the field name: **8 header shapes** across the 26
(`**Validation Date:**` 7, `**Revalidation Date:**` 5, `**Generated:**` 5, `**Date:**` 4, a quoted
`> Generated:` 2, `**Date**:` 2, `**Original Validation Date:**` and `**Re-Validation Date:**` 1 each —
27 lines over 26 files — the double is `image-revalidation-api-reference.md`, which carries
`**Revalidation Date:**` alongside `**Original Validation Date:**` (`**Re-Validation Date:**` is unique
to `image-revalidation-observability.md`; the first correction of this row said api-reference "carries
both of the last two", misidentifying the pair while keeping the 27/26 total it explained),
and validator attribution is a minority header — only **9/26** name Claude Opus 4.5 at all, split four
ways: `**Validator:**` 3, a quoted `> Validator:` 2, `**Reviewer:**` 2, `**Reviewer**:` 2 (note the
field role varies — 4 files call the model the _reviewer_, not the validator). An earlier draft of this
row said each file _begins_
"Generated: 2026-01-24 / Validator: Claude Opus 4.5"; that adjacent pair exists in exactly **2 of 26**
(both named `data-model`, at lines 3–4) — a generalisation from the two files the draft opened, not a
family property. Sizes vary far more than the draft's "~200–250 lines each": **median 315.5 (the 13th
and 14th files run 313 and 318), range 156–546** (`image-revalidation-observability.md` 156 →
`image-validation-security.md` 546), and only **7 of 26** fall in that band. (The first re-measurement
printed "median 315" here, which is no median at all — the probe took the mean of the two middle files,
315.5, and `int()` truncated it. Same lesson as the census: a printed statistic inherits its
instrument's arithmetic, and `int()` is an arithmetic.) Coverage is roughly one per architecture area, not exactly one: 10 validation files and 11
revalidation files each name a distinct `docs/architecture/<area>/`, and the two families' sets are
**one apart, not identical** — the revalidation half also names `data-model`, because
`image-revalidation-data-model.md` points at `docs/architecture/data-model/` while its validation twin
points at the _image_ tree it audited (`docs/images/architecture/data-model/`); all 11 directories are
still on disk. The other 5 name no `docs/architecture/<area>/` at all: validation `data-model` and
`dataflows` (whose headers point at the `docs/images/architecture/` image tree they audited —
`dataflows` and validation `security` are the two files carrying `**Hub:**`), validation `security`
(whose `**Hub:**` is the bare word "Security"), and `detection-pipeline` on **both** sides (neither
names any path). (The first corrections of this passage said "the two
families name the same 10 areas (identical sets)" and "the other 6 … carry `**Hub:**` instead" — the
residue is 5 files, not 6, only 2 carry `**Hub:**`, and the count was off because
`image-revalidation-data-model.md` was sitting in the residue list while naming an area directory.)
So 26 files cover ~11 architecture areas almost twice over — the positive form of "the same audit run
twice", not 26 distinct audits.
The cross-cites run **one way**: 8 of the 12 revalidation files name an `image-validation-*` sibling by
exact stem (0 the other way — the validation half never mentions the revalidation half), 9 such
occurrences in total across the family. **Zero `AGENTS.md` files cite them** (`git grep -lE
'image-(re)?validation-' -- '**/AGENTS.md' 'AGENTS.md'` → no hits) and they sit outside every CI
citation gate (OD-33 facts). Outside the family, **2 files mention it and neither is a re-aimable path**
(a third, this sheet, names the family as its own subject and is not a referrer to re-aim):
`docs/uplevel/40-docs.md:156` says "image-validation plans." in prose (cited as `:176` before the
merge — W2.1's rewrite of that file moved the line, not the mention),
and `docs/plans/2026-09-22-docs-scan-findings.md:311` records them as an audit finding — "other
image-validation-* and image-revalidation-_ (14 files)" — which is a _record of what that audit saw_,
so re-aiming it would falsify it. The draft's "2 external referrers to re-aim" was a file count of
those two prose mentions, not a citation count; the real re-aim surface is the 9 intra-family
occurrences.

**The archive destination is already ruled out.** An earlier draft of this row recommended moving the
family to `docs/archive/`, citing it as "the in-repo precedent for retired docs material", already in
the validator's `no_agents_md_required` list. Both halves were true at the measured commit and are
foreclosed by a standing ruling the draft had not read: **UR-19** (`docs/uplevel/README.md`) is
"`archive/` and `docs/archive/` are deleted … git history is not rewritten", **`O1.5`** (
`30-ops.md:125-137`) executes it — "`git rm -r archive docs/archive`. Remove the archive excludes from
… `.agents-md-validator.yml`" — and its status row is still `not started` (`README.md:246` at this
head, :243 before the merge — the table shifted, the row did not). README's
"Considered and rejected" table then rejects this row's exact move: "Moving dead code into `archive/` |
relocates sediment; git history already keeps every deleted file | UR-19". Recommending it again would
be reopening a settled ruling inside a ruling request. UR-19's stated reason is also the direct answer
to this row's own argument against deletion — "git history already keeps every deleted file" is why
deleting the family does not throw away the record. (The `no_agents_md_required` fact the draft leaned
on does no work either way: `check_missing_agents_md` fires on directories holding ≥`min_code_files: 2`
files matching `code_extensions` — `.md` is not among them — so 26 markdown files could not trip
`missing_agents_md` wherever they sat. Its `≥2` test lives at `agents_md_validator.py:702` at this
head (the draft's :619, moved by W2.1's +186/−6 growth of the validator), not in
`find_directories_with_code`.)

**Options.** (a) keep in place as history; (b) delete. (The archive move is not on the list because
UR-19 removed its destination.)

**Recommendation: (b) delete.** They are one-run audit outputs, not plans, and they sit in the tree the
programme reads as live plans: 26 files / 8,314 lines, ~11 architecture areas almost twice over (the
Facts above said ~10/twice until the fourth round fixed the area-set measurement — the recommendation
had kept the stale figure). Under
OD-33's (b) `docs/plans/` freezes as history either way, so (a) is coherent rather than wrong — choose
(a) if the January findings are still being consulted. Delete is recommended because the cost of (b) is
near zero and the cost of (a) is permanent: 9 intra-family occurrences to clear, no path citations
outside the family to re-aim, no gate to satisfy and no AGENTS.md consequence either way (above). The
gate claim is measured, not inferred: the only files mentioning the family are two prose mentions plus
this sheet, and **none of the five gate-validated directories mentions it at all** — so deleting the 26
files breaks zero citations in a gated tree. `git rm -r` of the two pathspecs keeps the record
recoverable, which is UR-19's own doctrine — and unlike the draft's version, this recommendation needs
no `validate_docs` before/after ERR-delta ritual, for that measured reason. If the owner rules (a), the
row's answer to "then what marks them as dead?" is OD-33's freeze rule, not a new file.

**Ruling:**

---

_Fill order for the owner: these three are Phase 2 `W2.2` rows; `R2` rules them in the same session
as the feature rows. The frontend lane's record PR copies each ruling into_
`docs/vss-integration/17-action-plan.md` _per the template's §4 — `OD-33/34/35` are new numbers and
the register has no rows for them yet, so the record step ADDS those three rows, it does not edit
existing ones._

## 3. Modules serving no feature

### Frontend

The inventory's §4: 136 production files under `frontend/src/` that `src/main.tsx` cannot reach
(37583 lines), which no row claims — listed with lines and last meaningful commit in
[`feature-inventory.md` §4](../reference/feature-inventory.md#4-modules-serving-no-feature). Its §5
adds the client requests only dead code sends (77). `F3.2` deletes both, with the tests that test
only them.

### Python

<!-- r2-python-dead-list:start -->
Measured at tool-inputs `d1dbe9d14c` from the fixed tool (`scripts/reachability.py` after the O2.3b ancestor fix, ruling 73): 157 non-shipping Python modules (60798 lines), listed with lines and last meaningful commit in [`feature-inventory.md` §4](../reference/feature-inventory.md#4-modules-serving-no-feature), Python. The 6 modules a row claims are named as exceptions there — `backend/services/calibration_service.py` (F-131); `backend/services/camera_status_service.py` (F-029); `backend/services/mqtt_client.py` (F-291); `backend/services/mqtt_command_handler.py` (F-291); `backend/services/scene_change_detector.py` (F-208/F-287); `backend/services/unified_embedding_service.py` (F-272). The ancestor-rule note for the ruling: parent packages of shipping modules ship (import runs them), so the list cannot be the pre-O2.3b count; regenerating it is `scripts/r2-python-dead-list.py`.
<!-- r2-python-dead-list:end -->

Ruling: approve the list for deletion as a whole, naming any exceptions and why.

**Ruling:**

## 4. After the session

The frontend lane's record PR copies each ruling and priority into the inventory, writes the OD
rulings into `docs/vss-integration/17-action-plan.md`, and sets `R2` to `done`. `OD-36`, `OD-37` and `OD-38` (ruling 62) are new numbers with no register rows yet: the record PR
adds them, as it does `OD-33`…`OD-35`. `OD-39` (ruling 67) is new in the same way. The next
free number is `OD-40`.

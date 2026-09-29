VSS R8 RETIREMENT — delete the legacy LLM/AI paths; ONE pipeline: VLM +
specialists. READ docs/plans/2026-09-28-r8-legacy-retirement-scope.md FIRST
(that doc is EVIDENCE, this is ORDER).
L=docs/plans/2026-09-23-vss-gaming-gpu-ledger.md: every slice gets an L row
(command+result+commit). Keep every evidence marker.

SETUP. Branch chore/r8-legacy-retirement off main; PR #6698 is MERGED — no
work there. `origin` is a dead path — use remote github; gh --repo
mikesvoboda/nemotron-v3-home-security-intelligence. NO A5500; repo + GB300
only.

R8=docs/vss-integration/12-postponed-roadmap.md:23 and §R8:108 ARE the
authorized scope (trigger reversed by owner). Per :10: open
docs/superpowers/specs/2026-09-28-r8-legacy-retirement-design.md
(What-goes/What-stays), mark R8 in 12 with date+link. NO impl-plan doc — spec
and L rows ARE the plan of record.

S0 Currency, ship ALONE: dated banners over docs/vss-integration/README.md:6 +
AGENTS.md:6 ("nothing implemented yet" — FALSE since 4bfd6fa4) +
00-context.md:5, form per 06-repo-a-readiness.md:11. Never rewrite frozen
prose or a spec's Status/rev.

S1 HARD RAISE (owner 2026-09-29: no back-compat). config.py:1084-1090 only
WARNS — a stale .env still boots it. Anything but "vlm" RAISES, then delete
every branch. Enumerate by the WIDE grep ('"legacy"' backend non-test = 13);
the narrow pipeline_mode grep returns 7 and MISSES pipeline_factory.py:52
(local var). Red-first: test "legacy" RAISES + grep-gate the COMPARISON, not
the string (config's raise text holds the word — a bare grep can't be empty).

S2 EXTRACT-THEN-DELETE: nemotron_analyzer.py (5,429 L) ~98% legacy but
:294-411 is imported by THE VLM PATH — hoist to
services/constrained_decoding.py, repoint its 4 importers FIRST. The
enrichment tier retires with it (container.py:508 gates it on legacy; 19/22
loaders go, the 3 VLM loaders plus model_loader_base stay — scope §4a). Edit
services/`__init__.py:95,245` BEFORE the rm.

S3 Retire ONE ai_contract provider per slice (PR-gated); never rm -rf an ai/
dir. Triton's shipped set is yolo26+reid only (residency.py:65): prune the 11
legacy FULL_MODEL_SET models, KEEP yolo26/reid/threat or S1's PASS is void.

S4 No alembic (schema = init_schema.py): a table retires = delete model class
and dated DROP SQL in docs/api/migrations/. threat_detections STAYS. Trap:
household.py:155 PersonEmbedding is LIVE while enrichment.py reid_embeddings
is legacy.

S5 R8:108's frontend panels are real (EnrichmentViewer/Badges/Panel,
EventEnrichmentSummary, poseVisualization.ts) — delete with their tables. Fix
the docs (scope §9), drive to green, report ONCE.

MINES: clear `__pycache__` before any deletion guard (R8:118). Coverage =
merged floors 84 unit / 37 integration (ci.yml:613, :1215), not pyproject 85 —
report direction, never lower. ~96 legacy test files go with their module, ~61
EDIT; deleting them moves the suppression census (ci.yml:101-104) —
regenerate, never hand-edit. 66/96 error at import here (no cv2) — judge by
CI. Frontend is frontend/, NOT src/frontend/.

DONE: no code compares pipeline_mode to legacy; "legacy" RAISES; no ai-llm in
any compose; ai_contract green; DROP SQL dated; threat_detections and
PersonEmbedding importing; constrained_decoding.py used by VLM;
README:6/AGENTS:6 fixed; R8 marked and spec exists; one L row per slice; CI
Gate green; +/- and coverage direction.

STOP AND ASK: the vlm Triton set or re-ID/face tables; threat_detections; any
ai_contract provider-row delete; models.yml delete vs enabled:false; R8's
reach into ai/enrichment providers; `full` for dev; coverage pressure;
anything needing the A5500. RESOLVED: legacy HARD-RAISES; enrichment tier
retires (container.py:508 gates it on legacy).

HARD RULES. TDD red-first, one slice one PR. Never --no-verify or SKIP=. Never
lower a floor or widen a quarantine. podman not docker. integration -n0. Do
NOT delete notification_filter.py:35 should_notify (unwired M1 gap, separate
job).

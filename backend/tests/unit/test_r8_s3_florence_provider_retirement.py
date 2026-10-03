"""R8 slice S3: the Florence provider retires, the Triton repository prunes to
the shipped set, and GATEWAY_MODEL_SET hard-raises. ABOUTME: this file is S3's
red-first guard -- it pins the END STATE the owner's five rulings of 2026-09-29
mandate, written (and proven red) BEFORE any deletion, per the goal prompt's
"TDD red-first" hard rule.

The five owner rulings this file encodes:

  1. Florence is THE S3 provider -- its provider row, client module, gateway
     adapter, serving dir and Triton dir retire here. Ruling 1 originally
     deferred CLIP and the enrichment providers to their own PR-gated slices;
     ruling 5 overrides that for CLIP (see below) -- "one provider per slice"
     still governs what was NEVER a ruling-5 consequence.
  2. models.yml: the legacy rows are DELETED (owner override of the evidence
     doc's enabled:false provenance default; provenance lives in git + ledger).
  3. GATEWAY_MODEL_SET: hard-raise -- unset, unknown and ``full`` ALL raise at
     container start, the same doctrine as S1's PIPELINE_MODE raise.
  4. R8's reach: ALL retired serving dirs are swept -- ``ai/florence``,
     ``ai/clip``, ``ai/enrichment``, ``ai/enrichment-light`` -- via ``git rm``,
     never ``rm -rf``.
  5. (Owner answer, this session, to the collision rulings 1 x 3 x 4 create:
     the goal prompt's "KEEP yolo26/reid/threat" arithmetic prunes ``clip``/
     ``clip_text``, which makes gateway CLIP unbootable, so CLIP's row could
     no longer register non-vacuously.) PRUNE TO 3 -- CLIP's whole surface
     retires in S3 as a PRUNE CONSEQUENCE: Triton clip/clip_text, adapters/
     clip.py, the clip_* ops, ``CLIPClient``, ``clip_url`` and the debug
     endpoint /api/face-events/compare (its only consumer, frontend hook
     measured at useFaceRecognitionApi.ts:700, which returns the endpoint's
     own error payload). The enrichment provider rows were ALREADY NOT-WIRED
     since S2b and stay paper until S4/S5; only their pruned-model OPS die
     here.

The boundary ruling 5 draws, and the most likely place a reader would
"fix" this file: ops die with their MODELS (the prune reaches any route whose
model cannot boot -- clip_*, enrichment_*, the enrich_lt_* trio on pruned
models, and the per_model_server management ops, whose sole schema/evidence
site is the swept ai/enrichment/model.py); provider ROWS die only when their
whole surface is unreachable (Florence by ruling 1; CLIP by ruling 5) or were
already unwired (enrichment, since S2b). What stays registered is the honest
shipped set: yolo26_detect/_batch/segment, enrich_lt_person_reid,
enrich_lt_threat_detect, llm_completion, llm_chat_completion, llm_slots,
vlm_assess.

Why pins rather than greps, per this repo's recurring lesson: prose is allowed
to name the dead. Every "X is gone" check reads source TEXT for LIVE forms only
(imports, registrations, mounted routes, settings fields, env assignments) or
uses import failure, so a tombstone comment cannot fail this file -- and every
scan pins its own non-vacuity (the S2b compose-vacuity lesson: a test iterating
a deleted thing passes happily on an empty list).

Negative space: this file does not re-prove the VLM path works (S2b's
startup-gate pins and the contract tier's ``-n0`` run do that), and it asserts
nothing about re-ID/face/plate TABLES -- those are DB lookups the VLM path
keeps, and their storage side is S4's.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

# The 11 models the goal prompt orders pruned from FULL_MODEL_SET. KEEP is
# yolo26/reid/threat "or S1's PASS is void".
PRUNED_MODELS = [
    "clip",
    "clip_text",
    "florence2",
    "vehicle",
    "fashion_clip",
    "demographics_age",
    "demographics_gender",
    "pet",
    "depth",
    "pose",
    "stgcn_action",
]
KEPT_MODELS = ["yolo26", "reid", "threat"]

# Ruling 4's sweep targets: the standalone per-model serving dirs, already out
# of every compose file since S2b.
RETIRED_SERVING_DIRS = ["ai/florence", "ai/clip", "ai/enrichment", "ai/enrichment-light"]

# The nine gateway-derived florence ops. Measured pre-slice from operations.py:
# the generator derives gateway ops by walking ``router.routes``, so removing
# the adapter's mount is what removes the rows -- this list is the ratchet's
# expected content, not a hand-edit of the registry.
FLORENCE_OP_IDS = [
    "florence_batch_extract",
    "florence_dense_caption",
    "florence_describe_region",
    "florence_detect",
    "florence_detect_security_objects",
    "florence_extract",
    "florence_ocr",
    "florence_ocr_with_regions",
    "florence_phrase_grounding",
]

# Ruling 5: CLIP's five gateway ops retire with their pruned models.
CLIP_OP_IDS = [
    "clip_anomaly_score",
    "clip_batch_similarity",
    "clip_classify",
    "clip_embed",
    "clip_similarity",
]

# Prune consequences: ops whose only serveable route calls a pruned model.
# enrichment_* (8): adapter routes onto vehicle/fashion_clip/demographics_*/
# pet/depth/pose/stgcn_action. The enrich_lt_* trio whose models are pruned
# (pose/pet/depth); its person_reid and threat_detect routes stay (kept dirs).
# model_preload/_status/_unload + object_distance (4): per_model_server ops
# whose only schema and evidence site is the swept ai/enrichment/model.py.
PRUNED_MODEL_OP_IDS = [
    "enrichment_action_classify",
    "enrichment_clothing_classify",
    "enrichment_demographics",
    "enrichment_depth_estimate",
    "enrichment_enrich",
    "enrichment_pet_classify",
    "enrichment_pose_analyze",
    "enrichment_vehicle_classify",
    "enrich_lt_depth_estimate",
    "enrich_lt_pet_classify",
    "enrich_lt_pose_analyze",
    "model_preload",
    "model_status",
    "model_unload",
    "object_distance",
]

# The honest shipped set after the prune. Measured pre-slice from the
# availability columns (38 ops today -> 9): what the gateway + light adapter +
# llamacpp + VLM-engine providers can still register from dirs that exist.
SURVIVING_OP_IDS = [
    "yolo26_detect",
    "yolo26_detect_batch",
    "yolo26_segment",
    "enrich_lt_person_reid",
    "enrich_lt_threat_detect",
    "llm_completion",
    "llm_chat_completion",
    "llm_slots",
    "vlm_assess",
]


def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603 - argv is a literal list, never a shell string
        ["git", *args],  # noqa: S607 - git on PATH is the repo's own convention (setup.py:1155)
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    ).stdout


class TestS3SurfaceIsRealBeforeItIsGone:
    """Vacuity guard, written FIRST. Every absence pin below only means
    something if the surface it scans exists and is non-empty on BOTH sides of
    the change. S2b's compose pins learned this the hard way:
    ``services.get(name, {}) == {}`` passes a parametrized absence test for a
    service nobody checked."""

    def test_the_contract_surface_is_nonempty(self) -> None:
        """The `> 20` floor this carried was written against the 38-op tree and
        S3 makes it unsatisfiable: the honest shipped set is NINE ops after two
        providers retire and twelve models are pruned, and the way to pass a
        floor written for a bigger world is never to inflate the registry. What
        the floor was FOR is restated structurally, derived, and it is a
        stronger claim than the count was:
          * the registry is non-empty and the fake's SPEC column equals it (a
            fake that dropped ops would make every fake-side absence pin
            vacuous -- the S2b compose lesson this class names);
          * every live slot column resolves at least one op (a pruned-to-empty
            column registers vacuously -- see test_every_provider_slot_is_still_populated);
          * at least one op still carries a real client binding (an all-
            sentinel registry is the decorative-contract mode, and the two
            bindings are the shipped VLM + detector paths).
        The exact membership is pinned by name in
        test_every_provider_slot_is_still_populated, which is where a count
        belongs: as a set equality against SURVIVING_OP_IDS, not a magnitude."""
        from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
        from backend.ai_contract.provider import (
            PROVIDER_SLOT,
            operations_for_slot,
            registered_providers,
        )

        assert OPERATION_IDS, "op registry empty; absence pins below are theatre"
        assert set(operations_for_slot("fake", OPERATIONS)) == set(OPERATION_IDS), (
            "the fake's spec column no longer covers the registry"
        )
        assert registered_providers(), "provider registry empty"
        for slot in PROVIDER_SLOT.values():
            if slot == "fake":
                continue
            assert operations_for_slot(slot, OPERATIONS), f"slot {slot!r} is empty"
        bound = {oid for oid, op in OPERATIONS.items() if op.client_methods}
        assert bound, "no op has a client binding -- the registry is decorative"

    def test_the_florence_surface_the_slice_removes_is_measurable_now(self) -> None:
        """The red-side witness. On the pre-retirement tree this MUST pass (the
        surface exists); after the slice it asserts the same surface is gone. A
        pin that cannot observe the thing it removes is the vacuity failure
        S2b's compose pins made real, so the two halves are named."""
        from backend.ai_contract.operations import OPERATION_IDS

        florence = sorted(i for i in OPERATION_IDS if i.startswith("florence_"))
        module_exists = (REPO_ROOT / "backend/services/florence_client.py").exists()
        row_exists = '"FlorenceClient"' in _src("backend/ai_contract/providers.py")
        if module_exists or row_exists:
            assert len(florence) == 9, (
                f"the client module/provider row is still wired but the op set "
                f"is {len(florence)} ({florence}) -- the slice is half-done, not done"
            )
        else:
            assert florence == [], f"provider retired but ops survive: {florence}"


class TestFlorenceProviderRowRetired:
    """Ruling 1: the ONE provider this slice retires."""

    def test_client_module_is_gone(self) -> None:
        assert not (REPO_ROOT / "backend/services/florence_client.py").exists()
        importlib.invalidate_caches()
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("backend.services.florence_client")

    def test_providers_map_no_longer_names_the_client(self) -> None:
        src = _src("backend/ai_contract/providers.py")
        assert '"FlorenceClient"' not in src
        # Ruling 5: CLIP's row goes too (its models are pruned, so its ops
        # cannot register non-vacuously). The survivors are the two clients
        # whose backends still boot.
        assert '"CLIPClient"' not in src
        for survivor in ('"DetectorClient"', '"VlmClient"'):
            assert survivor in src, survivor

    def test_registry_carries_no_florence_operations(self) -> None:
        from backend.ai_contract.operations import OPERATION_IDS

        florence = sorted(i for i in OPERATION_IDS if i.startswith("florence_"))
        assert florence == [], f"florence ops still registered: {florence}"
        # Non-vacuity: the registry did not collapse with them.
        assert any(i.startswith("yolo26") for i in OPERATION_IDS)
        assert "vlm_assess" in OPERATION_IDS

    def test_every_provider_slot_is_still_populated(self) -> None:
        """Ruling 5's arithmetic check, and the reason this slice cannot
        half-delete a provider. ``register_provider`` verifies the callable set
        EXACTLY equals ``required`` (default: the whole slot column), so a slot
        pruned to empty would register VACUOUSLY -- a deployed provider that
        declares nothing, the decorative-contract failure mode this registry
        exists to refuse. Measured pre-slice: 38 ops. After S3 the honest
        shipped set is the nine below, and every live provider still resolves
        at least one op from a dir that exists."""
        from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
        from backend.ai_contract.provider import PROVIDER_SLOT, operations_for_slot

        assert sorted(OPERATION_IDS) == sorted(SURVIVING_OP_IDS), (
            f"S3's surviving set is {sorted(SURVIVING_OP_IDS)}; found {sorted(OPERATION_IDS)}"
        )
        live_slot_providers = {
            "gateway": [
                "yolo26_detect",
                "yolo26_detect_batch",
                "yolo26_segment",
                "enrich_lt_person_reid",
                "enrich_lt_threat_detect",
            ],
            "enrichment_light_adapter": ["enrich_lt_person_reid", "enrich_lt_threat_detect"],
            "per_model_server": [
                "yolo26_detect",
                "yolo26_detect_batch",
                "enrich_lt_person_reid",
                "enrich_lt_threat_detect",
                "llm_completion",
                "llm_chat_completion",
                "vlm_assess",
            ],
        }
        for slot, expected in live_slot_providers.items():
            got = sorted(operations_for_slot(slot, OPERATIONS))
            assert got == sorted(expected), f"slot {slot!r}: {got}"
        assert PROVIDER_SLOT, "provider/slot map itself is gone (vacuity)"

    def test_generated_schemas_dropped_with_the_operations(self) -> None:
        schema_dir = REPO_ROOT / "backend/ai_contract/schemas"
        leftovers = sorted(p.name for p in schema_dir.glob("florence_*.json"))
        assert leftovers == [], f"orphan schema files: {leftovers}"
        assert any(schema_dir.glob("yolo26_*.json")), "schema dir lost the survivors too"

    def test_ratchet_adopts_all_nine_op_ids(self) -> None:
        """The WP7.3 deleted-op ratchet must adopt every retired id, so an
        adapter-route resurrection reddens BY NAME (the A7.2
        florence_analyze_scene precedent: the generator rediscovers gateway
        ops by walking router.routes, so a kept row can come back silently)."""
        src = _src("backend/tests/contracts/ai_providers/test_ai_contract_registry.py")
        missing = [o for o in FLORENCE_OP_IDS if f'"{o}"' not in src]
        assert missing == [], f"ops not adopted by DELETED_REGISTRY_OPS: {missing}"

    def test_adapter_module_is_gone(self) -> None:
        assert not (REPO_ROOT / "ai/gateway/adapters/florence.py").exists()
        importlib.invalidate_caches()
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("ai.gateway.adapters.florence")

    def test_gateway_main_no_longer_mounts_florence(self) -> None:
        src = _src("ai/gateway/main.py")
        assert "adapters.florence" not in src
        assert "florence_router" not in src
        assert '"/florence"' not in src
        # Ruling 5: the clip and heavy-enrichment mounts die the same way (their
        # routers' models are pruned; the enrichment light lane survives).
        assert "adapters.clip" not in src
        assert "clip_router" not in src
        assert '"/clip"' not in src
        assert "adapters.enrichment import" not in src
        assert '"/enrichment"' not in src
        # The surviving mounts stay (vacuity):
        assert '"/yolo26"' in src
        assert '"/enrich-lt"' in src

    def test_settings_fields_follow_their_retired_surface(self) -> None:
        """florence_url, clip_url and enrichment_url each die with the surface
        that read them (rulings 1 + 5): the florence client, the clip client,
        and -- for enrichment_url -- model_management's heavy lane, whose
        membership was already EMPTY since S2 (HEAVY_MODELS = frozenset(),
        measured pre-slice). enrichment_light_url SURVIVES: it is the live
        light lane's URL. Deleting a field whose consumer still ships is the
        pointer-at-nothing error; keeping a field whose every consumer is gone
        is the decorative-config mirror of it."""
        cfg = _src("backend/core/config.py")
        for gone in ("florence_url", "clip_url", "enrichment_url"):
            assert f"{gone}: str" not in cfg, f"the settings field still ships: {gone}"
            assert f'"{gone}"' not in cfg, f"still named in the validator tuple: {gone}"
        assert "enrichment_light_url: str" in cfg, "the light lane is the shipped surface"
        assert '"enrichment_light_url"' in cfg, "the validator must still validate it"
        # The validator itself survives for the remaining vision URLs:
        assert "validate_vision_service_urls" in cfg

    def test_health_and_system_probe_rows_retire_in_the_data(self) -> None:
        """The S2b precedent: a retired service's health row is replaced IN THE
        DATA, not left to probe a URL that no longer exists (the vacuity half
        of Compose Security's lesson -- a probe row for a retired service is a
        green assertion about nothing). Ruling 5 retires the florence, clip and
        enrichment rows -- all three probed URLs whose services cannot boot."""
        for rel in ("backend/api/routes/health_ai_services.py", "backend/api/routes/system.py"):
            src = _src(rel)
            for gone in ('"florence_url"', '"clip_url"', '"enrichment_url"'):
                assert gone not in src, f"{rel} still probes {gone}"
        # Survivors keep probing (vacuity):
        assert '"ai_vlm_url"' in _src("backend/api/routes/health_ai_services.py")

    def test_env_and_compose_stop_injecting_the_url(self) -> None:
        """Assignment lines only -- a ``#`` comment naming FLORENCE_URL is
        prose and prose is allowed to name the dead.

        ``setup.py`` is in the list because it GENERATES the operator's ``.env``
        from a Python string list, so its assignments arrive quoted rather than
        bare; the leading quote is stripped before the match or the scan would
        pass while the setup still wrote the line. The scan also asserts the
        generated file itself stays non-empty, so a green here cannot come from
        the generator having been emptied."""
        offenders: list[str] = []
        for fname in (
            "docker-compose.prod.yml",
            "docker-compose.ghcr.yml",
            "docker-compose.ci.yml",
            "config/docker-compose.gb300.yml",
            "config/docker-compose.test.yml",
            ".env.example",
            "setup.py",
        ):
            path = REPO_ROOT / fname
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip().lstrip("\"'")
                for gone in ("FLORENCE_URL=", "CLIP_URL=", "ENRICHMENT_URL="):
                    if stripped.startswith(gone):
                        offenders.append(f"{fname}: {stripped}")
        assert offenders == [], f"still injected: {offenders}"
        # Vacuity guard: the compose files still carry their OTHER AI wiring, so
        # "passing" cannot come from having deleted the file.
        prod = _src("docker-compose.prod.yml")
        assert "ai-gateway:" in prod
        assert "GATEWAY_MODEL_SET" in prod
        assert "ENRICHMENT_LIGHT_URL" in prod, "the surviving light lane keeps its wiring"
        # The generator stays a generator: it still writes the surviving URL
        # lines, so a green offender list is not the empty-file kind.
        setup = _src("setup.py")
        assert '"ENRICHMENT_LIGHT_URL=http://ai-gateway:8090/enrich-lt"' in setup, (
            "setup.py no longer writes the light lane -- the scan went vacuous"
        )

    def test_ai_fallback_strips_florence_AND_clip_but_the_module_survives(self) -> None:
        """``ai_fallback`` is kept-and-DEAD (zero shipped importers; ledgered as
        flagged-not-deleted). Its final death belongs to a dead-code slice, not
        this one -- so S3 removes only what its provider retirements DANGLE: the
        TYPE_CHECKING imports (which the annotation-resolvability guard would
        otherwise red on -- pointers at deleted modules), the enum members, the
        breaker configs and the health arms, for BOTH Florence (ruling 1) and
        CLIP (ruling 5). YOLO26 -- the one service whose backend still boots --
        stays."""
        src = _src("backend/services/ai_fallback.py")
        # LIVE forms only -- this file's own doctrine (prose may name the dead,
        # and a tombstone comment explaining WHY the member left is mandated by
        # the kept-and-DEAD ledger convention). The pins below are the shapes
        # that would still execute.
        for live in (
            "FlorenceClient",
            "CLIPClient",
            "AIService.FLORENCE",
            "AIService.CLIP",
            "florence_client",
            "clip_client",
            'FLORENCE = "',
            'CLIP = "',
        ):
            assert live not in src, f"still wired: {live}"
        assert "class AIFallbackService" in src, "the module was collateral-deleted, not stripped"
        assert "YOLO26" in src, "the kept service's arm stays"


class TestTritonRepositoryPruned:
    """The goal prompt's S3 text: prune the 11 legacy FULL_MODEL_SET models,
    KEEP yolo26/reid/threat or S1's PASS is void."""

    def test_full_model_set_is_the_kept_three(self) -> None:
        from ai.gateway.residency import FULL_MODEL_SET

        assert set(FULL_MODEL_SET) == set(KEPT_MODELS)
        assert len(FULL_MODEL_SET) == 3
        for pruned in PRUNED_MODELS:
            assert pruned not in FULL_MODEL_SET

    def test_shipped_repository_dirs_match_the_set_exactly(self) -> None:
        """The residency trap that made this a STOP-AND-ASK question:
        ``apply_model_set`` only moves names INSIDE ``FULL_MODEL_SET``, so a
        pruned set over an UNPRUNED repository silently serves the leftovers as
        foreign dirs -- the set narrows, the truth on disk does not. The dirs
        must be gone, not merely unlisted."""
        repo_dir = REPO_ROOT / "ai/triton/model_repository"
        present = {p.name for p in repo_dir.iterdir() if p.is_dir()}
        assert present == set(KEPT_MODELS), (
            f"repository dirs {sorted(present)} != kept set {sorted(KEPT_MODELS)}"
        )

    def test_all_retired_serving_dirs_are_swept(self) -> None:
        """Ruling 4 verbatim: ALL four dirs, not Florence alone."""
        for rel in RETIRED_SERVING_DIRS:
            assert not (REPO_ROOT / rel).exists(), f"retired serving dir present: {rel}"
        for keep in ("ai/gateway", "ai/triton", "ai/vlm", "ai/yolo26"):
            assert (REPO_ROOT / keep).is_dir(), f"survivor missing: {keep}"

    def test_sweep_used_git_rm_not_rm_rf(self) -> None:
        """Ruling 4: the sweep is a ``git rm``, never an ``rm -rf``.

        The discriminating signal is ``git diff-files`` (worktree vs index),
        scoped to the swept paths. ``git rm`` deletes from BOTH, so the index and
        worktree agree and the scoped diff is empty; ``rm -rf`` deletes only the
        worktree, leaving the index claiming files that are gone, so the same
        scoped diff lists them. (Verified on a scratch repo: git rm -> empty,
        rm -rf -> the path appears.)

        The original form of this assertion checked that ``git status
        --porcelain`` over the WHOLE tree was empty. That is wrong twice over:
        it reddens this unit test the instant ANY unrelated file is edited
        (mid-slice a sibling's edit turned it red with nothing wrong here), and
        it can NEVER pass after the merge either -- by the next commit the tree
        carries new edits and porcelain is non-empty forever. A pin that is only
        green in the one second after you run the command is not a pin. The
        path-scoped check holds at every point: before commit, after commit, and
        after the retired paths are long gone (an empty scoped diff over
        non-existent paths is still empty)."""
        for rel in RETIRED_SERVING_DIRS:
            disagreement = _git("diff-files", "--name-only", "--", rel).strip()
            assert disagreement == "", (
                f"{rel}: worktree and index disagree -- swept with rm -rf, not git rm\n"
                f"{disagreement}"
            )
            # A git rm also leaves the path untracked in the index.
            assert _git("ls-files", rel).strip() == "", f"{rel} still tracked in the index"

    def test_enrichment_light_adapter_survives_and_serves_the_kept_models(self) -> None:
        """re-ID and threat are KEPT, and ``enrichment_light`` is the adapter
        that serves them (measured pre-slice: ``model_name="threat"`` :392,
        ``model_name="reid"`` :439). The sweep may not delete the router the
        shipped VLM path calls, and the ops of its KEPT models must stay
        registered. Its three routes onto PRUNED models (pose/pet/depth) go."""
        src = _src("ai/gateway/adapters/enrichment_light.py")
        assert 'model_name="threat"' in src
        assert 'model_name="reid"' in src
        for pruned_route in ("/pose-analyze", "/pet-classify", "/depth-estimate"):
            assert f'"{pruned_route}"' not in src, (
                f"the light adapter still routes {pruned_route} to a pruned model"
            )

        from backend.ai_contract.operations import OPERATION_IDS

        for live in ("enrich_lt_person_reid", "enrich_lt_threat_detect"):
            assert live in OPERATION_IDS, f"{live} serves a KEPT model and must stay"

    def test_adapters_whose_models_are_all_pruned_retire_with_them(self) -> None:
        """The forced-consequence boundary, stated rather than smuggled.

        S2b's precedent kept retired providers' ops "as DEPLOYED gateway
        surface until their provider slice" -- but the prune + ruling 3 remove
        the precedent's PRECONDITION: with ``full`` hard-raised, no reachable
        deployment ever boots clip/clip_text/vehicle/fashion_clip/demographics/
        pose/stgcn/pet/depth, so EVERY route of adapters clip.py and
        enrichment.py calls a model that cannot exist. A router.routes-derived
        op the gateway can never serve is the false alarm check_phantoms
        exists to refuse, one layer up. So those adapters and their ops retire
        here as Triton-prune consequences; ruling 5 (owner answer this session)
        takes CLIP's provider row and client with them, because a deployed
        provider whose whole op set is unbootable would register VACUOUSLY."""
        for adapter in ("clip.py", "enrichment.py", "florence.py"):
            assert not (REPO_ROOT / "ai/gateway/adapters" / adapter).exists(), adapter
        from backend.ai_contract.operations import OPERATION_IDS

        for gone in FLORENCE_OP_IDS + CLIP_OP_IDS + PRUNED_MODEL_OP_IDS:
            assert gone not in OPERATION_IDS, f"{gone} survives; its model cannot boot"
        # The generator's adapter map shrinks to the two survivors.
        gen = _src("scripts/gen-ai-contract.py")
        assert '"florence": "/florence"' not in gen
        assert '"clip": "/clip"' not in gen
        assert '"enrichment": "/enrichment"' not in gen
        assert '"enrichment_light"' in gen, "the surviving light adapter stays mapped"

    def test_clip_the_debug_endpoint_retires_with_the_prune(self) -> None:
        """Ruling 5's live surface, pinned on the deletion side. The gateway
        /clip router's only backend consumer was the face-similarity debug tool
        (/api/face-events/compare). With the models pruned the endpoint could
        only 503 via the breaker or 404 behind the unmounted router; the owner
        ruling-5 option assumed the frontend would then render "the endpoint's
        own error payload", and MEASUREMENT corrected that: the debug panel
        never reads its mutation's error state (FaceSimilarityDebugTool.tsx
        renders result.error only on a 200 body), so a deleted endpoint would
        leave a button that silently does nothing -- a dead control, which is
        worse than an absent panel. So the whole NEM-4955 vertical goes:
        endpoint, schema, client, hook, panel, tab. (S5's frontend scope stays
        the R8:108 ENRICHMENT panels; this one died here because S3 killed its
        endpoint.)"""
        assert not (REPO_ROOT / "backend/services/clip_client.py").exists()
        assert not (REPO_ROOT / "backend/services/scene_baseline.py").exists(), (
            "scene_baseline's only injected dependency was the CLIP client, and "
            "it has no shipped consumers outside its own docstring (measured)"
        )
        assert "/face-events/compare" not in _src("backend/api/routes/face_recognition.py")
        assert "FaceSimilarityCompareResponse" not in _src(
            "backend/api/schemas/face_recognition.py"
        )
        # Non-vacuity: the face-recognition router AND its surviving DB-lookup
        # service stay (memory vlm-path-keeps-lookups-not-perception: face/ReID
        # lookups remain, only the CLIP re-perception went). The service named
        # here is the module the router actually imports
        # (backend/api/routes/face_recognition.py:83) -- an earlier draft of
        # this line asserted a `face_embedding_store.py` that has never existed
        # in any commit, which is a presence pin against a phantom: it cannot
        # ever be satisfied, so it asserts nothing about the surviving surface.
        assert (REPO_ROOT / "backend/api/routes/face_recognition.py").exists()
        assert (REPO_ROOT / "backend/services/face_recognition_service.py").exists()
        assert "face_recognition_service" in _src("backend/api/routes/face_recognition.py")

    def test_the_frontend_debug_panel_died_with_its_endpoint(self) -> None:
        """The vertical, pinned top-down. If a future "restore" re-adds the
        panel against the deleted endpoint, the frontend type-check still
        compiles (the hook's interface went too -- that is what makes the
        restore fail loudly rather than silently), but THIS pin reddens by
        name."""
        assert not (
            REPO_ROOT / "frontend/src/components/face-recognition/FaceSimilarityDebugTool.tsx"
        ).exists()
        hook = _src("frontend/src/hooks/useFaceRecognitionApi.ts")
        # LIVE export forms only -- the file's tombstone comment names the
        # retired functions by design (prose may name the dead).
        assert "export async function compareFaceSimilarity" not in hook
        assert "export function useCompareFaceSimilarity" not in hook
        page = _src("frontend/src/pages/FaceRecognitionPage.tsx")
        assert "debug-tools" not in page, "the tab returned with no member"
        # Vacuity: the page still ships its surviving tabs.
        assert "person-tracking" in page


class TestModelManagementTracksTheNarrowSet:
    """The last consumer of the retired enrichment URLs (measured pre-slice:
    ``get_router_urls`` at model_management.py:168, the only shipped reader of
    enrichment_url/enrichment_light_url). Its heavy lane was ALREADY empty
    since S2 (``HEAVY_MODELS = frozenset()``), so the heavy router probe has no
    members to describe -- it retires, and the gateway-root URL derivation
    rekeys off the light router alone."""

    def test_heavy_router_lane_is_gone_and_the_light_lane_survives(self) -> None:
        src = _src("backend/api/routes/model_management.py")
        assert '"/enrichment"' not in src, "still probes the deleted heavy router"
        assert "settings.enrichment_url" not in src, "still reads a deleted settings field"
        assert "enrich-lt" in src, "the light lane is the shipped readiness surface"
        # Vacuity: the router itself stays mounted (backend/main.py:1624).
        assert "model_management" in _src("backend/main.py")

    def test_no_shipped_source_still_reads_a_deleted_settings_field(self) -> None:
        """A Field deleted from Settings that some module still reads is the
        AttributeError-waiting-to-happen class S1's nemotron_url sweep
        enumerated. Targeted list, not a whole-tree walk (duration budget)."""
        importers = [
            "backend/api/routes/model_management.py",
            "backend/api/routes/health_ai_services.py",
            "backend/api/routes/system.py",
            "backend/services/ai_fallback.py",
            "backend/services/scene_baseline.py",
            "backend/api/routes/face_recognition.py",
            "backend/core/config.py",
        ]
        for rel in importers:
            path = REPO_ROOT / rel
            if not path.exists():
                continue
            src = path.read_text(encoding="utf-8")
            for gone in ("florence_url", "clip_url", "enrichment_url"):
                # Attribute reads only -- prose is allowed to name the dead,
                # and the field-declaration/validator-tuple forms are pinned
                # exactly, per file, by the tests above.
                assert f".{gone}" not in src, f"{rel} still reads settings.{gone}"


class TestGatewayModelSetHardRaise:
    """Ruling 3: unset, unknown and ``full`` all raise at container start."""

    def test_full_name_raises(self) -> None:
        from ai.gateway.residency import get_model_set

        with pytest.raises(KeyError):
            get_model_set("full")

    def test_unknown_name_raises(self) -> None:
        from ai.gateway.residency import get_model_set

        with pytest.raises(KeyError):
            get_model_set("banana")

    def test_unset_env_raises_no_bare_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The old bare-module default was ``full``, which is the ONLY reason
        this module ever tolerated an unset variable. With ``full`` retired,
        silence is a misconfiguration, and S1's PIPELINE_MODE doctrine says a
        misconfiguration stops the container rather than serving a surprise."""
        from ai.gateway import residency

        monkeypatch.delenv("GATEWAY_MODEL_SET", raising=False)
        with pytest.raises(KeyError):
            residency.resolve_active_set()

    def test_vlm_still_resolves_with_and_without_threat(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The arm that must NOT break, pinned next to the three that raise."""
        from ai.gateway import residency

        monkeypatch.setenv("GATEWAY_MODEL_SET", "vlm")
        monkeypatch.delenv("GATEWAY_ENABLE_THREAT", raising=False)
        assert residency.resolve_active_set() == ("yolo26", "reid")
        monkeypatch.setenv("GATEWAY_ENABLE_THREAT", "true")
        assert residency.resolve_active_set() == ("yolo26", "reid", "threat")

    def test_entrypoint_drops_the_full_default(self) -> None:
        src = _src("ai/gateway/entrypoint.sh")
        assert "${GATEWAY_MODEL_SET:-full}" not in src
        assert "ai.gateway.residency" in src, "the prune step must still run"

    def test_compose_still_pins_explicit_vlm(self) -> None:
        """The hard raise only has teeth because deployment ALWAYS states the
        set; that existing pairing must not drift while residency is edited."""
        assert "GATEWAY_MODEL_SET=${GATEWAY_MODEL_SET:-vlm}" in _src("docker-compose.prod.yml")


class TestModelsYmlLegacyRowsDeleted:
    """Ruling 2: DELETE the rows. The owner chose this OVER the evidence doc's
    ``enabled: false`` provenance default, and specifically declined to follow
    the X-CLIP precedent -- so a reviewer who "restores provenance" here is
    overriding a ruling, not fixing an omission."""

    def test_legacy_rows_absent_keepers_present(self) -> None:
        data = yaml.safe_load(_src("models.yml"))
        names = {m["name"] for m in data["models"]}
        # The two rows that carry a pruned triton_name (measured pre-slice:
        # florence-2-base -> florence2 at :110, yolov8n-pose -> pose at :221).
        assert "florence-2-base" not in names
        assert "yolov8n-pose" not in names
        # The retired LLM's row is legacy too (the engine died in S2; the row
        # was left behind and nothing in R8 brings it back).
        assert not any(n.startswith("nemotron") for n in names), names
        # Keepers: the shipped detection/embedding models and the LIVE DB-lookup
        # models (face + re-ID), whose TABLES are S4's business.
        assert {"yolo26", "osnet-ain-x1-0", "threat-detection-yolov8n"} <= names
        assert {"face-recognizer", "face-detector-scrfd"} <= names

    def test_yaml_still_parses_and_is_not_emptied(self) -> None:
        data = yaml.safe_load(_src("models.yml"))
        assert isinstance(data["models"], list) and len(data["models"]) >= 8, (
            "the file was gutted rather than pruned"
        )


class TestDiRenameLands:
    """Ledger item 45's close pointer ruled the ``"nemotron_analyzer"`` ->
    ``"vlm_analyzer"`` registry-string rename into S3: retiring a class and
    renaming a wiring string are different risks, and one slice carries one of
    them. The string is load-bearing -- the startup gate and
    core/dependencies resolve by it -- so all three sites move together and the
    S2b guard is RETARGETED, not deleted."""

    def test_container_registers_the_new_name(self) -> None:
        src = _src("backend/core/container.py")
        assert 'register_async_singleton("vlm_analyzer"' in src
        assert '"nemotron_analyzer"' not in src

    def test_resolvers_use_the_new_name(self) -> None:
        for rel in ("backend/core/dependencies.py", "backend/main.py"):
            src = _src(rel)
            assert 'get_async("vlm_analyzer")' in src, rel
            assert '"nemotron_analyzer"' not in src, rel

    def test_s2b_guard_was_retargeted_not_deleted(self) -> None:
        src = _src("backend/tests/unit/test_r8_s2b_nemotron_deletion.py")
        assert "class TestDiNameIsDeliberate" in src, (
            "the guard was deleted to make the rename pass; retarget its string"
        )
        assert 'register_async_singleton("vlm_analyzer"' in src


class TestDeadWithItsProvider:
    """``scene_ocr_service``'s only downstream was the florence router's
    ``/ocr-with-regions`` (its own docstring says so) and the ai-surface census
    already buckets it DEAD. S3 is the first slice where BOTH of its
    dependencies are gone, which makes it the slice that can say so -- the
    doctrine the S2b holes list states as 'deletion is a slice that must say
    so'."""

    def test_scene_ocr_service_retires_with_its_provider(self) -> None:
        assert not (REPO_ROOT / "backend/services/scene_ocr_service.py").exists()
        importlib.invalidate_caches()
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("backend.services.scene_ocr_service")

    def test_census_pin_follows_the_deletion_instead_of_laundering_it(self) -> None:
        """The census test asserts the module's bucket is DEAD; with the module
        gone the pin must state the ABSENCE (V3 tombstone doctrine), not go
        silent and not leave a lookup that KeyErrors on a missing module."""
        src = _src("scripts/test_ai_surface_census.py")
        assert 'mods["scene_ocr_service"]["bucket"] == "DEAD"' not in src, (
            "still requires a deleted module to exist -- retarget to absence"
        )

    def test_trajectory_analyzer_is_NOT_collaterally_deleted(self) -> None:
        """Negative space, pinned. ``trajectory_analyzer`` is kept-and-DEAD too,
        but no ruling retires it in S3: collateral deletion of a module nobody
        ruled on is scope creep wearing a tidiness costume."""
        assert (REPO_ROOT / "backend/services/trajectory_analyzer.py").exists()


class TestGatewaySuiteTracksTheNarrowSet:
    """``ai/gateway/tests`` pinned the 14-model world. Those pins are
    RETARGETED (kept-model assertions survive); ``test_adapters_florence.py``
    dies with its module, because a test of nothing is a suppression waiting
    to happen."""

    def test_florence_adapter_test_file_is_gone(self) -> None:
        assert not (REPO_ROOT / "ai/gateway/tests/test_adapters_florence.py").exists()

    def test_main_suite_stops_asserting_pruned_models(self) -> None:
        src = _src("ai/gateway/tests/test_main.py")
        assert '"florence2" in ALL_MODELS' not in src
        assert '"clip" in ALL_MODELS' not in src
        assert '"yolo26" in ALL_MODELS' in src, "the kept-model pin must survive the retarget"

    def test_gateway_health_describes_only_the_narrow_set(self) -> None:
        """main.py derives ALL_MODELS from FULL_MODEL_SET, so this is the drift
        pin test_residency.TestNamedSets already makes -- restated here because
        S3 is the slice that changes the tuple, and a health payload listing a
        model the repository no longer ships is a false alarm by construction."""
        src = _src("ai/gateway/main.py")
        assert "ALL_MODELS: list[str] = list(FULL_MODEL_SET)" in src


class TestNoLivePointerAtTheDeleted:
    """Final sweep over the sites MEASURED pre-slice as naming Florence in a
    LIVE position. Targeted by design: no whole-tree walk -- a fresh test-id
    that parses the world breaches the WP1.3 duration budget on its first run
    (4.03s against the 4.0s unit limit at ``ci.yml:2651``; ledger item 49)."""

    LIVE_IMPORTERS: ClassVar[list[str]] = [
        "backend/services/ai_fallback.py",
        "backend/ai_contract/providers.py",
        "backend/ai_contract/operations.py",
        "backend/ai_contract/fake/generators.py",
        "ai/gateway/main.py",
        "ai/gateway/adapters/__init__.py",
        "scripts/gen-ai-contract.py",
        "scripts/check-ai-provider-parity.py",
    ]
    DEAD_TARGETS: ClassVar[frozenset[str]] = frozenset(
        {
            "backend.services.florence_client",
            "ai.gateway.adapters.florence",
            "backend.services.scene_ocr_service",
        }
    )

    @pytest.mark.parametrize("rel", LIVE_IMPORTERS)
    def test_no_shipped_source_imports_a_deleted_module(self, rel: str) -> None:
        path = REPO_ROOT / rel
        if not path.exists():
            return  # its own retirement is pinned elsewhere, by name
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module]
            for m in mods:
                assert m not in self.DEAD_TARGETS, f"{rel} still imports {m}"

    def test_ops_scripts_do_not_exec_or_map_the_swept_paths(self) -> None:
        """An exec line or an id-prefix map entry aimed at a swept dir is the
        same 'pointer at nothing' class the providers.py S2 comment refuses for
        ``_CLIENT_MODULES`` -- one layer down the stack."""
        engines = _src("scripts/prebuild-tensorrt-engines.sh")
        assert "ai/clip/" not in engines
        assert "ai/enrichment/" not in engines

        parity = _src("scripts/check-ai-provider-parity.py")
        assert '"florence"' not in parity
        assert "florence_client" not in parity
        assert '"florence_url"' not in parity

        generator = _src("scripts/gen-ai-contract.py")
        assert '"florence": "/florence"' not in generator, (
            "the generator still walks a deleted adapter"
        )
        assert "ai.gateway.adapters.florence" not in generator

    def test_the_ai_contract_package_still_imports_nothing_from_ai(self) -> None:
        """Regression pin for the layering rule the sweep could break: the
        contract package must never import ``ai.*`` at runtime, and S3 touches
        exactly that seam (it deletes an ai-side adapter and an ai_contract
        row)."""
        pkg = REPO_ROOT / "backend/ai_contract"
        offenders: list[str] = []
        for py in sorted(pkg.rglob("*.py")):
            if "__pycache__" in py.parts:
                continue
            for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
                mods: list[str] = []
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    mods = [node.module]
                offenders += [f"{py.name}: {m}" for m in mods if m == "ai" or m.startswith("ai.")]
        assert offenders == []

# WP4.4 Triage Dossier — backend/api/routes/gpu_config.py

**Run state (meta as read 2026-09-17):** 367 total mutants → 99 killed, **111 survived (this dossier)**, 157 still unchecked (`null`). Verdicts are provisional until the run completes; survivors below survived on the *current* suite.

**Survivor distribution:** `_calculate_auto_assignments` 90, `_update_gpu_devices_in_db` 18, `_get_latest_config_update_time` 3. All three are exercised ONLY through endpoints (preview / detect / get-config) with a **mocked AsyncMock db** and **placement-blind assertions** (`len(assignments) >= 3`, `status == 200`, `commit called once`) — never on *which GPU each service lands on* or *what was passed to `db.add`/`db.execute`*. That single weakness explains ~80 of 111 survivors.

- Covering test file (all three functions): `backend/tests/unit/api/routes/test_gpu_config.py`
  - `TestPreviewGpuConfig` — lines 871-972 (placement-blind asserts at 890-891, 924-927, 954-955, 971-972)
  - `TestDetectGpus` — lines 797-863 (`test_detect_gpus_updates_database` asserts only `commit.assert_called_once()` at line 848)
  - `TestGetGpuConfig` — lines 232-359 (`updated_at` asserted only as `is None` / `is not None`)
- Diffs verified via `uv run mutmut show` spot-checks (`..._45`, `..._63` — matched) + programmatic variant-vs-`__mutmut_orig` diffing of all 111.
- Key structural fact: `GpuAssignment.gpu_index` defaults to **None** ("null for auto-assign", `backend/api/schemas/gpu_config.py:128`) and is `int | None` — every `gpu_index=X → None` / dropped-kwarg mutant yields a **valid, schema-passing response with wrong placement**. That is what let the index-erasure mutants slip through.
- VRAM table (`backend/services/gpu_detection_service.py:35`): llm 8192, florence 4096, enrichment 2048, clip 2048, yolo26 100 → total demand 16376 MB.

## Cluster table (20 clusters, n-sum = 111)

Fn abbrev: ca = `_calculate_auto_assignments`, ud = `_update_gpu_devices_in_db`, lc = `_get_latest_config_update_time`.

| # | Pattern | n | Class | Example keys | Killed by | Why it survives today |
|---|---|---|---|---|---|---|
| C1 | MANUAL strategy default `gpu_index=0` → None / dropped / `1` | 3 | TEST-GAP | ca_13, ca_15, ca_17 | T-A | Preview tests never assert manual placement; None passes schema as "auto" |
| C2 | VRAM_BASED capacity chain: fits-op `>=`→`>` (51); `gpu_remaining -=`→`=`/`+=` (58,59); `assigned=False`→`True` drops overflow (50); overflow guard `not assigned`→`assigned` duplicates (63); `vram_needed` lookup key→None = every service costs 0 (44,157); fit-loop `gpu_index=gpu.index`→None/dropped (54,56) | 9 | TEST-GAP | ca_51, ca_58, ca_63 | T-C | Existing 2-GPU fixture (24.5+8 GB) has total VRAM > total demand → overflow path never runs; missing/dup assignments hidden by `len >= 3` |
| C3 | VRAM_BASED GPU sort `sorted(gpus, key=lambda g: g.vram_total_mb, reverse=True)` → False/None/removed (ascending) | 3 | TEST-GAP | ca_22, ca_25, ca_27 | T-B | No placement assertion; fixture masks the flip for the largest service |
| C4 | VRAM_BASED service-order sort: `key=None` / key removed (alpha) / `.get(None,0)` (all-equal keys → stable) / `reverse` False/None/removed (ascending) | 6 | TEST-GAP | ca_30, ca_33, ca_41 | T-C | Placement never asserted; order changes invisible under `len >= 3` |
| C5 | BALANCED service-order sort mutants (exact same families, second call site lines 600-604) | 6 | TEST-GAP | ca_144, ca_145, ca_150 | T-B | Balanced distribution never asserted |
| C6 | BALANCED usage bookkeeping `gpu_usage[min] += vram_needed` → `=` / `-=` | 2 | TEST-GAP | ca_174, ca_175 | T-B | Accumulation only observable via distribution, which nothing checks |
| C7 | ISOLATION_FIRST: `len(gpus) >= 2` → `>2`/`>=3` (65,66); `second_gpu` predicate `!=`→`==` (75, StopIteration → 500); `service == "ai-llm"` flipped / clobber-case (76,77,78) | 6 | TEST-GAP | ca_65, ca_75, ca_76 | T-D | 2-GPU fixture exists but nothing asserts llm-on-largest / others-on-second; single-GPU test checks only warning presence |
| C8 | LATENCY `sorted(gpus, key=get_compute_score, reverse=True)` order mutants + `fastest_gpu = sorted_gpus[0]` → `[1]` (113) | 4 | TEST-GAP | ca_107, ca_113 | T-E | `sample_gpus` has **identical** compute_capability ("8.6","8.6") → tie makes the flip a no-op; placement never asserted anyway |
| C9 | LATENCY `critical_services = ["ai-yolo26","ai-enrichment"]` string clobbers (case/XX-wrap) + `in`→`not in` | 5 | TEST-GAP | ca_115, ca_119 | T-E | Critical-vs-other placement never asserted |
| C10 | LATENCY `other_gpu = sorted_gpus[-1] if len > 1` index/arity mutants: `[+1]`, `[-2]`, `> 2`, `and False` | 4 | TEST-GAP | ca_127, ca_129, ca_132 | T-E | 2-GPU-only fixtures make `[+1]`==`[-1]`, `[-2]`==`[0]` converge; `>2` collapses ternary only at len 2 — both need a 3-GPU *and* a 2-GPU case |
| C11 | Placement-arg erasure `gpu_index=<expr>` → None / kwarg dropped (isolation largest/second/gpus[0], latency fastest/other, balanced min) | 12 | TEST-GAP | ca_81, ca_122, ca_170 | T-B, T-D, T-E | `gpu_index` default None = schema-valid "auto"; every erasure still returns 200 with a plausible body |
| C12 | lc query clobber: `db.execute(None)` / `select(None)` / `func.max(None)` | 3 | TEST-GAP | lc_2, lc_3, lc_4 | T-F | AsyncMock executes any arg, returns canned scalar; response assert only `is None`/`is not None`; no test inspects `db.execute` call args |
| C13 | ud create-path clobbers: `now=None` / `datetime.now(None)` (naive), `db_device=None` / `db.add(None)`, every `GpuDeviceModel(...)` kwarg → None/dropped (gpu_index, name, vram_total/available_mb, compute_capability, last_seen_at) | 16 | TEST-GAP | ud_9, ud_16, ud_20 | T-F | `test_detect_gpus_updates_database` asserts only `commit.assert_called_once()` — mock db accepts `add(None)`; row contents never read back |
| C14 | ud read-path clobber: `execute(None)` / `select(None)` | 2 | TEST-GAP | ud_2, ud_3 | T-F | Mock db returns the canned result for *any* statement |
| E1 | Warning-message text mutants (XX-wrap/lower/upper on both warning strings) | 4 | EQUIVALENT | ca_2, ca_99, ca_100 | — | Tests assert case-insensitive substrings that survive the wrap; message text only |
| E2 | `vram_budget_override=None,` kwarg dropped at all 8 construction sites | 8 | EQUIVALENT | ca_16, ca_57, ca_173 | — | Pydantic field default is None → identical object |
| E3 | `len(sorted_gpus) > 1` → `or True` / `>= 1` in `other_gpu` ternary | 2 | EQUIVALENT | ca_128, ca_131 | — | Function early-returns on empty gpus; at len==1 `sorted_gpus[-1]` *is* `fastest_gpu` — condition is tautologic in the guard's domain |
| E4 | `assigned` flag falsy swaps: init `False`→None (49); `assigned = True`→None/False (60,61) | 3 | EQUIVALENT | ca_49, ca_60 | — | Only consumed via `if not assigned`; None falsy ≡ False. (Contrast ca_50 `False→True` and ca_63 guard flip = C2, real changes.) |
| E5 | BALANCED `gpu_usage = {g.index: 0 …}` seed → `1` | 1 | EQUIVALENT | ca_141 | — | Uniform shift; min-selection unchanged; dict never leaves the function |
| E6 | `.get(svc, DEFAULT)` default tweaks (None/dropped/1) on sort-key and vram_needed lines | 12 | LOW-VALUE | ca_37, ca_45, ca_48 | — | Default branch fires only for names absent from `AI_SERVICE_VRAM_REQUIREMENTS_MB`; the only caller (preview endpoint) always passes the dict's own keys → unreachable in any real flow. A direct unit call with `services=["unknown"]` would kill them if the team wants it |

**Totals: TEST-GAP 81, LOW-VALUE 12, EQUIVALENT 18 → 111** (sum verified programmatically; clusters disjoint).

## Root-cause note for WP4.4

Every TEST-GAP cluster reduces to two missing assertion kinds:
1. **Placement assertions** on `/gpu-config/preview` — exact `service → gpu_index` map per strategy, with fixtures that (a) put total demand above any single GPU (overflow path), (b) give GPUs *distinct* compute capabilities (sample_gpus' equal "8.6" is precisely why C8 survived), (c) use 3 GPUs (index mutants `[+1]`/`[-2]` converge at len 2).
2. **Write-arg assertions** on the mocked session — what was passed to `db.add(...)` / `db.execute(...)` — killing both mock-blind clusters (C12, C13, C14) in one stroke.

## Drafted tests (UNVERIFIED — not yet run red/green)

All target `backend/tests/unit/api/routes/test_gpu_config.py`; add alongside the matching class. Style follows the file (sync `TestClient`, `@patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)`, fixtures `client`/`mock_db_session`/`sample_gpus`). Expected placement maps were hand-traced against the real `AI_SERVICE_VRAM_REQUIREMENTS_MB` values; red/green proof still required.

**TDD procedure (one line):** run each draft against the mutant build — the new assertion must FAIL on the cluster's diff (red) — then against unmutated source and PASS (green); only then does the cluster count as covered.

### T-A → kills C1 (manual default index) — add to `TestPreviewGpuConfig`

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_manual_strategy_assigns_every_service_to_gpu_zero(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """MANUAL strategy defaults every service to GPU 0 (not null/auto, not 1)."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=manual")

        assert response.status_code == 200
        data = response.json()
        assert len(data["proposed_assignments"]) == 5  # every known AI service
        for assignment in data["proposed_assignments"]:
            assert assignment["gpu_index"] == 0, f"{assignment['service']} should default to GPU 0"
```

### T-B → kills C3, C5, C6 (+ balanced slice of C11)

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_vram_and_balanced_place_services_expected_gpu(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """VRAM_BASED packs the largest GPU first; BALANCED spreads by accumulated usage.

        Fixture choices are deliberate: two GPUs sized so a reversed GPU sort sends
        ai-llm to GPU 1, and three equal GPUs so every service-order and usage-
        bookkeeping mutant yields a different placement map.
        """
        big_small = [
            GpuDeviceDataclass(index=0, name="A5500", vram_total_mb=24564, vram_used_mb=0,
                               uuid="GPU-aaaaaaaa-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
            GpuDeviceDataclass(index=1, name="A400", vram_total_mb=8192, vram_used_mb=0,
                               uuid="GPU-bbbbbbbb-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
        ]
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=big_small)
        mock_get_service.return_value = mock_service

        # VRAM_BASED: largest-first fits ALL demand (16376 MB) on GPU 0, no warnings.
        # An ascending GPU sort would place ai-llm on GPU 1 (8192 fits exactly).
        response = client.get("/api/system/gpu-config/preview?strategy=vram_based")
        assert response.status_code == 200
        data = response.json()
        placement = {a["service"]: a["gpu_index"] for a in data["proposed_assignments"]}
        assert placement["ai-llm"] == 0
        assert set(placement.values()) == {0}
        assert data["warnings"] == []

        # BALANCED with three equal GPUs — hand-traced expectation (services sorted
        # VRAM-desc: llm 8192 > florence 4096 > enrichment/clip 2048 > yolo 100):
        #   llm->g0 (usage g0=8192) | florence->g1 (g1=4096) | enrichment->g2 (g2=2048,
        #   unique min) | clip->g2 (g2=2048 still unique min vs g1 4096) -> g2=4096
        #   | yolo->g1 (g1 4096 ties g2 4096; min() picks first, g1 precedes g2)
        three = [
            GpuDeviceDataclass(index=0, name="G0", vram_total_mb=24576, vram_used_mb=0,
                               uuid="GPU-cccccccc-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
            GpuDeviceDataclass(index=1, name="G1", vram_total_mb=24576, vram_used_mb=0,
                               uuid="GPU-dddddddd-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
            GpuDeviceDataclass(index=2, name="G2", vram_total_mb=24576, vram_used_mb=0,
                               uuid="GPU-eeeeeeee-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
        ]
        mock_service.detect_gpus = AsyncMock(return_value=three)
        response = client.get("/api/system/gpu-config/preview?strategy=balanced")
        assert response.status_code == 200
        data = response.json()
        placement = {a["service"]: a["gpu_index"] for a in data["proposed_assignments"]}
        assert placement == {
            "ai-llm": 0,
            "ai-florence": 1,
            "ai-enrichment": 2,
            "ai-clip": 2,
            "ai-yolo26": 1,
        }
```

### T-C → kills C2, C4 (VRAM capacity chain + service order)

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_vram_based_overflow_splits_and_warns_exactly(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Demand (16376 MB) exceeds two 4096 MB GPUs: ai-llm and ai-yolo26 must
        overflow with exactly two warnings; ai-enrichment/ai-clip must land on
        GPU 1 via the remaining-VRAM accounting. Service order (VRAM-desc) is
        baked into the exact map: any reorder moves clip/florence/enrichment."""
        small = [
            GpuDeviceDataclass(index=0, name="S0", vram_total_mb=4096, vram_used_mb=0,
                               uuid="GPU-11111111-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
            GpuDeviceDataclass(index=1, name="S1", vram_total_mb=4096, vram_used_mb=0,
                               uuid="GPU-22222222-0000-0000-0000-000000000000",
                               compute_capability="8.6"),
        ]
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=small)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=vram_based")

        assert response.status_code == 200
        data = response.json()
        assignments = data["proposed_assignments"]
        # exactly one assignment per service (kills flag/guard mutants that
        # duplicate or drop the overflow-path assignment)
        assert sorted(a["service"] for a in assignments) == [
            "ai-clip", "ai-enrichment", "ai-florence", "ai-llm", "ai-yolo26",
        ]
        placement = {a["service"]: a["gpu_index"] for a in assignments}
        assert placement == {
            "ai-llm": 0,        # 8192 fits neither GPU -> overflow lands on first max-remaining
            "ai-florence": 0,   # 4096 >= 4096 boundary (the `>` mutant sends this to GPU 1)
            "ai-enrichment": 1, # reachable only if gpu_remaining was DECREMENTED after florence
            "ai-clip": 1,
            "ai-yolo26": 0,     # neither GPU has 100 MB left -> overflow warning
        }
        assert len(data["warnings"]) == 2
        warned = " ".join(data["warnings"])
        assert "ai-llm" in warned and "ai-yolo26" in warned
```

### T-D → kills C7 (+ isolation slice of C11)

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_isolation_first_dedicates_largest_gpu(
        self, mock_get_service: MagicMock, client: TestClient, sample_gpus: list[GpuDeviceDataclass]
    ) -> None:
        """With two GPUs, ai-llm gets the largest (GPU 0) exclusively and every
        other service lands on the second GPU — with no warnings."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=isolation_first")

        assert response.status_code == 200
        data = response.json()
        placement = {a["service"]: a["gpu_index"] for a in data["proposed_assignments"]}
        assert placement["ai-llm"] == 0
        assert [idx for svc, idx in placement.items() if svc != "ai-llm"] == [1, 1, 1, 1]
        assert data["warnings"] == []

        # Single GPU: everything collapses to GPU 0 plus exactly one warning.
        single = [
            GpuDeviceDataclass(index=0, name="One", vram_total_mb=8000, vram_used_mb=0,
                               uuid="GPU-33333333-0000-0000-0000-000000000000",
                               compute_capability="8.6")
        ]
        mock_service.detect_gpus = AsyncMock(return_value=single)
        response = client.get("/api/system/gpu-config/preview?strategy=isolation_first")
        assert response.status_code == 200
        data = response.json()
        assert all(a["gpu_index"] == 0 for a in data["proposed_assignments"])
        assert len(data["warnings"]) == 1
        assert "Only one GPU" in data["warnings"][0]
```

### T-E → kills C8, C9, C10 (+ latency slice of C11)

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_preview_gpu_config_latency_optimized_places_critical_services(
        self, mock_get_service: MagicMock, client: TestClient
    ) -> None:
        """Critical path (ai-yolo26, ai-enrichment) must land on the highest
        compute-capability GPU; the rest go to the slowest GPU. Distinct compute
        scores and three GPUs make every sort/index mutant observable."""
        three = [
            GpuDeviceDataclass(index=0, name="Slow", vram_total_mb=24576, vram_used_mb=0,
                               uuid="GPU-44444444-0000-0000-0000-000000000000",
                               compute_capability="7.5"),
            GpuDeviceDataclass(index=1, name="Fast", vram_total_mb=8192, vram_used_mb=0,
                               uuid="GPU-55555555-0000-0000-0000-000000000000",
                               compute_capability="8.9"),
            GpuDeviceDataclass(index=2, name="Mid", vram_total_mb=16384, vram_used_mb=0,
                               uuid="GPU-66666666-0000-0000-0000-000000000000",
                               compute_capability="8.0"),
        ]
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=three)
        mock_get_service.return_value = mock_service

        response = client.get("/api/system/gpu-config/preview?strategy=latency_optimized")
        assert response.status_code == 200
        data = response.json()
        placement = {a["service"]: a["gpu_index"] for a in data["proposed_assignments"]}
        assert placement["ai-yolo26"] == 1      # fastest (8.9) — kills set-clobber/in-flip mutants
        assert placement["ai-enrichment"] == 1
        # slowest GPU (sorted_gpus[-1] == GPU 0) — kills [+1]/[-2]/and-False mutants
        assert placement["ai-llm"] == 0
        assert placement["ai-florence"] == 0
        assert placement["ai-clip"] == 0

        # Exactly two GPUs: other_gpu must STILL be the slow one (GPU 0). Kills the
        # `len > 2` mutant that collapses the ternary to fastest_gpu at len == 2.
        two = three[:2]  # GPU 0 (7.5) and GPU 1 (8.9)
        mock_service.detect_gpus = AsyncMock(return_value=two)
        response = client.get("/api/system/gpu-config/preview?strategy=latency_optimized")
        assert response.status_code == 200
        data = response.json()
        placement = {a["service"]: a["gpu_index"] for a in data["proposed_assignments"]}
        assert placement["ai-yolo26"] == 1
        assert placement["ai-llm"] == 0
```

### T-F → kills C12, C13, C14

Add import at top of file: `from backend.models.gpu_config import GpuDevice as GpuDeviceModel`.

```python
    @patch("backend.api.routes.gpu_config.get_gpu_detection_service", autospec=True)
    def test_detect_gpus_persists_full_device_rows(
        self,
        mock_get_service: MagicMock,
        client: TestClient,
        mock_db_session: AsyncMock,
        sample_gpus: list[GpuDeviceDataclass],
    ) -> None:
        """Detect must query gpu_devices and add a fully-populated, tz-aware row
        per detected GPU — commit alone proves nothing."""
        mock_service = AsyncMock()
        mock_service.detect_gpus = AsyncMock(return_value=sample_gpus)
        mock_get_service.return_value = mock_service

        mock_existing_devices_result = MagicMock()
        mock_existing_devices_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_existing_devices_result

        response = client.post("/api/system/gpu-config/detect")
        assert response.status_code == 200

        # the existing-devices query must target the gpu_devices table (not None/None-select)
        executed = mock_db_session.execute.call_args_list[0].args[0]
        assert executed is not None
        assert "gpu_devices" in str(executed)

        added = [call.args[0] for call in mock_db_session.add.call_args_list]
        assert len(added) == 2
        for row, device in zip(added, sample_gpus):
            assert isinstance(row, GpuDeviceModel)
            assert row.gpu_index == device.index
            assert row.name == device.name
            assert row.vram_total_mb == device.vram_total_mb
            assert row.vram_available_mb == device.vram_total_mb - device.vram_used_mb
            assert row.compute_capability == device.compute_capability
            assert row.last_seen_at is not None
            assert row.last_seen_at.tzinfo is not None  # datetime.now(UTC), not naive/None

    def test_get_gpu_config_reads_max_updated_at(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """The updated_at lookup must be MAX(gpu_configurations.updated_at)."""
        mock_strategy_result = MagicMock()
        mock_strategy_result.scalar_one_or_none.return_value = None
        mock_assignments_result = MagicMock()
        mock_assignments_result.scalars.return_value.all.return_value = []
        mock_updated_at_result = MagicMock()
        mock_updated_at_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.side_effect = [
            mock_strategy_result,
            mock_assignments_result,
            mock_updated_at_result,
        ]

        response = client.get("/api/system/gpu-config")
        assert response.status_code == 200

        third_stmt = mock_db_session.execute.call_args_list[2].args[0]
        rendered = str(third_stmt).lower()
        assert "max" in rendered and "updated_at" in rendered
```

## Residual / notes

- **E6 (12 survivors, LOW-VALUE):** the `.get(..., default)` branches are unreachable through the endpoint (preview always passes the dict's own keys). If WP4.4 wants them dead: a 3-line direct unit call `gpu_config._calculate_auto_assignments(strategy, gpus, services=["unknown-svc"])` asserting the default-driven placement. Otherwise leave them as accepted survivors.
- **157 unchecked mutants** (`null`) — this module is only ~30% verdicted; the survivor list and score will move. Re-triage after the run completes rather than re-reading this dossier.
- Fixture trap recorded for WP4.4: `sample_gpus` uses identical `compute_capability` strings ("8.6"/"8.6") — any latency-strategy test reusing it can never see a sort flip (that is exactly why C8 survived).
- T-B note: the `min()` tie-break in BALANCED picks the first minimum by iteration order (insertion order of `gpus`); expected map hand-traced (`enrichment`->g2 then `clip`->g2 as unique min, `yolo26`->g1 on the 4096/4096 tie). Red/green run will confirm; if tie semantics differ on the runner, adjust only the map, not the fixture.

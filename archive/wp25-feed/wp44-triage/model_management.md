# WP4.4 triage dossier — `backend/api/routes/model_management.py`

Gen-2 mutation baseline (WP4.3 feed into WP4.4). Triage only — **no tests were run, no repo file was modified.**
All 54 diffs came from `uv run mutmut show <key>` (worked for every key; raw dump `/tmp/wp25/wp44-triage/mm_diffs.txt`).
The cluster partition below was checked programmatically against the meta file: 54 keys in clusters == 54 survivors, disjoint, no invented keys.

## Run facts

| Item | Value |
| --- | --- |
| Mutants generated / checked | 155 / 155 (zero `null`) |
| Killed (exit 1) | 101 |
| **Survived (exit 0)** | **54** |
| Fold | **TEST-GAP 37 / EQUIVALENT 16 / LOW-VALUE 1** |

Survivors sit in 3 functions only: `_build_gpu_vram_info` 26, `_get_runtime_for_model` 27, `_fetch_service_status` 1.

## Root cause of the thin surface (read before fixing)

`pyproject.toml:639-641`: mutmut selects **`backend/tests/unit` only**. The integration file
`backend/tests/integration/api/routes/test_model_management_integration.py` *does* feed the primary
service keys (`vram_budget_mb`/`vram_used_mb`, built at `:72-73`) and *does* assert
`budget_mb == 6800` / `used_mb == 2100` / `available_mb == 4700` (`:406-408`) — but it is out of scope,
so it kills nothing. Consequences:

1. The only in-scope VRAM fixture is `backend/tests/unit/api/routes/test_model_management.py:690-703`,
   and it is doubly weak for this code: it supplies only the **fallback** key spellings
   (`budget_mb`/`used_mb`), and its values **mirror the module defaults exactly**
   (`HEAVY_VRAM_BUDGET_MB = 6800`, `LIGHT_VRAM_BUDGET_MB = 1200` at source `:91-92`). A fallback chain
   whose fallback equals the expected value cannot distinguish a clobbered lookup from a correct one.
2. Nothing in scope asserts `utilization_percent` at all — repo grep for `utilization` in
   `backend/tests/` hits only unrelated GPU-stats/audit surfaces; the integration tier asserts mere
   key presence (`:409`).
3. The only unit test carrying heavy-service runtime data (`:206`) asserts runtime for a **light**
   model (`:247-250`) and for a model absent from both payloads (`:253-255`) — never for a heavy model.
4. `load_count` is only ever asserted from a populated value (`:250`); its `.get(..., 0)` default and
   the not-loaded `load_count=0` constant are never reached/checked. `last_used` is never asserted at
   value level in scope (integration checks `"last_used" in runtime`, `:682`).
5. No `caplog`/`capsys` assertion exists in either model-management test file (grep clean) — so log
   text is unobservable by construction.

Covering tests per `mutants/mutmut-stats.json` (`tests_by_mangled_function_name`), all in
`backend/tests/unit/api/routes/test_model_management.py`:
`_build_gpu_vram_info` -> `TestVramSummary::test_vram_summary_aggregates_both_gpus` (`:681`),
`TestModelManagementRouterIntegration::test_vram_summary_endpoint_exists` (`:957`);
`_get_runtime_for_model` -> `:206`, `:263`, `:307`, `:925`; `_fetch_service_status` -> those plus `:681`, `:957`.
Neither helper is called directly by any test — both are reached only through the endpoint handlers.

## Cluster table (21 clusters, 37 TEST-GAP + 16 EQUIVALENT + 1 LOW-VALUE = 54)

Key prefix `MM.x__` omitted; `bgvri` = `_build_gpu_vram_info`, `grfm` = `_get_runtime_for_model`, `fss` = `_fetch_service_status`.

| # | Pattern | N | Class | Example keys | Basis |
| --- | --- | --- | --- | --- | --- |
| A | primary `vram_budget_mb` lookup clobbered (`None`, `XX..XX`, upper) | 3 | TEST-GAP | bgvri_3, bgvri_4, bgvri_5 | Loses the service's real budget; only unit fixture omits this key so the fallback path is what runs. |
| B | fallback `budget_mb` alias lookup clobbered -> module default | 3 | TEST-GAP | bgvri_6, bgvri_10, bgvri_11 | Kill needs a payload where `budget_mb` != `HEAVY/LIGHT_VRAM_BUDGET_MB`; the existing fixture mirrors the defaults, so the assert can't tell. |
| C | fallback budget default dropped (`default_budget_mb` -> `None`/omitted) | 2 | TEST-GAP | bgvri_7, bgvri_9 | Needs a payload with no budget key at all; original yields the module default, mutant yields `None` (schema `budget_mb: int` rejects it). |
| D | primary `vram_used_mb` lookup clobbered | 3 | TEST-GAP | bgvri_14, bgvri_15, bgvri_16 | Reports `used_mb=0`, inflates `available_mb`, zeroes utilization. Real production hazard: dashboard shows 0% used. |
| E | utilization scale flipped (`*100` -> `/100`, `*101`) | 2 | TEST-GAP | bgvri_41, bgvri_43 | 0.0 / 30.4 vs 30.1. |
| F | utilization zero-budget guard broken (`>=0`, `>1`, `and False`, `or True`) | 4 | TEST-GAP | bgvri_39, bgvri_40, bgvri_44, bgvri_45 | `>=0` and `or True` turn `budget_mb == 0` into a live **ZeroDivisionError**; `and False` forces 0.0. |
| G | utilization else-branch `0.0` -> `1.0` | 1 | TEST-GAP | bgvri_46 | Reports 1% used on a zero-budget GPU. |
| H | utilization rounding (`2`, `None`, dropped, `round(1)`) | 4 | TEST-GAP | bgvri_62, bgvri_63, bgvri_64, bgvri_65 | 29.42 / 29.0 / 29 / 1 vs 29.4. Discriminating value needed: 353/1200 = 29.4166 (29.4 vs 29.42). |
| I | `loaded_models_data` empty default `{}` -> `None` (+ trailing comma) | 2 | EQUIVALENT | bgvri_26, bgvri_28 | Both fail `isinstance(..., dict)` and `isinstance(..., list)` -> `loaded_models = []` either way. |
| J | `isinstance(..., list) or True` | 1 | EQUIVALENT | bgvri_35 | Branch only runs on a non-dict value, which must be a list or the `[]` default. |
| K | `used_mb` fallback default `0` -> `1` | 1 | LOW-VALUE | bgvri_23 | Only fires on a payload with neither `vram_used_mb` nor `used_mb`; 1 MB of phantom usage. |
| L | `status is None` branch: heavy models forced to `status = None` | 1 | TEST-GAP | grfm_3 | Most dangerous survivor: every GPU-0 model reports `loaded=False`, `actual_vram_mb=None`, `load_count=0` while the service says it is loaded. |
| M | not-loaded branches `load_count=0` -> `1` | 2 | TEST-GAP | grfm_12, grfm_70 | A never-loaded model claims 1 load. Both in-scope not-loaded asserts check only `loaded`/`actual_vram_mb`. |
| N | `actual_vram_mb` primary key clobbered | 3 | TEST-GAP | grfm_47, grfm_48, grfm_49 | Survives because both unit fixtures carry the legacy `vram_mb` key that the `or` fallback rescues. |
| O | `last_used` value dropped/clobbered | 5 | TEST-GAP | grfm_39, grfm_43, grfm_53, grfm_54, grfm_55 | Hard-coded `None`, arg removed, or key clobbered; no in-scope test asserts the value. |
| P | `load_count` fallback default -> `None`/`1` (+ trailing comma) | 3 | TEST-GAP | grfm_57, grfm_59, grfm_62 | Needs a loaded model whose detail omits `load_count`; both fixtures always populate it. |
| Q | `isinstance(models_dict, dict) and` -> `or` | 1 | TEST-GAP | grfm_33 | Only reachable with a malformed payload (list-format `loaded_models`, no `models` key): original degrades to `model_info=None`, mutant raises and the endpoint 500s. Needs a dedicated fixture; lower priority. |
| R | `.get("loaded_models"/"models", {})` default dropped | 4 | EQUIVALENT | grfm_15, grfm_17, grfm_28, grfm_30 | `None` and `{}` both fail the `isinstance` guards -> same path. |
| S | falsy sentinel swaps (`is_loaded=None`, `model_info=""`) | 2 | EQUIVALENT | grfm_20, grfm_22 | Both consumed only by `if x:`. |
| T | redundant explicit-`None` kwargs removed / trailing-comma call form | 6 | EQUIVALENT | grfm_8, grfm_9, grfm_10, grfm_66, grfm_67, grfm_68 | `actual_vram_mb=None`, `last_used=None` are the schema defaults (`schemas/model_management.py:73-88`); the constructed object is identical. |
| U | `logger.warning(f"Cannot connect to {service_url}")` -> `logger.warning(None)` | 1 | EQUIVALENT | fss_6 | No log-capture assertion in scope; return value unchanged. |

## Drafted tests (6) — `// UNVERIFIED - not yet run red/green`

Target file: `backend/tests/unit/api/routes/test_model_management.py` (append; reuses the existing
`mock_enrichment_client` fixture at `:84`, the `@patch(..., autospec=True)` decorator habit and the
local `from backend.api.routes.model_management import <fn>` import style of the surrounding tests).
`from datetime import UTC, datetime` must be added to the module's imports (style precedent:
`backend/tests/unit/api/schemas/test_model_management.py:16`).

TDD procedure, once for all six: write the test against the **mutant** diff, watch the named
assertion fail; run against the original source, watch it pass. Never run both at once.

### 1. `TestVramSummaryFallbackChain` — kills A, B, C, D (11 survivors)

```python
class TestVramSummaryFallbackChain:
    """VRAM budget/usage lookups: primary key, fallback alias, module default.

    The existing TestVramSummary fixture sends only the fallback spellings AND mirrors
    the module defaults (6800/1200), so every clobber of the four lookup slots in
    _build_gpu_vram_info was invisible at the unit tier.
    """

    @staticmethod
    def _client(mock_get_http_client: MagicMock, heavy: dict, light: dict) -> AsyncMock:
        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = heavy
        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = light

        async def mock_get(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                return light_response
            return heavy_response

        client = AsyncMock()
        client.get = mock_get
        mock_get_http_client.return_value = client
        return client

    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_vram_summary_reads_primary_vram_keys(
        self,
        mock_get_http_client: MagicMock,
    ) -> None:
        """vram_budget_mb / vram_used_mb win over the budget_mb / used_mb aliases."""
        # Both spellings present; the aliases carry decoys so a clobbered primary
        # lookup lands on a visibly wrong number instead of the correct fallback.
        self._client(
            mock_get_http_client,
            heavy={
                "vram_budget_mb": 6800, "budget_mb": 1,
                "vram_used_mb": 2000, "used_mb": 1,
                "loaded_models": {"fashion-clip": {"actual_vram_mb": 480}},
            },
            light={
                "vram_budget_mb": 1200, "budget_mb": 2,
                "vram_used_mb": 300, "used_mb": 2,
                "loaded_models": ["threat-detection-yolov8n"],
            },
        )

        from backend.api.routes.model_management import get_vram_summary

        result = await get_vram_summary(http_client=mock_get_http_client.return_value)

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        assert gpu0.budget_mb == 6800
        assert gpu0.used_mb == 2000
        assert gpu0.available_mb == 4800
        assert gpu0.loaded_models == ["fashion-clip"]

        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        assert gpu1.budget_mb == 1200
        assert gpu1.used_mb == 300
        assert gpu1.available_mb == 900
        assert gpu1.loaded_models == ["threat-detection-yolov8n"]

        assert result.totals.budget_mb == 8000
        assert result.totals.used_mb == 2300
        assert result.totals.available_mb == 5700

    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_vram_summary_falls_back_to_budget_mb_alias(
        self,
        mock_get_http_client: MagicMock,
    ) -> None:
        """With no vram_budget_mb, the budget_mb alias must be used -- NOT the module default.

        The alias values deliberately differ from HEAVY_VRAM_BUDGET_MB / LIGHT_VRAM_BUDGET_MB
        (6800 / 1200); a clobbered alias lookup silently substitutes those defaults.
        """
        self._client(
            mock_get_http_client,
            heavy={"budget_mb": 5000, "used_mb": 1000, "loaded_models": []},
            light={"budget_mb": 900, "used_mb": 100, "loaded_models": []},
        )

        from backend.api.routes.model_management import get_vram_summary

        result = await get_vram_summary(http_client=mock_get_http_client.return_value)

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        assert gpu0.budget_mb == 5000
        assert gpu0.used_mb == 1000
        assert gpu0.available_mb == 4000
        assert gpu1.budget_mb == 900
        assert gpu1.used_mb == 100
        assert gpu1.available_mb == 800

    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_vram_summary_uses_module_default_when_no_budget_key(
        self,
        mock_get_http_client: MagicMock,
    ) -> None:
        """A payload with no budget key at all must fall back to the module default budget."""
        self._client(
            mock_get_http_client,
            heavy={"loaded_models": []},
            light={"loaded_models": []},
        )

        from backend.api.routes.model_management import (
            HEAVY_VRAM_BUDGET_MB,
            LIGHT_VRAM_BUDGET_MB,
            get_vram_summary,
        )

        result = await get_vram_summary(http_client=mock_get_http_client.return_value)

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        assert gpu0.budget_mb == HEAVY_VRAM_BUDGET_MB
        assert gpu0.used_mb == 0
        assert gpu1.budget_mb == LIGHT_VRAM_BUDGET_MB
        assert gpu1.used_mb == 0
```

Kill mapping: **A/D** — clobbered primary lookups land on the decoy `1`/`2`, failing
`budget_mb == 6800` / `used_mb == 2000`. **B** — clobbered alias lookup lands on 6800/1200, failing
`budget_mb == 5000` / `== 900`. **C** — dropped default yields `None`, failing the same default
assert (and the `budget_mb: int` schema before that).

### 2. `TestVramUtilization` — kills E, F, G, H (11 survivors)

```python
class TestVramUtilization:
    """utilization_percent had no assertion anywhere in mutmut's unit-only scope."""

    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_vram_summary_computes_utilization_percent(
        self,
        mock_get_http_client: MagicMock,
    ) -> None:
        """Utilization is used / budget * 100, rounded to one decimal."""
        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = {
            "budget_mb": 6800, "used_mb": 2047, "loaded_models": ["fashion-clip"],
        }
        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = {
            "budget_mb": 1200, "used_mb": 353, "loaded_models": ["threat-detection-yolov8n"],
        }

        async def mock_get(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                return light_response
            return heavy_response

        client = AsyncMock()
        client.get = mock_get
        mock_get_http_client.return_value = client

        from backend.api.routes.model_management import get_vram_summary

        result = await get_vram_summary(http_client=client)

        gpu0 = next(g for g in result.gpus if g.gpu_id == 0)
        gpu1 = next(g for g in result.gpus if g.gpu_id == 1)
        # 2047/6800 = 30.10294% -> 30.1   (*101 mutant -> 30.4, /100 mutant -> 0.0)
        assert gpu0.utilization_percent == 30.1
        # 353/1200 = 29.41666% -> 29.4   (round(x,2) -> 29.42, round(x,None)/round(x) -> 29.0)
        assert gpu1.utilization_percent == 29.4

    def test_zero_and_unit_budget_do_not_raise_or_inflate_utilization(self) -> None:
        """budget_mb 0 must short-circuit (not ZeroDivisionError); budget_mb 1 must still compute."""
        from backend.api.routes.model_management import _build_gpu_vram_info

        zero = _build_gpu_vram_info(0, "ai-enrichment", {"budget_mb": 0, "used_mb": 0}, 6800)
        assert zero.budget_mb == 0
        assert zero.available_mb == 0
        assert zero.utilization_percent == 0.0

        one = _build_gpu_vram_info(0, "ai-enrichment", {"budget_mb": 1, "used_mb": 1}, 6800)
        assert one.utilization_percent == 100.0
```

Kill mapping: **E** 41/43 -> 0.0 / 30.4; **F** 39 -> 0.0, 40 and 44 -> `ZeroDivisionError` on the
zero-budget call, 45 (`> 1`) -> 0.0 instead of 100.0 on the budget-1 call; **G** 46 -> 1.0 instead of
0.0 on the zero-budget call; **H** 62/63/64/65 -> 29.0 / 1.0 / 29.0 / 29.42 against `== 29.4`.

### 3. `TestHeavyRuntimeState` — kills L (1 survivor, highest severity)

```python
class TestHeavyRuntimeState:
    """GPU-0 runtime state was never asserted against heavy service data."""

    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_list_models_reports_loaded_state_for_heavy_models(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        """Heavy models read the heavy service; light models read the light service."""
        mock_get_model_zoo.return_value = sample_model_configs

        heavy_response = MagicMock()
        heavy_response.status_code = 200
        heavy_response.json.return_value = {
            "loaded_models": {
                "fashion-clip": {
                    "actual_vram_mb": 480,
                    "last_used": "2025-01-31T10:20:00Z",
                    "load_count": 2,
                }
            }
        }
        light_response = MagicMock()
        light_response.status_code = 200
        light_response.json.return_value = {"loaded_models": {}}

        async def mock_get(url: str, **kwargs):
            if "ai-enrichment-light" in url:
                return light_response
            return heavy_response

        client = AsyncMock()
        client.get = mock_get
        mock_get_http_client.return_value = client

        from backend.api.routes.model_management import list_models

        response = await list_models(http_client=client)

        fashion = next(m for m in response.models if m.name == "fashion-clip")
        assert fashion.gpu_id == 0
        assert fashion.service == "ai-enrichment"
        # grfm_3 forces status=None for every non-light model, collapsing all three
        # of these to loaded=False / actual_vram_mb=None / load_count=0.
        assert fashion.runtime.loaded is True
        assert fashion.runtime.actual_vram_mb == 480
        assert fashion.runtime.load_count == 2

        # The genuinely empty light service must not look loaded either.
        threat = next(m for m in response.models if m.name == "threat-detection-yolov8n")
        assert threat.gpu_id == 1
        assert threat.runtime.loaded is False
        assert threat.runtime.load_count == 0
```

### 4. `TestRuntimeDetailFields` — kills N, O (8 survivors)

```python
class TestRuntimeDetailFields:
    """actual_vram_mb was only ever exercised via its legacy fallback; last_used never at value level."""

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_model_status_runtime_prefers_actual_vram_and_surfaces_last_used(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 200
        # Legacy vram_mb carries a decoy, so a clobbered actual_vram_mb lookup is
        # rescued into a visibly wrong number rather than passing by fallback.
        response.json.return_value = {
            "loaded_models": {
                model_name: {
                    "actual_vram_mb": 287,
                    "vram_mb": 111,
                    "last_used": "2025-01-31T10:30:00Z",
                    "load_count": 5,
                }
            }
        }
        client = AsyncMock()
        client.get = AsyncMock(return_value=response)
        mock_get_http_client.return_value = client

        from backend.api.routes.model_management import get_model_status

        result = await get_model_status(model_name=model_name, http_client=client)

        assert result.runtime.loaded is True
        assert result.runtime.actual_vram_mb == 287
        assert result.runtime.last_used == datetime(2025, 1, 31, 10, 30, 0, tzinfo=UTC)
        assert result.runtime.load_count == 5
```

### 5. `TestRuntimeDefaults::test_loaded_model_without_load_count_detail_defaults_to_zero` — kills P (3)

```python
class TestRuntimeDefaults:
    """The load_count fallback default and the not-loaded constants were never reached."""

    @patch("backend.api.routes.model_management.get_model_config", autospec=True)
    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_loaded_model_without_load_count_detail_defaults_to_zero(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_config: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        """A loaded model whose detail omits load_count reports 0 -- not 1, not None."""
        model_name = "threat-detection-yolov8n"
        mock_get_model_config.return_value = sample_model_configs[model_name]

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"loaded_models": {model_name: {"actual_vram_mb": 287}}}
        client = AsyncMock()
        client.get = AsyncMock(return_value=response)
        mock_get_http_client.return_value = client

        from backend.api.routes.model_management import get_model_status

        result = await get_model_status(model_name=model_name, http_client=client)

        assert result.runtime.loaded is True
        assert result.runtime.load_count == 0
        assert result.runtime.last_used is None
```

### 6. `TestRuntimeDefaults::test_unloaded_models_report_zero_load_count` — kills M (2)

```python
    @patch("backend.api.routes.model_management.get_model_zoo", autospec=True)
    @patch("backend.api.routes.model_management.get_http_client", autospec=True)
    async def test_unloaded_models_report_zero_load_count(
        self,
        mock_get_http_client: MagicMock,
        mock_get_model_zoo: MagicMock,
        sample_model_configs: dict[str, ModelConfig],
    ) -> None:
        """Every not-loaded model reports load_count 0 -- never 1."""
        import httpx

        mock_get_model_zoo.return_value = sample_model_configs
        client = AsyncMock()
        client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_get_http_client.return_value = client

        from backend.api.routes.model_management import list_models

        response = await list_models(http_client=client)

        assert len(response.models) == 5
        for model in response.models:
            assert model.runtime.loaded is False
            assert model.runtime.actual_vram_mb is None
            assert model.runtime.last_used is None
            assert model.runtime.load_count == 0, f"{model.name} was never loaded"
```

## Cluster -> drafted test map

| Cluster | Killed by |
| --- | --- |
| A, B, C, D | draft 1 (three methods: primary keys / alias / module default) |
| E, F, G, H | draft 2 (endpoint computation + zero/unit-budget direct call) |
| L | draft 3 |
| N, O | draft 4 |
| P | draft 5 |
| M | draft 6 |
| Q | **not drafted** — needs a malformed-payload fixture (list-format `loaded_models` with the `models` key absent) to reach the `or`-mutant's crash path; log as a follow-up, lowest priority of the TEST-GAP set. |
| K | not drafted (LOW-VALUE): a single payload without any usage key kills it via `available_mb == budget_mb` if the fix lane wants it. |
| I, J, R, S, T, U | not drafted (EQUIVALENT — semantically identical or unobservable by construction). |

## Notes for the fix lane

- **Cheapest structural win**: the existing `TestVramSummary` fixture (`:690-703`) is doing double
  duty wrong — its `budget_mb`/`used_mb` values equal `HEAVY_VRAM_BUDGET_MB`/`LIGHT_VRAM_BUDGET_MB`
  exactly, so even the *correct* fallback path is indistinguishable from a clobbered one. Any value
  change there (plus a `vram_*` pair) retires clusters A-D without new test bodies.
- Clusters A and D are the real production exposure: the enrichment services emit
  `vram_budget_mb`/`vram_used_mb`, and the unit tier has never fed those keys.
- Draft 2's `test_zero_and_unit_budget_do_not_raise_or_inflate_utilization` calls the private helper
  directly; the existing suite has no precedent for that (every test goes through a handler). If the
  fix lane prefers endpoint-only coverage, the zero-budget case can be driven through
  `get_vram_summary` instead, but then it needs a patched `HEAVY_VRAM_BUDGET_MB` to reach budget 0.
- `VramGpuInfo.utilization_percent` is bounded `ge=0.0, le=100.0` (`schemas/model_management.py:257-262`).
  A mutant whose output lands outside the range is clamped/rejected into equality with the original,
  which can mask a kill — the drafted assertions deliberately use in-range values (30.1, 29.4, 100.0).
- `pyproject.toml:639-641` is worth a ruling upstream: with `pytest_add_cli_args_test_selection`
  pinned to `backend/tests/unit`, every finding here is "untested at the tier that counts", not
  "untested anywhere".

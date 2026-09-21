# WP4.4 Triage Dossier — backend/services/orchestrator/models.py

- **Survivors:** 97 of 226 checked (129 killed, 0 unchecked)
- **Method:** survivor keys from `mutants/backend/services/orchestrator/models.py.meta`
  (`exit_code == 0`); diffs extracted from the mutant copy (block-diff of each
  `xǁManagedServiceǁ<fn>__mutmut_N` against its `__mutmut_orig`) and spot-cross-checked
  against `mutmut show` (agreement on sampled keys; batch `mutmut show` was rate-limited
  by the concurrent run, so the manual extraction is authoritative).
  Raw extraction: `/tmp/wp25/wp44-triage/manual-diffs.txt`; machine-readable cluster
  membership: `/tmp/wp25/wp44-triage/clusters.json`.
- **Functions hit:** `from_dict` (72), `from_config` (14), `to_dict` (10), `in_grace_period` (1).
  Every survivor is a one-line change inside a `cls(...)` kwarg, a `data.get(...)` call,
  a dict-literal key string, or one comparison operator. Nothing else.

## Why so many survive (root cause, shared by every cluster)

`ManagedService.__init__` accepts every field with a default and no validation, so *any*
wrong value / None / omitted kwarg is silently constructible. The covering tests
(`backend/tests/unit/services/orchestrator/test_models.py:106-201,289-322` and
`backend/tests/unit/services/test_service_registry.py:912-968`) then:

1. only assert fields whose payload value is **non-default and distinct from the dataclass
   default** — every field left at its default in the test payloads (`health_cmd`,
   `warmth_state`, backoffs, grace period, `image=None`, and even `port` in
   `test_from_dict`!) is invisible;
2. never parse a payload with **optional keys absent**, so every `data.get(key, default)`
   fallback default is never observed;
3. never assert the **wire key names** for 5 of the 19 `to_dict` keys;
4. never assert what `from_config` propagates for 7 of 13 kwargs.

Round-trip test (`test_models.py:289`) looks comprehensive but asserts only 8 fields
(name, display_name, container_id, category, status, failure_count, restart_count,
max_failures) — exactly the 8 whose fixture values are non-default. `health_cmd` is set
to `"curl /health"` in the fixture and never asserted.

## Cluster table (counts sum to 97; membership in clusters.json)

| # | Cluster | Fn | Count | Class | Example keys (suffix of `backend.services.orchestrator.models.xǁManagedServiceǁ…`) |
|---|---------|----|-------|-------|-----------|
| C1 | `data.get` **fallback default clobbered**: 0→1/None/omitted, 5→6/None, 5.0→6.0/None, 300.0→301.0/None, 60→61/None, True→False/None, "unknown"→"UNKNOWN"/"XXunknownXX", plus single-arg collapses (`data.get(5.0)` — declared fallback no longer supplied → field None on absent key). Observable only when key is absent. | from_dict | 30 | TEST-GAP | `from_dict__mutmut_102`, `_116`, `_137` |
| C2 | `data.get` **lookup key clobbered** (`"foo"`→`None`/`"XXfooXX"`/`"FOO"`) for image, health_endpoint, health_cmd, enabled, warmth_state, restart_backoff_base/max, startup_grace_period → a **present** payload value is silently discarded, dataclass default substituted | from_dict | 24 | TEST-GAP | `from_dict__mutmut_70`, `_85`, `_122` |
| C3 | **kwarg value hard-set to None** (`port=None`, `image=None`, `health_endpoint=None`, `health_cmd=None`, `enabled=None`, `warmth_state=None`, backoffs None, grace None) — payload value ignored, field becomes None | from_dict | 9 | TEST-GAP | `from_dict__mutmut_29`, `_34`, `_35` |
| C4 | **kwarg removed** (health_endpoint, health_cmd, enabled, warmth_state, restart_backoff_base/max, startup_grace_period) — payload value ignored, dataclass default substituted | from_dict | 7 | TEST-GAP | `from_dict__mutmut_53`, `_60`, `_62` |
| C5 | datetime **sentinel `None` → `""`** for absent `last_failure_at`/`last_restart_at` — module logic is truthiness-based so behavior is near-identical, but it violates the `datetime \| None` contract and downstream `is None` checks; existing tests assert `is not None` only in the *present* case, the *absent* case is only reached via `minimal_service` default (kills _1/_9 with `is None` if asserted) | from_dict | 2 | TEST-GAP | `from_dict__mutmut_1`, `_9` |
| C6 | `to_dict` **wire key renamed** (`"health_cmd"`→`"XXhealth_cmdXX"`/`"HEALTH_CMD"`, same pair for warmth_state, restart_backoff_base, restart_backoff_max, startup_grace_period) — API/persisted-JSON consumers reading these keys get undefined | to_dict | 10 | TEST-GAP | `to_dict__mutmut_13`, `_21`, `_39` |
| C7 | `from_config` **kwarg value → None** (port, health_endpoint, health_cmd, status, enabled, restart_backoff_base, restart_backoff_max) — discovered service gets None port/status/backoff; downstream health checks & self-healing break | from_config | 7 | TEST-GAP | `from_config__mutmut_5`, `_9`, `_10` |
| C8 | `from_config` **kwarg removed** for health_endpoint, health_cmd, restart_backoff_base, restart_backoff_max — config-provided values silently replaced by dataclass defaults (None/None/5.0/300.0) | from_config | 4 | TEST-GAP | `from_config__mutmut_20`, `_26`, `_27` |
| C9 | `from_config` **kwarg removed** for `status=ContainerServiceStatus.NOT_FOUND` and `enabled=True` — dataclass default *is* that same value, resulting state bit-identical | from_config | 2 | EQUIVALENT | `from_config__mutmut_23`, `_24` |
| C10 | `from_config` **`enabled=True` → `False`** — every discovered service starts with auto-restart disabled; self-healing silently dead | from_config | 1 | TEST-GAP | `from_config__mutmut_29` |
| C11 | `in_grace_period` **`elapsed < startup_grace_period` → `<=`** — boundary becomes inclusive; tests use elapsed 0s and 120s vs grace 60s, never the equality point | in_grace_period | 1 | TEST-GAP | `in_grace_period__mutmut_4` |

Totals: **TEST-GAP 95, EQUIVALENT 2, LOW-VALUE 0** (module contains no logging or
messages, so no truly cosmetic mutants exist).

### Exact members (mutant numbers per function; keys = prefix + name)

- C1 from_dict: 82, 83, 84, 87, 89, 90, 91, 94, 95, 97, 99, 102, 104, 106, 109, 111, 113, 116, 118, 119, 120, 123, 125, 126, 127, 130, 132, 133, 134, 137
- C2 from_dict: 70, 71, 72, 75, 76, 77, 78, 79, 80, 81, 85, 86, 88, 92, 93, 117, 121, 122, 124, 128, 129, 131, 135, 136
- C3 from_dict: 28, 29, 30, 31, 34, 35, 41, 42, 43
- C4 from_dict: 49, 50, 53, 54, 60, 61, 62
- C5 from_dict: 1, 9
- C6 to_dict: 13, 14, 21, 22, 37, 38, 39, 40, 41, 42
- C7 from_config: 5, 6, 7, 9, 10, 12, 13
- C8 from_config: 20, 21, 26, 27
- C9 from_config: 23, 24
- C10 from_config: 29
- C11 in_grace_period: 4

(Single-arg collapses — 83, 90, 119, 126, 133 — are counted under C1 by shape: the second
`get` argument was mutated into the first. T2 also kills them by behavior; T1 kills them
too via absent-key defaults. Double coverage is fine.)

## Covering tests (read, judged)

| Test | File:line | Asserts | Misses |
|------|-----------|---------|--------|
| `TestManagedService::test_to_dict` | test_models.py:106 | name, display_name, container_id, category, status, enabled | keys+values for health_cmd, warmth_state, restart_backoff_base/max, startup_grace_period, port, image, null-timestamps → **C6** |
| `TestManagedService::test_to_dict_with_timestamps` | test_models.py:116 | the two ISO timestamps | everything else |
| `TestManagedService::test_from_dict` | test_models.py:135 | name, category, status, failure_count, restart_count (payload port=8080, health_endpoint="/health" never asserted!) | value propagation for every optional field; absent-key defaults; `enabled` True case → **C1,C2,C3,C4,C5** |
| `TestManagedService::test_from_dict_with_timestamps` | test_models.py:158 | timestamps not-None + ±1s | everything else |
| `TestManagedService::test_from_config` | test_models.py:178 | name, display_name, container_id, image, category, max_failures, startup_grace_period | port, health_endpoint, health_cmd, status, enabled, restart_backoff_base/max → **C7,C8,C10** |
| `TestManagedService::test_roundtrip_to_from_dict` | test_models.py:289 | 8 fields | the other 11 (incl. health_cmd despite fixture setting it) → C2/C4/C6 |
| `TestManagedService::test_in_grace_period_*` | test_models.py:232/236/252 | False@never, True@elapsed 0s, False@120s (grace 60) | exact boundary elapsed == 60 → **C11** |
| `TestManagedServiceSerialization::test_to_dict` | test_service_registry.py:915 | 8 keys (adds image, port, health_endpoint) | same 5 keys as C6 |
| `TestManagedServiceSerialization::test_from_dict` | test_service_registry.py:939 | name, category, status, failure_count, last_failure_at-not-None; payload carries every optional key but at **default-equal values** (max_failures 5, backoffs 5.0/300.0, grace 60) so value-clobbers remain invisible | non-default optional values, absent-key defaults → **C1,C2,C3,C4** |

Style anchors: class-based `TestManagedService`, `-> None` annotations, docstring per test,
fixture `minimal_service` (health_cmd=None), bare `datetime.now(UTC)` (no global freezegun —
freeze per-test only, per memory "Vitest midnight flake window").

## Drafted kill-tests (5 tests kill 95 of 97 survivors)

Target file: `backend/tests/unit/services/orchestrator/test_models.py` — append the four
`TestManagedService` methods to that class; T5 also needs the module-level import line
shown. All **UNVERIFIED — not yet run red/green**.

### T1 — `test_from_dict_applies_defaults_for_omitted_optional_keys` → kills C1 (30) + C5 (2) = 32

```python
    def test_from_dict_applies_defaults_for_omitted_optional_keys(self) -> None:
        """from_dict fills declared fallback defaults for every omitted optional key."""
        data = {
            "name": "test",
            "display_name": "Test",
            "port": 8080,
            "category": "ai",
            "status": "not_found",
        }
        service = ManagedService.from_dict(data)
        assert service.container_id is None
        assert service.image is None
        assert service.health_endpoint is None
        assert service.health_cmd is None
        assert service.enabled is True  # kills _82/_84/_87 (enabled default None/omitted/False)
        assert service.warmth_state == "unknown"  # kills _94/_95 (sentinel clobbered)
        assert service.failure_count == 0  # kills _102/_109 (0 -> 1)
        assert service.last_failure_at is None  # kills C5 sentinels (_1/_9 None -> "")
        assert service.last_restart_at is None
        assert service.restart_count == 0  # kills _104/_106/_109 (0 -> None/omitted/1)
        assert service.max_failures == 5  # kills _111/_113/_116 (5 -> None/omitted/6)
        assert service.restart_backoff_base == 5.0  # kills _118/_119/_120/_123
        assert service.restart_backoff_max == 300.0  # kills _125/_126/_127/_130
        assert service.startup_grace_period == 60  # kills _132/_133/_134/_137
```

TDD: on any C1 mutant exactly one `==`/`is` default assertion flips (0→1, 60→61,
single-arg `get(60)` → None); on C5 the `is None` fails against `""`; green on original.

### T2 — `test_from_dict_reads_every_optional_field_from_payload` → kills C2 (24) + C3 (9) + C4 (7) = 40

```python
    def test_from_dict_reads_every_optional_field_from_payload(self) -> None:
        """from_dict propagates every optional field when the payload supplies non-default values."""
        data = {
            "name": "test",
            "display_name": "Test",
            "container_id": "abc123",
            "image": "postgres:16-alpine",  # kills _70/_71/_72 (C2) + _28 (None)
            "port": 8080,  # kills _29 (port=None)
            "health_endpoint": "/health",  # kills _75/_76/_77 + _30/_49
            "health_cmd": "pg_isready",  # kills _78/_79/_80 + _31/_50
            "category": "ai",
            "status": "running",
            "enabled": False,  # kills _81/_83/_85/_86 + _34 (None) + _53 (drop -> default True)
            "warmth_state": "warm",  # kills _88/_90/_92/_93 + _35 + _54
            "failure_count": 7,
            "restart_count": 3,
            "max_failures": 9,
            "restart_backoff_base": 2.5,  # kills _117/_119/_121/_122 + _41 + _60
            "restart_backoff_max": 90.5,  # kills _124/_126/_128/_129 + _42 + _61
            "startup_grace_period": 15,  # kills _131/_133/_135/_136 + _43 + _62
        }
        service = ManagedService.from_dict(data)
        assert service.container_id == "abc123"
        assert service.image == "postgres:16-alpine"
        assert service.port == 8080
        assert service.health_endpoint == "/health"
        assert service.health_cmd == "pg_isready"
        assert service.enabled is False
        assert service.warmth_state == "warm"
        assert service.failure_count == 7
        assert service.restart_count == 3
        assert service.max_failures == 9
        assert service.restart_backoff_base == 2.5
        assert service.restart_backoff_max == 90.5
        assert service.startup_grace_period == 15
```

TDD: C2 (key clobber) and C4 (kwarg drop) fall to the dataclass default ≠ payload value;
C3 (None-swap) fails every `==`/`is`; green on original.

### T3 — `test_to_dict_serializes_every_expected_key` → kills C6 (10)

```python
    TO_DICT_KEYS: frozenset[str] = frozenset(  # class attribute of TestManagedService
        {
            "name", "display_name", "container_id", "image", "port",
            "health_endpoint", "health_cmd", "category", "status", "enabled",
            "warmth_state", "failure_count", "last_failure_at", "last_restart_at",
            "restart_count", "max_failures", "restart_backoff_base",
            "restart_backoff_max", "startup_grace_period",
        }
    )

    def test_to_dict_serializes_every_expected_key(self) -> None:
        """to_dict emits exactly the canonical key set with correct values (wire contract)."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
            health_cmd="curl /health",
            warmth_state="warm",
            restart_backoff_base=2.0,
            restart_backoff_max=120.0,
            startup_grace_period=30,
        )
        data = service.to_dict()
        assert set(data) == self.TO_DICT_KEYS  # any rename (XX…/UPPER) mismatches here
        assert data["health_cmd"] == "curl /health"
        assert data["warmth_state"] == "warm"
        assert data["restart_backoff_base"] == 2.0
        assert data["restart_backoff_max"] == 120.0
        assert data["startup_grace_period"] == 30
```

TDD: renamed key ⇒ both the set-equality and the direct `data[...]` assert go red; green
on original.

### T4 — `test_from_config_propagates_all_settings` → kills C7 (7) + C8 (4) + C10 (1) = 12
(C9's 2 members are EQUIVALENT — unkillable by construction.)

```python
    def test_from_config_propagates_all_settings(self) -> None:
        """from_config copies every ServiceConfig setting (health + backoff) onto the service."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5433,
            health_endpoint="/healthz",
            health_cmd="pg_isready -U security",
            max_failures=8,
            restart_backoff_base=2.0,
            restart_backoff_max=64.0,
            startup_grace_period=15,
        )
        service = ManagedService.from_config(
            config_key="postgres",
            config=config,
            container_id="abc123",
            image="postgres:16-alpine",
        )
        assert service.port == 5433  # kills _5 (port=None)
        assert service.health_endpoint == "/healthz"  # kills _6, _20
        assert service.health_cmd == "pg_isready -U security"  # kills _7, _21
        assert service.status == ContainerServiceStatus.NOT_FOUND  # kills _9 (status=None)
        assert service.enabled is True  # kills _10 (None) and _29 (False)
        assert service.max_failures == 8
        assert service.restart_backoff_base == 2.0  # kills _12, _26 (drop -> dataclass 5.0)
        assert service.restart_backoff_max == 64.0  # kills _13, _27 (drop -> 300.0)
        assert service.startup_grace_period == 15
```

TDD: each None-swap/drop produces None or the dataclass default (5.0/300.0/None) ≠ config
value; `enabled is True` kills the False flip; green on original. Config values deliberately
differ from dataclass defaults so drops (C8) cannot masquerade as defaults — the exact
mistake the existing `test_from_config` makes with `max_failures=10` vs default 5.

### T5 — `test_in_grace_period_boundary_is_exclusive` → kills C11 (1)

```python
# add alongside the existing imports at module top of test_models.py:
#   import backend.services.orchestrator.models as models_module
    def test_in_grace_period_boundary_is_exclusive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """in_grace_period is False exactly at the boundary (strict <, not <=)."""
        fixed = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):  # type: ignore[override]
                return fixed if tz is None else fixed.astimezone(tz)

        monkeypatch.setattr(models_module, "datetime", _FrozenDatetime)
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
            last_restart_at=fixed - timedelta(seconds=60),
            startup_grace_period=60,
        )
        assert service.in_grace_period() is False  # elapsed == grace -> out (kills `<=` mutant)
        service.last_restart_at = fixed - timedelta(seconds=59)
        assert service.in_grace_period() is True  # elapsed < grace -> in
```

TDD: mutant `elapsed <= grace` returns True at elapsed == 60 ⇒ first assert red; original
`60 < 60` is False ⇒ green. Clock frozen per-test via monkeypatch of the models module
namespace (avoids the global-fake-timer pitfalls noted in memory).

## Kill ledger

| Drafted test | Clusters killed | Mutants |
|---|---|---|
| T1 | C1 + C5 | 32 |
| T2 | C2 + C3 + C4 | 40 |
| T3 | C6 | 10 |
| T4 | C7 + C8 + C10 | 12 |
| T5 | C11 | 1 |
| — (unkillable, EQUIVALENT) | C9 | 2 |
| **Total** | | **97** |

## WP4.4 notes

- `test_service_registry.py::TestManagedServiceSerialization` duplicates the same weak
  assertions; a fix in `test_models.py` suffices for the kill (coverage is the union),
  but keep both honest to avoid drift.
- Root-cause hardening beyond tests (Linear-worthy, out of WP4.4 scope): `from_dict`
  could validate parsed types (port int, backoff floats, timestamps datetime) so
  None-injection fails loudly instead of constructing a poisoned object.

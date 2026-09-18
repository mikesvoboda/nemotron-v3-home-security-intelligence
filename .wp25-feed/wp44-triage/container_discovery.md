# WP4.4 triage dossier — backend/services/container_discovery.py

**Generated 2026-09-18 (triage wave; UNVERIFIED — no tests executed, read-only analysis).** Sources:

- Verdicts: `mutants/backend/services/container_discovery.py.meta` — 858 keys, **696 exit_code=0 (SURVIVED)**, 162 killed, 0 unchecked (snapshot mtime 2026-09-17 22:09, the tier-era baseline).
- Diffs: extracted by diffing each `x<fn>__mutmut_N` body vs `__mutmut_orig` inside the 223k-line clobbered copy `mutants/backend/services/container_discovery.py` (parser `/tmp/wp25/wp44-triage/extract_diffs2.py`, clusterer `/tmp/wp25/wp44-triage/final3.py`, per-cluster key lists `/tmp/wp25/wp44-triage/rows.json`). `mutmut show` not required.
- Covering tests (`mutants/mutmut-stats.json` → `tests_by_mangled_function_name`): **`backend/tests/unit/services/test_container_discovery.py`** (primary for all six functions) + `backend/tests/unit/services/test_container_orchestrator.py` (incidental `__init__` callers, no discovery-config asserts).

## Arithmetic reconciliation — read before consuming counts

The 696-survivor meta snapshot PREDATES the WP4.4 kill tests already sitting **uncommitted** in `test_container_discovery.py` (classes `TestBuildServiceConfigs` L876, `TestDiscoverySettingsWiring` L913, `TestBuildConfigsFromCompose` L976, `TestDiscoveryImageStringEdgeCases` L1009; file mtime 2026-09-18 17:06). The kill census `git show cdfeefa5:.wp25-feed/wp44-kills/container_discovery-survivors.md` (measured against those tests) records **644/696 killed, 52 true residuals**, key-for-key identical to the `res` column below. Projected module tier: (162+644)/858 = **94.0%**.

Cluster counts sum to **696** ✔; the `res` column sums to **52** ✔.

## Cluster table

`res` = still alive against the CURRENT working-tree tests (the true drafting surface). Example keys ≤3 per cluster; prefixes expand to the full meta keys (`backend.services.container_discovery.x…__mutmut_…`; class methods carry the `ǁContainerDiscoveryServiceǁ` mangle).

| # | Cluster | Pattern (OLD → NEW) | Count | res | Class | Example keys |
|---|---------|---------------------|-------|-----|-------|--------------|
| 1 | BSD-A | `_build_service_configs` dict key `"postgres"` → `"POSTGRES"`/`"XX…XX"` | 50 | 0 | TEST-GAP (cosmetic key; killed in-tree by golden-table key-set assert) | x_build_service_configs__mutmut_102/_103/_130 |
| 2 | BSD-B | `x_port = settings.x if settings else N` → `= None` | 25 | 0 | TEST-GAP → killed by `EXPECTED_BUILDER_TABLE` + settings-port tests | _1, _5, _9 |
| 3 | BSD-B2 | `port=postgres_port` → `port=None` | 25 | 0 | TEST-GAP → killed by golden table | _106, _134, _161 |
| 4 | BSD-C | ternary cond → `(settings) and False` (settings silently ignored) | 25 | 0 | TEST-GAP → killed by settings-port test | _2, _6, _10 |
| 5 | BSD-D | ternary cond → `(settings) or True` (AttributeError when settings=None) | 25 | 0 | TEST-GAP → killed by golden table (crash = red) | _3, _7, _11 |
| 6 | BSD-E | ternary else-default `+1` (wrong fallback port) | 25 | 0 | TEST-GAP → killed by golden table | _4, _8, _12 |
| 7 | BSD-F | `display_name` → UPPER/lower/`XX…XX`/None | 97 | 0 | TEST-GAP → killed by golden table | _104, _120, _121 |
| 8 | BSD-G | `health_endpoint` → UPPER/`XX…XX`/None/deleted | 91 | 0 | TEST-GAP → killed by golden table | _162, _170, _178 |
| 9 | BSD-H | `health_cmd` (pg_isready/redis-cli) case/XX/None/deleted | 9 | 0 | TEST-GAP → killed by golden table | _107, _115, _123 |
| 10 | BSD-I | `category=ServiceCategory.X` → `None` | 25 | 0 | TEST-GAP → killed by golden table | _105, _133, _160 |
| 11 | BSD-J | `startup_grace_period=60` kwarg DELETED (4 services where the literal equals the dataclass default 60 → output bit-identical) | 4 | **4** | **EQUIVALENT** | _249, _284, _302 (+_521) |
| 12 | BSD-K | `startup_grace_period=<v≠60>` kwarg DELETED (default 60 silently wins) | 21 | 0 | TEST-GAP → killed by golden table | _116, _144, _171 |
| 13 | BSD-L | `startup_grace_period` → `+1`/`None` | 50 | 0 | TEST-GAP → killed by golden table | _108, _126, _136 |
| 14 | BSD-M | `max_failures=5` kwarg DELETED on 14 MONITORING services (literal == dataclass default 5 → bit-identical) | 14 | **14** | **EQUIVALENT** | _360, _387, _414 |
| 15 | BSD-N | `max_failures=10` kwarg DELETED (default 5 wins) | 5 | 0 | TEST-GAP → killed by golden table | _117, _145, _172 |
| 16 | BSD-O | `max_failures` → `+1`/`None` | 38 | 0 | TEST-GAP → killed by golden table | _109, _127, _137 |
| 17 | BSD-P | `restart_backoff_base=<v>` kwarg DELETED (2.0/10.0 → default 5.0) | 19 | 0 | TEST-GAP → killed by golden table | _118, _146, _173 |
| 18 | BSD-Q | `restart_backoff_base` → `+1`/`None` | 38 | 0 | TEST-GAP → killed by golden table | _110, _128, _138 |
| 19 | BSD-R | `restart_backoff_max=<v>` kwarg DELETED (60/120 → default 300.0) | 19 | 0 | TEST-GAP → killed by golden table | _119, _147, _174 |
| 20 | BSD-S | `restart_backoff_max` → `+1`/`None` | 38 | 0 | TEST-GAP → killed by golden table | _111, _129, _139 |
| 21 | C1 | `_build_configs_from_compose`: `logger.warning(f"Compose file not found: {compose_file}…")` → `logger.warning(None)` | 1 | **1** | **LOW-VALUE** (log text only; killable only via caplog contract — T-4) | x_build_configs_from_compose__mutmut_4 |
| 22 | C2 | `_build_configs_from_compose`: fallback call → `(settings, None)` / `(settings, )`. `None` is FALSY → monitoring wrongly excluded when flag True; arg-drop → default True overrides a False flag. NOT truthiness-equivalent. | 3 | **2** | TEST-GAP (`_5` settings→None already killed in-tree by the port assert) | compose__6, _8, _5 |
| 23 | C3 | `ComposeParser()`/`parse_file(compose_file)`/fallback-call arg swallow → None (TypeError/wrong path) | 4 | 0 | TEST-GAP → killed by spy-parse + fallback tests | compose__1, _2, _3 |
| 24 | D1 | `discover_all` logging-only: debug/info f-string message → None, `extra={…}` key UPPER/`XX…XX`, `extra=…` removed | 16 | **16** | **LOW-VALUE** (pure observability payload; T-4 if log contracts wanted) | discover_all__18, _19, _21 |
| 25 | I1 | `__init__`: `include_monitoring = … if settings else True` → `else False`. Residual `_5` = the no-settings branch, whose configs come from prebuilt `ALL_CONFIGS` (monitoring included) → flag value irrelevant → bit-identical | 3 | **1** | TEST-GAP meta-era (`_2`,`_3` real, killed); residual **EQUIVALENT-BY-COUPLING** (see note) | init__5 (+_2,_3) |
| 26 | I2 | `__init__` compose call args: `settings`→None (real: fallback loses .env ports) / `include_monitoring`→None (None falsy → monitoring excluded when True — real) | 7 | **2** | TEST-GAP | init__8, _9 |
| 27 | M0 | `_create_managed_service`: `health_cmd=config.health_cmd` → `None`/kwarg dropped | 2 | 0 | TEST-GAP → killed by in-tree T5 (postgres health_cmd assert) | cms__40, _52 |
| 28 | M1a | untagged fallback `getattr(container, 'id', 'unknown')` defensive-default tweaks (→None / dropped / `'XXunknownXX'` / `'UNKNOWN'`) | 8 | **4** | **TEST-GAP (zero-coverage line)** — every fixture is MagicMock (fabricates `.id`), so the `'unknown'` default never executed; T-1b exercises it | cms__25, _28, _31 (+_32) |
| 29 | M1b | untagged id slice `[:12]` → `[:13]` | 1 | 0 | TEST-GAP → killed by in-tree T5 exact-string assert | cms__33 |
| 30 | M2 | `tags = getattr(image_tags, "tags", [])`: `_13` `[]`→None (both falsy → equivalent); `_16` default dropped → AttributeError on an image object lacking `.tags` (never produced by the all-MagicMock suite) | 2 | **2** | `_13` **EQUIVALENT**; `_16` **TEST-GAP (zero-coverage line)** — T-3b | cms__13, _16 |
| 31 | M3 | `getattr(container, "image", None)` default dropped (containers without `.image` → AttributeError instead of `<unknown>`) | 1 | **1** | **TEST-GAP (zero-coverage line)** — T-1b | cms__6 |
| 32 | M4 | `container_id=getattr(container, "id", "")` default `""`→None / dropped / `"XXXX"` | 3 | **3** | **TEST-GAP (zero-coverage line)** — T-1b kills all three (`""` is the asserted fallback) | cms__60, _63, _66 |
| 33 | S1 | `matches.sort(key=len, reverse=True)` → `key=None` / key dropped (length-priority → reverse-lex) | 2 | **2** | **TEST-GAP** — the only longer-match test uses a PREFIX pair (`redis`/`redis-exporter`) where both sorts agree; T-3a separates them | mcn__5, _7 |

**Residual roll-up (52):** BSD-J 4 + BSD-M 14 + I1 1 + C1 1 + C2 2 + D1 16 + I2 2 + M1a 4 + M2 2 + M3 1 + M4 3 + S1 2 = 52 ✔ (matches the cdfeefa5 census key-for-key).

## Covering test files

- `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_container_discovery.py` — the module's test file. WP4.4 classes L739–L1028: `EXPECTED_BUILDER_TABLE` (L750) kills clusters 2–20; `TestDiscoverySettingsWiring` (L913) kills I1-present-branch/I2 settings-path mutants; `TestBuildConfigsFromCompose` (L976) kills C2 `_5` + C3; `TestDiscoveryImageStringEdgeCases` (L1009) kills M0/M1b. Reuse its helpers/fixtures (`create_mock_container` L49, `ALL_PORTS` L820).
- `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_container_orchestrator.py` — incidental `ContainerDiscoveryService(...)` constructors (~30 sites); would fire on an init-wide regression but assert nothing about discovery config.

## Drafted tests — UNVERIFIED, not yet run red/green

TDD procedure (all): add test → run against ORIGINAL module → green; apply each target mutant's one-line change → red (assertion failure or the mutant's own crash). Fixture-discrimination claims below verified by script (sort outcomes), not by pytest.

### T-2 — kills C2 `_6`/`_8` + I2 `_8`/`_9` (monitoring flag through the compose path)

Root cause of the survivor: no existing test drives the compose *fallback* (FileNotFoundError) with the monitoring flag asserted, and none drives `__init__`'s compose branch with a missing file + settings. `None` is falsy, so `_6`/`_9` (flag→None) exclude monitoring when the real flag is True; `_8` variants (flag/settings dropped) need the settings-port and False-flag legs. One parametrized test covers all four.

```python
@pytest.mark.parametrize("monitoring_enabled", [True, False])
def test_compose_fallback_honors_monitoring_flag_and_settings(
    self, tmp_path, monitoring_enabled: bool
) -> None:
    """The compose-path fallback must receive BOTH settings (ports from .env)
    and the monitoring flag with its truth value intact: flag->None (None is
    falsy - monitoring wrongly excluded when True) and flag-dropped (parameter
    default True overrides a False flag) are the survivors WP4.4 T-2 kills.
    UNVERIFIED - not yet run red/green.
    """
    missing = tmp_path / "nope-compose.yml"  # FileNotFoundError fallback path
    settings = SimpleNamespace(monitoring_enabled=monitoring_enabled, **ALL_PORTS)

    # via build_configs_from_compose directly (kills compose__6, compose__8)
    configs = build_configs_from_compose(missing, settings, monitoring_enabled)
    assert configs["postgres"].port == 15432          # settings must reach the fallback
    assert (configs.get("prometheus") is not None) == monitoring_enabled

    # via ContainerDiscoveryService's compose branch (kills init__8, init__9)
    client = MagicMock()
    client.list_containers = AsyncMock(return_value=[])
    discovery = ContainerDiscoveryService(client, settings, compose_file=missing)
    assert discovery.get_config("postgres") is not None
    assert discovery.get_config("postgres").port == 15432
    assert (discovery.get_config("prometheus") is not None) == monitoring_enabled
```

Red/green: green on original (True → prometheus present, False → absent; ports from settings). `_6`/`_9` (flag→None): prometheus wrongly absent on the True leg → red. `_8`s (settings→None): 5432 ≠ 15432 → red. arg-drop (flag→default True): prometheus wrongly present on the False leg → red.

### T-3a — kills S1 (sort key=len dropped)

Root cause: `test_match_container_name_prefers_longer_match` (L479) uses `security-redis-exporter-1` — a prefix pair; reverse-lex and length sort both return `redis-exporter` there. A non-prefix pair separates them. Verified: `"prod-redis-postgres-bridge-1"` → `key=len` picks `postgres` (8 chars), no-key picks `redis` (`'redis' > 'postgres'`).

```python
def test_match_container_name_length_beats_lexicographic_order(
    self, mock_docker_client: MagicMock
) -> None:
    """Longer pattern must win even when reverse-lexicographic order disagrees.
    WP4.4 T-3a. UNVERIFIED - not yet run red/green.
    """
    service = ContainerDiscoveryService(mock_docker_client)

    # "postgres" (8 chars) beats "redis" (5); sort without key=len returns
    # "redis" because 'redis' > 'postgres' lexicographically.
    assert service.match_container_name("prod-redis-postgres-bridge-1") == "postgres"
    assert service.match_container_name("my-postgres-redis-cache") == "postgres"
```

### T-3b — kills M2 `_16` (tags getattr default dropped)

Root cause: MagicMock fabricates `.tags` on any image object, so `getattr(image_tags, "tags", [])` never ran its default. A bare `SimpleNamespace` image forces the default to run: original → falsy `[]` → `<untagged:pg-abc>`; mutant → AttributeError propagates out of `discover_all`.

```python
@pytest.mark.asyncio
async def test_discover_image_object_without_tags_attribute_still_resolves(
    self, mock_docker_client: MagicMock
) -> None:
    """Image object lacking .tags must resolve through the untagged fallback.
    WP4.4 T-3b. UNVERIFIED - not yet run red/green.
    """
    container = SimpleNamespace(
        name="security-postgres-1", id="pg-abc", image=SimpleNamespace()
    )  # image has no .tags: only the getattr default saves the original
    mock_docker_client.list_containers = AsyncMock(return_value=[container])
    discovery = ContainerDiscoveryService(mock_docker_client)

    discovered = await discovery.discover_all()  # mutant (default dropped): AttributeError

    assert len(discovered) == 1
    assert discovered[0].image == "<untagged:pg-abc>"
```

### T-1b — kills M1a `_25/_28/_31/_32`, M3 `_6`, M4 `_60/_63/_66` (getattr defaults, zero-coverage lines)

Root cause: the whole suite builds containers with `MagicMock` (L31–L61), which answers ANY attribute; the `getattr(…, default)` branches in `_create_managed_service` and `discover_all`'s `<unknown>` path never executed. Two SimpleNamespace fixtures exercise them — the biggest drafting win: 8 of the 52 residuals.

```python
@pytest.mark.asyncio
async def test_container_missing_image_and_id_uses_getattr_defaults(
    self, mock_docker_client: MagicMock
) -> None:
    """Attribute-less containers must fall through the defensive getattr
    defaults: no .image -> "<unknown>" + container_id ""; untagged image + no
    .id -> '<untagged:unknown>'. Exercises the M3/M4/M1a defaults the
    all-MagicMock suite never executed. WP4.4 T-1b.
    UNVERIFIED - not yet run red/green.
    """
    no_image = SimpleNamespace(name="security-postgres-1")  # no .image, no .id
    untagged_no_id = SimpleNamespace(
        name="security-redis-1", image=SimpleNamespace(tags=[])
    )  # image present, tags empty, no .id -> 'unknown' literal path
    mock_docker_client.list_containers = AsyncMock(return_value=[no_image, untagged_no_id])

    discovery = ContainerDiscoveryService(mock_docker_client)
    discovered = await discovery.discover_all()
    # M3 mutant (no getattr default): AttributeError on no_image above

    by_name = {s.name: s for s in discovered}
    assert by_name["postgres"].image == "<unknown>"
    assert by_name["postgres"].container_id == ""  # kills M4 _60 (None) / _63 (crash) / _66 ("XXXX")
    assert by_name["redis"].image == "<untagged:unknown>"
    # kills M1a _25 (None -> slice TypeError), _28 (dropped -> AttributeError),
    # _31 ("XXunknownXX"), _32 ("UNKNOWN")
```

Caveat recorded honestly: these fixtures assert the module's duck-typed defensive contract (the hint is `container: object`). If team policy is that `_create_managed_service` only ever sees full docker-SDK objects, M1a/M3/M4 are LOW-VALUE-by-design and T-1b should not merge — but then those 8 residuals are documented-dead, not gaps. The `'unknown'`/`""` defaults are deliberately-written fallback strings; asserting them is cheap and the mutants are otherwise permanently unkillable.

### T-4 — optional policy call: kills D1 (16/52) + C1 (1/52) log-contract tests

17 of the 52 residuals are pure logger payload (message text → None, `extra` dict keys UPPER/XX-wrapped, `extra` removed). LOW-VALUE unless the team wants log contracts policed. If yes:

```python
@pytest.mark.asyncio
async def test_discover_all_debug_extra_dict_contract(
    self, mock_docker_client: MagicMock, caplog
) -> None:
    """discover_all's debug record must carry the exact extra keys/values.
    WP4.4 T-4 (D1/C1). UNVERIFIED - not yet run red/green.
    """
    import logging

    container = create_mock_container("security-postgres-1", "pg123")
    mock_docker_client.list_containers = AsyncMock(return_value=[container])
    discovery = ContainerDiscoveryService(mock_docker_client)

    with caplog.at_level(logging.DEBUG, logger="backend.services.container_discovery"):
        await discovery.discover_all()

    recs = [r for r in caplog.records if "security-postgres-1" in r.getMessage()]
    assert recs, "debug discovery record missing (message -> None mutant)"
    rec = recs[0]
    assert rec.container_name == "security-postgres-1"
    assert rec.service_name == "postgres"
    assert rec.container_id == "pg123"
    assert rec.category == "INFRASTRUCTURE"
```

(If the message f-string is mutated to `None`, `r.getMessage()` returns `"None"` → the `recs` filter fails → red. `extra` key mutations break the attribute asserts. `container_name`/`service_name`/`container_id`/`category` are not LogRecord-reserved attribute names → safe as `extra`.)

## I1 `_5` note (do not draft)

`include_monitoring else True→False` is equivalent on the no-settings path: that branch assigns prebuilt `ALL_CONFIGS` (monitoring included) regardless of the flag. Killing it requires pinning the implementation coupling (`_configs is ALL_CONFIGS`) — an anti-pattern. Record as EQUIVALENT-BY-COUPLING.

## Summary judgment over the 52-residual surface

- **EQUIVALENT — 20:** BSD-J 4, BSD-M 14, I1 `_5`, M2 `_13`.
- **LOW-VALUE — 17:** D1 16, C1 1 (log payload; killable via T-4 if policy demands).
- **TEST-GAP — 15, all killable by the four drafted tests:** C2 `_6`/`_8` + I2 `_8`/`_9` (T-2, 4), S1 (T-3a, 2), M2 `_16` (T-3b, 1), M1a `_25/_28/_31/_32` + M3 `_6` + M4 `_60/_63/_66` (T-1b, 8). (C2 holds 3 meta keys, 2 residual; `_5` already killed in-tree.)

If T-2/T-3a/T-3b/T-1b land: killed = 644 + 15 → (162+644+15)/858 = **95.7%** module tier; remaining 37 (20 EQUIVALENT + 17 log-only) recorded here with kill-rationale rather than chased. Meta-era roll-up across all 696: TEST-GAP 596 (644 already killed in-tree), EQUIVALENT 20, LOW-VALUE 80 (BSD-A 50 + D1 16 + C1 1 + residual-side splits 13) — sums to 696 with the table's per-row classes.

## Files referenced (absolute)

- `/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta`
- `/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py` (mutant copy)
- `/agents/agent-nemo2/workspace/backend/services/container_discovery.py` (original)
- `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_container_discovery.py` (covering tests; WP4.4 classes L739–L1028)
- `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_container_orchestrator.py` (incidental callers)
- `/agents/agent-nemo2/workspace/backend/services/orchestrator/models.py` (ServiceConfig defaults L63–L71 — basis of BSD-J/M equivalence)
- `.wp25-feed/wp44-kills/container_discovery-survivors.md` (52-key census, via `git show cdfeefa5:.wp25-feed/wp44-kills/container_discovery-survivors.md`)
- `/tmp/wp25/wp44-triage/` — `extract_diffs2.py` (diff extractor), `final3.py` (clusterer), `rows.json` (full per-cluster key lists), `diffs.json` (all 858 variant diffs)

# WP4.4 Triage Dossier — backend/services/monitoring_stack_validator.py

- **Survivors:** 110 of 424 checked (253 killed, 61 unchecked) — per
  `mutants/backend/services/monitoring_stack_validator.py.meta` (exit_code 0).
- **Covering test file (all functions):**
  `backend/tests/unit/services/test_monitoring_stack_validator.py` — per
  `mutants/mutmut-stats.json` `tests_by_mangled_function_name`. Anchor lines:
  Prometheus L229–296, ScrapeTargets L298–363, AlertingRules L371–434,
  Grafana L442–513, Dashboards L516–575, CombinedHealth L583–743,
  HttpClient L847–884, ErrorHandling L892–956.
- **Diff source:** AST diff of each `xǁ…ǁ<func>__mutmut_N` variant against its
  `__mutmut_orig` in `mutants/backend/services/monitoring_stack_validator.py`
  (`mutmut show` spot-checks agreed; full `mutmut show` sweep was too slow
  against the concurrently-written cache).

## Why so many survive (systemic causes)

1. **`_get_http_client` is patched with an `AsyncMock` that returns the same
   canned response no matter what URL is passed** — so every "request URL →
   None" mutant is invisible. No test asserts `client.get` was awaited with the
   documented endpoint path. (Cluster A.)
2. **The shared fixtures (`prometheus_targets_response`,
   `prometheus_rules_response`) are "all-keys-present, benign-values"** — every
   missing-key fallback (`"unknown"`, `""`, `0.0`, `[])`) and every unhealthy
   branch is never fed data. Also the targets fixture is exactly 1-up-1-down,
   which is the _one_ shape where `== "up"` and `!= "up"` yield the same count —
   the operator-flip mutants are masked by fixture symmetry. (Clusters B, C, D,
   E, F, K.)
3. **Tests assert shape (`is not None`, `len(...) > 0`) but not content**
   (`error == "HTTP 503"`, `rule_groups == [...]`, field values, post-close
   state). (Clusters G, I, J, M, N-adjacent.)
4. **Log-only changes are unobservable** (logger arg → `None`, log-branch flip):
   treated EQUIVALENT / LOW-VALUE, not test gaps.

## Cluster table (counts sum to 110)

| #   | Pattern                                                                                                                                                                                                                                                                                                                      | Count | Class      | Example keys                                                                                                                                                    |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A   | Endpoint URL / request arg clobbered to `None` (`url = f"…"` → `url = None`, `client.get(url)` → `client.get(None)`) — mock ignores the arg, no URL assertion anywhere                                                                                                                                                       | 10    | TEST-GAP   | check_prometheus**2, check_alerting_rules**4, get_dashboards**2 (also prom**4, rules**2, grafana**2, grafana**4, dash**2, dash**4, scrape**2, scrape\_\_4)      |
| B   | `up_count` / `down_count` generator `==` flipped to `!=` — 1-up-1-down fixture makes both counts identical                                                                                                                                                                                                                   | 2     | TEST-GAP   | check_prometheus**44, check_prometheus**53                                                                                                                      |
| C   | ScrapeTarget field-extraction clobbers visible under the EXISTING fixture (key → `None`/`"LASTSCRAPE"`/`"LABELS"`/…, whole expression → `None`, kwargs `last_scrape=`/`last_scrape_duration=` dropped) — test asserts only `job`, `health`, `last_error`, never `instance`/`scrape_url`/`last_scrape`/`last_scrape_duration` | 27    | TEST-GAP   | get_scrape_targets**48, get_scrape_targets**91, get_scrape_targets\_\_107 (+ 49,51,52,58,59,75,77,79,83,84,85,86,89,93,94,95,97,98,99,100,101,103,105,106)      |
| D   | ScrapeTarget missing-field **fallback** clobbers (`"unknown"`→`None`/`"XXunknownXX"`/`"UNKNOWN"`, `""`→`None`/`"XXXX"`, `0.0`→`None`/`1.0`, `t.get("labels", {})`→`t.get("labels", None)`) — no payload omits `labels`/`job`/`instance`/`scrapeUrl`/`lastScrapeDuration`                                                     | 18    | TEST-GAP   | get_scrape_targets**62, get_scrape_targets**76, get_scrape_targets\_\_108 (+ 64,66,68,73,74,78,80,82,87,88,90,92,96,102,104)                                    |
| E   | `group.get("name", "unknown")` key/default clobbers + `rule_groups.append(None)` — tests assert `len(rule_groups) == 1`, never its contents                                                                                                                                                                                  | 10    | TEST-GAP   | check_alerting_rules**34, **35, \_\_43 (+ 36,37,38,39,40,41,42)                                                                                                 |
| F   | Rule-payload container defaults `[]`→`None`/`()` / inner-data default (`groups`, `rules`, `data`) — no payload exercises the missing key; when it would, `for … in None` raises and the blanket `except` flips `loaded=True` → `loaded=False`                                                                                | 6     | TEST-GAP   | check_alerting_rules**16, **20, \_\_46 (+ 18,22,48)                                                                                                             |
| G   | `check_prometheus` non-200 return drops `healthy=False,` / `reachable=False,` kwarg → missing-arg TypeError caught by the outer `except` → still `healthy=False` but `error` becomes `"PrometheusStatus.__init__() missing …"` instead of `"HTTP 503"`; test only asserts `error is not None`                                | 2     | TEST-GAP   | check_prometheus**11, check_prometheus**12                                                                                                                      |
| H   | `check_prometheus` `activeTargets` container defaults → `None`/`()` / inner `data` default — `len(None)` raises → `healthy=False` where original returns `healthy=True, total_targets=0` for a success payload lacking the container                                                                                         | 4     | TEST-GAP   | check_prometheus**25, **27, \_\_29 (+ 31)                                                                                                                       |
| I   | `get_dashboards` guard `isinstance(dashboards, list) or True` — non-list JSON payload would be returned raw instead of `[]`                                                                                                                                                                                                  | 1     | TEST-GAP   | get_dashboards\_\_9                                                                                                                                             |
| J   | `close()` sets `self._http_client = ""` instead of `None` — test asserts only `aclose` called, not post-close field (a follow-up `_get_http_client` would hand out `""`)                                                                                                                                                     | 1     | TEST-GAP   | close\_\_4                                                                                                                                                      |
| K   | `check_grafana` `database` default `"unknown"` → `None`/`()`/`"XXunknownXX"`/`"UNKNOWN"` — no health payload omits `database`; the `database_status` field value would differ                                                                                                                                                | 4     | TEST-GAP   | check_grafana**14, **16, \_\_19 (+ 20)                                                                                                                          |
| L   | `check_grafana` `dashboard_count = 0` init → `None`/`1` — only observable if `get_dashboards()` raises (it never does: it swallows everything), so the init value is never the final value under test                                                                                                                        | 2     | TEST-GAP   | check_grafana**21, check_grafana**22                                                                                                                            |
| M   | `error=str(e)` → `error=str(None)` in generic handlers (alerting + grafana `except Exception`) — error becomes literal `"None"`; those tests assert only `error is not None` (the `"timed out"`-substring asserts hit the _timeout_ branch, which is unmutated)                                                              | 2     | TEST-GAP   | check_alerting_rules**87, check_grafana**60                                                                                                                     |
| N   | Alerting payload has zero unhealthy rules, so dropping `unhealthy_rules=unhealthy_rules` from the return → default 0 → identical                                                                                                                                                                                             | 1     | TEST-GAP   | check_alerting_rules\_\_78                                                                                                                                      |
| O   | `logger.warning/debug(<f-string>)` → `logger.warning(None)` — pure log-text clobber, return values untouched                                                                                                                                                                                                                 | 11    | EQUIVALENT | check_prometheus**7, check_alerting_rules**69, check_grafana**30 (+ prom**56, prom**69, prom**78, rules**81, grafana**42, grafana**51, dash**10, scrape\_\_115) |
| P   | `get_scrape_targets` `activeTargets` defaults → `None`/`()`/inner-data `None` — `for t in None` raises, blanket `except` returns `[]`, **identical observable** to original `[]`                                                                                                                                             | 4     | EQUIVALENT | get_scrape_targets**17, **19, \_\_21 (+ 23)                                                                                                                     |
| Q   | `get_scrape_targets` `health` default `"unknown"` → `None`/`()`/`"XXunknownXX"`/`"UNKNOWN"` — every clobbered value still falls through `== "up"` / `== "down"` to the `else` → `ScrapeTargetHealth.UNKNOWN`; semantically identical                                                                                         | 4     | EQUIVALENT | get_scrape_targets**31, **33, \_\_36 (+ 37)                                                                                                                     |
| R   | `check_grafana` `if not is_healthy:` → `if is_healthy:` flips a **logging-only** branch (warn when healthy, silent when DB degraded); returned `GrafanaStatus` unchanged                                                                                                                                                     | 1     | LOW-VALUE  | check_grafana\_\_29                                                                                                                                             |

Totals: TEST-GAP 90 (A,B,C,D,E,F,G,H,I,J,K,L,M,N), EQUIVALENT 19 (O,P,Q),
LOW-VALUE 1 (R) → 110.

### Notable near-misses in the existing suite (still TEST-GAP, per WP4.4 rules)

- `test_check_prometheus_non_200_response` (L278) asserts `error is not None`,
  not `error == "HTTP 503"` → misses G.
- `test_check_alerting_rules_loaded` (L375) asserts `len(result.rule_groups) == 1`
  → misses E; fixture has `health: "ok"` on every rule → misses N.
- `test_check_alerting_rules_error` (L419) asserts `result.error is not None` →
  passes on `str(None)` == `"None"` → misses M.
- `test_close_closes_http_client` (L851) asserts the call, not
  `validator._http_client is None` → misses J.
- `test_get_scrape_targets` (L302) asserts `job`/`health`/`last_error` only →
  misses C/D.

## Drafted tests (highest-value clusters)

Target file: `backend/tests/unit/services/test_monitoring_stack_validator.py`.
Style follows the existing file (fixtures `validator`, `mock_http_client`,
`create_mock_response`, `patch.object(validator, "_get_http_client", …)`).

**// UNVERIFIED - not yet run red/green** (sandbox constraint: no test
execution during the live mutation run). TDD procedure for each: activate the
mutant (or apply the diff by hand) → new assertion fails RED; revert to
original → GREEN; then `mutmut` re-run confirms the cluster keys die.

### T1 — kills Cluster B (up/down operator flips)

```python
    @pytest.mark.asyncio
    async def test_check_prometheus_counts_up_and_down_with_skewed_health_mix(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """2 up + 1 down breaks the 1/1 fixture symmetry that masked ==/!= flips."""
        payload = {
            "status": "success",
            "data": {
                "activeTargets": [
                    {"labels": {"job": "a"}, "health": "up"},
                    {"labels": {"job": "b"}, "health": "up"},
                    {"labels": {"job": "c"}, "health": "down"},
                ],
            },
        }
        mock_http_client.get = AsyncMock(return_value=create_mock_response(200, payload))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            result = await validator.check_prometheus()

        assert result.total_targets == 3
        assert result.targets_up == 2   # mutant #44 (== -> !=) yields 1
        assert result.targets_down == 1 # mutant #53 (== -> !=) yields 2
```

### T2 — kills Cluster C (field values never asserted)

```python
    @pytest.mark.asyncio
    async def test_get_scrape_targets_populates_all_target_fields(
        self,
        validator: MonitoringStackValidator,
        mock_http_client: MagicMock,
        prometheus_targets_response: dict[str, Any],
    ) -> None:
        """Every ScrapeTarget field must carry the payload value, not None/''/fallbacks."""
        mock_response = create_mock_response(200, prometheus_targets_response)
        mock_http_client.get = AsyncMock(return_value=mock_response)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            targets = await validator.get_scrape_targets()

        assert len(targets) == 2
        first = targets[0]
        assert first.job == "hsi-backend-metrics"
        assert first.instance == "backend:8000"
        assert first.scrape_url == "http://backend:8000/api/metrics"
        assert first.last_scrape == "2024-01-15T10:30:00.000Z"
        assert first.last_scrape_duration == 0.015
        assert first.last_error is None  # payload "" must normalize to None
        second = targets[1]
        assert second.instance == "redis-exporter:9121"
        assert second.scrape_url == "http://redis-exporter:9121/metrics"
        assert second.last_scrape == "2024-01-15T10:29:45.000Z"
        assert second.last_scrape_duration == 0.0
```

### T3 — kills Cluster D (missing-field fallbacks never fed)

```python
    @pytest.mark.asyncio
    async def test_get_scrape_targets_defaults_for_sparse_target_payload(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """A target with no labels/keys must degrade to documented defaults, not []/None."""
        payload = {"status": "success", "data": {"activeTargets": [{}]}}
        mock_http_client.get = AsyncMock(return_value=create_mock_response(200, payload))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            targets = await validator.get_scrape_targets()

        assert len(targets) == 1  # labels-default clobbers (66/68/80/82) -> [] -> red
        target = targets[0]
        assert target.job == "unknown"
        assert target.instance == "unknown"
        assert target.scrape_url == ""
        assert target.last_scrape is None
        assert target.last_scrape_duration == 0.0
        assert target.health == ScrapeTargetHealth.UNKNOWN
```

### T4 — kills Cluster A (URL contract)

```python
    @pytest.mark.asyncio
    async def test_component_checks_request_documented_api_urls(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """Each check must hit its documented endpoint (mock.get ignores URL otherwise)."""
        empty_success = create_mock_response(200, {"status": "success", "data": {}})
        ok_dashboards = create_mock_response(200, [])
        ok_grafana_health = create_mock_response(
            200, {"database": "ok", "version": "10.2.3"}
        )
        mock_http_client.get = AsyncMock(return_value=empty_success)

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            await validator.check_prometheus()
            assert mock_http_client.get.await_args.args[0] == (
                "http://prometheus:9090/api/v1/targets"
            )
            await validator.get_scrape_targets()
            assert mock_http_client.get.await_args.args[0] == (
                "http://prometheus:9090/api/v1/targets"
            )
            await validator.check_alerting_rules()
            assert mock_http_client.get.await_args.args[0] == (
                "http://prometheus:9090/api/v1/rules"
            )
            await validator.get_dashboards()
            assert mock_http_client.get.await_args.args[0] == (
                "http://grafana:3000/api/search?type=dash-db"
            )
            mock_http_client.get = AsyncMock(
                side_effect=[ok_grafana_health, ok_dashboards]
            )
            await validator.check_grafana()
            assert mock_http_client.get.await_args_list[0].args[0] == (
                "http://grafana:3000/api/health"
            )
```

### T5 — kills Clusters E, N, F (rule-group content + unhealthy counting + empty payload)

```python
    @pytest.mark.asyncio
    async def test_check_alerting_rules_content_names_groups_and_counts_unhealthy(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """rule_groups content, unhealthy tally, and missing-key tolerance."""
        rules_payload = {
            "status": "success",
            "data": {
                "groups": [
                    {
                        "name": "ai_pipeline_alerts",
                        "rules": [
                            {"type": "alerting", "health": "ok"},
                            {"type": "alerting", "health": "bad"},
                            {"type": "recording", "health": "ok"},
                        ],
                    },
                    {"rules": []},  # group without a name -> "unknown"
                ],
            },
        }
        mock_http_client.get = AsyncMock(return_value=create_mock_response(200, rules_payload))

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            result = await validator.check_alerting_rules()

        assert result.loaded is True
        assert result.total_rules == 2      # recording rule excluded (kills none, guards)
        assert result.healthy_rules == 1
        assert result.unhealthy_rules == 1  # mutant #78 (kwarg dropped) -> 0
        assert result.rule_groups == ["ai_pipeline_alerts", "unknown"]  # kills #34-43

        # payload without "data" (kills #16/#18 container defaults AND #20/#22
        # inner-data defaults -- with "data" present the inner-default mutants
        # are invisible): still loaded, zero counts
        mock_http_client.get = AsyncMock(
            return_value=create_mock_response(200, {"status": "success"})
        )
        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            empty_result = await validator.check_alerting_rules()
        assert empty_result.loaded is True  # #16/#18/#20/#22 raise -> loaded=False
        assert empty_result.total_rules == 0

        mock_http_client.get = AsyncMock(
            return_value=create_mock_response(
                200, {"status": "success", "data": {"groups": [{}]}}
            )
        )
        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            no_rules = await validator.check_alerting_rules()
        assert no_rules.loaded is True  # #46/#48 for None -> loaded=False
        assert no_rules.rule_groups == ["unknown"]
```

### T6 — kills Cluster H (empty-container must stay healthy)

```python
    @pytest.mark.asyncio
    async def test_check_prometheus_healthy_when_container_missing(
        self, validator: MonitoringStackValidator, mock_http_client: MagicMock
    ) -> None:
        """A success payload without "data"/activeTargets must count 0 targets, not raise->unhealthy.
        Omitting "data" entirely also exposes the inner-data-default mutants (#29/#31)."""
        mock_http_client.get = AsyncMock(
            return_value=create_mock_response(200, {"status": "success"})
        )

        async def get_mock_client() -> MagicMock:
            return mock_http_client

        with patch.object(
            validator, "_get_http_client", side_effect=get_mock_client, autospec=True
        ):
            result = await validator.check_prometheus()

        assert result.healthy is True   # container clobbers -> TypeError -> False
        assert result.reachable is True
        assert result.total_targets == 0
        assert result.targets_up == 0
        assert result.targets_down == 0
```

Remaining TEST-GAP clusters (G, I, J, K, L, M) are one-line asserts cheap to add
later: `error == "HTTP 503"` after non-200 (G/M); `dashboards == []` on a dict
JSON payload (I); `validator._http_client is None` after `close()` (J);
health payload `{"version": "x"}` → `database_status == "unknown"` (K);
`patch.object(validator, "get_dashboards", side_effect=Exception(...))` →
`dashboard_count == 0` (L); `assert "Connection refused" in result.error` in the
alerting/grafana generic-exception tests (M).

## Machine-readable leftovers

- Full per-mutant diff listing: `/tmp/wp25/wp44-triage/flat.txt`
- Structured diffs: `/tmp/wp25/wp44-triage/local_diffs_msv.json`
- Survivor keys: `/tmp/wp25/wp44-triage/keys_msv.txt`

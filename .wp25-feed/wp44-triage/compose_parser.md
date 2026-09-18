# WP4.4 Triage Dossier — backend/services/compose_parser.py

Source of truth: `mutants/backend/services/compose_parser.py.meta` (`exit_code_by_key`, exit_code 0 = survived).
**Survivors: 117 of 409 keys.** Per-function: `_format_display_name` 70, `_parse_healthcheck` 18, `_parse_service` 15, `_parse_port` 6, `_parse_duration` 4, `_labels_list_to_dict` 3, `_get_category` 1.

Diff source: `uv run mutmut show <key>` on all 117 keys (all succeeded, no cache-contention fallback needed). Raw: `/tmp/wp25/wp44-triage/diffs_raw.txt`; compact one-liners: `/tmp/wp25/wp44-triage/diffs_compact.txt`. No tests were executed (mutation run owns the box); classifications are static.

**Covering test file (the only one):** `backend/tests/unit/services/test_compose_parser.py`
- `TestComposeParser` lines 12-321 (compose-level, drives everything through `parse_file`)
- `TestDisplayNameFormatting` lines 324-353 (asserts only 4 of 17 `special_cases` entries)
- `TestDurationParsing` lines 356-378 (s/m/bare/None — no hours)

## Cluster table (26 clusters; counts sum to 117)

TEST-GAP = 111, EQUIVALENT = 6, LOW-VALUE = 0.

| # | Pattern | N | Class | Example keys (fn-suffix) | Note |
|---|---------|---|-------|--------------------------|------|
| C1 | `_format_display_name` special_cases **lookup-key** clobbers/de-casers for 14 unexercised entries (florence, redis, go2rtc, grafana, prometheus, loki, jaeger, alertmanager, pyroscope, alloy, elasticsearch, dcgm exporter, node exporter, cadvisor) | 28 | TEST-GAP | `format_display_name__mutmut_34`, `_44`, `_53` | Tests hit the dict loop but only for postgres/redis-value/llm/clip/yolo26; missing key → `.title()` fallback ≠ expected |
| C2 | `_format_display_name` special_cases **value** clobbers (`"XXGrafanaXX"`, `"grafana"`, `"GRAFANA"`, …) for the same entries | 38 | TEST-GAP | `_55`, `_61`, `_106` | Returned display_name differs; never asserted for these names |
| C3 | `_format_display_name` line 434 `replace("-"/"_", " ")` key+value clobbers | 4 | TEST-GAP | `_16`, `_17`, `_18` | Every covering input is hyphen/underscore-free, line never executes observably |
| C4 | `_parse_healthcheck` `healthcheck.get("disable")` key clobbers (`None`, `"XXdisableXX"`, `"DISABLE"`) | 3 | TEST-GAP | `parse_healthcheck__mutmut_1`, `_2`, `_3` | Survives only because the one disable test has no `test:` key, so the next guard returns the same `(None,None,None)`; with disable+test present (legal compose) mutant parses the test anyway |
| C5 | `_parse_healthcheck` `"CMD"` tuple-member clobbers (`"XXCMDXX"`, `"cmd"`) — prefix strip skipped | 2 | TEST-GAP | `_12`, `_13` | `test_parse_file_returns_configs` runs `['CMD','pg_isready']` through it but asserts only port/category; health_cmd would read `"CMD pg_isready"` |
| C6 | `_parse_healthcheck` `test and` → `test or` in prefix check | 1 | TEST-GAP | `_9` | `test` is always truthy there (`if not test` early-returns), so the mutant **always** drops test[0]; original drops it only for CMD/CMD-SHELL. All tests use prefixed lists, so the difference never surfaces. An unprefixed list test (legal compose: `test: ['redis-cli','ping']`) would read `"ping"` instead of `"redis-cli ping"` |
| C7 | `_parse_healthcheck` `" ".join` → `"XX XX".join` | 1 | TEST-GAP | `_20` | No test has a multi-token remainder after prefix strip (redis test is single-token) |
| C8 | `_parse_healthcheck` `port = int(match.group(1))` → `port = None` | 1 | TEST-GAP | `_24` | Masked: test asserts port==8095 which the ports-list fallback coincidentally reproduces; healthcheck-port precedence unasserted |
| C9 | `_parse_healthcheck` endpoint default `"/health"` string clobbers (`"XX/healthXX"`, `"/HEALTH"`) | 2 | TEST-GAP | `_36`, `_37` | Bare-URL (no path) input never constructed |
| C10 | `_parse_healthcheck` endpoint condition `lastindex >= 2` → `(...) or True` / `lastindex or …` | 2 | TEST-GAP | `_30`, `_33` | Diverges exactly on bare-URL inputs (group(2)=None returned instead of "/health") — same missing input as C9 |
| C11 | `_parse_healthcheck` `startswith("sh -c")` clobbers | 2 | TEST-GAP | `_40`, `_41` | String-form `test: "sh -c '...'"` never in any test; strip branch dead for current inputs but real |
| C12 | `_parse_healthcheck` cmd-port regex (`port_match=None`, regex clobber, `-P`) | 3 | TEST-GAP | `_43`, `_48`, `_49` | No test asserts a port extracted from a non-HTTP healthcheck command (e.g. `pg_isready -p 5432`) |
| C13 | `_parse_healthcheck` annotation assignment `cmd_port: int \| None = ""` | 1 | EQUIVALENT | `_42` | `""` is falsy like `None`; `_parse_port` guards with `if health_port:` — no observable difference |
| C14 | `_parse_service` `health_port` → `None` at `_parse_port(...)` call | 1 | TEST-GAP | `parse_service__mutmut_31` | Same root gap as C8: precedence healthcheck-port > ports-list unasserted |
| C15 | `_parse_service` `labels.get("orchestrator.startup_grace_period")` key clobbers | 3 | TEST-GAP | `_46`, `_47`, `_48` | No test sets this label; falls to start_period/default |
| C16 | `_parse_service` `orchestrator.max_failures` key clobbers + `retries` key clobbers + `or`→`and` | 7 | TEST-GAP | `_58`, `_59`, `_63` | retries path asserted; label path and precedence chain never. `_58` (`… max_failures") and healthcheck.get("retries")`) diverges whenever both sources set — no test sets the label |
| C17 | `_parse_service` `CATEGORY_DEFAULTS.get(category, …)` key → `None` (silently AI-defaults everything) | 1 | TEST-GAP | `_16` | Category-specific defaults (grace 15 vs 60) never asserted anywhere |
| C18 | `_parse_service` same call fallback arg → `None` / removed | 2 | EQUIVALENT | `_17`, `_19` | Fallback unreachable: `_get_category` only returns dict-valid ServiceCategory keys |
| C19 | `_parse_service` `str(defaults["startup_grace_period"])` → `str(None)` | 1 | TEST-GAP | `_52` | Reachable (label+start_period absent): original yields category default (15/60/30), mutant → unparseable "None" → 30. Not dead — defaults are non-falsy so the `or` DOES reach `str(defaults[...])` |
| C20 | `_parse_port` `split("/")` → `split(None)` / `split("XX/XX")` — `/tcp` strip broken | 2 | TEST-GAP | `parse_port__mutmut_16`, `_19` | No test port spec carries `/tcp` |
| C21 | `_parse_port` index `parts[-1]` → `parts[+1]` / `parts[-2]` | 2 | TEST-GAP | `_17`, `_18` | Survives because every tested spec is `A:A` symmetric (parts[1]==parts[-1], parts[-2]==parts[-1] on 2-part); asymmetric/host-bound specs unasserted |
| C22 | `_parse_port` `get("ports", [])` → `get("ports", None)` / default removed | 2 | TEST-GAP | `_3`, `_5` | No test has a service with no `ports:` AND no healthcheck port (would `for … in None` → TypeError → service dropped) |
| C23 | `_labels_list_to_dict` `split("=",1)` → `rsplit` / maxsplit `2` / removed | 3 | TEST-GAP | `labels_list_to_dict__mutmut_8`, `_9`, `_11` | Equivalent only for single-`=` values; label values containing `=` (real compose usage) diverge (wrong key/value or ValueError unpack) |
| C24 | `_parse_duration` unit fallback `"s"` → `"XXsXX"` / `"S"` | 2 | EQUIVALENT | `duration__mutmut_21`, `_22` | Fallback only when group(2) absent (bare digits) — both mutants still land in the else-branch returning `value`; m/h branches unaffected |
| C25 | `_parse_duration` `elif unit == "h"` clobbers | 2 | TEST-GAP | `_29`, `_30` | No test parses hours; "1h" → 1 instead of 3600 |
| C26 | `_get_category` `labels.get("orchestrator.category", "")` default → `"XXXX"` | 1 | EQUIVALENT | `get_category__mutmut_9` | `"XXXX"` truthy → `ServiceCategory["XXXX"]` KeyError → warning → falls through to inference — same category as original's skip; only extra log noise |

Sum: 28+38+4+3+2+1+1+1+2+2+2+3+1+1+3+7+1+2+1+2+2+2+3+2+2+1 = **117** ✔
(TEST-GAP 28+38+4+3+2+1+1+2+2+2+3+1+3+7+1+1+2+2+2+3+2 = 110; EQUIVALENT 1+1+2+2+1 = 7; LOW-VALUE 0.)

## Structural findings

1. **The `_format_display_name` dict is the single biggest hole (70/117).** `test_special_names_formatted_correctly` (test_compose_parser.py:346) exercises the lookup loop for 4 of 17 entries (postgres, redis-value, ai-llm, ai-clip) and kills their mutants — proving the mechanism works — but 14 rows are never selected, so 66 dict mutants survive. Plus 4 separator mutants survive because no tested name contains `-`/`_`. One parametrized test closes all 70.
2. **Label-driven config is entirely unasserted.** The module's whole advertised contract — `orchestrator.startup_grace_period`, `orchestrator.max_failures`, category-default fallback chain (label → healthcheck → category default) — has zero tests that set the labels or check the category default (C15, C16, C17, C19 = 12 survivors). Only `backoff_base/max` labels are tested (line 269).
3. **Port precedence + format variety.** Healthcheck-port-over-ports-list (C8, C14), container-vs-host part selection on asymmetric specs (C21), `/tcp` suffix stripping (C20), the missing-ports default path (C22), and non-HTTP command port extraction (C12) are all live behavior nobody pins (11 survivors).
4. **True equivalences are few (6):** unreachable defensive fallback (C18), log-only label-default quirk (C26), falsy-annotation tweak (C13), and the duration unit-fallback pair that can never change a return (C24). (C6's `and`→`or` looks equivalent at a glance but is a real behavior change on unprefixed test lists.)

## Drafted tests — UNVERIFIED, not yet run red/green

Target file: `backend/tests/unit/services/test_compose_parser.py` (match existing style: `tmp_path` + `dedent` compose fixtures for parse_file tests; direct `parser._private(...)` calls like `TestDurationParsing` does).
TDD procedure for each: add test → run against the mutant copy → assertion FAILS on the cluster's change → run against `backend/services/compose_parser.py` → PASSES.

### T-A — kills C1+C2+C3 (70 survivors)

```python
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("ai-florence", "Florence-2"),
            ("go2rtc", "go2rtc"),
            ("grafana", "Grafana"),
            ("prometheus", "Prometheus"),
            ("loki", "Loki"),
            ("jaeger", "Jaeger"),
            ("alertmanager", "Alertmanager"),
            ("pyroscope", "Pyroscope"),
            ("alloy", "Grafana Alloy"),
            ("elasticsearch", "Elasticsearch"),
            ("dcgm-exporter", "DCGM Exporter"),
            ("node-exporter", "Node Exporter"),
            ("cadvisor", "cAdvisor"),
            ("ai-some_service", "Some Service"),
            ("multi-word-service", "Multi Word Service"),
        ],
    )
    def test_all_special_cases_and_separators(self, name: str, expected: str) -> None:
        """Every special_cases entry and both separator replacements format correctly."""
        parser = ComposeParser()
        assert parser._format_display_name(name) == expected
```

Key clobbers miss the lowercase key and fall to `.title()`; value clobbers mismatch directly; separator clobbers break the last two names. (`"DCGM Exporter"` also confirms the `"dcgm exporter"` row is hit rather than title-casing.)

### T-B — kills C15+C16 (10 survivors)

```python
    def test_labels_override_startup_grace_and_max_failures(self, tmp_path: Path) -> None:
        """orchestrator.startup_grace_period / max_failures labels beat healthcheck values."""
        compose_content = dedent("""
            version: '3.8'
            services:
              labeled-service:
                image: test:latest
                ports:
                  - '8080:8080'
                labels:
                  orchestrator.startup_grace_period: "45"
                  orchestrator.max_failures: "7"
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8080/health']
                  start_period: 120s
                  retries: 10
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["labeled-service"].startup_grace_period == 45  # not 120s
        assert configs["labeled-service"].max_failures == 7  # not retries=10
```

### T-C — kills C8+C14+C20+C21+C22 (7 survivors)

```python
    def test_port_from_healthcheck_when_no_ports_list(self, tmp_path: Path) -> None:
        """With no ports section, the healthcheck port is used."""
        compose_content = dedent("""
            version: '3.8'
            services:
              portless:
                image: test:latest
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8091/health']
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["portless"].port == 8091
```

Kills C8 (`port=None` → default 8080) and C14 (health_port dropped at call site → 8080). The `get("ports", None)` mutants (C22) crash here? No — the early `if health_port: return` short-circuits before the `ports` line; C22 is covered by the next test.

```python
    def test_default_port_when_nothing_specified(self, tmp_path: Path) -> None:
        """A service with neither healthcheck nor ports falls back to 8080."""
        compose_content = dedent("""
            version: '3.8'
            services:
              bare-service:
                image: test:latest
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["bare-service"].port == 8080
```

C22 mutants: `for port_def in None` raises TypeError → parse_file's per-service handler drops the service → KeyError.

```python
    def test_ports_container_part_selected_by_format(self, tmp_path: Path) -> None:
        """Container port is parts[-1] minus /tcp, on asymmetric and bound specs."""
        compose_content = dedent("""
            version: '3.8'
            services:
              asymmetric:
                image: test:latest
                ports:
                  - '9999:8080'
              bound:
                image: test:latest
                ports:
                  - '127.0.0.1:1883:1884/tcp'
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["asymmetric"].port == 8080  # kills parts[-2] -> 9999
        assert configs["bound"].port == 1884  # kills parts[+1] -> 1883, /tcp strip -> ValueError -> 8080
```

### T-D — kills C9+C10 (4 survivors)

```python
    def test_url_without_path_defaults_to_health(self, tmp_path: Path) -> None:
        """A healthcheck URL with no path defaults the endpoint to /health."""
        compose_content = dedent("""
            version: '3.8'
            services:
              bare-url:
                image: test:latest
                healthcheck:
                  test: ['CMD', 'curl', '-f', 'http://localhost:8097']
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["bare-url"].health_endpoint == "/health"
        assert configs["bare-url"].port == 8097
```

`or True` / `lastindex or …` variants return `group(2)` = None here → mismatch.

### T-E — kills C4+C5+C6+C7+C11+C12 (12 survivors), direct-call style

```python
class TestHealthcheckParsing:
    """Tests for _parse_healthcheck edge paths."""

    def test_disable_flag_wins_over_test(self) -> None:
        """disable: true short-circuits even when a test command is present."""
        parser = ComposeParser()
        result = parser._parse_healthcheck(
            {"disable": True, "test": ["CMD", "curl", "-f", "http://localhost:8095/health"]}
        )
        assert result == (None, None, None)

    def test_cmd_prefix_stripped_and_multi_token_join(self) -> None:
        """CMD/CMD-SHELL prefixes are stripped and remaining tokens joined with single spaces."""
        parser = ComposeParser()
        _, cmd, _ = parser._parse_healthcheck({"test": ["CMD", "pg_isready"]})
        assert cmd == "pg_isready"
        _, cmd2, _ = parser._parse_healthcheck(
            {"test": ["CMD-SHELL", "redis-cli", "-a", "pw", "ping"]}
        )
        assert cmd2 == "redis-cli -a pw ping"
        # Unprefixed list: only CMD/CMD-SHELL are stripped, never an arbitrary first token
        _, cmd3, _ = parser._parse_healthcheck({"test": ["redis-cli", "ping"]})
        assert cmd3 == "redis-cli ping"

    def test_sh_c_string_form_stripped(self) -> None:
        """String-form 'sh -c ...' healthchecks have the wrapper stripped."""
        parser = ComposeParser()
        _, cmd, _ = parser._parse_healthcheck({"test": "sh -c 'redis-cli ping'"})
        assert cmd == "redis-cli ping"

    def test_port_extracted_from_command(self) -> None:
        """Ports are extracted from non-HTTP healthcheck commands like pg_isready -p."""
        parser = ComposeParser()
        _, _, port = parser._parse_healthcheck(
            {"test": ["CMD-SHELL", "pg_isready", "-p", "5432"]}
        )
        assert port == 5432
```

### T-F — kills C17+C19 (2 survivors)

```python
    def test_category_default_startup_grace_period(self, tmp_path: Path) -> None:
        """Services without labels or start_period get their category's default grace."""
        compose_content = dedent("""
            version: '3.8'
            services:
              postgres:
                image: postgres:16
                ports:
                  - '5432:5432'
                healthcheck:
                  test: ['CMD', 'pg_isready']
        """)
        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text(compose_content)

        parser = ComposeParser()
        configs = parser.parse_file(compose_file)

        assert configs["postgres"].startup_grace_period == 15  # INFRASTRUCTURE default, not AI's 60 or 30
```

### T-G — kills C23+C25 (5 survivors)

```python
    def test_label_value_containing_equals(self) -> None:
        """split('=', 1) keeps the full remainder as the value."""
        parser = ComposeParser()
        result = parser._labels_list_to_dict(["key=value=more", "noequals", "a=b"])
        assert result == {"key": "value=more", "a": "b"}
```

```python
    def test_parse_hours(self) -> None:
        """Hours are converted to seconds."""
        parser = ComposeParser()
        assert parser._parse_duration("1h") == 3600
        assert parser._parse_duration("2h") == 7200
```

## Coverage math

| Test | Kills | Count |
|------|-------|-------|
| T-A | C1+C2+C3 | 70 |
| T-B | C15+C16 | 10 |
| T-C | C8+C14+C20+C21+C22 | 8 |
| T-D | C9+C10 | 4 |
| T-E | C4+C5+C6+C7+C11+C12 | 12 |
| T-F | C17+C19 | 2 |
| T-G | C23+C25 | 5 |
| **Total** | | **111 = all TEST-GAP survivors** |

The 6 EQUIVALENT (C13, C18, C24, C26) are not killable by any input — they can be closed via mutmut config (exclusions) if the baseline wants a clean score.

// UNVERIFIED - not yet run red/green.

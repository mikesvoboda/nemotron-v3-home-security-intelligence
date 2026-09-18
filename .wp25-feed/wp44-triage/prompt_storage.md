# WP4.4 triage dossier — backend/services/prompt_storage.py

- Source: `backend/services/prompt_storage.py` (724 lines)
- Meta: `mutants/backend/services/prompt_storage.py.meta` — 579 keys total, **104 survived** (exit_code 0), 163 killed, 312 null (not-yet-run; excluded).
- Diff source: `uv run mutmut show <key>` for all 104 (all succeeded; raw dumps under `/tmp/wp25/ps-diffs/`).
- Covering tests: **single file** `backend/tests/unit/services/test_prompt_storage.py` (1620 lines) per `mutants/mutmut-stats.json` `tests_by_mangled_function_name`. Key class anchors: TestGetConfig :268, TestGetConfigWithMetadata :321, TestGetHistory :463, TestGetVersion :562, TestRestoreVersion :629, TestExportAll :727, TestImportConfigs :763, TestInitializeDefaultConfig :1451, TestInvalidVersionFilenames :1534.
- `safe_parse_datetime` has **no direct test at all** — it is only reached transitively through get_history/get_version tests, and those never assert `created_at`.

Totals: **TEST-GAP 88 · EQUIVALENT 9 · LOW-VALUE 7** (sum 104).

## Source oddity (not a survivor, flagged for rot ledger)

`backend/services/prompt_storage.py:58` — `except ValueError, TypeError:` (no parens). Verified in the sandbox build (Python 3.14.4): it **parses and catches both types** (AST shows the handler type as a `Tuple`), so the fallback path here behaves like `except (ValueError, TypeError):`. This is the old py2 / PEP-758-style spelling that CPython 3.0–3.13 reject with SyntaxError ("old try-except… syntax"). Given the known CI-vs-sandbox minor-version skew (memory: py-version-skew-annotation-hazard), parenthesize it: `except (ValueError, TypeError):`.

## Cluster table (30 clusters, 104 survivors)

Key shorthand: `<fn>__mutmut_N` = `backend.services.prompt_storage.x[ǁPromptStorageServiceǁ]<fn>__mutmut_N`; `SPD` = `x_safe_parse_datetime`.

| #   | Cluster (pattern @ function)                                                                                                                                                                                                               | n   | Keys (examples ≤3)                         | Class      | Why                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --- | ------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `safe_parse_datetime`: any change that forces the fallback or breaks the parse — `if fallback is None`→`is not`, `fallback=datetime.now(UTC)`→`None`/`now(None)`, `if not value`→`if value`, `value.replace("Z","+00:00")`→`None`/bad args | 9   | SPD_1, SPD_2, SPD_4                        | TEST-GAP   | Mutants 4–9 make _every_ truthy string return fallback (created_at=now instead of parsed); 1–3 corrupt the fallback itself (None/naive). Reached via get_history/get_version (test file :463, :562) but `created_at` is never asserted. Killed by draft T1.                                                               |
| 2   | `safe_parse_datetime`: `replace("Z","XX+00:00XX")` — Zulu suffix no longer translated correctly                                                                                                                                            | 1   | SPD_12                                     | TEST-GAP   | `"…Z"` inputs now return fallback instead of the parsed aware datetime. Same draft T1 assert (`== expected`) kills it.                                                                                                                                                                                                    |
| 3   | `safe_parse_datetime`: `replace("XXZXX","+00:00")` — Zulu never translated                                                                                                                                                                 | 1   | SPD_10                                     | EQUIVALENT | Python ≥3.11 `datetime.fromisoformat` accepts trailing `Z` natively (verified on the 3.14.4 build: `…Z` parses to aware UTC). Identical output on every reachable input.                                                                                                                                                  |
| 4   | `safe_parse_datetime`: `replace("z","+00:00")` — case flip on the Z literal                                                                                                                                                                | 1   | SPD_11                                     | LOW-VALUE  | Differs only for lowercase-`z`-suffixed strings; nothing in the codebase produces them (writes use `isoformat()` → `+00:00`) and original behavior on `z` is just "fallback". Asserting it pins a non-contract.                                                                                                           |
| 5   | `get_config`: corrupt-`current.json` fallbacks/guard removed — `data.get("config", DEFAULT_CONFIGS.get(…))`→`data.get("config", None)`/`, )`/inner `get(None,…)`; `isinstance(config, dict) else {}`→`… or True`                           | 5   | get_config_9, get_config_11, get_config_19 | TEST-GAP   | A stored current.json lacking `"config"` (or with a non-dict `"config"`) now yields `{}`/raw non-dict instead of defaults/`{}`. Tests only cover malformed-JSON (:303), never a well-formed-but-field-missing file. Killed by appendix test C1.                                                                           |
| 6   | `get_config`: inner `DEFAULT_CONFIGS.get(model_name, {}→None)` default                                                                                                                                                                     | 1   | get_config_15                              | EQUIVALENT | model_name is validated upstream (`_get_model_dir` raises) and every supported model is a DEFAULT_CONFIGS key — the changed default is unreachable.                                                                                                                                                                       |
| 7   | `get_config_with_metadata`: read path clobbered/inverted — first `data=_read_json(...)`→`None` (:274), `if data is None`→`is not None` (:276), `return data or {…}`→`data and {…}` (:281)                                                  | 3   | gcwm_3, gcwm_5, gcwm_9                     | TEST-GAP   | Mutant 3 silently re-initializes (overwrites) stored configs with defaults on every call; 5 skips init when the file is missing and returns `None`-ish paths; 9 returns the synthesized default instead of stored data. All existing tests use fresh storage and only check key presence (:324–:348). Killed by draft T5. |
| 8   | `get_config_with_metadata`: second read after init replaced by `None` (:279) → returns synthesized dict, not the file it just wrote                                                                                                        | 1   | gcwm_7                                     | TEST-GAP   | Result loses `created_by`/`description`/`created_at` fidelity vs the persisted file. Killed by draft T5 (fresh-model branch).                                                                                                                                                                                             |
| 9   | `_initialize_default_config`: `config=default_config`→`config=None` — writes `"config": null` into current.json + v1.json                                                                                                                  | 1   | init_7                                     | TEST-GAP   | Data corruption: every later `get_config`/`get_history` read of that model sees `{}`. Return value is unchanged so all existing asserts pass (test file :1454). Killed by draft T4.                                                                                                                                       |
| 10  | `_initialize_default_config`: persisted audit metadata mutated — `created_by="system"`→None/removed/`"XXsystemXX"`/`"SYSTEM"`, `description="Initial default configuration"`→None/removed/case/XX-wrapped                                  | 9   | init_8, init_9, init_12                    | TEST-GAP   | current.json/v1.json carry wrong provenance (null/user/case-banged). No test ever reads back the persisted default-init file. Killed by draft T4.                                                                                                                                                                         |
| 11  | `_initialize_default_config`: `DEFAULT_CONFIGS.get(model_name, {}→None / removed)`                                                                                                                                                         | 2   | init_3, init_5                             | EQUIVALENT | Fallback unreachable for supported models; unsupported models raise in `update_config` either way.                                                                                                                                                                                                                        |
| 12  | `get_history`: invalid-filename `continue`→`break` (:390) — history listing truncated at first bad filename                                                                                                                                | 1   | hist_12                                    | TEST-GAP   | Real truncation bug; existing test (:1558) survives only because glob returned the valid file first (filesystem-order accident). Draft T3 creates the bad file _before_ the valid ones (insertion order, stable on tmpfs/ext4/overlay) so the break truncates deterministically.                                          |
| 13  | `get_history`: sort key removed — `sort(key=lambda x: x[0], reverse=True)`→`key=None` / key arg dropped                                                                                                                                    | 2   | hist_13, hist_15                           | EQUIVALENT | `list.sort(key=None)` is identical to no-key; tuple `(version, path)` ordering == version ordering because version numbers are unique per history dir (one `vN.json` per N). Newest-first order unchanged.                                                                                                                |
| 14  | `get_history`: `config` field of every PromptVersion corrupted — `data.get("config", {})`→`config=None`, `get(None,{})`, key `"XXconfigXX"`/`"CONFIG"` → always `{}`/None                                                                  | 4   | hist_27, hist_42, hist_46                  | TEST-GAP   | History entries ship empty/None config. Tests assert len/order/created_by/description only (:466–:548). Killed by draft T2.                                                                                                                                                                                               |
| 15  | `get_history`: `created_at` corrupted — `created_at=None`, `safe_parse_datetime(None)`, `data.get(None / "XXcreated_atXX" / "CREATED_AT")` → fallback now                                                                                  | 5   | hist_28, hist_48, hist_50                  | TEST-GAP   | Timestamp silently wrong (None or now()). Killed by draft T2 (compare against persisted `created_at`).                                                                                                                                                                                                                    |
| 16  | `get_history`: stored-`version` field ignored/fallback nulled — key `None`/`"XXversionXX"`/`"VERSION"` → filename number wins; `get("version", None / )` → None when field missing                                                         | 5   | hist_36, hist_37, hist_40                  | TEST-GAP   | Only observable with hand-edited/corrupt history files (stored `version` ≠ filename number, or field absent). That mismatch is exactly what the stored-vs-filename fallback exists for; no crafted-file test asserts it. Killed by draft T3.                                                                              |
| 17  | `get_history`: missing-`config`-key fallback nulled — `get("config", None)` / `get("config", )`                                                                                                                                            | 2   | hist_43, hist_45                           | TEST-GAP   | Crafted file without `config` → `.config` is None, not `{}`. Killed by draft T3.                                                                                                                                                                                                                                          |
| 18  | `get_history`: `created_by` fallback corrupted — `get("created_by", None / )`, fallback `"XXunknownXX"`/`"UNKNOWN"`                                                                                                                        | 4   | hist_53, hist_58, hist_59                  | TEST-GAP   | File missing `created_by` → None/wrong sentinel instead of `"unknown"`. Killed by draft T3.                                                                                                                                                                                                                               |
| 19  | `get_version`: `created_at` corrupted — `created_at=None`, `safe_parse_datetime(None)`, key `None`/`XXcreated_atXX`/`CREATED_AT`                                                                                                           | 5   | ver_9, ver_29, ver_31                      | TEST-GAP   | Same as cluster 15 but via `get_version`; the only get_version fidelity test (:565) asserts version/config/created_by, never created_at. Killed by draft T2 (get_version section).                                                                                                                                        |
| 20  | `get_version`: `description` corrupted — `description=None`, `data.get(None / "XXdescriptionXX" / "DESCRIPTION")`                                                                                                                          | 4   | ver_11, ver_41, ver_42                     | TEST-GAP   | Restored/inspected versions lose their description. Killed by draft T2.                                                                                                                                                                                                                                                   |
| 21  | `get_version`: stored-`version` precedence/fallbacks — key→None/XX/CASE (filename arg wins), fallback→None                                                                                                                                 | 5   | ver_17, ver_18, ver_21                     | TEST-GAP   | Killed by draft T3 (crafted `v7.json` with stored version 42, and `v8.json` `{}`).                                                                                                                                                                                                                                        |
| 22  | `get_version`: missing-`config` fallback nulled — `get("config", None)` / `get("config", )`                                                                                                                                                | 2   | ver_24, ver_26                             | TEST-GAP   | Killed by draft T3.                                                                                                                                                                                                                                                                                                       |
| 23  | `get_version`: `created_by` fallback corrupted — None fallbacks / `"XXunknownXX"` / `"UNKNOWN"`                                                                                                                                            | 4   | ver_34, ver_39, ver_40                     | TEST-GAP   | Killed by draft T3.                                                                                                                                                                                                                                                                                                       |
| 24  | `restore_version`: `created_by=created_by`→None / argument removed (→ default `"user"`) (:486)                                                                                                                                             | 2   | restore_12, restore_16                     | TEST-GAP   | Restored version's audit trail (returned PromptVersion + persisted file) shows None/"user" instead of the acting user. Existing restore tests (:632–:687) assert version/config/description, never `created_by`. Killed by appendix one-liner R1.                                                                         |
| 25  | `export_all`: `datetime.now(UTC).isoformat()`→`datetime.now(None).isoformat()` (:508)                                                                                                                                                      | 1   | export_3                                   | TEST-GAP   | `exported_at` becomes a naive local timestamp (no offset). Existing test (:750) only parses it. Killed by appendix one-liner E1.                                                                                                                                                                                          |
| 26  | `import_configs`: seed values of the `results` dict `""`→`"XXXX"` for imported/skipped/errors                                                                                                                                              | 3   | imp_4, imp_7, imp_10                       | EQUIVALENT | All three seeds are unconditionally overwritten after the loop (:560–:562) — pure dead assignment.                                                                                                                                                                                                                        |
| 27  | `import_configs`: seed-dict **keys** renamed — `"imported"`→`"XXimportedXX"`/`"IMPORTED"` etc. (initial dict literal :529–:533)                                                                                                            | 6   | imp_2, imp_3, imp_5                        | LOW-VALUE  | Correct keys are still created by the join lines; the only observable delta is extra junk keys. Consumers (routes/frontend) read specific keys; no tested consumer iterates the result. Note: appendix test's `result == {…}` equality (in draft T6 empty-batch test) also kills these.                                   |
| 28  | `import_configs`: `continue`→`break` in unsupported-model (:541) and skip-existing (:547) branches                                                                                                                                         | 2   | imp_16, imp_22                             | TEST-GAP   | One bad/skipped model aborts the whole import loop; the rest are silently neither imported nor reported. Dict insertion order makes this deterministic if the trigger is placed first. Killed by draft T6.                                                                                                                |
| 29  | `import_configs`: persisted audit metadata mutated — `created_by=created_by`→None/removed (→`"user"`), `description="Imported configuration"`→None/removed/case/XX                                                                         | 7   | imp_25, imp_26, imp_29                     | TEST-GAP   | Imported versions lose provenance. Tests pass `created_by="import_test"` (:773) and never assert it landed. Killed by draft T6.                                                                                                                                                                                           |
| 30  | `import_configs`: result formatting — `", ".join`→`"XX, XX".join` (imported/skipped), `"; ".join`→`"XX; XX".join` (errors), `else "none"`→`""`/`"XXnoneXX"`/`"NONE"`, `if skipped`→`if skipped or True`                                    | 6   | imp_42, imp_49, imp_60                     | TEST-GAP   | Multi-name reports get garbage separators; the empty-case `"none"` sentinel (UI contract, asserted for 2 of 3 keys at :829–:830 — `skipped` is never checked). Killed by draft T6.                                                                                                                                        |

Sum check: 9+1+1+1+5+1+3+1+1+9+2+1+2+4+5+5+2+4+5+4+5+2+4+2+1+3+6+2+7+6 = **104** = TEST-GAP 88 + EQUIVALENT 9 + LOW-VALUE 7. ✔

## Drafted tests (highest-value TEST-GAP clusters)

All append to `backend/tests/unit/services/test_prompt_storage.py`, follow its style (classes, `storage_service`/`temp_storage_dir` fixtures, docstrings). **UNVERIFIED - not yet run red/green.** TDD procedure for each: run the test against each cluster mutant → assert fails on the mutant diff; run against the original → passes.

Add to the existing import block for T1:

```python
from backend.services.prompt_storage import (
    ...,
    safe_parse_datetime,   # ADD THIS LINE
)
```

### T1 — direct safe_parse_datetime coverage (kills clusters 1+2, 10 mutants)

```python
class TestSafeParseDatetimeDirect:
    """Direct unit tests for safe_parse_datetime().
    UNVERIFIED - not yet run red/green
    """

    def test_parses_offset_and_zulu_timestamps(self):
        """Valid ISO strings (offset and Zulu forms) parse to the exact UTC datetime."""
        expected = datetime(2024, 1, 15, 8, 30, tzinfo=UTC)
        assert safe_parse_datetime("2024-01-15T08:30:00+00:00") == expected
        assert safe_parse_datetime("2024-01-15T08:30:00Z") == expected

    def test_invalid_value_falls_back_to_aware_now(self):
        """An unparseable value falls back to a timezone-aware now(), never None/naive."""
        result = safe_parse_datetime("not-a-timestamp")
        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert abs((datetime.now(UTC) - result).total_seconds()) < 5

    def test_explicit_fallback_is_returned_verbatim(self):
        """Falsy values and unparseable values return the caller's fallback unchanged."""
        fallback = datetime(2000, 1, 1, tzinfo=UTC)
        assert safe_parse_datetime("", fallback) == fallback
        assert safe_parse_datetime(None, fallback) == fallback
        assert safe_parse_datetime("garbage", fallback) == fallback
```

Kill map: case-1 mutants 4–9 and cluster-2 mutant (SPD_12) die on test 1 (`== expected`); mutants 1–3 die on tests 2–3 (None/naive/overridden fallback). SPD_10/11 are EQUIVALENT/LOW-VALUE by ruling — not expected to die.

### T2 — persisted-field fidelity for get_history + get_version (kills clusters 14, 15, 19, 20)

```python
    def test_history_and_version_preserve_all_persisted_fields(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Every PromptVersion field matches the persisted JSON, incl. created_at/config.
        UNVERIFIED - not yet run red/green
        """
        created = storage_service.update_config(
            model_name="nemotron",
            config={"system_prompt": "Fidelity prompt", "temperature": 0.25},
            created_by="hist_user",
            description="Fidelity desc",
        )
        raw = json.loads((temp_storage_dir / "nemotron" / "history" / "v1.json").read_text())

        entry = storage_service.get_history("nemotron")[0]
        assert entry.version == raw["version"] == created.version
        assert entry.config == raw["config"] == {"system_prompt": "Fidelity prompt", "temperature": 0.25}
        assert entry.created_by == "hist_user"
        assert entry.description == "Fidelity desc"
        assert entry.created_at == datetime.fromisoformat(raw["created_at"])

        ver = storage_service.get_version("nemotron", 1)
        assert ver is not None
        assert ver.config == raw["config"]
        assert ver.created_by == "hist_user"
        assert ver.description == "Fidelity desc"
        assert ver.created_at == datetime.fromisoformat(raw["created_at"])
```

### T3 — crafted history files: stored-vs-filename precedence, fallbacks, bad filenames (kills clusters 12, 16, 17, 18, 21, 22, 23)

```python
class TestCraftedHistoryFiles:
    """History files not written by update_config must honor stored fields and defaults.
    UNVERIFIED - not yet run red/green
    """

    def test_get_version_and_history_honor_stored_fields_with_fallbacks(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        history_dir = temp_storage_dir / "nemotron" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        # Invalid filename FIRST so a `break` (instead of `continue`) deterministically
        # truncates the listing (relies on readdir insertion order — stable on tmpfs/ext4).
        (history_dir / "vzz.json").write_text('{"config": {}}')
        # Stored "version" (42) overrides the filename-derived number (7).
        (history_dir / "v7.json").write_text(
            json.dumps({"version": 42, "config": {"system_prompt": "stored"}})
        )
        # No optional fields at all → filename number, {} config, "unknown" author, aware now().
        (history_dir / "v8.json").write_text("{}")

        v7 = storage_service.get_version("nemotron", 7)
        assert v7 is not None
        assert v7.version == 42
        assert v7.config == {"system_prompt": "stored"}

        v8 = storage_service.get_version("nemotron", 8)
        assert v8 is not None
        assert v8.version == 8
        assert v8.config == {}
        assert v8.created_by == "unknown"
        assert v8.description is None
        assert v8.created_at is not None and v8.created_at.tzinfo is not None

        by_version = {v.version: v for v in storage_service.get_history("nemotron")}
        assert 42 in by_version and 8 in by_version
        assert by_version[8].created_by == "unknown"
        assert by_version[8].config == {}
```

### T4 — default-init persists a faithful, system-attributed file (kills clusters 9, 10, 11 mutants excluded by ruling)

```python
    def test_initialize_default_config_persists_system_metadata(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """The default-init file round-trips the real default config with system provenance.
        UNVERIFIED - not yet run red/green
        """
        config = storage_service._initialize_default_config("nemotron")
        raw = json.loads((temp_storage_dir / "nemotron" / "current.json").read_text())

        assert config == DEFAULT_CONFIGS["nemotron"]
        assert raw["config"] == DEFAULT_CONFIGS["nemotron"]  # kills config=None writes
        assert raw["created_by"] == "system"
        assert raw["description"] == "Initial default configuration"
        assert raw["version"] == 1

        history_raw = json.loads(
            (temp_storage_dir / "nemotron" / "history" / "v1.json").read_text()
        )
        assert history_raw["config"] == DEFAULT_CONFIGS["nemotron"]
        assert history_raw["created_by"] == "system"
```

### T5 — get_config_with_metadata returns stored data, not defaults (kills clusters 7, 8)

```python
    def test_get_config_with_metadata_preserves_existing_and_reads_back(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """Stored config is returned verbatim; a fresh default is read back from the file.
        UNVERIFIED - not yet run red/green
        """
        storage_service.update_config(
            "nemotron", {"system_prompt": "Custom", "temperature": 0.5}, created_by="tester"
        )
        raw = json.loads((temp_storage_dir / "nemotron" / "current.json").read_text())
        result = storage_service.get_config_with_metadata("nemotron")
        # Must NOT re-initialize with defaults over the stored config.
        assert result == raw
        assert result["config"]["system_prompt"] == "Custom"

        fresh = storage_service.get_config_with_metadata("fashion_clip")
        fresh_raw = json.loads((temp_storage_dir / "fashion_clip" / "current.json").read_text())
        # Returned dict is the file that was just written, not a synthesized stand-in.
        assert fresh == fresh_raw
        assert fresh["created_by"] == "system"
```

### T6 — import_configs: exact reports, loop completion, persisted provenance (kills clusters 28, 29, 30; equality also kills LOW-VALUE cluster 27)

```python
    def test_import_configs_mixed_batch_reports_exactly(
        self, storage_service: PromptStorageService, temp_storage_dir: Path
    ):
        """One bad/skipped model must not abort the batch; reports are exact strings.
        UNVERIFIED - not yet run red/green
        """
        storage_service.update_config("nemotron", {"system_prompt": "Existing"}, created_by="user")
        storage_service.update_config("xclip", {"action_classes": ["walking"]}, created_by="user")

        configs = {
            "unknown_a": {"data": 1},          # unsupported FIRST → breaks batch (m16)
            "nemotron": {"system_prompt": "New"},   # skipped FIRST → breaks batch (m22)
            "xclip": {"action_classes": ["running"]},
            "florence2": {"vqa_queries": ["q"]},
            "yolo_world": {"object_classes": ["person"]},
            "unknown_b": {"data": 2},
        }
        result = storage_service.import_configs(configs, created_by="import_test")

        assert result["imported"] == "florence2, yolo_world"
        assert result["skipped"] == "nemotron, xclip"
        assert result["errors"] == (
            "unknown_a: Unsupported model; unknown_b: Unsupported model"
        )

        raw = json.loads((temp_storage_dir / "florence2" / "current.json").read_text())
        assert raw["created_by"] == "import_test"
        assert raw["description"] == "Imported configuration"

    def test_import_configs_empty_batch_reports_none_for_all_three_keys(
        self, storage_service: PromptStorageService
    ):
        """Empty import: all three report slots are exactly 'none' (no junk keys).
        UNVERIFIED - not yet run red/green
        """
        result = storage_service.import_configs({})
        assert result == {"imported": "none", "skipped": "none", "errors": "none"}
```

### Appendix — small one-liner kills (clusters 5, 24, 25)

```python
# C1 (kills cluster 5) — extend TestGetConfig:
    def test_get_config_well_formed_file_missing_or_bad_config_key(self, temp_storage_dir: Path):
        """UNVERIFIED - not yet run red/green"""
        service = PromptStorageService(storage_path=temp_storage_dir)
        (temp_storage_dir / "nemotron" / "current.json").write_text('{"model_name": "nemotron"}')
        assert service.get_config("nemotron") == DEFAULT_CONFIGS["nemotron"]  # kills _9/_11/_14/_17
        (temp_storage_dir / "xclip" / "current.json").write_text('{"config": "not-a-dict"}')
        assert service.get_config("xclip") == {}                              # kills _19

# R1 (kills cluster 24) — append to test_restore_version_creates_new_version body:
        assert result.created_by == "admin"   # kills restore_12 (None) and restore_16 ("user")

# E1 (kills cluster 25) — append to test_export_all_has_valid_timestamp body:
        assert timestamp.tzinfo is not None   # kills export_3 (naive now(None))
```

## Notes

- The 312 `null` verdict keys are mid-run; re-extract survivors after the run completes before landing these tests (some nulls may join clusters above; the patterns are stable, counts may grow).
- Reconciliation hint: T2+T3+appendix C1/R1/E1 collectively cover 45 of the 88 TEST-GAP mutants; T1 covers 10; T4 10; T5 4; T6 15 (13 + 2 via loop-completion asserts) — expected kill uplift ≈ 84–88 for this module.
- Cluster 12's kill (draft T3) leans on readdir insertion order to place the invalid filename first; the test is green on the original regardless of order, so it can only under-kill, never false-fail.

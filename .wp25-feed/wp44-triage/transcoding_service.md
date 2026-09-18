# WP4.4 Triage Dossier — backend/services/transcoding_service.py

- **Survivors:** 108 of 333 checked (106 killed, 119 unchecked at snapshot time)
- **Method:** diffs derived locally by AST-indexing `mutants/backend/services/transcoding_service.py`
  (every variant is a named top-level def `x…__mutmut_N`, baseline = same name `__mutmut_orig`) and
  unified-diffing. Cross-checked against `uv run mutmut show` on a sample (identical). The `.spans`
  file is **stale** vs the live mutant copy — do not use byte offsets.
- **Covering test file (primary):** `backend/tests/unit/services/test_transcoding_service.py` (848 lines)
  (`backend/tests/unit/services/test_transcoding.py` covers the *other* module `backend/services/transcoding.py`;
  `mutmut-stats.json` confirms every survivor's covering tests are in test_transcoding_service.py.)
- **Baseline facts discovered while classifying:**
  - `transcoding_cache_directory` is **not** a field on `Settings` (grep of `backend/` — only the service's
    own `getattr(…, "transcoding_cache_directory", …)` at transcoding_service.py:280). The getattr default
    is therefore **live behavior in production**, and every existing test that goes through settings
    explicitly *sets the attribute* on the mock (test_transcoding_service.py:80,444,456) — the default
    branch is never exercised.
  - Existing command-vector assertions: only `"h264_nvenc" in call_args` / `"libx264" in call_args`
    (test_transcoding_service.py:793-794, 847-848), and those encoder args come from a *mocked*
    `get_video_encoder_args` — nothing asserts the ffmpeg argv literals built inside `_remux_video` /
    `transcode_video`, nor the `create_subprocess_exec` kwargs.
  - All existing cache-file fixtures avoid the 1000-byte boundary (they write ≥1KB, e.g. `b"cached content" + b"\x00"*1024`).

## Cluster table (sum = 108)

| ID | Pattern (mutation kind × function/concern) | N | Class | Example keys (≤3) | Covering tests (file:line) | Note |
|----|--------------------------------------------|---|-------|-------------------|---------------------------|------|
| C1 | `_remux_video` ffmpeg argv string literals (`"ffmpeg"`,`"-y"`,`"-i"`,`"-c:v"`,`"copy"`,`"-c:a"`,`"-movflags"`,`"+faststart"`, `str(video_path)→str(None)`, `str(cache_path)→str(None)`) — XX-wrapped/UPPER-cased/None-substituted | 20 | **TEST-GAP** | `…_remux_video__mutmut_2`, `_2`-family … `_remux_video__mutmut_12`, `_remux_video__mutmut_8` | test_transcoding_service.py:218,262,741 (mock exec, argv never asserted) | Mutated remux always fails in real life → silent loss of fast path + broken remux; mocks make it invisible. Killed by draft D1. |
| C2 | `transcode_video` ffmpeg argv string literals (same family incl. `-i` path `str(validated_path)→str(None)`, `-c:a` flag) | 14 | **TEST-GAP** | `…_transcode_video__mutmut_18`, `_24`, `_25` | test_transcoding_service.py:218-247,741-794 | Only `h264_nvenc`/`libx264` membership asserted (793,847); every other token unguarded. Killed by draft D2. |
| C3 | `create_subprocess_exec` kwargs: `stdout/stderr=asyncio.subprocess.PIPE` removed or set to `None` (both methods) | 8 | **TEST-GAP** | `…_remux_video__mutmut_27`, `…_transcode_video__mutmut_38`, `_41` | test_transcoding_service.py:227,270,753 | Real change: dropping `stderr=PIPE` destroys the ffmpeg-stderr diagnostic used in the TranscodingError text (transcoding_service.py:512-517) and leaks ffmpeg output to parent stdio. Killed by D1+D2 kwargs asserts. |
| C4 | pure log/exception **message text**: `logger.*(f"…")→logger.*(None)`, `' '.join(cmd)→'XX XX'.join`, message XX/case tweaks, `TranscodingError("XXffmpeg not foundXX")` | 27 | EQUIVALENT | `…_remux_video__mutmut_22`, `…_transcode_video__mutmut_58`, `_61` | — | Per harness definition: log/message-text only. `match="ffmpeg not found"` (test:315) even still passes `_61` because the substring survives XX-wrapping. Nobody should assert log call text. |
| C5 | 1000-byte file-validity **boundary flip**: `file_size < 1000 → <=/​<1001` (`get_cached_video`); `file_size > 1000 → >=/>1001` (`_remux_video`) | 4 | **TEST-GAP** | `…_get_cached_video__mutmut_7`, `_8`, `…_remux_video__mutmut_42` | test_transcoding_service.py:169-178 (writes 1038 bytes — avoids boundary), :218 | Exactly-1000-byte cache file flips corrupted↔valid. Killed by draft D3. |
| C6 | `cleanup_cache` age-window math: `*24*60*60` with one factor mutated (`/60`, `*25`, `*61`, `/24`) + `file_age > → >=` | 7 | **TEST-GAP** | `…_cleanup_cache__mutmut_5`, `_7`, `_15` | test_transcoding_service.py:382-408 (8-days-ago vs 8-min — passes every threshold tweak) | Aged-300s / aged-200000s / aged-610000s / exact-boundary files separate all variants. Killed by draft D4 (monkeypatched `time.time`). |
| C7 | `cleanup_cache` summary-log guard `deleted_count > 0 → >= 0 / > 1` | 2 | LOW-VALUE | `…_cleanup_cache__mutmut_20`, `_21` | — | Guard only wraps a `logger.info` summary line; no return-value change. |
| C8 | `cleanup_cache` default `max_age_days 7→8`; `deleted_count += 1 → = 1` | 2 | **TEST-GAP** | `…_cleanup_cache__mutmut_1`, `_16` | test_transcoding_service.py:382 (always passes explicit arg, single file) | Both change the returned count / retention window; killed together with C6 by draft D4. |
| C9 | `get_or_transcode` cache shortcut replaced: `cached = self.get_cached_video(…) → cached = None` | 1 | **TEST-GAP** | `…_get_or_transcode__mutmut_6` | test_transcoding_service.py:367-376 (valid cache file — mutant masked because `transcode_video` re-checks the cache) | Observable only via **corrupted** (<1KB) cache file: original deletes-and-retranscodes, mutant serves the corrupt file. Killed by draft D5. |
| C10 | `transcode_video` passes `None` as source to `_remux_video` (`self._remux_video(None, cache_path)`) | 1 | **TEST-GAP** | `…_transcode_video__mutmut_9` | test_transcoding_service.py:218,262 | Remux would run `-i None` → always fails in production (silent fast-path loss); output still correct via fallback. Killed by draft D2's assert on remux call's `-i` value. |
| C11 | `transcode_video` error-msg ternary: `error_msg = None` / `… if stderr and False` / `… if stderr or True` | 3 | **TEST-GAP** | `…_transcode_video__mutmut_45`, `_46`, `_47` | test_transcoding_service.py:297-306 (matches only `"FFmpeg exited with code 1"`) | Real change: diagnostics degraded to `None`/always-`"Unknown error"`; `_47` decodes `b""`→`""` (differs from original's `"Unknown error"`). Killable by a stronger `pytest.raises(match=…)` — sketched below (S1), not one of the 6 full drafts. |
| C12 | fallback text `"Unknown error"` → `"XXUnknown errorXX"` / lowercase / upper | 3 | LOW-VALUE | `…_transcode_video__mutmut_48`, `_49`, `_50` | — | Message text inside exception only; S1's match would incidentally kill these. |
| C13 | `_validate_video_path` option-injection guard neutered: `str(video_path_obj)→str(None)`; `startswith("-")→startswith("XX-XX")` | 2 | **TEST-GAP** | `…_validate_video_path__mutmut_8`, `_9` | test_transcoding_service.py:122-131 (test itself concedes a resolved path can't start with `-`; only asserts `not result.startswith("-")`) | Security guard becomes dead code under both mutants. Killed by draft D6 (stubbed `Path` in the module namespace). |
| C14 | `hashlib.md5(…, usedforsecurity=False)` kwarg: `=None`, removed (default), `=True` | 3 | EQUIVALENT | `…_compute_file_hash__mutmut_4`, `_6`, `_7` | test_transcoding_service.py:137-157 | Digest unchanged; flag is advisory (would only bite on FIPS-OpenSSL builds — note only). |
| C15 | `__init__` cache-dir **fallback default** `"data/transcoded_cache"` → `None` / omitted / `XX…XX` / uppercased | 4 | **TEST-GAP** | `…__init____mutmut_9`, `_12`, `_15` | test_transcoding_service.py:77-87,441-463 (every settings-path test sets the attribute) | `transcoding_cache_directory` is NOT a real Settings field → default is what production actually gets; mutants give `TypeError`/`AttributeError`/wrong dir. Killed by draft S2 (sketch). |
| C16 | `_ensure_cache_directory` `mkdir(parents=True)` → `parents=None/False` / kwarg removed | 3 | **TEST-GAP** | `…_ensure_cache_directory__mutmut_1`, `_3`, `_5` | test_transcoding_service.py:90-98 (single-level dir only) | Nested cache path fails under mutants (`FileNotFoundError` re-raised by the except clause). Killed by draft S3 (sketch). |
| C17 | `_remux_video` "remux failed" branch `cache_path.unlink(missing_ok=True)` → `missing_ok=False/None` | 2 | EQUIVALENT | `…_remux_video__mutmut_46`, `_47` | — | The raised `FileNotFoundError` is swallowed by the method's own `except Exception` (same-site unlink there is unmutated) → identical outcome (return None) on every path. Genuinely equivalent. |
| C18 | `_remux_video` `asyncio.wait_for(…, timeout=30.0)` → `timeout=None` / `31.0` | 2 | **TEST-GAP** | `…_remux_video__mutmut_34`, `_37` | test_transcoding_service.py:218 (mock completes instantly) | `timeout=None` = hung ffmpeg blocks forever in production. Only assertable by patching `asyncio.wait_for` and checking kwargs — sketch S4. |

Class totals: TEST-GAP 71 (C1,C2,C3,C5,C6,C8,C9,C10,C11,C13,C15,C16,C18) · LOW-VALUE 5 (C7,C12) · EQUIVALENT 32 (C4,C14,C17). 71+5+32 = 108. ✔

## Drafted tests — 6 highest-value clusters

**TDD procedure (one line):** apply the mutant, run the named test → the new assert must FAIL on the mutant diff (proves red); revert to original, run → PASS (proves green).

// UNVERIFIED - not yet run red/green (per harness constraint: no test execution in this triage lane)

All drafts drop into `backend/tests/unit/services/test_transcoding_service.py`, reusing its existing
fixtures (`transcoding_service`, `temp_video_file`, `temp_cache_dir`) and style (AsyncMock + `patch("asyncio.create_subprocess_exec", autospec=True)`).
Add `import asyncio` to the import block (lines 7-9).

### D1 → kills C1 (+ remux half of C3)

```python
@pytest.mark.asyncio
async def test_remux_invokes_exact_ffmpeg_stream_copy_argv(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """_remux_video must build the exact ffmpeg stream-copy argv with captured stdio."""
    file_hash = _compute_file_hash(temp_video_file)
    cache_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    source = temp_video_file.resolve()

    with patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 1  # fail the remux; we only inspect the command
        mock_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))
        mock_exec.return_value = mock_process

        result = await transcoding_service._remux_video(source, cache_file)

        assert result is None
        args, kwargs = mock_exec.call_args
        assert list(args) == [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(cache_file),
        ]
        assert kwargs["stdout"] is asyncio.subprocess.PIPE
        assert kwargs["stderr"] is asyncio.subprocess.PIPE
```

Each C1 key breaks exactly one list element (including `str(None)` substitutions); kwargs asserts kill
remux_video 27/28/30/31.

### D2 → kills C2, C10 (+ transcode half of C3)

```python
@pytest.mark.asyncio
async def test_transcode_video_builds_exact_ffmpeg_command_for_validated_source(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """transcode_video must remux the validated path, then transcode with the exact output recipe."""
    file_hash = _compute_file_hash(temp_video_file)
    expected_output = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    if expected_output.exists():
        expected_output.unlink()
    source = temp_video_file.resolve()

    encoder_args = ["-c:v", "libx264", "-preset", "fast", "-crf", "23", "-pix_fmt", "yuv420p"]

    with (
        patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec,
        patch(
            "backend.services.transcoding_service.get_video_encoder_args",
            return_value=encoder_args,
            autospec=True,
        ),
    ):
        mock_remux_process = AsyncMock()
        mock_remux_process.returncode = 1
        mock_remux_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))

        mock_transcode_process = AsyncMock()
        mock_transcode_process.returncode = 0

        async def create_output(*args, **kwargs):
            expected_output.write_bytes(b"transcoded content" + b"\x00" * 1024)
            return (b"", b"")

        mock_transcode_process.communicate = create_output
        mock_exec.side_effect = [mock_remux_process, mock_transcode_process]

        await transcoding_service.transcode_video(temp_video_file)

    remux_args = mock_exec.call_args_list[0][0]
    assert remux_args[remux_args.index("-i") + 1] == str(source)  # kills _remux_video(None, ...)

    transcode_args, transcode_kwargs = mock_exec.call_args_list[1]
    assert list(transcode_args) == [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        *encoder_args,
        "-c:a",
        OUTPUT_AUDIO_CODEC,
        "-movflags",
        "+faststart",
        str(expected_output),
    ]
    assert transcode_kwargs["stdout"] is asyncio.subprocess.PIPE
    assert transcode_kwargs["stderr"] is asyncio.subprocess.PIPE
```

### D3 → kills C5

```python
def test_get_cached_video_boundary_is_exactly_1000_bytes(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """A cache file of exactly 1000 bytes is valid; 999 is corrupted and gets removed."""
    file_hash = _compute_file_hash(temp_video_file)
    cached_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

    cached_file.write_bytes(b"\x00" * 1000)
    assert transcoding_service.get_cached_video(temp_video_file) == cached_file

    cached_file.write_bytes(b"\x00" * 999)
    assert transcoding_service.get_cached_video(temp_video_file) is None
    assert not cached_file.exists()


@pytest.mark.asyncio
async def test_remux_output_validity_boundary_is_exactly_1000_bytes(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """Remux accepts only outputs strictly larger than 1000 bytes."""
    file_hash = _compute_file_hash(temp_video_file)
    cache_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"

    # 1000 bytes -> rejected as suspicious, file removed, fall back to transcode
    with patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 0

        async def create_1000(*args, **kwargs):
            cache_file.write_bytes(b"\x00" * 1000)
            return (b"", b"")

        mock_process.communicate = create_1000
        mock_exec.return_value = mock_process

        result = await transcoding_service._remux_video(temp_video_file.resolve(), cache_file)
        assert result is None
        assert not cache_file.exists()

    # 1001 bytes -> accepted
    with patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec:
        mock_process = AsyncMock()
        mock_process.returncode = 0

        async def create_1001(*args, **kwargs):
            cache_file.write_bytes(b"\x00" * 1001)
            return (b"", b"")

        mock_process.communicate = create_1001
        mock_exec.return_value = mock_process

        result = await transcoding_service._remux_video(temp_video_file.resolve(), cache_file)
        assert result == cache_file
```

### D4 → kills C6, C8 (deterministic via monkeypatched clock)

```python
def test_cleanup_cache_age_window_is_days_times_86400(
    transcoding_service, temp_cache_dir, monkeypatch
):
    """cleanup_cache() with default age deletes files strictly older than 7*86400s, and counts all."""
    import time as time_module

    now = 1_700_000_000.0
    monkeypatch.setattr(time_module, "time", lambda: now)

    ages = {  # seconds old
        "recent.mp4": 300,          # kills 60*60 -> /60 variants (threshold 168s)
        "half_day.mp4": 200_000,    # kills days/24 variant (threshold 1050s)
        "exact_boundary.mp4": 604_800,  # exactly 7d: strictly-older rule kills >= mutant
        "just_over.mp4": 604_801,   # deleted by original
        "ancient.mp4": 900_000,     # deleted by original AND by default-arg mutant (=8d)
    }
    for name, age in ages.items():
        f = temp_cache_dir / f"{name.split('.')[0]}_transcoded.{OUTPUT_CONTAINER}"
        f.write_bytes(b"x" * 2048)
        os.utime(f, (now - age, now - age))

    # default max_age_days: original = 7 (deletes just_over + ancient = 2); mutant default=8 deletes only ancient
    deleted = transcoding_service.cleanup_cache()
    assert deleted == 2
    assert not (temp_cache_dir / f"just_over_transcoded.{OUTPUT_CONTAINER}").exists()
    assert not (temp_cache_dir / f"ancient_transcoded.{OUTPUT_CONTAINER}").exists()
    assert (temp_cache_dir / f"exact_boundary_transcoded.{OUTPUT_CONTAINER}").exists()
    assert (temp_cache_dir / f"half_day_transcoded.{OUTPUT_CONTAINER}").exists()
    assert (temp_cache_dir / f"recent_transcoded.{OUTPUT_CONTAINER}").exists()
```

Add `import os` to the import block (the existing test at :390 imports it inline). Two deletions in one
call also kill `deleted_count = 1` (would return 1, original returns 2 — kills C8 `_16`; the
`+=1 → =1` mutant also survives the *single-file* existing tests only because count==1 either way).

### D5 → kills C9

```python
@pytest.mark.asyncio
async def test_get_or_transcode_discards_corrupted_cache_file(
    transcoding_service, temp_video_file, temp_cache_dir
):
    """A corrupted (<1KB) cached file must be dropped and re-transcoded, not served."""
    file_hash = _compute_file_hash(temp_video_file)
    cache_file = temp_cache_dir / f"{file_hash}_transcoded.{OUTPUT_CONTAINER}"
    cache_file.write_bytes(b"tiny" + b"\x00" * 496)  # 500 bytes: corrupted cache

    with patch("asyncio.create_subprocess_exec", autospec=True) as mock_exec:
        mock_remux_process = AsyncMock()
        mock_remux_process.returncode = 1
        mock_remux_process.communicate = AsyncMock(return_value=(b"", b"remux failed"))

        mock_transcode_process = AsyncMock()
        mock_transcode_process.returncode = 0

        async def create_output(*args, **kwargs):
            cache_file.write_bytes(b"fresh transcoded content" + b"\x00" * 1024)
            return (b"", b"")

        mock_transcode_process.communicate = create_output
        mock_exec.side_effect = [mock_remux_process, mock_transcode_process]

        result = await transcoding_service.get_or_transcode(temp_video_file)

    assert result == cache_file
    assert cache_file.stat().st_size > 1000
    assert mock_exec.call_count == 2
```

The mutant (`cached = None`) short-circuits at `transcode_video`'s plain `cache_path.exists()` check and
serves the 500-byte file with `call_count == 0` — the asserts catch both.

### D6 → kills C13

```python
def test_validate_video_path_rejects_resolved_path_starting_with_dash(monkeypatch):
    """Defense-in-depth: a resolved path that looks like an option must be rejected."""
    import backend.services.transcoding_service as ts

    class FakePath:
        def __init__(self, raw):
            self.raw = raw

        def resolve(self):
            return self

        def exists(self):
            return True

        def is_file(self):
            return True

        def __str__(self):
            return "-evil.mp4"

    monkeypatch.setattr(ts, "Path", FakePath)

    with pytest.raises(ValueError, match="Invalid video path"):
        ts._validate_video_path("-evil.mp4")
```

`str(None)` mutant never raises (guard is dead); `startswith("XX-XX")` mutant never raises for a `-…`
path; original raises. Existing test at :122 can't reach this because a *real* resolved absolute path
can never start with `-` — the stub is the only honest way to execute the guard.

## Sketched (drafted later, not one of the six)

- **S1 (C11, C12):** strengthen `test_transcode_video_ffmpeg_failure` (:297): make remux fail with
  stderr `b"boom detail"`, transcode fail with `returncode=1, stderr=b"detail here"`, then
  `with pytest.raises(TranscodingError, match="detail here")`; second case: `stderr=b""` →
  `match=r"code 1: Unknown error$"`. Kills 45/46/47 (and 48-50 incidentally).
- **S2 (C15):** `patch(get_settings)` returning `SimpleNamespace()` (no attribute — matching real
  `Settings`, which lacks the field) → assert `service.cache_directory == Path("data/transcoded_cache")`.
  Mutants raise `AttributeError`/`TypeError` or point elsewhere.
- **S3 (C16):** `TranscodingService(cache_directory=str(tmp_path / "a/b/c"))` → assert nested dir exists.
- **S4 (C18):** patch `backend.services.transcoding_service.asyncio.wait_for` (wrap passthrough) → assert
  called with `timeout=30.0`.
- **S5 (C7, LOW-VALUE):** assert-nothing / caplog-based; not recommended.

## Reconciliation

Cluster N sum: 20+14+8+27+4+7+2+2+1+1+3+3+2+3+4+3+2+2 = **108** = survivors_total. Machine-checked
disjoint union against the meta-derived key set (`/tmp/wp25/wp44-triage/ts-clusters.json`).

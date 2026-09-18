# WP4.4 Triage Dossier — backend/api/routes/cameras.py

- **Module:** `backend/api/routes/cameras.py` (2211 lines, original)
- **Meta:** `mutants/backend/api/routes/cameras.py.meta` — 175 keys total: **130 SURVIVED**, 45 killed, 0 unchecked (run complete for this module as of 2026-09-18).
- **Diffs:** all 130 extracted by AST-aligning each `x__<fn>__mutmut_N` variant body in `mutants/backend/api/routes/cameras.py` against the original function (no clobbered-name variants in this copy — full variant functions instead). Cross-checked byte-identical against `uv run mutmut show` for the sampled key. Raw JSON: `/tmp/wp25/wp44-triage/_cam_diffs.json`; readable dump: `/tmp/wp25/wp44-triage/cameras_table.txt` and `cameras_diffs_manual.txt`.
- **Survivors live in exactly 3 functions:** `_extract_frame_from_video` (81/97), `_resolve_camera_dir` (48/64), `_is_cache_valid` (1/5). Every other function in the module has 0 survivors (most endpoint handlers have 0 generated mutants — thin delegators).

## Covering test files

| File | Relevant classes (file:line) |
|---|---|
| `backend/tests/unit/api/routes/test_cameras.py` | `TestGetCameraSnapshot` :885 (path-traversal :1071, invalid-folder-name :1111), `TestGetCameraSnapshotVideoFallback` :1312, `TestCameraSnapshotHelpers` :1574 (`_is_cache_valid` :1577-1611, `_extract_frame_from_video` :1612-1685), `TestRefreshCameraSnapshot` :1687 |
| `backend/tests/unit/routes/test_cameras_routes.py` | `TestGetCameraSnapshot` :763 (outside-base-path + fallback cases :781, :813, :858) |

Drafted tests all belong in `backend/tests/unit/api/routes/test_cameras.py` (direct-call helper style, `TestCameraSnapshotHelpers`).

## Why 130/175 survived — the two root causes

1. **`_extract_frame_from_video` is tested with `asyncio.to_thread` mocked and only `assert_called_once()`** (`test_cameras.py:1612-1685`). The ffmpeg argv list (the *product* of this function: `-y -ss 1 -i … -vf format=yuvj420p,scale=…:…,pad=… -q:v 2`), the invocation kwargs (`capture_output=True, text=True, timeout=30`) and the output-dir `mkdir(parents=True)` are executed but never inspected. That one weak assertion hosts 38 TEST-GAP survivors.
2. **The other 89 survivors are `logger.*` argument mutations** (message text, `extra=` dict keys/values, `extra=None`, line removals) in log-only positions. Classified LOW-VALUE/EQUIVALENT — no test (and no production consumer today) reads these fields. Caveat: if structured-log ingestion ever keys on `extra["video_path"]` etc., promote clusters 13/25 to TEST-GAP.

**Anomaly note:** mutants that *remove* a logger's positional message (`logger.warning(extra=…)` → TypeError) survive inside `_extract_frame_from_video` because its own `except Exception:` swallows the crash and still returns `False` — production logging is silently broken under them but the return contract holds. In `_resolve_camera_dir` the same shape (`resolve__18`) has **no** surrounding try, so its recorded survival looks like a stale verdict (WP4.3 widened-cache reuse) — WP4.4 red/green should re-check that one.

## Cluster table (27 clusters, 130 survivors, sums exactly)

Example keys are shortened: `extract__N` = `backend.api.routes.cameras.x__extract_frame_from_video__mutmut_N`, `resolve__N` = `…x__resolve_camera_dir__mutmut_N`, `cache__N` = `…x__is_cache_valid__mutmut_N`.

| # | Cluster (pattern × concern) | N | Class | Example keys | Kill vector |
|---|---|---|---|---|---|
| 1 | `_extract_frame_from_video`: ffmpeg argv flag/value strings clobbered (`XX-yXX`, `-Y`, `XX-ssXX`, `"1"→"XX1XX"`, `-i→-I`, `-vframes`, `-vf→-VF`, `-q:v→-Q:V`, `"2"→"XX2XX"`, `ffmpeg→FFMPEG`) — command never asserted | 17 | TEST-GAP | `extract__8, extract__11, extract__29` | D1 |
| 2 | `_extract_frame_from_video`: argv input/output path elements → `str(None)` (`"None"` passed to ffmpeg / output written to a file named `None`) | 2 | TEST-GAP | `extract__17, extract__30` | D1 |
| 3 | `_extract_frame_from_video`: `-vf`/`pad` width index `size[0]→size[1]` (640x480 becomes 480x480 — aspect squish on 2 of 4 uses) | 2 | TEST-GAP | `extract__23, extract__25` | D1 (assert `scale=640:480` + `pad=640:480`) |
| 4 | `_extract_frame_from_video`: `cmd = None` (whole argv list clobbered) | 1 | TEST-GAP | `extract__7` | D1 (`call_args.args[1]` → TypeError/None) |
| 5 | `_extract_frame_from_video`: `mkdir(parents=True)` → `parents=False` / kwarg removed — nested cache dir creation breaks | 2 | TEST-GAP | `extract__3, extract__5` | D2 |
| 6 | `_extract_frame_from_video`: `mkdir parents=True → parents=None` — pathlib treats `None` as falsy → non-recursive, same broken behavior as cluster 5 | 1 | TEST-GAP | `extract__1` | D2 |
| 7 | `_extract_frame_from_video`: `asyncio.to_thread(subprocess.run, cmd, …)` — func/cmd args → `None` or kwarg-lines removed | 8 | TEST-GAP | `extract__32, extract__37, extract__41` | D3 |
| 8 | `_extract_frame_from_video`: `capture_output=True`/`text=True` → `None`/`False` (stderr capture — the point of the failure-log path — silently lost) | 4 | TEST-GAP | `extract__34, extract__42, extract__43` | D3 (`call.kwargs ==` exact) |
| 9 | `_extract_frame_from_video`: `timeout=30 → 31` | 1 | TEST-GAP | `extract__44` | D3 |
| 10 | `_extract_frame_from_video` logging: msg arg → `None` / removed (4 log sites) | 5 | LOW-VALUE | `extract__47, extract__49, extract__78` | — (crash swallowed by broad `except Exception`; return contract intact) |
| 11 | `_extract_frame_from_video` logging: `extra={...}` → `None` / removed | 8 | LOW-VALUE | `extract__48, extract__65, extract__89` | — |
| 12 | `_extract_frame_from_video` logging: msg text XX-wrapped/case-changed | 9 | LOW-VALUE | `extract__51, extract__68, extract__92` | — |
| 13 | `_extract_frame_from_video` logging: `extra` dict **keys** clobbered (`XXvideo_pathXX`, `VIDEO_PATH`, …) | 12 | LOW-VALUE | `extract__53, extract__74, extract__84` | — (promote if log ingestion keys on these) |
| 14 | `_extract_frame_from_video` logging: `extra` dict **values** → `str(None)` | 5 | LOW-VALUE | `extract__55, extract__76, extract__96` | — |
| 15 | `_extract_frame_from_video` logging: stderr ternary `if result.stderr` → `and False` / `or True` — same outcome either way | 2 | EQUIVALENT | `extract__58, extract__59` | — |
| 16 | `_extract_frame_from_video` logging: stderr slice `[:500]→[:501]` | 1 | LOW-VALUE | `extract__60` | — |
| 17 | `_extract_frame_from_video` logging: stderr empty-fallback `"" → "XXXX"` | 1 | LOW-VALUE | `extract__61` | — |
| 18 | `_resolve_camera_dir` **security gate**: `or`→`and` flips in `if ".." in name or "/" in name or "\\" in name` — `".."`-only and `"\\"`-only names now slip past the traversal check into fallback resolution | 2 | TEST-GAP | `resolve__7, resolve__8` | D4 |
| 19 | `_resolve_camera_dir` security gate: `".."` / `"\\"` literals clobbered (`XX..XX`, `XX\XX`) — same slip-past effect | 2 | TEST-GAP | `resolve__9, resolve__13` | D4 |
| 20 | `_resolve_camera_dir` security gate: `"/"` literal clobbered — `Path(x).name` can never contain `/` (pathlib strips it), so check is dead defensive code → truly equivalent | 1 | EQUIVALENT | `resolve__11` | — (unkillable) |
| 21 | `_resolve_camera_dir` fallback: `if fallback_path.exists() and fallback_path.is_dir()` → `or` — resolver can return a **file** (or broken symlink) as the camera dir → `rglob` crash / dir-semantics break upstream | 1 | TEST-GAP | `resolve__31` | D5 |
| 22 | `_resolve_camera_dir` logging: msg arg → `None` / removed (3 log sites) | 3 | LOW-VALUE | `resolve__15, resolve__32, resolve__50` | — (but see anomaly note re `resolve__18` removal variant) |
| 23 | `_resolve_camera_dir` logging: `extra=` → `None` / removed | 6 | LOW-VALUE | `resolve__16, resolve__33, resolve__51` | — |
| 24 | `_resolve_camera_dir` logging: msg text XX-wrapped/case-changed | 9 | LOW-VALUE | `resolve__19, resolve__37, resolve__55` | — |
| 25 | `_resolve_camera_dir` logging: `extra` dict **keys** clobbered | 18 | LOW-VALUE | `resolve__22, resolve__41, resolve__59` | — |
| 26 | `_resolve_camera_dir` logging: `extra` values → `sanitize_log_value(None)` / `str(None)` | 6 | LOW-VALUE | `resolve__26, resolve__43, resolve__61` | — |
| 27 | `_is_cache_valid`: freshness comparison `(time.time() - mtime) < ttl` → `<=` — a cache entry exactly at TTL flips expired→valid (cache never expires at the boundary) | 1 | TEST-GAP | `cache__5` | D6 (frozen `time.time`) |

**Classification rollup:** TEST-GAP 44, LOW-VALUE 83, EQUIVALENT 3 → 130.
(EQUIVALENT members: cluster 15's `and False`/`or True` truthiness no-ops ×2, cluster 20's dead `/`-token check ×1.)

### Why 18/19/21 are TEST-GAP, not LOW-VALUE
The existing path-traversal tests (`test_cameras.py:1071`, `:1111`) only assert the endpoint's final `404` — they never prove the *gate* did the rejecting vs. some later check. A name that slips the gate (`".."`, `"dir\sub"`) with a matching fallback dir silently resolves a directory the caller never named — exactly the NEM-2540 fallback behavior weaponized. D4 constructs the scenario where gate-skip changes the return value (None → a real Path).

## Drafted tests (6 tests kill all 44 TEST-GAP survivors)

Add to `backend/tests/unit/api/routes/test_cameras.py` (class `TestCameraSnapshotHelpers`; existing imports at top: `time`, `Path`, `unittest.mock (AsyncMock, MagicMock, patch)`, `pytest`).

**TDD procedure (one line):** run each test with its cluster's mutant active (`MUTANT_UNDER_TEST=<key>`) — the new assertion must go red on the mutant diff (a TypeError/AttributeError raised by the mutant also counts as red) and green on the original.

**// UNVERIFIED - not yet run red/green**

### D1 — ffmpeg argv is the contract (kills clusters 1, 2, 3, 4 = 22)

```python
    @pytest.mark.asyncio
    async def test_extract_frame_from_video_builds_correct_ffmpeg_command(
        self, tmp_path: Path
    ) -> None:
        """The ffmpeg argv must pin overwrite, seek-to-1s, 1-frame, aspect-correct scale/pad, JPEG quality.

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread", autospec=True) as mock_thread:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_thread.return_value = mock_result

            # Simulate ffmpeg creating the output file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("fake image data")

            result = await _extract_frame_from_video(video_path, output_path)

        assert result is True
        cmd = mock_thread.call_args.args[1]  # to_thread(subprocess.run, cmd, ...)

        assert cmd[0] == "ffmpeg"
        assert cmd[1] == "-y"                                   # overwrite
        assert cmd[2] == "-ss" and cmd[3] == "1"               # skip black first second
        assert cmd[4] == "-i" and cmd[5] == str(video_path)    # real input path, not "None"
        assert cmd[6] == "-vframes" and cmd[7] == "1"          # exactly one frame
        assert cmd[8] == "-vf"
        # scale AND pad must both use width x height (640x480 default) — catches size[1]-for-size[0]
        assert cmd[9] == (
            "format=yuvj420p,scale=640:480:force_original_aspect_ratio=decrease,"
            "pad=640:480:(ow-iw)/2:(oh-ih)/2"
        )
        assert cmd[10] == "-q:v" and cmd[11] == "2"            # high-quality JPEG
        assert cmd[12] == str(output_path)                     # real output path, not "None"
```

### D2 — output directory must be created (kills cluster 5 = 2, plus 6)

```python
    @pytest.mark.asyncio
    async def test_extract_frame_from_video_creates_missing_output_directory(
        self, tmp_path: Path
    ) -> None:
        """Nested cache dirs (…/.snapshot_cache lives two levels deep) must be auto-created.

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "missing" / "deep" / "snapshot.jpg"
        assert not output_path.parent.exists()

        mock_result = MagicMock()
        mock_result.returncode = 0

        async def fake_to_thread(func, *args, **kwargs):  # noqa: ANN001 - test double
            # Plain write (no mkdir): only succeeds if the function pre-created the parent dir
            output_path.write_text("fake image data")
            return mock_result

        with patch("backend.api.routes.cameras.asyncio.to_thread", autospec=True) as mock_thread:
            mock_thread.side_effect = fake_to_thread

            result = await _extract_frame_from_video(video_path, output_path)

        assert result is True
        assert output_path.parent.is_dir()
```

### D3 — subprocess invocation kwargs are the contract (kills clusters 7, 8, 9 = 13)

```python
    @pytest.mark.asyncio
    async def test_extract_frame_from_video_invokes_subprocess_run_with_capture_and_timeout(
        self, tmp_path: Path
    ) -> None:
        """ffmpeg must run via subprocess.run with captured text output and a hard 30 s timeout.

        // UNVERIFIED - not yet run red/green
        """
        import subprocess

        from backend.api.routes.cameras import _extract_frame_from_video

        video_path = tmp_path / "test.mkv"
        output_path = tmp_path / "output" / "snapshot.jpg"

        with patch("backend.api.routes.cameras.asyncio.to_thread", autospec=True) as mock_thread:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_thread.return_value = mock_result

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("fake image data")

            result = await _extract_frame_from_video(video_path, output_path)

        assert result is True
        call = mock_thread.call_args
        assert call.args[0] is subprocess.run
        assert call.kwargs == {"capture_output": True, "text": True, "timeout": 30}
```

### D4 — fallback security gate must reject traversal tokens (kills clusters 18, 19 = 4)

```python
    @pytest.mark.parametrize(
        "folder_tail",
        ["..", "back\\slash"],
        ids=["dotdot-only", "backslash-only"],
    )
    def test_resolve_camera_dir_rejects_traversal_tokens_in_folder_name(
        self, tmp_path: Path, folder_tail: str
    ) -> None:
        """Stored folder names carrying traversal tokens must never reach fallback resolution.

        Each dangerous name has a matching existing directory under base_root, so a mutant
        that slips past the gate silently RESOLVES that directory instead of returning None.

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.cameras import _resolve_camera_dir

        base_root = tmp_path / "base"
        base_root.mkdir()
        # Bait: both fallback candidates exist (folder-name lookup AND camera-id lookup)
        (base_root / "cam1").mkdir()
        (base_root / folder_tail).mkdir()
        outside = tmp_path / "outside"  # NOT under base_root -> forces the ValueError fallback path
        outside.mkdir()
        camera_folder_path = str(outside / folder_tail)

        result = _resolve_camera_dir(camera_folder_path, "cam1", base_root)

        assert result is None
```

### D5 — fallback must resolve a directory, not a file (kills cluster 21 = 1)

```python
    def test_resolve_camera_dir_fallback_requires_directory(self, tmp_path: Path) -> None:
        """A fallback candidate that exists but is a file must be skipped (exists AND is_dir).

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.cameras import _resolve_camera_dir

        base_root = tmp_path / "base"
        base_root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        folder_name = "not_a_dir"
        (base_root / folder_name).write_text("file masquerading as a camera folder")

        result = _resolve_camera_dir(str(outside / folder_name), "missing-cam-id", base_root)

        assert result is None
```

### D6 — cache TTL boundary is strictly-less-than (kills cluster 27 = 1)

```python
    def test_is_cache_valid_boundary_is_strictly_less_than_ttl(self, tmp_path: Path) -> None:
        """An entry whose age EQUALS the TTL is expired: (now - mtime) < ttl, not <=.

        // UNVERIFIED - not yet run red/green
        """
        import os

        from backend.api.routes.cameras import _is_cache_valid

        cache_file = tmp_path / "snapshot.jpg"
        cache_file.write_text("data")

        frozen = 1_700_000_000.0  # exact float; age == ttl to the nanosecond under the frozen clock
        with patch("backend.api.routes.cameras.time.time", return_value=frozen):
            os.utime(cache_file, (frozen - 60.0, frozen - 60.0))
            assert _is_cache_valid(cache_file, ttl_seconds=60) is False   # age == ttl -> expired
            os.utime(cache_file, (frozen - 59.0, frozen - 59.0))
            assert _is_cache_valid(cache_file, ttl_seconds=60) is True    # sanity: age < ttl -> valid
```

## Notes for the WP4.4 serial-verify lane

- Re-run red/green against the CURRENT suite: cluster-10's message-removal variants crash into the function's own `except Exception` (return contract intact), but `resolve__18` (same shape, no enclosing try) *should* have died — its survivor verdict smells like WP4.3 stale-cache reuse; if it is truly executed by `test_get_snapshot_invalid_folder_name`, no new test is needed for it.
- `resolve__11` ("/" token) is provably unkillable (pathlib `.name` never yields `/`) — candidate for the baseline's equivalent-mutant list.
- D4's backslash bait directory requires a POSIX filesystem (Linux CI — fine); avoid on Windows runners.
- All drafted tests are direct-call helper tests — no FastAPI/TestClient, no SetupGuard 503-cache hazard (see memory: setup-guard-cache-poisoning).

# WP4.4 Triage Dossier — backend/services/clip_generator.py

**Run context:** WP4.3 mutation baseline. Meta: `mutants/backend/services/clip_generator.py.meta` — 420 total keys,
**179 survivors** (exit_code 0), 176 killed, 65 unchecked (null — excluded from this triage).
All 179 diffs pulled read-only via `uv run mutmut show <key>` (0 failures). Diff dump: `/tmp/wp25/wp44-triage/clip-diffs.txt` (compact: `clip-compact.txt`).

## Covering test files (from mutants/mutmut-stats.json → tests_by_mangled_function_name)

| File                                                    | Role                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/unit/services/test_clip_generator.py`    | The only test file that asserts this module's internals. Fixtures L23-74; ffmpeg cmd spot-asserts L285-288 (video), L416-418 (mp4), L451-452 (gif); pre/post-roll test L325-350 (**comment says "Verify -ss and -t" but only `-ss` is asserted**); duration guards L1046-1081; concat-file tests L1257-1305 (**L1276 tautology, see C14**); image-path filter tests L880-913 + L1205-1220; security unit tests L707-792 |
| `backend/tests/unit/api/routes/test_events_coverage.py` | Exercises `get_clip_generator()` / clip routes only; never asserts the lines mutated here                                                                                                                                                                                                                                                                                                                               |
| `backend/tests/unit/api/routes/test_media.py`           | Same — routes-level only                                                                                                                                                                                                                                                                                                                                                                                                |

## Why survivors cluster the way they do (key structural fact)

The success tests spot-assert only: `call_args[0] == "ffmpeg"`, `"-i" in cmd`, path-in-cmd, `"-c:v"`/`"libx264"` (mp4), `"-loop"` (gif), `"-ss"` value. Every mutant on an _asserted_ token died (verified: `ffmpeg` binary, `-ss`, `-i`, input path, output path, `-c:v`, `libx264`, `-loop`, `-vf` f-string, gif/mp4 path args are all KILLED). Everything on an _unasserted_ token survived: the codec/quality flag runs and the `-t` duration. That single assertion gap = 68 of the 93 TEST-GAP survivors (clusters C7/C8).

## Cluster table (counts sum to 179)

| #   | Pattern                                                                                                                                                                                                                                                                  | Func(s)                                                                                         | n      | Class      | Example keys (≤3)                                                                                                                                                                                                                                                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| C1  | logger.{debug,info,error,warning} message arg clobbered to `None` / XX-wrapped / case variants (incl. `exc_info` kwarg removal)                                                                                                                                          | all methods                                                                                     | **54** | EQUIVALENT | `…generate_clip_from_video__mutmut_8`, `…generate_clip_from_images__mutmut_38`, `…delete_clip__mutmut_3`                                                                                                                                                                                                                                                           |
| C2  | Error-message _string_ text variants: `type(None).__name__` in ValueError f-strings, `"pre_seconds"`/`"post_seconds"` param_name tweaks, `"Unknown error"` case/XX variants                                                                                              | `_validate_fps`, `_validate_roll_seconds`, `generate_clip_from_video`, `_run_ffmpeg_for_images` | **14** | EQUIVALENT | `x__validate_fps__mutmut_3`, `…generate_clip_from_video__mutmut_22`, `…_run_ffmpeg_for_images__mutmut_77`                                                                                                                                                                                                                                                          |
| C3  | `str(path).startswith("-")` guard made always-false (`str(None)` / `"XX-XX"`)                                                                                                                                                                                            | `_validate_video_path`, `_validate_image_paths`                                                 | **4**  | EQUIVALENT | `x__validate_video_path__mutmut_8`, `…_validate_image_paths__mutmut_12` — after `.resolve()` paths are absolute, so the guard branch is unreachable on POSIX; existing dash tests hit the earlier `not exists()` raise                                                                                                                                             |
| C4  | Semantically-identical arg tweaks: `NamedTemporaryFile(delete=None)` (falsy ≡ `False`; nt-only branch), `fps=validated_fps` kwarg removal (`validated_fps ≡ fps` at that point)                                                                                          | `_create_concat_file`, `generate_clip_for_event`                                                | **2**  | EQUIVALENT | `…_create_concat_file__mutmut_3`, `…generate_clip_for_event__mutmut_17`                                                                                                                                                                                                                                                                                            |
| C5  | Temp concat-file `suffix` cosmetic variants (`None`, removed, `"XX.txtXX"`, `".TXT"`)                                                                                                                                                                                    | `_create_concat_file`                                                                           | **4**  | LOW-VALUE  | `…_create_concat_file__mutmut_2`, `…_create_concat_file__mutmut_10` — temp filename suffix is unreadable by anything (ffmpeg gets `-f concat` explicitly)                                                                                                                                                                                                          |
| C6  | `create_subprocess_exec` `stdout/stderr=PIPE` → `None` / kwarg removed                                                                                                                                                                                                   | `generate_clip_from_video`, `_run_ffmpeg_for_images`                                            | **8**  | LOW-VALUE  | `…generate_clip_from_video__mutmut_86`, `…_run_ffmpeg_for_images__mutmut_68` — only degrades diagnostic capture (stderr falls back to "Unknown error", already covered by C11 test); invisible to fully-mocked subprocess                                                                                                                                          |
| C7  | ffmpeg **video-extract argv** flag/value string mutations never asserted (`-y`,`-t`-value,`-c:v`,`libx264`,`-preset`,`fast`,`-crf`,`23`,`-c:a`,`copy`,`-movflags`,`+faststart`, incl. `str(duration)`→`str(None)`)                                                       | `generate_clip_from_video`                                                                      | **24** | TEST-GAP   | `…generate_clip_from_video__mutmut_51`, `…generate_clip_from_video__mutmut_60`, `…generate_clip_from_video__mutmut_71` — tests execute cmd construction (mock captures argv) but spot-assert only `-i`/paths; flipped flags break real ffmpeg                                                                                                                      |
| C8  | ffmpeg **image-sequence argv** flag/value mutations never asserted — GIF branch and MP4 branch (`-y`,`-f`,`concat`,`-safe`,`0`,`-i`-value,`-vf`,`-loop`,`-c:v`,`-preset`,`fast`,`-crf`,`23`,`-pix_fmt`,`yuv420p`,`-movflags`,`+faststart`, output-path `str(None)`)      | `_run_ffmpeg_for_images`                                                                        | **44** | TEST-GAP   | `…_run_ffmpeg_for_images__mutmut_13`, `…_run_ffmpeg_for_images__mutmut_54`, `…_run_ffmpeg_for_images__mutmut_60` — same root cause as C7 (mp4 test asserts only `"-c:v"`/`"libx264"`, gif test only `"-loop"`)                                                                                                                                                     |
| C9  | Duration formula: `+ validated_post` → `- validated_post` / `- validated_pre` → `+ validated_pre` (real `-t` value change)                                                                                                                                               | `generate_clip_from_video` L260                                                                 | **2**  | TEST-GAP   | `…generate_clip_from_video__mutmut_36`, `…generate_clip_from_video__mutmut_37` — the one test meant to check rolls (`test_generate_clip_from_video_custom_pre_post_roll`, L325-350) asserts `-ss` only, never `-t` despite its own comment                                                                                                                         |
| C10 | Duration guard boundary flips: `< 0`→`<= 0`/`< 1`, `> 3600`→`>= 3600`/`> 3601`                                                                                                                                                                                           | `generate_clip_from_video` L263                                                                 | **4**  | TEST-GAP   | `…generate_clip_from_video__mutmut_40`, `…generate_clip_from_video__mutmut_42`, `…generate_clip_from_video__mutmut_43` — existing tests use 5400s and −20s, never duration 0.0 / 3600 / 3601                                                                                                                                                                       |
| C11 | stderr-fallback ternary mutations: `error_msg = None`, `if stderr and False`, `if stderr or True` (loses real ffmpeg stderr from the raised `ClipGenerationError`; `or True` crashes `None.decode()` when stderr is absent, turning a raise into a silent `None` return) | `generate_clip_from_video`, `_run_ffmpeg_for_images`                                            | **6**  | TEST-GAP   | `…generate_clip_from_video__mutmut_94`, `…generate_clip_from_video__mutmut_96`, `…_run_ffmpeg_for_images__mutmut_75` — tests assert only `"FFmpeg exited with code 1"`, never the stderr detail                                                                                                                                                                    |
| C12 | `raise ClipGenerationError(f"FFmpeg exited…")` → `raise ClipGenerationError(None)`                                                                                                                                                                                       | `_run_ffmpeg_for_images` L407                                                                   | **1**  | TEST-GAP   | `…_run_ffmpeg_for_images__mutmut_80` — image-path test asserts only the exception _type_, never its message                                                                                                                                                                                                                                                        |
| C13 | Roll-seconds upper-bound off-by-one: `seconds > 300` → `seconds > 301`                                                                                                                                                                                                   | `_validate_roll_seconds` L82                                                                    | **1**  | TEST-GAP   | `x__validate_roll_seconds__mutmut_8` — tests probe −1 and 400 and accept 300, never 301                                                                                                                                                                                                                                                                            |
| C14 | Concat single-quote escaping mutations: `escaped_path`/`escaped_last` → `None` / `str(None)`, `replace("'", …)` pattern/replacement clobbered (escapes lost or corrupted, incl. the repeat-last-image line)                                                              | `_create_concat_file` L527,531                                                                  | **8**  | TEST-GAP   | `…_create_concat_file__mutmut_17`, `…_create_concat_file__mutmut_23`, `…_create_concat_file__mutmut_35` — existing test L1276 `assert "…\\''…" in content or "frame" in content` is a **tautology**: the repeat-last line always contains `frame`, so every escape mutation passes. The escape is a real ffmpeg-injection concern (paths land in `file '…'` lines) |
| C15 | `_validate_image_paths` `continue` → `break` (skip-invalid becomes stop-at-first-invalid)                                                                                                                                                                                | `_validate_image_paths` L504,507                                                                | **2**  | TEST-GAP   | `…_validate_image_paths__mutmut_6`, `…_validate_image_paths__mutmut_9` — all three existing tests put the valid path **first** and invalid last, so break-after-skip is indistinguishable; a valid path listed after an invalid one is silently dropped                                                                                                            |
| C16 | `validated_fps` → `None` at the `_run_ffmpeg_for_images(...)` call (fps reaches the GIF `-vf` string only)                                                                                                                                                               | `generate_clip_from_images` L481                                                                | **1**  | TEST-GAP   | `…generate_clip_from_images__mutmut_28` — gif test asserts `-loop` only, never `-vf` contents                                                                                                                                                                                                                                                                      |

**Totals:** EQUIVALENT 74 (C1 54 + C2 14 + C3 4 + C4 2) · LOW-VALUE 12 (C5 4 + C6 8) · TEST-GAP 93 (C7 24 + C8 44 + C9 2 + C10 4 + C11 6 + C12 1 + C13 1 + C14 8 + C15 2 + C16 1). Sum = 179.

## Drafted tests (7 tests, covering all 10 TEST-GAP clusters)

All target `backend/tests/unit/services/test_clip_generator.py`; every needed import (`pytest`, `Path`, `datetime`, `AsyncMock`, `MagicMock`, `patch`, `ClipGenerator`, `ClipGenerationError`, `_validate_roll_seconds`) and fixture (`clip_generator`, `mock_event`, `temp_clips_dir`) already exists in that file. Append as a new class.
**TDD procedure (one line):** run each test against the mutant copy (or hand-apply the cluster's one-line diff) — assert must FAIL red; restore original — must PASS green.

// UNVERIFIED - not yet run red/green (pytest not executed per WP4.3 live-run constraint)

### T1 — exact ffmpeg argv, video extraction → kills C7 (24) + C9 (2)

```python
@pytest.mark.asyncio
async def test_generate_clip_from_video_exact_ffmpeg_argv(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Pin the complete ffmpeg argv for video extraction.

    Kills every flag/value mutation in the cmd list (C7) and the
    pre/post-roll arithmetic flips (C9): mock_event spans 30s, fixture
    rolls are 5/5, so -t must be exactly "40.0".
    """
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    expected_output = temp_clips_dir / f"{mock_event.id}_clip.mp4"

    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
    ) as mock_exec:
        expected_output.touch()

        result = await clip_generator.generate_clip_from_video(mock_event, video_path)

        assert result == expected_output
        assert mock_exec.call_args[0] == (
            "ffmpeg",
            "-y",
            "-ss", "5",
            "-i", str(video_path.resolve()),
            "-t", "40.0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(expected_output),
        )
```

### T2 — exact ffmpeg argv, image sequence mp4 + gif → kills C8 (44) + C16 (1)

The concat-list path is the one value we can't hardcode (tempfile). Get it by running the
real `_create_concat_file` once, then patch it to return exactly that path — so the expected
tuple below is fully literal, the `-i` value mutants (`str(None)`) still fail (they'd put
`"None"` where a real path is expected), and we don't couple to the cosmetic suffix
cluster C5.

```python
@pytest.mark.asyncio
async def test_generate_clip_from_images_exact_argv_mp4_and_gif(
    clip_generator, mock_event, tmp_path, temp_clips_dir
):
    """Pin the full argv for both image-sequence branches, incl. fps in -vf."""
    img1 = tmp_path / "frame1.jpg"
    img1.touch()
    img2 = tmp_path / "frame2.jpg"
    img2.touch()

    # Real run once -> the exact temp list path the patched call will return.
    real_list = clip_generator._create_concat_file(
        clip_generator._validate_image_paths([str(img1), str(img2)]), fps=4
    )

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    # --- MP4 branch ---
    out_mp4 = temp_clips_dir / f"{mock_event.id}_clip.mp4"
    with (
        patch(
            "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
        ) as mock_exec,
        patch.object(ClipGenerator, "_create_concat_file", return_value=real_list),
    ):
        out_mp4.touch()
        result = await clip_generator.generate_clip_from_images(
            mock_event, [str(img1), str(img2)], fps=4, output_format="mp4"
        )
        assert result == out_mp4
        assert mock_exec.call_args[0] == (
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            str(real_list),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out_mp4),
        )
    real_list.unlink(missing_ok=True)  # already unlinked by _run_ffmpeg_for_images finally

    # --- GIF branch (also pins fps propagation into the -vf filter, killing C16) ---
    real_list_gif = clip_generator._create_concat_file(
        clip_generator._validate_image_paths([str(img1), str(img2)]), fps=3
    )
    out_gif = temp_clips_dir / f"{mock_event.id}_clip.gif"
    with (
        patch(
            "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
        ) as mock_exec,
        patch.object(ClipGenerator, "_create_concat_file", return_value=real_list_gif),
    ):
        out_gif.touch()
        await clip_generator.generate_clip_from_images(
            mock_event, [str(img1), str(img2)], fps=3, output_format="gif"
        )
        assert mock_exec.call_args[0] == (
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            str(real_list_gif),
            "-vf", "fps=3,scale=320:-1:flags=lanczos",
            "-loop", "0",
            str(out_gif),
        )
    real_list_gif.unlink(missing_ok=True)
```

### T3 — duration formula boundaries → kills C10 (4)

```python
@pytest.mark.asyncio
async def test_generate_clip_from_video_duration_guard_boundaries(
    clip_generator, tmp_path, temp_clips_dir
):
    """duration == 0.0 and == 3600 are ACCEPTED; 3601 rejected without exec.

    Kills <0→<=0 and <0→<1 (0-duration reject), >3600→>=3600 (3600 reject),
    >3600→>3601 (3601 accept).
    """
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"", b""))

    def make_event(event_id: int, seconds: int) -> MagicMock:
        event = MagicMock()
        event.id = event_id
        event.started_at = datetime(2024, 1, 15, 10, 0, 0)
        event.ended_at = event.started_at + __import__("datetime").timedelta(seconds=seconds)
        return event

    # duration exactly 0.0: zero-length event, zero rolls -> must run ffmpeg
    out = temp_clips_dir / "501_clip.mp4"
    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
    ) as mock_exec:
        out.touch()
        result = await clip_generator.generate_clip_from_video(
            make_event(501, 0), video_path, pre_seconds=0, post_seconds=0
        )
        assert mock_exec.called
        assert result == out

    # duration exactly 3600: 3500s event + 50 + 50 -> must run ffmpeg
    out = temp_clips_dir / "502_clip.mp4"
    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
    ) as mock_exec:
        out.touch()
        result = await clip_generator.generate_clip_from_video(
            make_event(502, 3500), video_path, pre_seconds=50, post_seconds=50
        )
        assert mock_exec.called
        assert result == out

    # duration 3601: 3501 + 50 + 50 -> must reject WITHOUT invoking ffmpeg
    # (a mutant that accepts it would still return None here since the output
    # file is absent — asserting not-called is what distinguishes it)
    with patch(
        "asyncio.create_subprocess_exec", return_value=mock_process, autospec=True
    ) as mock_exec:
        result = await clip_generator.generate_clip_from_video(
            make_event(503, 3501), video_path, pre_seconds=50, post_seconds=50
        )
        assert result is None
        assert not mock_exec.called
```

(Style fix for final: import `timedelta` at module top instead of `__import__` — existing file imports `from datetime import datetime`.)

### T4 — stderr detail survives into the exception → kills C11 (6) + C12 (1)

```python
@pytest.mark.asyncio
async def test_ffmpeg_failure_error_message_carries_stderr_detail(
    clip_generator, mock_event, tmp_path
):
    """ClipGenerationError must embed real stderr text on both clip paths.

    Kills error_msg -> None / forced "Unknown error" (C11) and the
    ClipGenerationError(None) message clobber in _run_ffmpeg_for_images (C12).
    """
    video_path = tmp_path / "source.mp4"
    video_path.touch()

    fail_proc = AsyncMock()
    fail_proc.returncode = 1
    fail_proc.communicate = AsyncMock(return_value=(b"", b"boom: bad input"))

    with patch("asyncio.create_subprocess_exec", return_value=fail_proc, autospec=True):
        with pytest.raises(ClipGenerationError) as exc_info:
            await clip_generator.generate_clip_from_video(mock_event, video_path)
    assert "FFmpeg exited with code 1" in str(exc_info.value)
    assert "boom: bad input" in str(exc_info.value)

    # Absent stderr must still yield the fallback message, not crash on
    # None.decode() (kills the `if stderr or True` mutation, which would be
    # swallowed by the generic except and return None instead of raising).
    fail_no_stderr = AsyncMock()
    fail_no_stderr.returncode = 1
    fail_no_stderr.communicate = AsyncMock(return_value=(b"", None))
    with patch("asyncio.create_subprocess_exec", return_value=fail_no_stderr, autospec=True):
        with pytest.raises(ClipGenerationError, match="Unknown error"):
            await clip_generator.generate_clip_from_video(mock_event, video_path)

    # Image-sequence path: exception message, not just type.
    img = tmp_path / "frame.jpg"
    img.touch()
    with patch("asyncio.create_subprocess_exec", return_value=fail_proc, autospec=True):
        with pytest.raises(ClipGenerationError) as exc_info:
            await clip_generator.generate_clip_from_images(mock_event, [str(img)])
    assert "boom: bad input" in str(exc_info.value)
```

### T5 — concat escaping + repeat-last contract, exact content → kills C14 (8)

Replaces the vacuous `… or "frame" in content` assertion (test_clip_generator.py L1276) with full-content equality.

```python
def test_create_concat_file_exact_escape_and_repeat_contract(self, tmp_path):
    """Every file line must be exactly quoted-escaped; repeat line must be the last path."""
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    generator = ClipGenerator(clips_directory=str(clips_dir))

    first = tmp_path / "plain.jpg"
    first.touch()
    quoted = tmp_path / "frame's_2.jpg"
    quoted.touch()

    concat = generator._create_concat_file([first, quoted], fps=2)
    try:
        escaped_quoted = str(quoted).replace("'", "'\\''")
        assert concat.read_text() == (
            f"file '{first}'\n"
            "duration 0.5\n"
            f"file '{escaped_quoted}'\n"
            "duration 0.5\n"
            f"file '{escaped_quoted}'\n"  # repeat-last-image line
        )
        assert "file 'None'" not in concat.read_text()
        assert f"file '{quoted}'" not in concat.read_text()  # never unescaped
    finally:
        concat.unlink()
```

### T6 — skip vs stop in the image-path filter → kills C15 (2)

```python
def test_validate_image_paths_keeps_valid_paths_after_invalid_ones(self, clip_generator, tmp_path):
    """Invalid entries are SKIPPED, not loop-terminators (continue vs break)."""
    valid_a = tmp_path / "a.jpg"
    valid_a.touch()
    valid_b = tmp_path / "b.jpg"
    valid_b.touch()
    missing = tmp_path / "missing.jpg"
    directory = tmp_path / "subdir"
    directory.mkdir()

    result = clip_generator._validate_image_paths(
        [str(missing), str(directory), str(valid_a), str(valid_b)]
    )

    assert result == [valid_a.resolve(), valid_b.resolve()]
```

### T7 — roll-seconds upper bound at 301 → kills C13 (1)

```python
def test_validate_roll_seconds_rejects_just_above_limit(self):
    """301 is out of bounds (guards off-by-one on the 300 upper bound)."""
    with pytest.raises(ValueError, match="pre_seconds must be between 0 and 300"):
        _validate_roll_seconds(301, "pre_seconds")
```

## Notes for WP4.4

- C7+C8 (68 mutants) die to two exact-argv tests (T1, T2) — highest kill-per-test in this module.
- The `or "frame" in content` tautology at test_clip_generator.py:1276 is worth a grep across the suite for similar `assert X in content or substring_of_X in content` patterns.
- C3's guard is dead-on-POSIX after `resolve()`; if the team wants the injection guard to be live, the fix is to validate the _pre-resolution_ string — until then those 4 mutants (and the branch) are permanent EQUIVALENTs.
- 65 keys still unchecked (null) will add to these clusters when the run finishes; expected distribution: flag runs (C7/C8 tail) and log-message variants dominate.

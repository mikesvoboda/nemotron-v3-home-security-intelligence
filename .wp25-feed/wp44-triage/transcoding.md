# WP4.4 Triage Dossier — backend/services/transcoding.py

- **Source**: `backend/services/transcoding.py` (validators L108-175, check_ffmpeg_available L237-272, get_video_info L274-350, transcode_to_mp4 L352-492, delete_transcoded_file L505-525)
- **Covering test file (sole)**: `backend/tests/unit/services/test_transcoding.py` — TestValidateInputPath L41, TestValidateOutputFilename L74, TestValidateQualityPreset L114, TestCheckFFmpegAvailable L196, TestGetVideoInfo L279, TestTranscodeToMp4 L450, TestUtilityMethods L757
- **Survivors**: **152** (folded from `mutants/backend/services/transcoding.py.meta` at end of triage; snapshot at start was 150 — two `_validate_input_path` keys flipped null→0 mid-run, included below as E9). Cluster counts sum to 152; partition verified programmatically (no overlaps, no uncovered survivor).
- **Diff method**: orig-vs-variant AST diff over `mutants/backend/services/transcoding.py` for all 152 keys (dedup'd, name-normalized), spot-verified against `uv run mutmut show <key>` on 3 keys — exact match. No tests were run; no repo files modified.
- **Root cause of the TEST-GAP mass**: every existing test mocks `subprocess.run` / `asyncio.to_thread` / `asyncio.create_subprocess_exec` and asserts only the **return value** (or partial membership like `"-c:a" in call_args`, test_transcoding.py L529-533). Nobody asserts **what was passed to the mock**, so every command-string, kwarg, and call-scope mutant survives. One `assert_called_once_with` per function kills ~70 keys.

## Cluster table (counts sum to 152)

| #   | Cluster                                                                                                                                                                                                                                                                                                                                                          | Func : source line                     | N   | Class      | Example keys                                                      |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | --- | ---------- | ----------------------------------------------------------------- |
| G1  | ffprobe argv list clobbered/removed (`cmd=None`, `"FFPROBE"`, `"-V"`, `"XXjsonXX"`, flag case/XX flips)                                                                                                                                                                                                                                                          | get_video_info L290-299                | 15  | TEST-GAP   | `gvi__4`, `gvi__5`, `gvi__14`                                     |
| G2  | Input-validation bypass — `_validate_input_path` call clobbered (`validated_path=None`) and path arg →`str(None)`; security validator result never used                                                                                                                                                                                                          | get_video_info L285, L298              | 2   | TEST-GAP   | `gvi__1`, `gvi__19`                                               |
| G3  | `asyncio.to_thread(subprocess.run, cmd, …)` call mutated (func→None, cmd→None, `capture_output=False/None/deleted`, `text=False/None/deleted`) — stdout contract broken                                                                                                                                                                                          | get_video_info L302-309                | 10  | TEST-GAP   | `gvi__21`, `gvi__22`, `gvi__33`                                   |
| G4  | `audio_stream` first-vs-last flip: `elif codec_type == "audio" and audio_stream is None` → `or` (last audio wins; subtitle can land in `audio_codec`)                                                                                                                                                                                                            | get_video_info L324                    | 1   | TEST-GAP   | `gvi__60`                                                         |
| G5  | Missing-`"format"`/`"duration"` defaults mutated (`{}→None` → swallowed AttributeError → `return None`; `0→None`/`0→1`)                                                                                                                                                                                                                                          | get_video_info L331, L334              | 5   | TEST-GAP   | `gvi__70`, `gvi__79`, `gvi__84`                                   |
| G6  | Availability probe argv clobbered/removed (`["ffmpeg","-version"]`→None, `"XXffmpegXX"`, `"FFMPEG"`, `"-VERSION"`)                                                                                                                                                                                                                                               | check_ffmpeg_available L248            | 6   | TEST-GAP   | `cff__3`, `cff__13`, `cff__16`                                    |
| G7  | transcode argv build clobbered (`"ffmpeg"` XX/case, `"-y"`, `"-i"`, input/output →`str(None)`, `"-movflags"`, `"+faststart"` case/None) — would transcode wrong file or none                                                                                                                                                                                     | transcode_to_mp4 L426-443              | 12  | TEST-GAP   | `tmp__47`, `tmp__53`, `tmp__65`                                   |
| G8  | subprocess plumbing (`stdout`/`stderr=PIPE` removed or →None; `wait_for(..., timeout=None)` disables the 1-hour cap)                                                                                                                                                                                                                                             | transcode_to_mp4 L450-458              | 5   | TEST-GAP   | `tmp__72`, `tmp__76`, `tmp__79`                                   |
| G9  | stderr→error-message extraction (ternary `and False`/`or True`, `split(None)`, `join(None)`, `[-5:]`→`[-6:]`/`[+5:]`, `>5`→`>=5`/`>6`, whole expr→None)                                                                                                                                                                                                          | transcode_to_mp4 L466-473              | 13  | TEST-GAP   | `tmp__86`, `tmp__99`, `tmp__102`                                  |
| G10 | NVENC opt-out: `get_video_encoder_args(use_hardware=True)` → `None`/`False` (hardware accel silently disabled for every transcode)                                                                                                                                                                                                                               | transcode_to_mp4 L423                  | 2   | TEST-GAP   | `tmp__44`, `tmp__45`                                              |
| L1  | Timeout constants (`5→None/6/deleted`, `30→None/31/deleted`) — hang-window only; killed incidentally by G1/G2/G6 call-arg asserts                                                                                                                                                                                                                                | check_ffmpeg L251, get_video_info L307 | 6   | LOW-VALUE  | `cff__6`, `cff__19`, `gvi__35`                                    |
| L2  | `capture_output`/`text` kwarg mutations in availability check — its stdout/stderr are never read, so return-value behavior is unchanged                                                                                                                                                                                                                          | check_ffmpeg_available L249-250        | 6   | LOW-VALUE  | `cff__4`, `cff__17`, `cff__18`                                    |
| L3  | `video_info = await self.get_video_info(…)` call removed / arg→None — result feeds **only** the pre-transcode log line                                                                                                                                                                                                                                           | transcode_to_mp4 L408                  | 2   | LOW-VALUE  | `tmp__22`, `tmp__23`                                              |
| E1  | check_ffmpeg_available log-message text (`logger.*(None)`, `XX…XX`, case flips)                                                                                                                                                                                                                                                                                  | L256-269                               | 17  | EQUIVALENT | `cff__24`, `cff__28`, `cff__32`                                   |
| E2  | get_video_info log-message text (`None` args on error/warning paths)                                                                                                                                                                                                                                                                                             | L287, L312, L328, L343-349             | 6   | EQUIVALENT | `gvi__3`, `gvi__67`, `gvi__110`                                   |
| E3  | transcode log text (video-info f-string dict-key flips, `logger.debug(None)`, join sep, MB-size `1024*1024` tweaks / message None) — log-only                                                                                                                                                                                                                    | L410-417, L445, L480-483               | 24  | EQUIVALENT | `tmp__24`, `tmp__35`, `tmp__108`                                  |
| E4  | exception **message text** (`"XXFFmpeg is not availableXX"`, `"Unknown error"` case flips, `"XXFFmpeg executable not foundXX"`) — `pytest.raises(match=…)` substrings still match                                                                                                                                                                                | L402-404, L467, L488                   | 5   | EQUIVALENT | `tmp__19`, `tmp__88`, `tmp__113`                                  |
| E5  | `check=` kwarg no-ops (`False→None`, `False` deleted, `check=True` → CalledProcessError caught by generic `except Exception` → same False/None outcome)                                                                                                                                                                                                          | check_ffmpeg L252, get_video_info L308 | 6   | EQUIVALENT | `cff__7`, `cff__20`, `gvi__36`                                    |
| E6  | `data.get("streams", [])` → default None/removed — every path still lands at `return None`                                                                                                                                                                                                                                                                       | get_video_info L320                    | 2   | EQUIVALENT | `gvi__45`, `gvi__47`                                              |
| E7  | delete_transcoded_file log-message args → None                                                                                                                                                                                                                                                                                                                   | L518, L521, L524                       | 3   | EQUIVALENT | `dtf__3`, `dtf__5`, `dtf__7`                                      |
| E8  | validator error-message text (`XX…XX` wraps; raises still raised, regex still matches)                                                                                                                                                                                                                                                                           | L147, L173                             | 2   | EQUIVALENT | `x__validate_output_filename__3`, `x__validate_quality_preset__6` |
| E9  | `_validate_input_path` dash-check arg clobbered (`startswith("XX-XX")` / `str(None)`) — **the check itself is dead on both platforms**: `Path.resolve()` returns an absolute path, so `str(path_obj)` can never start with `-`; the existing "dash prefix" test actually trips the not-found branch (its input never exists). Mutants change nothing observable. | L129                                   | 2   | EQUIVALENT | `x__validate_input_path__8`, `x__validate_input_path__9`          |

Key prefixes: `gvi` = `…xǁTranscodingServiceǁget_video_info`, `tmp` = `…transcode_to_mp4`, `cff` = `…check_ffmpeg_available`, `dtf` = `…delete_transcoded_file` (full key = `backend.services.transcoding.` + prefix + `__mutmut_N`).

**Totals**: TEST-GAP 71 (G1-G10), LOW-VALUE 14 (L1-L3), EQUIVALENT 67 (E1-E9). 71+14+67 = 152.

Notes: within G9, `tmp__96` (`or True`) and `tmp__101` (`>=5`) are _actually equivalent at every input_ (at len==5, `"\n".join(lines[-5:]) == error_msg`) — kept in-cluster, but drafted T4 deliberately cannot kill them.

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure per test: add to target file → run against mutant variant (assert fails on the mutant diff) → run against original `backend/services/transcoding.py` (passes green). Target file: `backend/tests/unit/services/test_transcoding.py`. New import needed at top: `import asyncio` (json/subprocess/MagicMock/patch/AsyncMock/pytest/TranscodingError/TranscodingService already imported there).

### T1 — `TestGetVideoInfo::test_ffprobe_command_is_executed_verbatim` (kills G1+G2+G3 = 27 keys, plus gvi L1 timeouts → ~30)

```python
    @pytest.mark.asyncio
    async def test_ffprobe_command_is_executed_verbatim(
        self, service: TranscodingService, tmp_path: Path, sample_ffprobe_output: dict
    ) -> None:
        """The ffprobe argv and subprocess kwargs are the contract — assert them."""
        video_path = tmp_path / "test.mkv"
        video_path.write_bytes(b"fake video")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(sample_ffprobe_output)

        with patch("asyncio.to_thread", return_value=mock_result, autospec=True) as mock_thread:
            info = await service.get_video_info(str(video_path))

        assert info is not None
        mock_thread.assert_called_once_with(
            subprocess.run,
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path.resolve()),  # validation ran: resolved path, not None
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
```

### T2 — `TestCheckFFmpegAvailable::test_availability_check_invokes_ffmpeg_version` (kills G6=6 + L1-cff=3 + L2=6 + E5-cff=3 → 18)

```python
    def test_availability_check_invokes_ffmpeg_version(self, tmp_path: Path) -> None:
        """Availability must probe exactly `ffmpeg -version` with capture + timeout."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result, autospec=True) as mock_run:
            service = TranscodingService(output_dir=str(tmp_path))
            assert service.check_ffmpeg_available() is True

        mock_run.assert_called_once_with(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
```

### T3 — `TestTranscodeToMp4::test_ffmpeg_argv_and_plumbing` (kills G7+G8+G10 = 19)

```python
    @pytest.mark.asyncio
    async def test_ffmpeg_argv_and_plumbing(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """argv must carry binary, -y/-i/input, encoder args, faststart, output;
        pipes and the caller timeout must be wired."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video content")
        output_path = service.output_dir / "output.mp4"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        captured: dict[str, object] = {}

        async def mock_wait_for(coro, timeout):
            captured["timeout"] = timeout
            return await coro

        with (
            patch(
                "backend.services.transcoding.get_video_encoder_args",
                return_value=["-c:v", "libx264"],
                autospec=True,
            ) as mock_encoder,
            patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
                autospec=True,
            ) as mock_exec,
            patch("asyncio.wait_for", side_effect=mock_wait_for, autospec=True),
            patch.object(service, "get_video_info", return_value=None, autospec=True),
        ):
            output_path.write_bytes(b"transcoded video")

            result = await service.transcode_to_mp4(
                input_path=str(input_path),
                output_filename="output.mp4",
                quality_preset="medium",
            )

        assert result == output_path
        mock_encoder.assert_called_once_with(use_hardware=True)
        argv = mock_exec.call_args[0]
        assert argv[0] == "ffmpeg"
        assert argv[1] == "-y"
        assert argv[2] == "-i"
        assert argv[3] == str(input_path.resolve())
        assert argv[argv.index("-movflags") + 1] == "+faststart"
        assert argv[-1] == str(output_path)
        assert mock_exec.call_args[1] == {
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        assert captured["timeout"] == 3600
```

### T4 — `TestTranscodeToMp4::test_failure_message_contains_tail_of_stderr` (kills 11 of G9's 13; `tmp__96`/`tmp__101` are true-equivalents and survive by design)

```python
    @pytest.mark.asyncio
    async def test_failure_message_contains_tail_of_stderr(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """On ffmpeg failure the error must quote the LAST 5 stderr lines — not more,
        not fewer, and never the 'Unknown error' fallback when stderr exists."""
        input_path = tmp_path / "input.mkv"
        input_path.write_bytes(b"fake video")

        async def mock_wait_for(coro, timeout):
            return await coro

        # 7 stderr lines -> expect lines 3..7 only
        stderr_text = "\n".join(f"err{i} detail{i}" for i in range(1, 8))
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", stderr_text.encode()))
        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process, autospec=True),
            patch("asyncio.wait_for", side_effect=mock_wait_for, autospec=True),
            patch.object(service, "get_video_info", return_value=None, autospec=True),
            pytest.raises(TranscodingError) as exc_info,
        ):
            await service.transcode_to_mp4(input_path=str(input_path))
        message = str(exc_info.value)
        assert message.endswith("\n".join(f"err{i} detail{i}" for i in range(3, 8)))
        assert "err1" not in message
        assert "err2" not in message

        # 6 stderr lines -> expect lines 2..6 (kills the >5 vs >6 boundary mutants)
        mock_process.communicate = AsyncMock(
            return_value=(b"", "\n".join(f"s{i}" for i in range(1, 7)).encode())
        )
        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process, autospec=True),
            patch("asyncio.wait_for", side_effect=mock_wait_for, autospec=True),
            patch.object(service, "get_video_info", return_value=None, autospec=True),
            pytest.raises(TranscodingError) as exc_info2,
        ):
            await service.transcode_to_mp4(input_path=str(input_path))
        assert str(exc_info2.value).endswith("s2\ns3\ns4\ns5\ns6")
        assert "s1\n" not in str(exc_info2.value)

        # empty stderr -> fallback message exactly "Unknown error"
        mock_process.communicate = AsyncMock(return_value=(b"", None))
        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process, autospec=True),
            patch("asyncio.wait_for", side_effect=mock_wait_for, autospec=True),
            patch.object(service, "get_video_info", return_value=None, autospec=True),
            pytest.raises(TranscodingError) as exc_info3,
        ):
            await service.transcode_to_mp4(input_path=str(input_path))
        assert "Unknown error" in str(exc_info3.value)
```

### T5 — `TestGetVideoInfo::test_first_audio_stream_wins` (kills G4 = 1)

```python
    @pytest.mark.asyncio
    async def test_first_audio_stream_wins(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """With multiple audio streams (and a subtitle stream), the FIRST audio stream
        must be reported — not the last, and never the subtitle."""
        video_path = tmp_path / "multi.mkv"
        video_path.write_bytes(b"fake video")
        ffprobe_output = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720},
                {"codec_type": "audio", "codec_name": "aac"},
                {"codec_type": "subtitle", "codec_name": "subrip"},
                {"codec_type": "audio", "codec_name": "mp3"},
            ],
            "format": {"duration": "10.0"},
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        with patch("asyncio.to_thread", return_value=mock_result, autospec=True):
            info = await service.get_video_info(str(video_path))
        assert info is not None
        assert info["audio_codec"] == "aac"
        assert info["has_audio"] is True
```

### T6 — `TestGetVideoInfo::test_missing_format_defaults_to_zero_duration` (kills G5 = 5)

```python
    @pytest.mark.asyncio
    async def test_missing_format_defaults_to_zero_duration(
        self, service: TranscodingService, tmp_path: Path
    ) -> None:
        """ffprobe output without a "format" section must still yield a dict with
        duration 0.0 — not None via a swallowed AttributeError."""
        video_path = tmp_path / "nofmt.mkv"
        video_path.write_bytes(b"fake video")
        ffprobe_output = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240},
            ],
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(ffprobe_output)
        with patch("asyncio.to_thread", return_value=mock_result, autospec=True):
            info = await service.get_video_info(str(video_path))
        assert info is not None
        assert info["duration"] == 0.0
        assert info["width"] == 320
```

**Kill estimate**: T1 ~30, T2 ~18, T3 ~19, T4 ~11, T5 1, T6 5 → ~84 keys, including all 71 TEST-GAP keys except `tmp__96`/`tmp__101` (true-equivalents inside G9) — no further tests needed. Remaining survivors become EQUIVALENT by construction.

**Side observation for WP4.4 (not a test gap, a product note)**: `_validate_input_path`'s dash check (L129) is unreachable after `resolve()` — the E9 pair documents it. If the check is meant to matter, it must run before `resolve()` or use `os.path.relpath`; until then, mutmut will keep breeding equivalent mutants there. Same class of dead code as `test_rejects_dash_prefix` (test_transcoding.py L54-57), which passes for the wrong reason (not-found, not dash).

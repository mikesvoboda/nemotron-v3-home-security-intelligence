# WP4.4 Triage Dossier — backend/api/routes/media.py (strict-census survivors)

Source meta: `mutants/backend/api/routes/media.py.meta` — 218 keys total, 177 killed (exit 1),
**41 survivors** (exit 0), 0 null. All diffs pulled via `uv run mutmut show <key>` (41/41, no failures).

Mutated functions: `_validate_and_resolve_path` (16), `_try_alternate_path` (4),
`serve_detection_image` (21). Helpers: `_is_path_within`, `_validate_and_resolve_path` are also
reached via `serve_camera_file` / `serve_thumbnail` / `serve_clip`.

Covering test files (from `mutants/mutmut-stats.json` tests_by_mangled_function_name):

| Concern | File | Key anchors |
|---|---|---|
| helper + endpoint unit tests (main) | `backend/tests/unit/api/routes/test_media.py` (885 ln) | `TestValidateAndResolvePath` :38, `TestIsPathWithin` :162, `TestTryAlternatePath` :188, `TestServeDetectionImage` :399, `TestServeMediaCompat` :701 |
| route-level + content-type tests (secondary) | `backend/tests/unit/routes/test_media_routes.py` (839 ln) | `TestValidateAndResolvePath` :66, `TestEdgeCasesAndSecurity` :601 (`test_handles_very_long_filename` :638 uses 200 chars — never near MAX_PATH_LENGTH=4096), `TestContentTypes` :726 |

No test anywhere exercises `/export/foscam/` or `/mnt/foscam/` through `_try_alternate_path`
(only factories/hypothesis fixtures use the prefix as data: `backend/tests/factories.py:110`,
`backend/tests/hypothesis_strategies.py:133`).

## Cluster table (counts sum to 41)

| # | Cluster | Count | Keys (≤3 shown) | Class |
|---|---|---|---|---|
| V1 | `len(path) > MAX_PATH_LENGTH` → `>=` (off-by-one at exactly 4096) | 1 | `x__validate_and_resolve_path__mutmut_1` | LOW-VALUE |
| V2 | Error-detail `path` truncation expression clobbered at 414-site and 400-site (slice 100→101, `>100`→`>=100`/`>101`, `+`→`-` "..." suffix → `"XX...XX"`, `or True`) | 9 | `..._mutmut_13`, `..._mutmut_48`, `..._mutmut_50` | TEST-GAP |
| V3 | 400-site truncation condition forced (`and False` / `or True`) | 2 | `..._mutmut_44`, `..._mutmut_45` | TEST-GAP |
| V4 | `_validate_and_resolve_path` error-message strings XX-clobbered (traversal / outside-base / not-found) | 3 | `..._mutmut_30`, `..._mutmut_60`, `..._mutmut_74` | TEST-GAP |
| T1 | Host prefix `"/export/foscam/"` broken in `_try_alternate_path` host_prefixes (XX-clobber + upper-case) | 2 | `x__try_alternate_path__mutmut_15`, `_16` | TEST-GAP |
| T2 | Host prefix `"/mnt/foscam/"` broken (XX-clobber + upper-case) | 2 | `x__try_alternate_path__mutmut_17`, `_18` | TEST-GAP |
| S1 | `serve_detection_image` error strings XX-clobbered (not-found / no-file / outside-dir / disk) | 4 | `x_serve_detection_image__mutmut_16`, `_29`, `_74` | TEST-GAP |
| S2 | `data_path` allowed-directory segments broken (`"data"`/`"cameras"` → XX or UPPER) — silently rewrites the security allowlist | 4 | `x_serve_detection_image__mutmut_39`, `_41`, `_42` | TEST-GAP |
| S3 | Detection lookup query clobbered (`execute(None)`, `select(None)`, `where(None)`, `==`→`!=`) — invisible under blanket AsyncMock | 4 | `x_serve_detection_image__mutmut_2`, `_4`, `_5` | TEST-GAP |
| S4 | Alternate-path call disabled / base clobbered (`alt_path = None`, `_try_alternate_path(file_path, None)`) | 2 | `x_serve_detection_image__mutmut_43`, `_45` | TEST-GAP |
| S5 | File-exists guard `or` → `and` (`not exists or not is_file` → `and`) — directory named `*.jpg` would be served | 2 | `x_serve_detection_image__mutmut_49`, `_77` | TEST-GAP |
| S6 | Response `media_type` dropped (`content_type = None` / `media_type=None` / arg removed) | 2 | `x_serve_detection_image__mutmut_102`, `_104` | EQUIVALENT |
| S7 | Response `filename` dropped (`filename=None` / arg removed) — kills Content-Disposition | 3 | `x_serve_detection_image__mutmut_105`, `_107`, `_108` | TEST-GAP |

16 + 4 + 21 = **41**.

## Cluster notes

- **V1 (LOW-VALUE).** Only observable for `len == MAX_PATH_LENGTH` exactly (tests use 4097 and 200).
  Pinning "4096 chars is OK" is not behavior worth asserting. Not drafted.
- **V2/V3 (TEST-GAP).** Line `backend/api/routes/media.py:62` (414 branch) and `:86` (400 resolve-error
  branch): both compute `requested_path[:100] + "..." if len(...) > 100 else requested_path`.
  Covering tests `test_media.py:51` (414) and `test_media.py:77-93` (400) use 4097-char and 9-char
  inputs and only substring-assert the `error` field — the `path` field is never inspected. Every
  V2/V3 mutant is killable with three length probes (100 → untruncated, 101 → first-100+"...",
  150 → first-100+"...") plus the 414 long-path case. Key `_mutmut_11` (`or True` at the 414 site) is
  equivalent-in-practice: a 414 is only raised when `len > 4096 > 100`, so the forced branch always
  matches the original. Note `mutmut_46`/`_52`-style `+`→`-` (`str - str`) crashes → trivially killed;
  `mutmut_108` is syntactically invalid → collected-error kill; census shows them killed, consistent.
- **V4/S1 (TEST-GAP, with a census tension worth flagging).** `test_media.py:67,117,128,455,478,545,607`
  already contain `"Path traversal detected" in str(exc_info.value.detail)`-style **substring** asserts,
  yet the XX-clobbers survived. `str({"error": "XXFile not foundXX", ...})` contains `"File not found"`,
  so the substring form tolerates the clobber exactly at the 404 site (`test_media.py:128`, and
  `test_media_routes.py:95-102` which asserts status only) — that fully explains `v..74` (S-404)
  surviving. For the remaining S1/V4 keys the covering-run selection apparently did not bind those
  asserts; treat as TEST-GAP: **the durable fix is `==` on `detail["error"]`, not `in` on `str(detail)`**.
  Draft D6 below pins all seven sites exactly. (Re-run these 7 keys in the WP4.4 verification lane.)
- **T1/T2 (TEST-GAP).** `media.py:156` `host_prefixes = ["/export/foscam/", "/mnt/foscam/"]`.
  `TestTryAlternatePath` (test_media.py:188-235) tests ONLY the seeded `/app/data/cameras/` prefix —
  the NEM-2662 host-path translation the docstring calls the function's reason to exist has zero unit
  coverage. Upper-case variants (`_16`, `_18`) additionally pass `str.startswith` case-sensitivity
  checks only if asserted. Draft D1.
- **S2 (TEST-GAP).** `media.py:397` `data_path = Path(__file__).parent.parent.parent.parent / "data" / "cameras"`.
  This is one of the two directories the 403 boundary check at `media.py:416` accepts. No test ever
  serves a detection whose file lives under `<repo>/backend/data/cameras/`, so renaming the accepted
  segments is undetected. Exploitable in the benign direction (legit seeded detections 403) and in the
  dangerous direction if a real `backend/data/DATA`-style tree existed. `data_path` is computed from
  the module global `__file__` at call time → testable by patching `__file__` or shaping tmp_path
  (`tmp/backend/api/routes` → `tmp/backend/data/cameras`). Draft D3.
- **S3 (TEST-GAP).** `media.py:371` `select(Detection).where(Detection.id == detection_id)`. All 9
  `TestServeDetectionImage` tests stub `db.execute` to return whatever they want — the SQL is never
  examined. `!=` (`_5`) means "serve the wrong detection's image", a real correctness/security change.
  Killable by compiling the captured statement: `str(mock_db.execute.await_args.args[0].compile())`.
  Draft D4. (Caveat for implementer: no `aiosqlite` in the venv — assert on compiled SQL text, do not
  try a real async in-memory DB.)
- **S4 (TEST-GAP).** `media.py:402` alternate-path call site. Survives only because no
  `serve_detection_image` test uses a host-prefixed `file_path` — while `tests/factories.py:110`
  generates exactly that shape (`/export/foscam/{camera_id}/image_XXXX.jpg`), i.e. this is the shape
  seeded detections carry in production. Draft D2 (serve-level) kills `_43` (alt disabled → falls to
  relative branch → nonexistent join → 404 instead of FileResponse) and `_45` (`None` base →
  TypeError inside `_try_alternate_path`).
- **S5 (TEST-GAP).** `media.py:426` `if not full_path.exists() or not full_path.is_file():`.
  `or`→`and` (`_49`, `_77`) is observable on exactly one input shape: an **existing directory whose
  name has an allowed extension** (`snapshot.jpg/`). Original: 404 "File not found on disk". Mutant:
  falls through the type check (`.jpg` allowed) and returns a FileResponse over a directory. Existing
  `test_serve_detection_image_file_not_on_disk_returns_404` uses a missing file, where both operators
  agree. Draft D5.
- **S6 (EQUIVALENT).** starlette 1.6.0 `FileResponse.__init__`: `if media_type is None:
  media_type = guess_type(filename or path)[0] or "application/octet-stream"` (verified against the
  venv source). For every allowed extension `mimetypes.guess_type` (default strict=True) returns the
  exact `ALLOWED_TYPES` value — `.webm`→`video/webm`, `.avi`→`video/x-msvideo` all match (verified
  locally). So `content_type=None` / `media_type=None` is byte-identical output; removing the kwarg
  (`mutmut_106`, already killed per census — consistent: starlette default arg removal is a signature
  break… it survived elsewhere; census shows killed here, fine). No test can distinguish on allowed
  extensions; do not chase.
- **S7 (TEST-GAP).** `media.py:448-452`. Dropping `filename=full_path.name` changes
  `FileResponse.filename` to None and drops the `Content-Disposition: attachment; filename="..."`
  header (starlette gates it on `self.filename is not None`); the media_type fallback then guesses
  from `path`, which coincidentally still matches — so only the filename/header asserts kill it. No
  test reads `result.filename` or `result.headers` anywhere in either file. `mutmut_108` (syntactically
  broken) is a free kill once the module is importable-red. Draft D5-bis folded into D5's class as
  D4/D5 naming below.

## Drafted tests

Style follows `backend/tests/unit/api/routes/test_media.py` (direct-call handlers, `AsyncMock` db,
`MagicMock(spec=Detection)`, `patch("backend.api.routes.media.get_settings", autospec=True)`).
Add to the class named under each. **TDD procedure for every test below: run against the mutant
copy → the pinned assert FAILS (or the mutant crashes); run against `backend/api/routes/media.py`
original → PASSES.** All code is `// UNVERIFIED - not yet run red/green` (read-only triage lane).

### D1 — `TestTryAlternatePath::test_host_prefix_translation_both_variants_case_sensitive` (kills T1+T2)

```python
    def test_host_prefix_translation_both_variants_case_sensitive(self, tmp_path: Path) -> None:
        """NEM-2662: both host prefixes translate; variants (XX-clobber / upper-case) must NOT match.

        // UNVERIFIED - not yet run red/green
        """
        alt_file = tmp_path / "front_door" / "image.jpg"
        alt_file.parent.mkdir(parents=True)
        alt_file.write_text("test")

        for prefix in ("/export/foscam/", "/mnt/foscam/"):
            result = _try_alternate_path(f"{prefix}front_door/image.jpg", tmp_path)
            assert result == alt_file.resolve(), f"{prefix} must be a recognized host prefix"

        # startswith() is case-sensitive: upper-cased prefixes (mutants) must return None,
        # and the original must too (the listed prefixes are lower-case).
        assert _try_alternate_path("/EXPORT/FOSCAM/front_door/image.jpg", tmp_path) is None
        assert _try_alternate_path("/MNT/FOSCAM/front_door/image.jpg", tmp_path) is None
```

### D2 — `TestServeDetectionImage::test_serve_detection_image_host_path_end_to_end` (kills S4, re-kills T1/T2 end-to-end)

```python
    @pytest.mark.asyncio
    async def test_serve_detection_image_host_path_end_to_end(self, tmp_path: Path) -> None:
        """Detections seeded with host paths (/export/foscam/...) serve from container base (NEM-2662).

        // UNVERIFIED - not yet run red/green
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        # factory-shaped host path (tests/factories.py:110)
        mock_detection.file_path = "/export/foscam/front_door/image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file.resolve())
```

### D3 — `TestServeDetectionImage::test_serve_detection_image_data_cameras_directory_is_allowed` (kills S2)

```python
    @pytest.mark.asyncio
    async def test_serve_detection_image_data_cameras_directory_is_allowed(self, tmp_path: Path) -> None:
        """backend/data/cameras is the second allowlisted root of the 403 boundary check.

        data_path = Path(media.__file__).parents[3] / "data" / "cameras" is computed at call
        time, so we pin the module __file__ and shape tmp_path to match the same layout:
        tmp/backend/api/routes/media.py  +  tmp/backend/data/cameras/seeded.jpg
        Any segment clobber (data->DATA/XXdataXX, cameras->CAMERAS/XXcamerasXX) makes the
        boundary check reject -> 403 instead of serving.

        // UNVERIFIED - not yet run red/green
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        routes_dir = tmp_path / "backend" / "api" / "routes"
        routes_dir.mkdir(parents=True)
        (routes_dir / "media.py").write_text("")  # anchors Path(__file__)

        data_cameras = tmp_path / "backend" / "data" / "cameras"
        data_cameras.mkdir(parents=True)
        test_file = data_cameras / "seeded.jpg"
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = str(test_file)  # absolute: within data_path, NOT foscam base

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        foscam_base = tmp_path / "foscam"
        foscam_base.mkdir()

        with (
            patch("backend.api.routes.media.__file__", str(routes_dir / "media.py")),
            patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings,
        ):
            mock_settings.return_value.foscam_base_path = str(foscam_base)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.path == str(test_file.resolve())
```

### D4 — `TestServeDetectionImage::test_serve_detection_image_query_filters_on_detection_id` (kills S3)

```python
    @pytest.mark.asyncio
    async def test_serve_detection_image_query_filters_on_detection_id(self, tmp_path: Path) -> None:
        """The lookup must actually filter on Detection.id — a stubbed AsyncMock otherwise hides
        execute(None)/select(None)/where(None)/!= (wrong detection's image gets served).

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 7
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            await serve_detection_image(detection_id=7, db=mock_db)

        assert mock_db.execute.await_count == 1
        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt.compile())  # 'detections.id = :id_1'; != mutant -> 'detections.id != :id_1'
        assert "detections.id = " in sql
        assert "!=" not in sql
```

### D5 — `TestServeDetectionImage` pair: directory-named-image 404 + response metadata (kills S5, S7)

```python
    @pytest.mark.asyncio
    async def test_serve_detection_image_directory_named_like_image_returns_404(
        self, tmp_path: Path
    ) -> None:
        """exists-or-isfile guard must stay `or`: a DIRECTORY named snapshot.jpg is not a file -> 404.
        (with `or`→`and` the guard passes and the .jpg suffix sails through to a FileResponse.)

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.media import serve_detection_image

        fake_dir = tmp_path / "front_door" / "snapshot.jpg"
        fake_dir.mkdir(parents=True)

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "snapshot.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            with pytest.raises(HTTPException) as exc_info:
                await serve_detection_image(detection_id=1, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "File not found on disk" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_serve_detection_image_response_preserves_filename_and_disposition(
        self, tmp_path: Path
    ) -> None:
        """FileResponse must carry filename=full_path.name -> Content-Disposition header.
        filename=None mutants drop the header (media_type then re-guesses and looks fine —
        only the filename/header asserts kill them).

        // UNVERIFIED - not yet run red/green
        """
        from fastapi.responses import FileResponse

        from backend.api.routes.media import serve_detection_image

        test_file = tmp_path / "front_door" / "image.jpg"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("detection image")

        mock_db = AsyncMock()
        mock_detection = MagicMock(spec=Detection)
        mock_detection.id = 1
        mock_detection.camera_id = "front_door"
        mock_detection.file_path = "image.jpg"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_detection
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            result = await serve_detection_image(detection_id=1, db=mock_db)

        assert isinstance(result, FileResponse)
        assert result.filename == "image.jpg"
        assert result.media_type == "image/jpeg"
        assert 'filename="image.jpg"' in result.headers["content-disposition"]
```

### D6 — `TestValidateAndResolvePath` truncation trio + exact error strings (kills V2 except `_11`, V3, V4, V4/S1 exact-string family)

```python
    def test_error_detail_path_truncation_boundary(self, tmp_path: Path) -> None:
        """The [:100] + '...' truncation expression is pinned at both sites (414 branch, 400 branch):
        len<=100 -> verbatim, len 101 -> first 100 chars + '...', long -> same;
        never XX...XX / [:101] / >101 / 'and False' untruncated.

        // UNVERIFIED - not yet run red/green
        """
        # 414 site: only reachable with len > MAX_PATH_LENGTH, so pin truncation only.
        long_path = "b" * (MAX_PATH_LENGTH + 900)
        with pytest.raises(HTTPException) as exc_info:
            _validate_and_resolve_path(tmp_path, long_path)
        assert exc_info.value.status_code == 414
        assert exc_info.value.detail["path"] == "b" * 100 + "..."

        # 400 site (resolve() raises): three boundary lengths.
        with patch.object(Path, "resolve", side_effect=ValueError("boom"), autospec=True):
            # exactly 100 chars -> NOT truncated (kills >=100 mutants)
            with pytest.raises(HTTPException) as exc_info_100:
                _validate_and_resolve_path(tmp_path, "d" * 96 + ".jpg")
            # 101 chars -> truncated to first 100 chars + '...' (kills >101 and [:101])
            with pytest.raises(HTTPException) as exc_info_101:
                _validate_and_resolve_path(tmp_path, "d" * 97 + ".jpg")
            # 150 chars -> truncated (kills 'and False' untruncation and 'XX...XX' suffix)
            with pytest.raises(HTTPException) as exc_info_150:
                _validate_and_resolve_path(tmp_path, "c" * 150)

        assert exc_info_100.value.status_code == 400
        assert exc_info_100.value.detail["path"] == "d" * 96 + ".jpg"
        assert exc_info_101.value.status_code == 400
        assert exc_info_101.value.detail["path"] == "d" * 97 + ".jp" + "..."
        assert exc_info_150.value.status_code == 400
        assert exc_info_150.value.detail["path"] == "c" * 100 + "..."

    def test_error_detail_error_field_exact_strings(self, tmp_path: Path) -> None:
        """detail['error'] must EQUAL the message (==, not `in str(detail)`): XX-clobbered
        messages survive substring asserts because str(dict) still contains the inner text.

        // UNVERIFIED - not yet run red/green
        """
        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "../etc/passwd")
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "Path traversal detected"

        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "nonexistent.jpg")
        assert exc.value.status_code == 404
        assert exc.value.detail["error"] == "File not found"

        # outside-base (same symlink setup as test_path_outside_base_returns_403, :95-120):
        other_dir = tmp_path.parent / "other_exact"
        other_dir.mkdir(exist_ok=True)
        escape_target = other_dir / "t.jpg"
        escape_target.write_text("t")
        symlink = tmp_path / "escape_exact.jpg"
        try:
            symlink.symlink_to(escape_target)
        except OSError:
            pytest.skip("Symlinks not supported on this filesystem")
        with pytest.raises(HTTPException) as exc:
            _validate_and_resolve_path(tmp_path, "escape_exact.jpg")
        assert exc.value.status_code == 403
        assert exc.value.detail["error"] == "Access denied - path outside allowed directory"

    @pytest.mark.asyncio
    async def test_serve_detection_image_error_fields_exact(self, tmp_path: Path) -> None:
        """All four serve_detection_image error sites pinned with == on detail['error'].

        // UNVERIFIED - not yet run red/green
        """
        from backend.api.routes.media import serve_detection_image

        def mock_db_for(detection: object | None) -> AsyncMock:
            db = AsyncMock()
            result = MagicMock()
            result.scalar_one_or_none.return_value = detection
            db.execute.return_value = result
            return db

        with patch("backend.api.routes.media.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = str(tmp_path)

            # 1) not found
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=999, db=mock_db_for(None))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "Detection not found"

            # 2) no file path
            det = MagicMock(spec=Detection)
            det.id, det.camera_id, det.file_path = 1, "front_door", None
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "Detection has no associated file"

            # 3) outside allowed directory
            outside = tmp_path.parent / "outside_exact"
            outside.mkdir(exist_ok=True)
            (outside / "x.jpg").write_text("x")
            det2 = MagicMock(spec=Detection)
            det2.id, det2.camera_id, det2.file_path = 1, "front_door", str(outside / "x.jpg")
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det2))
            assert exc.value.status_code == 403
            assert exc.value.detail["error"] == "Access denied - file outside allowed directory"

            # 4) file not on disk
            det3 = MagicMock(spec=Detection)
            det3.id, det3.camera_id, det3.file_path = 1, "front_door", "missing.jpg"
            with pytest.raises(HTTPException) as exc:
                await serve_detection_image(detection_id=1, db=mock_db_for(det3))
            assert exc.value.status_code == 404
            assert exc.value.detail["error"] == "File not found on disk"
```

## Kill map (drafted vs remaining)

| Cluster | Draft kills | Post-draft status |
|---|---|---|
| V1 | — | stays survivor (LOW-VALUE, deliberate) |
| V2 | D6 (8 of 9) | `_mutmut_11` remains — equivalent-in-practice (414 ⇒ len>4096>100) |
| V3 | D6 | cleared |
| V4 | D6 | cleared |
| T1, T2 | D1 (+D2 end-to-end) | cleared |
| S1 | D6 (after re-run confirms binding) | cleared pending verify run |
| S2 | D3 | cleared |
| S3 | D4 | cleared |
| S4 | D2 | cleared |
| S5 | D5a | cleared |
| S6 | — | stays survivor (EQUIVALENT: starlette guess_type fallback identical for all ALLOWED_TYPES) |
| S7 | D5b | cleared |

Verification order for the serial pytest lane: apply drafts → `uv run pytest backend/tests/unit/api/routes/test_media.py -p no:randomly` green on original → strict census re-run of media.py
expects survivors_total to drop from 41 to ≤ 3 (V1, V2-`_11`, S6 pair minus 108-style noise).

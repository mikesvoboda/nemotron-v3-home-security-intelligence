# WP4.4 kill record — backend/api/routes/media.py

**Baseline:** 218 mutants, 177 killed by the pre-existing unit suite, 41 survivors.
**Batch:** `TestWp44MediaGaps` (9 tests) appended to
`backend/tests/unit/api/routes/test_media.py`.
**Strict census v1: 32/41. Residual audit found one killable TEST-GAP
(serve_4 `select(None)`); added a SELECT-list pin, green-proved, re-censused.**
**Strict census v2 (drafted tests only, 41/41 keys, 0 no-verdicts): 33 killed / 41 probed.**
Module total after batch: **210/218 = 96.3% killed**.

## Killed (33)

| Dossier cluster | Keys | Killing test |
|---|---|---|
| T1+T2 — host prefixes XX-clobbered/upper-cased in `_try_alternate_path` | `try_alternate_path 15,16,17,18` | test_host_prefix_translation_both_variants_case_sensitive (both /export/foscam/ and /mnt/foscam/ resolve; upper-case → None) |
| V2+V3 — truncation ternary at 414- and 400-sites (slice 100→101, thresholds, `+`→`-` suffix, forced condition) | `_validate_and_resolve_path 13,14,44,45,46,47,48,49,50` (11 of the V2/V3 13; `_11` + the `_15/_16` twins remain) | test_error_detail_path_truncation_boundary (resolve→ValueError: len 100 verbatim, 101 → first-100+"...", 150 truncated; 414 site len-414 pinned `"b"*100+"..."`) |
| V4+S1 — error strings XX-clobbered (substring `in` tolerated them) | `_validate_and_resolve_path 30,60,74` + `serve 16,29,74,88` | test_error_detail_error_field_exact_strings — exact-`==` on `detail["error"]` across 4 sites |
| S2 — `data_path` allowlist segments broken (`"data"`/`"cameras"` XX/UPPER) | `serve 39,40,41,42` | test_serve_detection_image_data_cameras_directory_is_allowed (`patch media.__file__` 4-parent hop; 4 parents from tmp_path/x/api/routes land on tmp_path — dossier's layout was wrong, corrected) |
| S3 — detection lookup clobbered (execute/where/`==`, select(None)) | `serve 2,3,4,5` (4 via v2) | test_serve_detection_image_query_filters_on_detection_id — WHERE pin + `NULL AS`/`detections.file_path` SELECT-list pin (select(None) keeps WHERE but renders `SELECT NULL AS anon_1`) |
| S4 — alternate call disabled / base clobbered | `serve 43,45` | test_serve_detection_image_host_path_end_to_end (mock detection file_path="/export/foscam/…", foscam_base=tmp_path → FileResponse.path) |
| S5 — file-exists guard or→and (directory named *.jpg) | `serve 77` (the `_49` twin is EQUIVALENT — see below) | test_serve_detection_image_directory_named_like_image_returns_404 |
| S7 — filename/Content-Disposition dropped | `serve 105,108` (`_107` diff is media_type, not filename) | test_serve_detection_image_response_preserves_filename_and_disposition (result.filename, disposition header) |

## Remaining survivors (8 — all classified)

| Key | Diff-verified semantics | Class |
|---|---|---|
| `_validate_and_resolve_path 1` | `len > 4096` → `>=`: observable only at len==4096 exactly | LOW-VALUE (dossier V1, deliberate) |
| `_validate_and_resolve_path 11,15,16` | 414-site ternary forced/relaxed (`or True`, `>=100`, `>101`): a 414 requires len > 4096 > 101, so every reachable input truncates identically | EQUIVALENT-in-practice (dossier note on `_11` extended to the twins) |
| `serve_detection_image 49` | `if Path(file_path).is_absolute()` → `… and False`: pathlib join with an absolute right operand yields the absolute path anyway — both branches resolve identically | EQUIVALENT (diff-verified; dossier S5 example-list mis-attribution corrected) |
| `serve_detection_image 102,104,107` | `media_type` dropped from FileResponse: starlette `guess_type` fallback reproduces the same content type for every ALLOWED_TYPES extension | EQUIVALENT (dossier S6; `_107` diff shows the media_type removal, not filename) |

**Module closed: 210 killed + 8 classified = 218 = mutants_total.**

**Census note:** v1 (32/41) archived at `/tmp/wp25/wp44-kills/pre-media-s4/`;
the only v1→v2 delta is the SELECT-list pin in the query-filters test, which
killed exactly `serve_4`.

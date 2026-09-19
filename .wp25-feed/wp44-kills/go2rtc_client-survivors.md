# WP4.4 kill record — backend/services/go2rtc_client.py

**Baseline:** 101 mutants, 61 killed by the pre-existing unit suite, 40 survivors.
**Batch:** 6 module-level tests appended to
`backend/tests/unit/services/test_go2rtc_client.py`.
**Strict census v1: 29/40. Found one killable gap (whitelist test exercised
500/200/204 but not 404); added the 404 no-warn case, green-proved, re-censused.**
**Strict census v2 (drafted tests only, 40/40 keys, 0 no-verdicts): 30 killed / 40 probed.**
Module total after batch: **91/101 = 90.1% killed**.

## Killed (30 — dossier TEST-GAP clusters C1–C4, C12–C16 + LOW-VALUE incidental re-kills)

| Dossier cluster | Keys | Killing test |
|---|---|---|
| C1 — `__init__` URL normalization clobbers (rstrip/lstrip variants) | `__init__ 1–8` | test_strips_trailing_slash_from_configured_urls (`"http://h/testX/"` → attrs; `"…/testX/"` decisive) |
| C2+C16 — request URL/timeout → None on health/register/unregister | `health_check 2`, `register_stream 12,23,25,28`, `unregister_stream 3,5` | test_requests_use_configured_urls_and_timeout (autospec `args[1]` == configured endpoints, `kwargs["timeout"]==2.0`) |
| C3 — response-map fallbacks never executed (stream-id + webrtc_url template) | `register_stream 37,39,45,47` | test_register_stream_falls_back_to_generated_stream_id (`json={}` → prefix + 12-hex suffix + exact webrtc_url) |
| C4 — acceptable-status whitelist (not-in→in, 200→201, 204→205, **404→405**) | `unregister_stream 6,7,8,9` | test_unregister_stream_warning_log_matches_status_whitelist (500 warns naming stream; 200/204/**404** silent) |
| C12 — credential gate `and`→`or` | `register_stream 5` | test_register_stream_credential_matrix_sends_exact_source (single credential → raw rtsp_url, no `admin:None@`) |
| C13 — `urlparse(None)` source clobber | `register_stream 7` | same (exact `source_url` equality — substring asserts tolerate `b''` fields) |
| C14+C15 — validation space regex / host check | `_validate_rtsp_url 5,11` | test_register_stream_rejects_malformed_rtsp_urls (embedded space → "spaces"; `rtsp://:554/stream1` → "host"; post not called) |
| C9/C10 incidental — token_hex / suffix→None | `register_stream 9,10,11` | fallback test's 12-hex suffix regex |

## Remaining survivors (10 — all dossier-classified)

- C5 LOW-VALUE (2): `unregister_stream 11,12` — ConnectError-warning logger args
  → None (diagnostics lose stream id; the HTTP-error branch's stream-id assert
  doesn't reach this branch).
- C8 LOW-VALUE (2): `register_stream 14,15` — debug-log arg fidelity.
- C6+C7 EQUIVALENT (4): `unregister_stream 16,17`, `register_stream 19,20` —
  pure log message text (XX-wrap / lowercase).
- C11 EQUIVALENT (2): `register_stream 29,30` — POST payload key casing
  (`"name"`→`"XXnameXX"`/`"NAME"`); wire contract not asserted by policy
  (baseline rule: payload key casing tweaks).

**Module closed: 91 killed + 10 classified = 101 = mutants_total.**

**Census note:** v1→v2 delta is exactly `unregister_stream__9` (404→405 flip),
v1 archived at `/tmp/wp25/wp44-kills/pre-g2r404/`.

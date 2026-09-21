import json

groups = json.load(open("/tmp/wp25/groups_named.json"))
PFX = "backend.services.enrichment_client."

CLS = {
    "C1 parse-default-branch": "TEST-GAP",
    "C2 parse-clobber-key-arg": "TEST-GAP",
    "C3 parse-expr-to-none": "TEST-GAP",
    "C4 msg-text": "TEST-GAP",
    "C5 ctxstring-default": "LOW-VALUE",
    "C6 unified-to_dict": "TEST-GAP",
    "C7 join-separator": "LOW-VALUE",
    "C8 http-call-args": "TEST-GAP",
    "C9 cast-inert": "EQUIVALENT",
    "C10 log-arg": "LOW-VALUE",
    "C11 breaker-fallback": "TEST-GAP",
    "C12 retry-500-boundary": "TEST-GAP",
    "C13 action-0.7-boundary": "TEST-GAP",
    "C14 status-error-msg": "TEST-GAP",
    "C15 dead-guard-equiv": "EQUIVALENT",
}
DESC = {
    "C1 parse-default-branch": "`_parse_unified_response`: the DEFAULT branch of `X.get(key, default)` flipped across pose/clothing/demographics/vehicle/threat sub-dicts and top-level `inference_time_ms` (src lines 3059-3107): `0.0`->`None`/`1.0`/omitted, `\"unknown\"`->`None`/`\"UNKNOWN\"`/`\"XXunknownXX\"`, `False`->`None`/`True`, `[]`->`None`/omitted, `\"none\"`->`None`/`\"NONE\"`. Fires only when a *present* sub-dict omits that key; every existing parse test (`test_parse_full_response`, `test_parse_partial_response`, `test_enrich_detection_*` in backend/tests/unit/services/test_enrichment_client.py:2952-3046, :2597+) supplies every key, so the default branch never fires with a missing key.",
    "C2 parse-clobber-key-arg": "`_parse_unified_response`: the LOOKUP KEY of `.get(...)` clobbered - `\"age_confidence\"`->`None`/`0.0`/`\"XXage_confidenceXX\"`/`\"AGE_CONFIDENCE\"`, same pattern for keypoints/pose_class/confidence/is_suspicious/categories/gender(_confidence)/color/type/threats/has_threat/max_severity (src 3059-3107). Lookup misses the real key and silently falls back to the default. A single partial-sub-dict parse test asserting every defaulted field equals its default value kills the whole cluster at once (a missing key reads as absent from the mangled key too, returning the same default - so only the FULL-sub-dict-with-asserted-defaults shape separates them; see drafted test 1 which asserts defaults AND full-payload field values).",
    "C3 parse-expr-to-none": "`_parse_unified_response`: whole field expression replaced with `None` (`keypoints=None`, pose `confidence=None`, `categories=None`, `age_confidence=None`, `gender_confidence=None`, `color=None`, vehicle `confidence=None`, `threats=None`, `max_severity=None`) - `X.get(k, d)` call removed entirely. Fires whenever that sub-dict is present in the payload, even fully populated.",
    "C4 msg-text": "`to_context_string` ALERT/tag literals clobbered across ClothingClassificationResult (189-204), PoseAnalysisResult (677-699), UnifiedPoseResult (399-404), UnifiedClothingResult (434-435), VehicleClassificationResult (98-107): XX-padding `\"  [ALERT: ...]\"`->`\"XX  [ALERT: ...]XX\"` or CAPS swap `\"Potentially suspicious\"`->`\"POTENTIALLY SUSPICIOUS\"`. Covering tests assert only `\"ALERT\" in context`, `\"suspicious\" in context.lower()`, `\"Service/delivery worker\" in context`, `\"Commercial/delivery vehicle\" in context` - all substrings that survive XX-padding (which merely extends the line) and the case variants (`.lower()` comparison; case-insensitive substrings).",
    "C5 ctxstring-default": "`UnifiedClothingResult.to_context_string` (src 430-436) and `UnifiedThreatResult.to_context_string` (src 538-540): fallback defaults inside `top.get(\"category\", \"unknown\")`, `top.get(\"confidence\", 0)` and `t.get(\"type\", \"unknown\")` clobbered to None/omitted/CAPS/XX-padding. Only observable when a category/threat dict omits the key; every fixture (`{\"category\": \"casual\", \"confidence\": 0.85}`, `{\"type\": \"knife\", ...}`) populates both keys, so the defaults are dead code under the current tests.",
    "C6 unified-to_dict": "`UnifiedEnrichmentResult.to_dict` (src 585-609): field-name string literals in the `convertible_fields` list (`\"vehicle\"`->`\"VEHICLE\"`/`\"XXvehicleXX\"`) and `direct_fields` list (`\"pet\"`/`\"action\"`/`\"depth\"`-> XX/CAPS variants) clobbered, plus `result[field_name] = field_value.to_dict()`->`= None`. The existing `test_to_dict` (test_enrichment_client.py:2508-2518) asserts membership only for pose/clothing/demographics/threat/reid_embedding and never supplies pet/action/depth - so `\"XXvehicleXX\"` in place of `\"vehicle\"` (pose fixture keeps its own assert green) and the `= None` swap for a field whose membership is checked (`result[\"vehicle\"] is None`) both pass. NOTE: it does assert `\"threat\" in result`, which is why the threat-name mutants were killed; the same membership assert on vehicle/pet/action/depth kills this cluster.",
    "C7 join-separator": "`\"\\n\".join(lines)`->`\"XX\\nXX\".join(lines)` in 6 multi-line context builders (ActionClassificationResult src 332, ClothingClassificationResult 203, PoseAnalysisResult 699, UnifiedClothingResult 436, UnifiedPoseResult 404, UnifiedEnrichmentResult 637) plus `' '.join(parts)`->`'XX XX'.join` (UnifiedVehicleResult 510) and `', '.join(threat_types)`->`'XX, XX'.join` (UnifiedThreatResult 540). These DO change multi-line output, but every covering test uses substring asserts (`\"standing\" in context`, `\"red\" in context`, `\"knife\" in context`, `\"ALERT\" in context`) that survive any separator mangling; and several instances are exercised with single-element joins where the mutation is a literal no-op. A format-strict test (assert `\\n` in multi-section output) is cheap and kills the multi-line members.",
    "C8 http-call-args": "`get_model_status` (src 3256-3258) and `preload_model` (src 3287-3289): request URL arg mutated to `None` or the whole kwarg dropped, and `headers=self._get_headers()`->`headers=None`/dropped. The NEM-3147 W3C Trace Context header propagation on these two endpoints is therefore untested. `test_preload_model_success` checks `\"models/preload\" in call_args.args[0]` and params, but never headers; `test_get_model_status_success` never inspects the call at all (mutmut_4/5 - URL and headers args *removed* - survive because a kwargs-only call still returns the mocked 200).",
    "C9 cast-inert": "`cast(\"dict[str, Any]\", response.json())` type-string clobbered to `\"XXdict[str, Any]XX\"`, `\"dict[str, any]\"`, `\"DICT[STR, ANY]\"` (string literals, never evaluated) and `cast(None, ...)` (src 3260). `typing.cast` returns its first-position value argument unchanged at runtime - zero behavioral difference; only a type checker would notice.",
    "C10 log-arg": "`logger.warning(f\"Failed to get model status: {e}\")`, `logger.info(f\"Successfully preloaded model: {model_name}\")` and two warning siblings replaced with `logger.warning(None)`/`logger.info(None)` (src 3266, 3291, 3294, 3297). Real change to log content, but no test in the enrichment test files asserts log output (zero `caplog` usage in backend/tests/unit/services/test_enrichment_client*.py). Cosmetic observability; nobody should assert on it here.",
    "C11 breaker-fallback": "`is_circuit_open` (src 1020) and `reset_circuit_breaker` (src 1034): `self._breakers.get(endpoint, self._breakers[\"enrich\"])` default dropped (`None`/omitted) -> returns `breaker=None` -> `AttributeError: 'NoneType' has no attribute 'get_state'/'reset'` for ANY endpoint string not in the 10-key breakers dict, including `endpoint=None` passed positionally through the non-None branch guard? No - None short-circuits; the gap is unknown-endpoint names (typos, future models) which are supposed to fall back to the shared enrich breaker. Existing tests pass only \"vehicle\"/\"pose\" or None (test_enrichment_client.py:1913-1930, test_enrichment_client_circuit_breaker.py:428-465).",
    "C12 retry-500-boundary": "`_is_retryable_error` (src 1082): `status_code >= 500`->`> 500` and `>= 500`->`>= 501`. HTTP 500 flips retryable->non-retryable. Retry tests use 503 (`test_is_retryable_error_5xx`) and 400 (4xx test); no test calls the helper with 500. Caution for the fix-author: the classify_* retry loops inline their own `< 500` checks (e.g. src 1240) and do NOT call this helper, so the behavioral blast radius today is limited to helper callers elsewhere/future use - but the helper IS the documented retry policy contract, so a boundary unit assert is the right kill.",
    "C13 action-0.7-boundary": "`ActionClassificationResult.has_security_alerts` (src 340): `risk_weight >= 0.7`->`> 0.7`. A risk weight of exactly 0.7 stops alerting. Tests use 0.75/True, 0.5/False, 0.2/False - never the 0.7 boundary.",
    "C14 status-error-msg": "`get_model_status` ConnectError/Timeout except branch (src 3270): `\"error\": str(e)`->`\"error\": str(None)` - the error dict now carries the literal string `\"None\"` instead of the exception message. `test_get_model_status_connection_error` asserts only `\"error\" in result` (key presence), never content.",
    "C15 dead-guard-equiv": "`UnifiedClothingResult.to_context_string` (src 430): `self.categories[0] if self.categories else {}`->`self.categories[0] if (self.categories) or True else {}`. `x or True` is always truthy, which WOULD index an empty list - except the line is unreachable with empty categories: the preceding guard `if not self.categories: return \"Clothing: No classification available\"` already returned. Semantically identical on every reachable path.",
}

def short(k):
    v = k[len(PFX):]
    p = v.split("ǁ")
    return f"{p[1]}.{p[2]}"

rows = []
for g in sorted(groups, key=lambda x: int(x.split()[0][1:])):
    ks = sorted(groups[g])
    rows.append({
        "cluster": g,
        "count": len(ks),
        "classification": CLS[g],
        "examples": [short(k) for k in ks[:3]],
        "note": DESC[g],
        "members": [short(k) for k in ks],
    })
total = sum(r["count"] for r in rows)
assert total == 158, total
json.dump(rows, open("/tmp/wp25/rows.json", "w"), indent=1)
for r in rows:
    print(f"{r['count']:3d} {r['classification']:10s} {r['cluster']}")
print("TOTAL", total)

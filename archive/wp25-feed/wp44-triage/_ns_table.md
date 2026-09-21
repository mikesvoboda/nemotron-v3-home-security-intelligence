| id | cluster (pattern @ concern) | N | class | example keys |
|----|------------------------------|---|-------|--------------|
| A1 | logger extra= dict clobbers/deletions (3 warning blocks) | 21 | EQUIVALENT | …__mutmut_134,140,141 |
| A2 | logger message text clobbers/None (warning/info msgs) | 14 | EQUIVALENT | …__mutmut_133,137,138 |
| A3 | parse-fallback dict key renames (values still via .get defaults) | 4 | EQUIVALENT | …__mutmut_289,290,292 |
| A4 | final complete-event or-fallback tweaks (unreachable branch) | 9 | EQUIVALENT | …__mutmut_432,434,435 |
| A5 | retryable LLM recoverable=True DELETED (schema default True) | 3 | EQUIVALENT | …__mutmut_260,267,279 |
| A6 | logger.error exc_info=True -> False/None/deleted | 4 | LOW-VALUE | …__mutmut_269,270,272 |
| A7 | Prometheus metrics args/labels/duration sign | 12 | LOW-VALUE | …__mutmut_248,249,252 |
| A8 | error_message user-facing text clobbers | 4 | LOW-VALUE | …__mutmut_8,280,281 |
| A9 | fatal-error recoverable=False flipped/deleted (default True) | 10 | TEST-GAP | …__mutmut_11,50,65 |
| A10 | retryable LLM recoverable True->False | 3 | TEST-GAP | …__mutmut_261,268,283 |
| A11 | idempotency-hit complete-event fallbacks (or->and/51/casing) | 12 | TEST-GAP | …__mutmut_27,28,29 |
| A12 | idempotency/broadcast collaborator args ->None/deleted | 7 | TEST-GAP | …__mutmut_13,16,404 |
| A13 | camera lookup select/where/scalar + name fallback | 7 | TEST-GAP | …__mutmut_69,70,71 |
| A14 | batch_fetch_detections/_format_detections args ->None | 4 | TEST-GAP | …__mutmut_87,88,104 |
| A15 | enrichment fetch call args (_get_enriched_context/_get_enrichment_result) | 14 | TEST-GAP | …__mutmut_107,108,109 |
| A16 | context-fetch internals (scene-changes/tuning args) | 11 | TEST-GAP | …__mutmut_128,129,130 |
| A17 | context seed values ''->None/'XXXX' + enrichment_result seed | 7 | TEST-GAP | …__mutmut_122,126,127 |
| A18 | detections_for_household dicts: key clobbers/list->None/bbox filter flip/args | 29 | TEST-GAP | …__mutmut_167,168,169 |
| A19 | detection_dicts build: key/default clobbers, confidence filter flip, list->None | 9 | TEST-GAP | …__mutmut_208,209,210 |
| A20 | kwargs piped into call_llm_streaming at call site | 13 | TEST-GAP | …__mutmut_220,221,222 |
| A21 | accumulated_text init/+=/kwarg + parse-input arg | 4 | TEST-GAP | …__mutmut_218,242,247 |
| A22 | Event row construction kwargs + risk_data.get defaults | 29 | TEST-GAP | …__mutmut_307,308,309 |
| A23 | event_detections junction INSERT stmt/values/on_conflict | 11 | TEST-GAP | …__mutmut_362,363,364 |
| A24 | LLMInteraction record + observability builders | 29 | TEST-GAP | …__mutmut_375,376,377 |
| A25 | detections json.loads else-[] corner | 1 | TEST-GAP | …__mutmut_56 |
| L1 | _build_prompt kwargs ->None(8)/deleted(8) context contract | 16 | TEST-GAP | …call_llm_streaming__mutmut_6,7,8 |
| L2 | sanitize_camera_name/sanitize_detection_description(None) | 2 | TEST-GAP | …call_llm_streaming__mutmut_2,4 |
| L3 | prompt = None / _validate_and_truncate_prompt(None) | 2 | TEST-GAP | …call_llm_streaming__mutmut_26,27 |
| L4 | payload dict->None + wire key renames/UPPER (prompt/temp/top_p/max_tokens/stop/stream) | 13 | TEST-GAP | …call_llm_streaming__mutmut_29,30,31 |
| L5 | payload value tweaks: temp 0.3->1.3, top_p .95->1.95, stream True->False, stop tokens | 7 | TEST-GAP | …call_llm_streaming__mutmut_34,37,42 |
| L6 | Content-Type header key/value case+clobber | 5 | LOW-VALUE | …call_llm_streaming__mutmut_50,51,52 |
| L7 | httpx request construction: timeout=None, stream(method/url/json/headers ->None/deleted/case) | 11 | TEST-GAP | …call_llm_streaming__mutmut_57,58,59 |
| L8 | break->[DONE] loop-end -> return (identical at generator end) | 1 | EQUIVALENT | …call_llm_streaming__mutmut_78 |
| L9 | data.get('content') default ''->None/deleted (both falsy) | 2 | EQUIVALENT | …call_llm_streaming__mutmut_83,85 |
| L10 | data.get('content', 'XXXX'): missing-content SSE yields 'XXXX' | 1 | TEST-GAP | …call_llm_streaming__mutmut_88 |
| L11 | malformed-SSE log message None / truncation 100->101 | 2 | LOW-VALUE | …call_llm_streaming__mutmut_89,90 |

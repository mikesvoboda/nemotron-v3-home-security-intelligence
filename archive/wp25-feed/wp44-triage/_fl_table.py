import json, re, collections
d = json.load(open("/tmp/wp25/wp44-triage/_fl_diffs.json")); res = d["res"]
cl = json.load(open("/tmp/wp25/wp44-triage/_fl_clusters_final.json"))
sp = json.load(open("/tmp/wp25/wp44-triage/_fl_splits.json"))

def short(k):
    core = k.split("florence_client.",1)[1][1:]
    return core.replace("ǁ","::").replace("__mutmut_","#")

TABLE = {}
def add(name, keys, cls, note):
    TABLE[name] = {"count": len(keys), "classification": cls, "examples": [short(k) for k in keys[:3]], "note": note}

# split ERR 56 -> raise-arg removed vs None
def sig(k):
    return "\n".join(res[k]["diff"])
err_none = [k for k in cl["ERR_original_error"] if "original_error=None" in sig(k)]
err_drop = [k for k in cl["ERR_original_error"] if k not in err_none]

# split CBK: keep as one
# CBQ: 3 original + 2 _get_breaker fallback-defaults

gb2 = []
cb_key = [k for k in sp["cb_key"] if k not in gb2]
cbq = cl["CBQ_breaker_lookup"]

# split LOG_call: arg None/removed vs text swap
def is_none(k):
    dl = sig(k)
    plus = [l for l in dl.splitlines() if l.startswith("+") and not l.startswith("+++")]
    return any(re.match(r'^\+\s*(logger\.\w+\()?(None)?\)?\s*,?\s*$', l) or l.strip() in ("+","+(", "+None", "+None)", "+logger.debug(None)", "+logger.info(None)", "+logger.warning(None)", "+logger.error(None)") for l in plus) or any("None)" in l and "XX" not in l for l in plus)
lg_none = [k for k in cl["LOG_call"] if is_none(k)]
lg_txt = [k for k in cl["LOG_call"] if k not in lg_none]

add("MET-pipeline_error-label wrong on non-extract endpoints", cl["MET_pipeline_error_label"], "TEST-GAP",
    "record_pipeline_error('<label>') string mutated to None/XX-labelXX/UPPER on ocr, ocr_with_regions, detect, dense_caption, describe_regions, phrase_grounding, detect_security_objects, batch_extract and _check_circuit_breaker. TestMetricsRecording (test_florence_client.py:1107-1236) asserts labels for EXTRACT paths only; per-endpoint labels never asserted.")
add("PAY payload/encoder clobber (all endpoints)", cl["PAY_payload"], "TEST-GAP",
    "payload dict -> None, key 'image'/'prompt'/'regions'/'phrases'/'items' -> XX..XX/UPPER or removed, image_b64 -> None, encode arg -> None. HTTP Request Verification tests (test_florence_client.py:1240-1330) check payload only for extract/ocr/detect/ocr_with_regions/dense_caption/describe_regions/phrase_grounding basic keys; batch_extract + detect_security_objects payloads NEVER asserted; value correctness (decodable base64, as_dict regions) never asserted -> XXkeyXX/UPPER survive everywhere.")
add("ERR raise-site original_error kwarg removed", err_drop, "TEST-GAP",
    "raise FlorenceUnavailableError(msg, original_error=e) -> original_error arg deleted. Tests assert message text only, never .original_error / __cause__ on client-raised errors (the 4 direct-construction tests at :181-210 do not exercise raise sites).")
add("ERR original_error=e -> None", err_none, "LOW-VALUE",
    ".original_error becomes None; message text still interpolates {e}. Real but a field nobody's client-side code reads; would be killed by the same drafted cause-assertion as above.")
add("DUR duration_ms arithmetic clobbered (log-feed only)", sp["dur_log"], "LOW-VALUE",
    "duration_ms = int((time.time()-start)*1000) -> None / /1000 / +start / *1001. value feeds only logger.debug + logger.error extra={} — no metric, no return.")
add("DUR ai_duration clobbered (observe_ai_request_duration feed)", sp["dur_metric"], "TEST-GAP",
    "ai_duration = time.time() - ai_start_time mutated per endpoint (9 methods); value is the observation passed to observe_ai_request_duration. extract's test asserts isinstance(args[1], float) (:1111-1126) which survives /1000 and None; other endpoints never assert the duration arg.")
add("CBINIT breakers-dict endpoint KEY mutated", cb_key, "TEST-GAP",
    "_breakers dict key 'ocr_with_regions'/'dense_caption'/'describe_region'/'phrase_grounding'/'detect_security_objects'/'batch_extract' -> XX..XX/UPPER: that endpoint silently falls back to the extract breaker, breaking isolation. Isolation test (:1416) exercises only extract/ocr/detect.")
add("CBINIT breakers share _cb_config kwarg removed", sp["cb_cfg"], "TEST-GAP",
    "CircuitBreaker(name=..., config=_cb_config) -> config=None/absent -> breaker uses builtin defaults (threshold 5/30s/3 instead of settings 10/60s/3). Only the _circuit_breaker (extract) alias config is asserted (:1469-1474).")
add("CBINIT breaker name= mutated", sp["cb_name"], "LOW-VALUE",
    "CircuitBreaker name -> None/XX/UPPER; name only labels Prometheus circuit-breaker gauges + one init log line.")
add("CBK breaker-endpoint arg mutated at call sites", cl["CBK_breaker_endpoint_args"], "TEST-GAP",
    "_check_circuit_breaker('<ep>')/_get_breaker('<ep>') -> None/XX/UPPER inside every endpoint method, plus _check_circuit_breaker default endpoint. Wrong arg routes success/failure recording to the extract breaker: endpoint never opens its own breaker and is tripped by unrelated failures. Isolation test covers extract/ocr/detect only.")
add("CBQ breaker-state lookup mutations", cbq, "TEST-GAP",
    "get_circuit_breaker_state endpoint-is-None flip (named endpoint returns worst-state) and _get_breakers fallback default -> None/removed (AttributeError for unknown endpoints). No test asserts state for a named endpoint or unknown-endpoint fallback.")
add("HDR correlation headers dropped on POST/GET", cl["HDR_headers_dropped"], "TEST-GAP",
    "headers=self._get_headers() -> None/absent on check_health GET and every endpoint POST. W3C trace-context (NEM-3147) silently lost; no test asserts the headers value is passed (only presence of the 'headers' key for health :1314-1329).")
add("CFG httpx.Timeout/Limits clobbered in __init__", cl["CFG_httpx"], "TEST-GAP",
    "connect/read/write/pool= settings.* -> None (client silently unbounded/default httpx timeout), timeout=self._timeout removed, Limits max/keepalive mutated. test_init_timeout_configuration asserts only `is not None` (:265-270); test_http_connection_pooling checks limits for a different construction path.")
add("CFG circuit-breaker settings defaults mutated", cl["CFG_cb_defaults"], "TEST-GAP",
    "getattr(settings,'florence_cb_*',10/60.0/3) default+obj mutated; only bites when settings lacks the attr. test_circuit_breaker_uses_config_settings asserts the alias via fixture-provided values, never the defaults.")
add("MET florence_task label/task_type derivation", cl["MET_task_type"], "TEST-GAP",
    "record_florence_task('<ep>') labels on non-extract endpoints mutated + extract's prompt->task_type strip/split/startswith/"'"extract"'" fallback mutated. record_florence_task NEVER asserted anywhere; task_type wrong for non-< prompts.")
add("MET observe_ai_request_duration service label", cl["MET_observe_label"], "TEST-GAP",
    "observe_ai_request_duration('florence_dense_caption'|'florence_ocr_regions'|'florence_describe_region'|'florence_phrase_grounding',...) -> None/XX/UPPER. Tests assert args[0] for florence/florence_ocr/florence_detect only (:1111-1158).")
add("PARSE response field defaults mutated (describe_regions)", cl["PARSE_response_fields"], "TEST-GAP",
    "CaptionedRegion(caption=d.get('caption',''), bbox=d.get('bbox',[])) defaults/keys -> None/''-swap/UPPER: missing-key rows become caption=None/bbox=None. Existing 'missing fields' tests cover ocr_with_regions/detect/dense_caption only (test_florence_client.py:751,887,1021).")
add("ST 5xx boundary >=500 flipped on 3 endpoints", cl["ST_status_branch"], "TEST-GAP",
    "if status_code >= 500 -> >500 / >=501 in ocr_with_regions, dense_caption, phrase_grounding: a 500 response is treated as client error (returns [] instead of raising + breaker failure). 5xx tests for those 3 use 502/503 only; extract has the dedicated 500 case (:448).")
add("URL endpoint path arg mutated for batch/security post", cl["URL_endpoint_arg"], "TEST-GAP",
    "post URL f'{base}/batch-extract' / f'{base}/detect_security_objects' -> None/removed: request goes nowhere. No test calls batch_extract or detect_security_objects against the mock client at all (batch only exercised via test_vision_extractor).")
add("URL base_url init rstrip/gateway-default tweaks", cl["URL_base_url"], "EQUIVALENT",
    "rstrip('/')->rstrip('XX/XX') strips same-or-more from real URLs (no trailing X); getattr 'use_ai_gateway' default False->None/True is dead (Settings always defines the field). Gateway tests keep passing.")
add("LOG logger call argument -> None/removed", lg_none, "EQUIVALENT",
    "logger.debug/warning/info/error(msg) arg -> None or call body deleted: log text only; return values and control flow untouched.")
add("LOG logger message text swaps (XX/UPPER/lower)", lg_txt, "EQUIVALENT",
    "pure message-string rewrites on logger.* calls.")
add("LOGEXC exc_info kwarg mutated", cl["LOGEXC_exc_info"], "LOW-VALUE",
    "exc_info=True->None/False/removed on error logs: traceback capture in logs only; nobody asserts logging internals.")
add("LOGEXC extra={} log metadata mutated", cl["LOGEXC_extra"], "LOW-VALUE",
    "extra={'duration_ms':...,'status_code':...} -> None/removed/key-mutated on logger.error calls in extract's error paths: diagnostic metadata only.")
add("MSG raise/log message text mutated", cl["MSG_raise_text"], "LOW-VALUE",
    "f-string messages (raise messages and remaining log args) -> None/removed/arg-swaps. pytest.raises match= strings still hold for the paths they cover ('circuit breaker is open' survives via regex match; full-text identity never asserted).")
add("ENC base64/mode-membership mutated", sp["enc_mode"], "TEST-GAP",
    "'LA'/'P' -> 'la'/'p'/'XXLAXX' in mode-conversion membership (PIL modes are case-sensitive: LA/P input then crashes in JPEG save) + decode('utf-8')->'UTF-8' (equivalent). Encode tests cover RGB/RGBA/L only (:305-323).")
add("ENC jpeg format/quality cosmetic", sp["enc_qual"], "LOW-VALUE",
    "format='JPEG'->'jpeg' (case-insensitive), quality=85->86/removed (default 75): different bytes, same valid JPEG.")
add("NOOP no-op content variants", cl["NOOP"], "EQUIVALENT",
    "_check_circuit_breaker signature-line variants with identical content (docstring/formatting-only under mutmut).")

tot = sum(v["count"] for v in TABLE.values())
print("cluster sum:", tot)
assert tot == 629, tot
json.dump(TABLE, open("/tmp/wp25/wp44-triage/_fl_table_final.json","w"), indent=1)
for name, v in sorted(TABLE.items(), key=lambda x: -x[1]["count"]):
    print(f"{v['count']:4d} {v['classification']:10s} {name}")

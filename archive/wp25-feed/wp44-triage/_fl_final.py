import json, re, collections
d = json.load(open("/tmp/wp25/wp44-triage/_fl_diffs.json")); res = d["res"]

def content(diff):
    out=[]
    for l in diff:
        if l.startswith("@@"): continue
        t=l[1:].strip()
        if re.match(r'^(async )?def x',t) or t=="=>": continue
        out.append((l[0],t))
    return out

def fn_of(k):
    core = k.split("florence_client.",1)[1][1:]
    return core.split("ǁ")[-1]

C = collections.defaultdict(list)
for k,v in res.items():
    cs = content(v["diff"])
    M = " ~ ".join(t for s,t in cs if s=="-")
    P = " ~ ".join(t for s,t in cs if s=="+")
    both = M + " || " + P
    fn = fn_of(k)

    if not M and not P:
        C["NOOP"].append(k); continue
    # headers kwarg on http calls
    if "headers=self._get_headers" in M:
        C["HDR_headers_dropped"].append(k); continue
    # raise-site original_error wiring
    if "original_error" in both:
        C["ERR_original_error"].append(k); continue
    # circuit breaker call-site endpoint args
    if "_check_circuit_breaker(" in both or "_get_breaker(" in both:
        C["CBK_breaker_endpoint_args"].append(k); continue
    # breaker-internal helpers
    if fn.startswith("_check_circuit_breaker"):
        C["CBK_breaker_endpoint_args"].append(k); continue
    if fn == "_get_breaker" or fn == "get_circuit_breaker_state":
        C["CBQ_breaker_lookup"].append(k); continue
    # metrics
    if "record_pipeline_error(" in both:
        C["MET_pipeline_error_label"].append(k); continue
    if "record_florence_task(" in both or "task_type" in both or "prompt.startswith" in both:
        C["MET_task_type"].append(k); continue
    if "observe_ai_request_duration(" in both:
        C["MET_observe_label"].append(k); continue
    # duration math
    if re.search(r'duration_ms = int|ai_duration = time', both) or ("start_time = " in both):
        C["DUR_duration_math"].append(k); continue
    # logger kwargs
    if "exc_info=" in both:
        C["LOGEXC_exc_info"].append(k); continue
    if "extra=" in both:
        C["LOGEXC_extra"].append(k); continue
    # response parsing
    if re.search(r'\.get\(', both) and ("CaptionedRegion(" in both or "Detection(" in both or "OCRRegion(" in both or "GroundedPhrase(" in both or "objects_queried" in both or "BatchExtractResult(" in both):
        C["PARSE_response_fields"].append(k); continue
    # payload / url argument / image encoding call
    if re.search(r'"(image|regions|prompt|phrases|items)"', both) or "payload" in both:
        C["PAY_payload"].append(k); continue
    if "image_b64 = self._encode_image_to_base64" in both:
        C["PAY_payload"].append(k); continue
    # http url arg for posts/gets
    if re.search(r'/batch-extract|/detect_security_objects|/describe-region|/phrase-grounding|/extract|/ocr|/detect|/dense-caption|/health', both):
        C["URL_endpoint_arg"].append(k); continue
    # breaker dict init
    if "CircuitBreaker(" in both or "config=_cb_config" in both:
        # key mutation (dict key changed) vs name mutation vs config mutation
        if re.search(r'^\s*"', M) or re.search(r'"[a-z_]+": CircuitBreaker', both) and 'name=' in M and "name=" in P and re.search(r'\bCircuitBreaker\(name=', M) and re.search(r'\bCircuitBreaker\(name=', P):
            pass
        # classify by what changed: dict key = the part before the colon at line start
        changed_key = False; changed_name = False; changed_cfg = False
        for s,t in cs:
            mm = re.match(r'^"([A-Za-z_]+)":', t)
            mm0 = re.match(r'^"([A-Za-z_]+)":', M if s=="-" else "")
        C["CBINIT_dict_entry"].append(k); continue
    if "_circuit_breaker = self._breakers" in both or "self._breakers" in both:
        C["CBINIT_dict_entry"].append(k); continue
    # breaker config from settings getattr defaults
    if "florence_cb_" in both:
        C["CFG_cb_defaults"].append(k); continue
    # httpx config
    if re.search(r'\b(connect|read|write|pool)=', both) or "httpx.Limits" in both or "max_connections" in both or "httpx.Timeout" in both or "httpx.AsyncClient" in both or "timeout=self._" in both:
        C["CFG_httpx"].append(k); continue
    # status branches
    if "status_code >" in both or "status_code in" in both:
        C["ST_status_branch"].append(k); continue
    # encode internals
    if "image.mode in" in both or "convert(" in both or "image.save" in both or "b64encode" in both:
        C["ENC_encode"].append(k); continue
    # base url init
    if "rstrip(" in both or "gw_url" in both or "use_ai_gateway" in both or "florence_url" in both or "_base_url =" in both:
        C["URL_base_url"].append(k); continue
    # logger
    if "logger." in both:
        C["LOG_call"].append(k); continue
    # raise message args
    C["MSG_raise_text"].append(k); continue

tot=0
for c,keys in sorted(C.items(), key=lambda x:-len(x[1])):
    tot+=len(keys)
    print(f"{len(keys):4d} {c}")
print("TOTAL", tot)
json.dump({c:sorted(ks) for c,ks in C.items()}, open("/tmp/wp25/wp44-triage/_fl_clusters_final.json","w"), indent=1)

import json, re, collections
d = json.load(open("/tmp/wp25/wp44-triage/_fl_diffs.json"))
res = d["res"]

def content(diff):
    out = []
    for l in diff:
        if l.startswith("@@"): continue
        t = l[1:].strip()
        if re.match(r'^(async )?def x', t) or t == "=>": continue
        out.append((l[0], t))
    return out

def fn_of(k):
    core = k.split("florence_client.", 1)[1]
    core = core[1:]  # drop leading x
    return core.split("ǁ")[-1]

cluster = collections.defaultdict(list)
for k, v in res.items():
    cs = content(v["diff"])
    M = " ~ ".join(t for s, t in cs if s == "-")
    P = " ~ ".join(t for s, t in cs if s == "+")
    both = M + " || " + P
    fn = fn_of(k)

    def has(s): return s in both

    if "headers=self._get_headers" in both and ("headers=None" in P or not any(t.startswith("headers") for s, t in cs if s == "+")):
        cluster["HDR_headers_dropped"].append(k); continue
    if has("original_error"):
        cluster["ERR_original_error"].append(k); continue
    if "_check_circuit_breaker(" in both or "_get_breaker(" in both:
        cluster["CBK_breaker_endpoint_args"].append(k); continue
    if "record_pipeline_error(" in both:
        cluster["MET_pipeline_error_label"].append(k); continue
    if "record_florence_task(" in both or "task_type" in both:
        cluster["MET_task_type"].append(k); continue
    if "observe_ai_request_duration(" in both:
        cluster["MET_observe_label"].append(k); continue
    if re.search(r'duration_ms = int|ai_duration = time|start_time = time\.time', both):
        cluster["DUR_duration_math"].append(k); continue
    if "exc_info=" in both:
        cluster["LOGEXC_exc_info"].append(k); continue
    if "extra=" in both:
        cluster["LOGEXC_extra"].append(k); continue
    if has("payload") or '"image"' in both or '"regions"' in both or '"prompt"' in both or '"phrases"' in both or '"items"' in both:
        cluster["PAY_payload"].append(k); continue
    if "image_b64 = self._encode_image_to_base64" in both:
        cluster["PAY_payload"].append(k); continue
    if "CircuitBreaker(" in both or "_cb_config" in both or "_circuit_breaker = self._breakers" in both:
        cluster["CBINIT_breakers_dict"].append(k); continue
    if "httpx.Timeout" in both or re.search(r'\b(connect|read|write|pool)=', both) or "httpx.Limits" in both or "max_connections" in both:
        cluster["CFG_httpx"].append(k); continue
    if "httpx.AsyncClient" in both or "timeout=self._" in both:
        cluster["CFG_httpx"].append(k); continue
    if "status_code >=" in both or "status_code >" in both or "status_code in" in both:
        cluster["ST_status_branch"].append(k); continue
    if "image.mode in" in both or "convert(" in both or "image.save" in both or "b64encode" in both or ".decode(" in both:
        cluster["ENC_encode"].append(k); continue
    if "get_circuit_breaker_state" in both or "_breakers.get(endpoint" in both or "if endpoint is" in both:
        cluster["CBQ_breaker_lookup"].append(k); continue
    if "rstrip(" in both or "gw_url" in both or "use_ai_gateway" in both or "florence_url" in both or "_base_url" in both:
        cluster["URL_base_url"].append(k); continue
    if "logger." in both:
        if re.search(r'\bNone\b', P) or P.strip() == "" or (not re.search(r'[\'"]', P)):
            cluster["LOG_arg_removed"].append(k)
        else:
            cluster["LOG_text"].append(k)
        continue
    if "FlorenceUnavailableError(" in both:
        cluster["MSG_raise_text"].append(k); continue
    if "response = await" in both or "response = None" in P:
        cluster["RESP_response_none"].append(k); continue
    cluster["MISC"].append(k)

tot = 0
for c, keys in sorted(cluster.items(), key=lambda x: -len(x[1])):
    tot += len(keys)
    fns = collections.Counter(fn_of(k) for k in keys)
    print(f"{len(keys):4d} {c:28s} | " + ", ".join(f"{f}:{n}" for f, n in fns.most_common(10)))
    print("      e.g.", keys[:3])
print("TOTAL", tot)
json.dump({c: sorted(ks) for c, ks in cluster.items()}, open("/tmp/wp25/wp44-triage/_fl_clusters.json", "w"), indent=1)

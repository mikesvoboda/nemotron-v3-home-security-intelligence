import json, re, difflib, collections

REPO = "/agents/agent-nemo2/workspace"
lines = open(REPO + "/mutants/backend/services/florence_client.py").read().splitlines()
def_re = re.compile(r"^    (?:async )?def xǁFlorenceClientǁ(\w+)__mutmut_(orig|\d+)\(")
spans = []
for i, ln in enumerate(lines):
    m = def_re.match(ln)
    if m: spans.append((i, m.group(1), m.group(2)))
blocks = {}
for i, func, num in spans:
    end = len(lines)
    for j in range(i+1, len(lines)):
        if def_re.match(lines[j]) or re.match(r"^    (?:@|def |async def |class )", lines[j]):
            end = j; break
    blocks[(func,num)] = lines[i:end]

def norm(b):
    return ["    async def METHOD(" if re.match(r"^    (?:async )?def xǁFlorenceClientǁ", ln) else ln for ln in b]

with open(REPO + "/mutants/backend/services/florence_client.py.meta") as f:
    ebk = json.load(f)["exit_code_by_key"]
survivors = collections.defaultdict(set)
for k,v in ebk.items():
    if v==0:
        m=re.match(r"backend\.services\.florence_client\.xǁFlorenceClientǁ(\w+)__mutmut_(\d+)$",k)
        if m: survivors[m.group(1)].add(int(m.group(2)))

def qstrip(s):  # replace string contents with placeholder
    return re.sub(r'"[^"]*"','"S"',s)
def fstrip(s):  # placeholder for any string incl f-strings: crude - collapse quoted regions & interpolation
    s = re.sub(r'f"[^"]*"','F',s)
    s = re.sub(r'"[^"]*"','S',s)
    return s

def classify(func, hunks, orig, mut):
    """Return cluster name. hunks: list of (a1,a2,b1,b2)."""
    # gather full -/+ text
    O = "\n".join(" ".join(x.strip() for x in orig[a1:a2]) for a1,a2,b1,b2 in hunks).strip()
    M = "\n".join(" ".join(x.strip() for x in mut[b1:b2]) for a1,a2,b1,b2 in hunks).strip()
    Os, Ms = qstrip(O), qstrip(M)
    # per-hunk views
    (a1,a2,b1,b2) = hunks[0]
    o0 = orig[a1:a2]; m0 = mut[b1:b2]
    o0j = " ".join(x.strip() for x in o0)
    m0j = " ".join(x.strip() for x in m0)

    # breaker line regions
    if "_check_circuit_breaker" in o0j or "_get_breaker" in o0j:
        if "None" in m0j and "_get_breaker" in o0j and "_get_breaker(" in m0j:
            return "A3 wrong-breaker-on-open-circuit (endpoint arg -> None)"
        if "breaker = None" in m0j or m0j == "breaker = None":
            return "A4 breaker handle clobbered to None"
        if "None" in m0j:
            return "A1 wrong-breaker-on-open-circuit (endpoint arg -> None)"
        return "A2 wrong-breaker-on-open-circuit (endpoint name string mutated)"
    if "record_pipeline_error" in o0j and "record_pipeline_error" in m0j:
        if "None" in m0j: return "C2 record_pipeline_error(None)"
        return "C1 record_pipeline_error label string mutated"
    if "record_florence_task" in o0j:
        return "C4 record_florence_task label/None mutated"
    if "observe_ai_request_duration" in o0j:
        return "C3 observe_ai_request_duration label/None mutated"
    if "logger." in o0j:
        return "B1 logger call argument clobbered (text-only)"
    if "duration_ms = int" in o0j or "ai_duration = time.time()" in o0j or "start_time = time.time()" in o0j:
        return "B3 duration arithmetic mutated (feeds debug log/metric value only)"
    if "original_error" in o0j:
        return "A7 error-chain metadata dropped (original_error=None / kwarg removed)"
    if "status_code >=" in o0j or "status_code >" in m0j or "status_code >" in o0j:
        return "A8 HTTP 500 boundary flip in 5xx-vs-4xx branch"
    if "headers=self._get_headers" in o0j:
        return "A9 correlation/tracing headers dropped"
    if "json=payload" in o0j:
        return "A10 request body (json payload) dropped"
    if "_encode_image_to_base64" in o0j:
        return "A11 request construction removed (encode/payload/post -> None)"
    if "response = await self._http_client.post" in o0j or "response = None" in m0j:
        return "A11 request construction removed (encode/payload/post -> None)"
    if "payload = None" in m0j:
        return "A11 request construction removed (encode/payload/post -> None)"
    if "payload = {" in o0j or '"image"' in o0j or '"regions"' in o0j or '"phrases"' in o0j:
        return "A5 HTTP payload key string mutated"
    if "self._base_url}" in o0j:
        return "A12 HTTP URL string arg clobbered/removed"
    if ".get(" in o0j and (".get(" in m0j or "None" in m0j):
        return "A6 response-parsing .get() key/default mutated"
    if "FlorenceUnavailableError" in O or "sanitize_error" in o0j or ("f\"" in o0j and "raise" in O):
        return "B2 exception message text clobbered"
    if Os == Ms:
        return "B9 misc string-constant text-only change"
    return f"Z UNCLASSIFIED [{func}]: -{o0j[:80]} +{m0j[:80]}"

out = collections.defaultdict(list)
for func in sorted(survivors):
    orig = norm(blocks[(func,"orig")])
    for n in sorted(survivors[func]):
        mut = norm(blocks[(func,str(n))])
        sm = difflib.SequenceMatcher(None, orig, mut, autojunk=False)
        hunks = [(a1,a2,b1,b2) for tag,a1,a2,b1,b2 in sm.get_opcodes() if tag!="equal"]
        cname = classify(func, hunks, orig, mut)
        out[cname].append(f"{func}__mutmut_{n}")

total = 0
for c in sorted(out):
    total += len(out[c])
    print(f"{c}  ::  n={len(out[c])}")
    print("    " + ", ".join(k.replace("ǁ",".") for k in out[c]))
print("TOTAL", total)
json.dump(out, open("/tmp/wp25/wp44-triage/_florence-clusters.json","w"), indent=1)

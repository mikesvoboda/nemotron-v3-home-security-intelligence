import json, re, collections

d = json.load(open("/tmp/wp25/wp44-triage/_clip_diffs.json"))
SEP = "ǁ"

EMBED_METHODS = {"embed"}
CASE_ONLY = re.compile(r"^[\s\"']*(XX.*?XX.*|\S*)[\s\"',)]*$")

def case_or_xx_only(old_s, new_s):
    """new equals old modulo case and XX-annotation of string text."""
    a = re.sub(r"XX", "", old_s).strip().lower()
    b = re.sub(r"XX", "", new_s).strip().lower()
    return a == b and old_s != new_s


def classify(v):
    chs = v["changes"]
    fn = v["fn"]
    old = " ;; ".join(c["old"] for c in chs)
    new = " ;; ".join(c["new"] for c in chs)
    if not chs or all(c["old"] == "" and c["new"] == "" for c in chs):
        return "C01-NOOP-IDENTICAL"
    if "rstrip(" in old and "XX/XX" in new:
        return "C02-RSTRIP-CHARSET-EQUIV"
    if 'getattr(settings, "use_ai_gateway"' in old:
        return "C03-GATEWAY-DEFAULT-EQUIV"
    if 'format="png"' in new or 'decode("UTF-8")' in new:
        return "C04-ENCODE-CASE-EQUIV"
    if "raise ValueError(" in old:
        return "C05-VALUEERROR-MSGTEXT"
    if "original_error=e" in old:
        return "C06-ERR-CHAIN"
    if "status_code >= 500" in old:
        return "C07-STATUS-500-BOUNDARY"
    if "_check_circuit_breaker(" in old or ("self._get_breaker(" in old and fn not in {"_get_breaker"}):
        return "C08-BREAKER-CALLSITE" + ("-EMBED" if fn == "embed" else "")
    if "self._breakers.get(" in old:
        return "C09-GETBREAKER-FALLBACK"
    if "CircuitBreaker(name=" in old:
        if "config=None" in new or re.search(r'name="[^"]+", \)', new):
            return "C10-BREAKER-CONFIG"
        ko = re.match(r'^"([^"]+)"', old)
        kn = re.match(r'^"([^"]+)"', new)
        if ko and kn and ko.group(1) != kn.group(1):
            return "C11-BREAKER-DICTKEY"
        return "C12-BREAKER-NAME"
    if "record_pipeline_error(" in old and "circuit" in old.lower():
        return "C13-CIRCUIT-OPEN-LABEL"
    if "observe_ai_request_duration(" in old:
        return "C14-OBSERVE-LABEL"
    if old.strip().startswith("ai_duration ="):
        return "C15-AIDURATION-ARITH"
    if "headers=self._get_headers()" in old:
        return "C16-HEADERS"
    if re.search(r'"image":|"labels":|"text":|"texts":|"baseline_embedding":|payload =|json=payload|image_b64 =', old):
        return "C17-PAYLOAD"
    if re.search(r"connect=settings|read=settings|write=settings|pool=settings|timeout=self\.|limits=httpx", old):
        return "C18-INIT-CLIENT-CONFIG"
    ctxs = {c["ctx"] for c in chs}
    if ctxs == {"raise CLIPUnavailableError"}:
        if re.search(r"^\s*None,?\s*$|==> None", new) or new.strip().startswith("None"):
            return "C19-RAISE-MSG-NONE"
        if "sanitize_error(None)" in new:
            return "C20-RAISE-MSG-SANITIZE-NONE"
        return "C21-RAISE-MSG-CASE"
    # logger catch-all
    if "exc_info" in old or "exc_info" in new:
        return "C22-LOG-EXCINFO"
    if "extra=" in old:
        return "C23-LOG-EXTRA"
    if "duration_ms = int(" in old:
        return "C24-DURATION-COMPUTE"
    if any("None" in c["new"] or "sanitize_error(None)" in c["new"] for c in chs):
        return "C25-LOG-MSG-NONE"
    return "C26-LOG-MSG-CASE"


clusters = collections.defaultdict(list)
for k, v in d.items():
    clusters[classify(v)].append(k)

CLS = {
    "C01-NOOP-IDENTICAL": "EQUIVALENT",
    "C02-RSTRIP-CHARSET-EQUIV": "EQUIVALENT",
    "C03-GATEWAY-DEFAULT-EQUIV": "EQUIVALENT",
    "C04-ENCODE-CASE-EQUIV": "EQUIVALENT",
    "C05-VALUEERROR-MSGTEXT": "EQUIVALENT",
    "C06-ERR-CHAIN": "TEST-GAP",
    "C07-STATUS-500-BOUNDARY": "TEST-GAP",
    "C08-BREAKER-CALLSITE": "TEST-GAP",
    "C08-BREAKER-CALLSITE-EMBED": "EQUIVALENT",
    "C09-GETBREAKER-FALLBACK": "TEST-GAP",
    "C10-BREAKER-CONFIG": "TEST-GAP",
    "C11-BREAKER-DICTKEY": "TEST-GAP",
    "C12-BREAKER-NAME": "LOW-VALUE",
    "C13-CIRCUIT-OPEN-LABEL": "TEST-GAP",
    "C14-OBSERVE-LABEL": "TEST-GAP",
    "C15-AIDURATION-ARITH": "TEST-GAP",
    "C16-HEADERS": "TEST-GAP",
    "C17-PAYLOAD": "TEST-GAP",
    "C18-INIT-CLIENT-CONFIG": "TEST-GAP",
    "C19-RAISE-MSG-NONE": "TEST-GAP",
    "C20-RAISE-MSG-SANITIZE-NONE": "TEST-GAP",
    "C21-RAISE-MSG-CASE": "EQUIVALENT",
    "C22-LOG-EXCINFO": "LOW-VALUE",
    "C23-LOG-EXTRA": "LOW-VALUE",
    "C24-DURATION-COMPUTE": "LOW-VALUE",
    "C25-LOG-MSG-NONE": "LOW-VALUE",
    "C26-LOG-MSG-CASE": "EQUIVALENT",
}
tot = 0
for c in sorted(clusters):
    keys = clusters[c]
    tot += len(keys)
    fns = collections.Counter(d[k]["fn"] for k in keys)
    cls = CLS.get(c, "??")
    print(f"{c:32s} {cls:11s} {len(keys):4d}  {dict(fns)}")
    for ex in keys[:3]:
        print("        ", ex.split(SEP)[-1])
print("TOTAL", tot, "of", len(d))
json.dump(
    {
        c: {
            "classification": CLS.get(c, "??"),
            "count": len(keys),
            "fns": dict(collections.Counter(d[k]["fn"] for k in keys)),
            "example_keys": keys[:3],
            "sample_changes": [d[k]["changes"] for k in keys[:2]],
        }
        for c, keys in clusters.items()
    },
    open("/tmp/wp25/wp44-triage/_clusters.json", "w"),
    indent=1,
)

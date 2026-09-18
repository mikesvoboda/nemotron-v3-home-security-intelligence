import json, re, difflib, collections

REPO = "/agents/agent-nemo2/workspace"
MPATH = REPO + "/mutants/backend/services/florence_client.py"
SPATH = REPO + "/backend/services/florence_client.py"

with open(REPO + "/mutants/backend/services/florence_client.py.meta") as f:
    ebk = json.load(f)["exit_code_by_key"]

survivors = collections.defaultdict(set)
for k, v in ebk.items():
    if v == 0:
        m = re.match(r"backend\.services\.florence_client\.xǁFlorenceClientǁ(\w+)__mutmut_(\d+)$", k)
        if m:
            survivors[m.group(1)].add(int(m.group(2)))

lines = open(MPATH).read().splitlines()
def_re = re.compile(r"^    (?:async )?def xǁFlorenceClientǁ(\w+)__mutmut_(orig|\d+)\(")
spans = []
for i, ln in enumerate(lines):
    m = def_re.match(ln)
    if m:
        spans.append((i, m.group(1), m.group(2)))

blocks = {}
for i, func, num in spans:
    end = len(lines)
    for j in range(i + 1, len(lines)):
        if def_re.match(lines[j]) or re.match(r"^    (?:@|def |async def |class )", lines[j]):
            end = j
            break
    blocks[(func, num)] = lines[i:end]

def norm(body):
    return ["    async def METHOD(" if re.match(r"^    (?:async )?def xǁFlorenceClientǁ", ln) else ln for ln in body]

SRC = open(SPATH).read().splitlines()
srcline = {}
for si, sl in enumerate(SRC):
    m = re.match(r"^    async def (\w+)\(", sl)
    if m: srcline.setdefault(m.group(1), si)

def classify(func, o, m):
    """Return (cluster_name, classification) from the -/+ lines."""
    joined_o, joined_m = o, m
    # metrics string label changes
    if "record_pipeline_error(" in joined_o and re.sub(r'"[^"]*"', '"X"', joined_o) == re.sub(r'"[^"]*"', '"X"', joined_m):
        return ("record_pipeline_error label string changed", "LOW-VALUE (metrics label only; unit tests don't assert Prometheus counters by label)")
    if "record_florence_task(" in joined_o and re.sub(r'"[^"]*"', '"X"', joined_o) == re.sub(r'"[^"]*"', '"X"', joined_m):
        return ("record_florence_task label string changed", "LOW-VALUE")
    if "observe_ai_request_duration(" in joined_o and re.sub(r'"[^"]*"', '"X"', joined_o) == re.sub(r'"[^"]*"', '"X"', joined_m):
        return ("observe_ai_request_duration label string changed", "LOW-VALUE")
    # logger message text only
    if re.match(r"^(logger\.(debug|warning|error|info))", joined_o) and re.sub(r'[A-Za-z0-9_ \.\:\-\(\)\{\}%\'"]+', "X", joined_o) == re.sub(r'[A-Za-z0-9_ \.\:\-\(\)\{\}%\'"]+', "X", joined_m):
        return ("logger message text mutated", "EQUIVALENT (log text only)")
    # generic: pure string-constant change
    oq, mq = re.sub(r'"[^"]*"', '"S"', joined_o), re.sub(r'"[^"]*"', '"S"', joined_m)
    if oq == mq:  # only string contents differ
        # where does the string live?
        if "payload" in joined_o or '"image"' in joined_o or '"regions"' in joined_o or '"phrases"' in joined_o:
            return ("HTTP payload key string mutated", "TEST-GAP")
        if ".get(" in joined_o:
            return ("response-parsing .get() key/default mutated", "TEST-GAP")
        if "_check_circuit_breaker" in joined_o or "_get_breaker" in joined_o:
            return ("circuit-breaker endpoint name string mutated", "TEST-GAP")
        if "post(" in joined_o or "/ocr" in joined_o or "/describe" in joined_o or "/phrase" in joined_o or "/detect" in joined_o or '"{' in joined_o:
            return ("HTTP URL path string mutated", "TEST-GAP")
        if "FlorenceUnavailableError" in joined_o or "raise" in joined_o:
            return ("exception message text mutated", "EQUIVALENT")
        return ("misc string constant mutated: " + joined_o.strip()[:60], "?")
    # structural
    if joined_o.strip() == joined_m.strip():
        return ("whitespace/formatting only", "EQUIVALENT")
    return (None, None)

clusters = collections.defaultdict(list)  # cluster -> [(key, func, o, m, srcline)]
detail = open("/tmp/wp25/wp44-triage/_florence-raw-diffs.txt", "w")
unclassified = []
for func in sorted(survivors):
    orig = norm(blocks[(func, "orig")])
    for n in sorted(survivors[func]):
        mut = norm(blocks[(func, str(n))])
        sm = difflib.SequenceMatcher(None, orig, mut, autojunk=False)
        changes = []
        for tag, a1, a2, b1, b2 in sm.get_opcodes():
            if tag == "equal": continue
            o = "\\n".join(x.strip() for x in orig[a1:a2])
            m = "\\n".join(x.strip() for x in mut[b1:b2])
            h = srcline.get(func, 0) + a1 + 1
            changes.append((o, m, h))
        key = f"{func}__mutmut_{n}"
        detail.write(f"==== {key} ({len(changes)} hunk(s))\n")
        for o, m, h in changes:
            detail.write(f"  src~{h}\n  - {o}\n  + {m}\n")
        if len(changes) == 1:
            o, m, h = changes[0]
            cname, cls = classify(func, o, m)
            if cname is None:
                clusters[(func, "STRUCTURAL", "STRUCTURAL")].append((key, o, m, h))
            else:
                clusters[(func, cname, cls)].append((key, o, m, h))
        else:
            clusters[(func, "MULTI-HUNK", "MULTI")].append((key, " || ".join(c[0] for c in changes), " || ".join(c[1] for c in changes), changes[0][2]))
detail.close()

total = 0
for (func, cname, cls), rows in sorted(clusters.items(), key=lambda kv: (kv[0][0], -len(kv[1]))):
    total += len(rows)
    print(f"### [{func}] {cname}  ::  {cls}  ::  count={len(rows)}")
    print(f"    examples: {', '.join(r[0].split('ǁ')[-1] for r in rows[:3])}")
    print(f"    src~{rows[0][3]}  - {rows[0][1][:110]}")
    print(f"              + {rows[0][2][:110]}")
print("TOTAL", total, "EXPECTED", sum(len(s) for s in survivors.values()))

import re, json, difflib, collections
SRC = "mutants/backend/services/clip_client.py"
SEP = "ǁ"
lines = open(SRC, encoding="utf-8").read().split("\n")
n = len(lines)
def_re = re.compile(
    r"^    (?:async )?def x" + SEP + r"(?P<cls>[A-Za-z_]+)" + SEP + r"(?P<fn>.+?)__mutmut_(?P<num>[0-9]+|orig)\("
)
stops = re.compile(r"^(    (?:async )?def |    @_mutmut|    @|mutants_x|class )")
blocks = []
i = 0
while i < n:
    m = def_re.match(lines[i])
    if m:
        cls, fn, num = m.group("cls"), m.group("fn"), m.group("num")
        start = i + 1
        j = start
        while j < n and not stops.match(lines[j]):
            j += 1
        body = lines[start:j]
        while body and body[-1].strip() == "":
            body.pop()
        blocks.append((cls, fn, num, body))
        i = j
    else:
        i += 1
bykey = collections.defaultdict(dict)
for cls, fn, num, body in blocks:
    bykey[(cls, fn)][num] = body
surv = [l for l in open("/tmp/wp25/wp44-triage/_clip_survivors.txt").read().split() if l]
def parse(k):
    idx = k.find("CLIPClient")
    rest = k[idx + len("CLIPClient"):]
    fn = rest.split("__mutmut_")[0].lstrip(SEP)
    num = rest.split("__mutmut_")[1]
    return fn, num
out = {}
missing = []
for k in surv:
    fn, num = parse(k)
    d = bykey[("CLIPClient", fn)]
    if "orig" not in d or num not in d:
        missing.append((k, sorted(d.keys())[:3]))
        continue
    a, b = d["orig"], d[num]
    sm = difflib.SequenceMatcher(a=a, b=b)
    changes = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ol = " | ".join(x.strip() for x in a[i1:i2])
        nl = " | ".join(x.strip() for x in b[j1:j2])
        changes.append((ol, nl))
    out[k] = {"fn": fn, "num": int(num), "changes": changes}
json.dump(out, open("/tmp/wp25/wp44-triage/_clip_diffs.json", "w"))
print("survivors:", len(surv), "diffed:", len(out), "missing:", len(missing))
for m in missing[:5]:
    print("missing", m)

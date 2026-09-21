import json, re, difflib, collections

REPO = "/agents/agent-nemo2/workspace"
MPATH = REPO + "/mutants/backend/services/florence_client.py"
SPATH = REPO + "/backend/services/florence_client.py"

with open(REPO + "/mutants/backend/services/florence_client.py.meta") as f:
    ebk = json.load(f)["exit_code_by_key"]

survivors = {}
for k, v in ebk.items():
    if v == 0:
        m = re.match(r"backend\.services\.florence_client\.xǁFlorenceClientǁ(\w+)__mutmut_(\d+)$", k)
        if m:
            survivors.setdefault(m.group(1), set()).add(int(m.group(2)))

lines = open(MPATH).read().splitlines()

# locate all "def xǁFlorenceClientǁFUNC__mutmut_N(" lines
def_re = re.compile(r"^    (?:async )?def xǁFlorenceClientǁ(\w+)__mutmut_(orig|\d+)\(")
spans = []
for i, ln in enumerate(lines):
    m = def_re.match(ln)
    if m:
        spans.append((i, m.group(1), m.group(2)))

# for terminator, find next top-level-ish def/class after span start
blocks = {}  # (func, num) -> body lines
for idx, (i, func, num) in enumerate(spans):
    # end: next span start OR next line at indent <= 4 that is a def/decorator not part of this variant
    end = len(lines)
    for j in range(i + 1, len(lines)):
        ln = lines[j]
        if def_re.match(ln):
            end = j
            break
        # decorator or def at class-body indent that's not inside our variant
        if re.match(r"^    (?:@|def |async def |class )", ln):
            end = j
            break
    blocks[(func, num)] = lines[i:end]

def norm(body, func):
    out = []
    for ln in body:
        # strip the def name variant difference; keep the rest
        if re.match(r"^    (?:async )?def xǁFlorenceClientǁ", ln):
            out.append("    async def METHOD(" )
        else:
            out.append(ln)
    return out

SRC = open(SPATH).read().splitlines()

summary = collections.defaultdict(list)  # (func, pattern) -> list of (num, orig_line, mut_line, src_line_hint)
for func in sorted(survivors):
    if (func, "orig") not in blocks:
        print("!! no orig for", func)
        continue
    orig = norm(blocks[(func, "orig")], func)
    # find source line of the method def for offset hints
    srcline = None
    for si, sl in enumerate(SRC):
        if re.match(rf"^    async def {func}\(", sl):
            srcline = si
            break
    for n in sorted(survivors[func]):
        if (func, str(n)) not in blocks:
            print("!! missing variant", func, n)
            continue
        mut = norm(blocks[(func, str(n))], func)
        sm = difflib.SequenceMatcher(None, orig, mut, autojunk=False)
        changes = []
        for tag, a1, a2, b1, b2 in sm.get_opcodes():
            if tag == "equal":
                continue
            o = "\\n".join(x.strip() for x in orig[a1:a2])
            m = "\\n".join(x.strip() for x in mut[b1:b2])
            src_hint = (srcline + a1) if srcline else None
            changes.append((o, m, src_hint))
        if len(changes) == 1:
            o, m, h = changes[0]
            summary[(func, o, m)].append((n, h))
        else:
            for o, m, h in changes:
                summary[(func, o, m, "MULTI")].append((n, h))

for (func, o, m, *rest), nums in sorted(summary.items()):
    tag = rest[0] if rest else "SINGLE"
    print(f"### {func} [{tag}] x{len(nums)} keys={sorted(k for k,_ in nums)[:8]}{'...' if len(nums)>8 else ''}")
    print(f"    src_line~ {nums[0][1]}")
    print(f"    - {o}")
    print(f"    + {m}")

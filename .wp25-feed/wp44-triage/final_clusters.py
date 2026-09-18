import json, re
from collections import Counter, defaultdict

rows = json.load(open('/tmp/wp25/wp44-triage/rows.json'))

STR = r'"[^"]*"'
QSTR = r"'[^']*'"
BOTH = '(' + STR + '|' + QSTR + ')'


def str_variant(o, n):
    """Return family if difference is purely string-literal text."""
    so = re.findall(BOTH, o)
    sn = re.findall(BOTH, n)
    if len(so) == 1 and len(sn) == 1 and re.sub(BOTH, 'S', o) == re.sub(BOTH, 'S', n):
        a, b = so[0], sn[0]
        core, nc = a[1:-1], b[1:-1]
        if nc == 'XX' + core + 'XX' or nc == 'xx' + core.lower() + 'xx':
            return 'STR-XXwrap'
        if nc == core.upper() and core != core.upper():
            return 'STR-UPPER'
        if nc == core.upper():
            return 'STR-UPPER'
        if nc == core.lower() and core != core.lower():
            return 'STR-lower'
        if nc == '':
            return 'STR-empty'
        if nc in ('XX', 'xx'):
            return 'STR-XXwrap'
        return 'STR-other'
    return None


def final_family(r):
    old, new = r['old'], r['new']
    if len(old) != 1 or len(new) != 1:
        # multi-line: mostly argument deletion / call removal
        o = '\n'.join(old)
        n = '\n'.join(new)
        if len(new) < len(old):
            return 'MULTI-arg-or-block-deleted'
        return 'MULTI-other'
    o, n = old[0], new[0]

    f = str_variant(o, n)
    if f:
        return f
    # multi-token string clobbers that also touched adjacent token: check strings only differ
    so = re.findall(BOTH, o)
    sn = re.findall(BOTH, n)
    if so and sn and len(so) == len(sn):
        stripped_o = [s for s in so]
        stripped_n = [s for s in sn]
        if stripped_o != stripped_n and re.sub(BOTH, 'S', o) == re.sub(BOTH, 'S', n):
            return 'STR-XXwrap/UPPER-multi'

    # exc_info True -> None/False
    if 'exc_info=True' in o and ('exc_info=None' in n or 'exc_info=False' in n):
        return 'LOG-exc_info-killed'

    # condition boolean adders/removers
    if re.search(r'\b(and|or)\s+(False|True)\b', n) and not re.search(r'\b(and|or)\s+(False|True)\b', o):
        return 'COND-andFalse-orTrue'
    if is_not_flip(o, n):
        return 'COND-isNotNone-flip'
    # 'if X:' -> 'if not X:' and inverse
    if (n.replace(' not ', ' ', 1) == o or o.replace(' not ', ' ', 1) == n) and re.match(r'^\s*(if|elif|while|assert)\b', o):
        return 'COND-not-added-removed'

    if re.match(r'^\s*(continue|break)\s*$', o) and re.match(r'^\s*(continue|break)\s*$', n) and o != n:
        return 'FLOW-continue-break'

    # True -> False / False -> True literals (value positions)
    if 'True' in o and 'False' in n and o.replace('True', 'X') == n.replace('False', 'X'):
        return 'BOOL-True-to-False'
    if 'False' in o and 'True' in n and o.replace('False', 'X') == n.replace('True', 'X'):
        return 'BOOL-False-to-True'

    # result of a call/await replaced by None:  X = <call>  ==>  X = None
    m = re.match(r'^(\s*[\w.\[\]]+\s*(:[^=]+)?= )(.+)$', o)
    if m and n.strip().startswith(m.group(1)) and re.match(r'^(\s*[\w.\[\]]+\s*(:[^=]+)?= )(None)\s*,?\s*$', n):
        return 'DATA-call-to-None'

    # kwarg X=expr -> X=None (or arg removed entirely -> ')')
    if re.search(r'(\w+)=', o):
        m2 = re.match(r'.*?(\w+)=.*$', o)
        mm = re.findall(r'(\w+)=', o)
        mn = re.findall(r'(\w+)=', n)
        if n.strip() in (')',):
            return 'DATA-kwarg-removed'
        if 'None' in n:
            m3 = re.match(r'.*(\w+)=None\s*,?\s*$', n)
            if m3 and m3.group(1) in mm:
                return 'DATA-kwarg-to-None'
    if n.strip() in (')',):
        return 'DATA-kwarg-removed'

    # default-arg removal: .get("k", 0) -> .get("k", )
    if re.search(r'\w\.get\([^()]*,\s*\)', n) or re.search(r'\w\([^()]*,\s*\)', n):
        if ', )' in n and ', )' not in o:
            return 'DATA-default-removed'
    if re.search(r'index_elements=\[[^\]]*\]\)?', o) and 'index_elements=None' in n:
        return 'DATA-kwarg-to-None'

    # call positional arg -> None: f(a, b) -> f(a, None)
    if 'None' in n and 'None' not in o:
        to = re.sub(r'[A-Za-z_]\w*', 'V', o)
        tn = re.sub(r'[A-Za-z_]\w*', 'V', n)
        # allow None to have replaced a token V
        if to.count('V') == tn.count('V') + n.count('None'):
            return 'DATA-arg-to-None'
        return 'DATA-to-None-other'
    if 'None' in o and 'None' not in n:
        return 'DATA-None-to-expr'

    # operator flips
    to = re.findall(r'\*\*|//|<=|>=|==|!=|<-|->|[-+*/<>=&|^%]|\band\b|\bor\b|is not|is|\bnot\b|[A-Za-z_][\w.]*|"[^"]*"|\d+\.\d+|\d+|.', o)
    tn = re.findall(r'\*\*|//|<=|>=|==|!=|<-|->|[-+*/<>=&|^%]|\band\b|\bor\b|is not|is|\bnot\b|[A-Za-z_][\w.]*|"[^"]*"|\d+\.\d+|\d+|.', n)
    if len(to) == len(tn):
        diffs = [(a, b) for a, b in zip(to, tn) if a != b]
        if len(diffs) == 1:
            a, b = diffs[0]
            if re.fullmatch(r'\d+(\.\d+)?', a) and re.fullmatch(r'\d+(\.\d+)?', b):
                return 'NUM-tweak'
            if a in ('<', '<=', '>', '>=', '==', '!=') and b in ('<', '<=', '>', '>=', '==', '!='):
                return 'OP-comparison-flip'
            if a in ('and', 'or') and b in ('and', 'or'):
                return 'OP-and-or-flip'
            if a in ('is', 'is not') or b in ('is', 'is not'):
                return 'OP-is-flip'
            if a in ('+', '-', '*', '/', '**') or b in ('+', '-', '*', '/', '**'):
                return 'OP-arith-flip'
            if a == b:
                return 'X-identical'
            return 'TOK-other:' + a + '->' + b
    return 'Z-rest'


def is_not_flip(o, n):
    pairs = [('is not None', 'is None'), ('is None', 'is not None')]
    for a, b in pairs:
        if a in o and b in n and o.replace(a, '#') == n.replace(b, '#'):
            return True
    return False


fam = defaultdict(list)
for r in rows:
    fam[final_family(r)].append(r)

tot = 0
for k in sorted(fam, key=lambda k: -len(fam[k])):
    print('%5d  %s' % (len(fam[k]), k))
    tot += len(fam[k])
print('TOTAL', tot)

json.dump({k: [{'func': r['func'], 'idx': r['idx'], 'old': r['old'], 'new': r['new']} for r in v]
           for k, v in fam.items()},
          open('/tmp/wp25/wp44-triage/final.json', 'w'))

# cross-tab top families x functions
print()
print('=== Z-rest / TOK-other leftovers sample ===')
for k in fam:
    if k.startswith('Z-rest') or k.startswith('TOK-other'):
        cnt = Counter((r['func'], tuple(r['old'])[:1], tuple(r['new'])[:1]) for r in fam[k])
        print('---', k, len(fam[k]))
        for (f, o, n), c in cnt.most_common(12):
            print('   ', c, f, ' | ', str(o)[:80], '==>', str(n)[:80])

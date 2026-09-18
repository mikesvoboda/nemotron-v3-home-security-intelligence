import json, re
from collections import Counter, defaultdict

groups = json.load(open('/tmp/wp25/wp44-triage/groups.json'))
un = groups['U-UNCLASS']

OPS = ['<=', '>=', '==', '!=', '<', '>', ' and ', ' or ', ' is not ', ' is ',
       ' not in ', ' in ', '+', '-', '*', '/', '**']


def toks(line):
    return re.findall(r'"[^"]*"|\'[^\']*\'|[A-Za-z_][\w.]*|\d+\.\d+|\d+|<=|>=|==|!=|\*\*|[-+*/<>()=,:\[\]{}]', line)


def classify(r):
    o, n = r['old'][0], r['new'][0]
    # boolean-literal driven condition looseners/strengtheners
    if 'and False' in n or 'or False' in n or 'and True' in n or 'or True' in n:
        return 'D1-cond-andFalse-orTrue'
    if re.match(r'^(\s*)if (not )?(\w[\w.\[\]\'"]*)\s*:\s*$', o) and re.sub(r'\bif not ', 'if ', o) != n and 'not ' in n:
        return 'D2-not-inserted'
    if ' not ' in n and ' not ' not in o and n.replace(' not ', ' ', 1) == o:
        return 'D2-not-inserted'
    # True/False literal flips (non cond-add)
    if re.search(r'\bTrue\b', o) and re.search(r'\bFalse\b', n) and o.replace('True', 'X') == n.replace('False', 'X'):
        return 'D3-True-to-False'
    if re.search(r'\bFalse\b', o) and re.search(r'\bTrue\b', n) and o.replace('False', 'X') == n.replace('True', 'X'):
        return 'D3-False-to-True'
    # continue/break
    if o.strip() == 'continue' and n.strip() == 'break':
        return 'D4-continue-to-break'
    if o.strip() == 'break' and n.strip() == 'continue':
        return 'D4-break-to-continue'
    # keyword arg = <expr> -> kwarg=None  (RHS is call/attr)
    m1 = re.match(r'^(\w+)=.+$', o)
    if m1 and re.match(r'^(\w+)=None,?$', n) and m1.group(1) == re.match(r'^(\w+)=None,?$', n).group(1):
        return 'C1b-kwarg-expr-to-None'
    # call argument to None:  f("x") -> f(None)  or  f(a, b) -> f(None, b)
    if re.sub(r'\w+\(', '', o) == re.sub(r'\w+\(', '', n):
        pass
    if '(None' in n and '(None' not in o and ('.get(' in o or 'str(' in o or '(' in o):
        so = re.sub(r'[A-Za-z_][\w.]*', 'V', o)
        sn = re.sub(r'[A-Za-z_][\w.]*', 'V', n)
        if so == sn:
            return 'C4-callarg-to-None'
    if re.search(r'\((None[,)]|\w+,\s*None\))', n) and 'None' not in o:
        return 'C4-callarg-to-None'
    # numeric tweaks: same token stream except numbers
    to, tn = toks(o), toks(n)
    if len(to) == len(tn):
        diffs = [(a, b) for a, b in zip(to, tn) if a != b]
        if len(diffs) == 1:
            a, b = diffs[0]
            if re.fullmatch(r'[\d.]+', a) and re.fullmatch(r'[\d.]+', b):
                return 'N1-numeric-tweak'
            if a in OPS or b in OPS or a in ('<', '>', '<=', '>=', '==', '!=') or b in ('<', '>', '<=', '>=', '==', '!='):
                return 'O1-op-flip:' + a + '_to_' + b
            if a in ('+', '-', '*', '/', '**') or b in ('+', '-', '*', '/', '**'):
                return 'O2-arith-flip:' + a + '_to_' + b
            if a == 'None' or b == 'None':
                return 'C5-None-swap'
            return 'X-other-tok:' + a + '_to_' + b
        if len(diffs) == 0:
            return 'X-identical-tokens'
    # and/or flips with same length
    return 'Y-UNCLASS2'


g2 = defaultdict(list)
for r in un:
    g2[classify(r)].append(r)

tot = 0
for k in sorted(g2, key=lambda k: -len(g2[k])):
    print('%5d  %s' % (len(g2[k]), k))
    tot += len(g2[k])
print('TOTAL', tot)
json.dump({k: [{'func': r['func'], 'idx': r['idx'], 'old': r['old'], 'new': r['new']} for r in v]
           for k, v in g2.items()},
          open('/tmp/wp25/wp44-triage/groups2.json', 'w'))

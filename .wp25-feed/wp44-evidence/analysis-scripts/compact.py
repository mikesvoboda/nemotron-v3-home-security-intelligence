import re, difflib, json
txt = open('/tmp/wp25/surv_diffs.txt').read()
blocks = txt.split('### ')[1:]
out = []
for b in blocks:
    lines = b.splitlines()
    key = lines[0].strip()
    minus = [l[2:] for l in lines if l.startswith('  -')]
    plus  = [l[2:] for l in lines if l.startswith('  +')]
    if not minus:
        out.append((key, lines[0], 'NO-DIFF-SIGNATURE')); continue
    a = ' '.join(minus).split()
    c = ' '.join(plus).split()
    sm = difflib.SequenceMatcher(None, a, c, autojunk=False)
    frags = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal': continue
        frags.append(f"{' '.join(a[i1:i2]) or '<none>'} -> {' '.join(c[j1:j2]) or '<none>'}")
    out.append((key, key, ' ;; '.join(frags)))
for k, _, f in out:
    print(k.replace('backend.services.alert_service.xǁAlertServiceǁ','').replace('backend.services.alert_service.',''), '|', f)

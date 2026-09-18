import sim, math, random
from datetime import datetime, timedelta
BASE = sim.BASE; SRC = sim.SRC
CODES = {}

def vns(old, new):
    key = (old, new)
    if key not in CODES:
        assert old in SRC, f'ANCHOR-MISS {old!r}'
        CODES[key] = compile(SRC.replace(old, new), 'mut', 'exec')
    ns = {}
    exec(CODES[key], ns)
    return ns

def run(fn, ns):
    try:
        fn(ns); return None
    except AssertionError as e: return f'Assert: {str(e)[:100]}'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:90]}'

def verify(cluster, testfn, variants):
    r = {'orig': run(testfn, BASE) or 'PASS', 'mutants': {}}
    for suf, o, n in variants:
        try: ns = vns(o, n)
        except AssertionError: r['mutants'][suf] = 'ANCHOR-MISS'; continue
        r['mutants'][suf] = run(testfn, ns) or 'NOT-KILLED'
    return r

def report(r):
    for k, v in r['mutants'].items():
        mark = 'KILLED' if not v.startswith(('NOT-KILLED', 'ANCHOR')) else '>>> ' + v
        print(f"  {k:>4}: {mark if mark.startswith('>>>') else 'KILLED'}")
    print('  orig:', r['orig'])

def pts(coords, iv=5.0):
    base = datetime(2026, 1, 26, 12, 0, 0)
    return [{'x': x, 'y': y, 'timestamp': (base + timedelta(seconds=i * iv)).isoformat()}
            for i, (x, y) in enumerate(coords)]
def entry(coords=None, name='Front Door'):
    return {'name': name, 'zone_type': 'entry_point',
            'coordinates': coords or [[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]]}
def zone(name='Driveway', coords=None):
    return {'name': name, 'zone_type': 'driveway', 'coordinates': coords or [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]]}
def pts_d(dseq, iv=3.0):
    return pts([(100 + d, 100) for d in dseq], iv=iv)
E2 = entry(coords=[[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]])
E1 = entry()
EZ = {'name': 'E', 'zone_type': 'entry_point', 'coordinates': [[0.9, 0.1], [0.95, 0.1], [0.95, 0.3], [0.9, 0.3]]}

def bf(fn_name, old, new, n=200000, seed=11):
    """Search for an input where mutant differs from original. Returns (input, orig, mut) or None."""
    mns = vns(old, new)
    rnd = random.Random(seed)
    f_o, f_m = BASE[fn_name], mns[fn_name]
    for _ in range(n):
        m = rnd.choice([3, 4, 5, 6])
        zx, zy = rnd.choice([(500, 500), (100, 100), (1728, 216), (900, 300), (200, 700)])
        zz = {'name': 'Z', 'zone_type': 'entry_point',
              'coordinates': [[(zx-250)/1920, (zy-150)/1080], [(zx+250)/1920, (zy-150)/1080],
                              [(zx+250)/1920, (zy+150)/1080], [(zx-250)/1920, (zy+150)/1080]]}
        if rnd.random() < 0.15:
            zz = {'name': 'Z', 'zone_type': 'yard', 'coordinates': zz['coordinates']}
        if rnd.random() < 0.1:
            zz = {'name': 'Z', 'zone_type': 'entry_point', 'coordinates': []}
        if rnd.random() < 0.1:
            zz = {'zone_type': 'entry_point', 'coordinates': zz['coordinates']}
        ps = pts([(rnd.randint(0, 1920), rnd.randint(0, 1080)) for _ in range(m)], iv=3)
        try:
            a = f_o(ps, [zz], 1920, 1080)
        except Exception as e: a = 'E' + type(e).__name__
        try:
            b = f_m(ps, [zz], 1920, 1080)
        except Exception as e: b = 'E' + type(e).__name__
        if a != b:
            return (ps, zz, a, b)
    return None

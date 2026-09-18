import sim, math, random, itertools
BASE = sim.BASE; SRC = sim.SRC

def variant_ns(old, new, count=1):
    """Global module-level replace (works for methods too)."""
    assert SRC.count(old) >= 1, f'ANCHOR-MISS {old!r}'
    ns = {}
    exec(compile(SRC.replace(old, new, count), 'm', 'exec'), ns)
    return ns

def run(testfn, ns):
    try:
        testfn(ns); return None
    except AssertionError as e: return f'Assert: {str(e)[:90]}'
    except Exception as e: return f'{type(e).__name__}: {str(e)[:80]}'

OUT = {}
def verify(cluster, testfn, variants):
    r = {'orig': run(testfn, BASE) or 'PASS', 'mutants': {}}
    for suf, o, n in variants:
        try: ns = variant_ns(o, n)
        except AssertionError as e: r['mutants'][suf] = 'ANCHOR-MISS'; continue
        r['mutants'][suf] = run(testfn, ns) or 'NOT-KILLED'
    OUT[cluster] = r

from datetime import datetime, timedelta
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
EZ = {'name': 'E', 'zone_type': 'entry_point', 'coordinates': [[0.9, 0.1], [0.95, 0.1], [0.95, 0.3], [0.9, 0.3]]}  # center (1728,216) @1920x1080

# ===== T1 describe_speed =====
def t1(ns):
    f = ns['_describe_speed']
    for v, e in [(4.99,'stationary'),(5.0,'slow (walking pace)'),(29.99,'slow (walking pace)'),
                 (30.0,'moderate (brisk walk)'),(79.99,'moderate (brisk walk)'),(80.0,'fast (running)'),
                 (149.99,'fast (running)'),(150.0,'very fast (vehicle speed)')]:
        got = f(v); assert got == e, f'{v}: {got!r}!={e!r}'
verify('T1', t1, [
 ('1','if speed_px_per_sec < 5:','if speed_px_per_sec <= 5:'),
 ('2','if speed_px_per_sec < 5:','if speed_px_per_sec < 6:'),
 ('5','elif speed_px_per_sec < 30:','elif speed_px_per_sec <= 30:'),
 ('6','elif speed_px_per_sec < 30:','elif speed_px_per_sec < 31:'),
 ('9','elif speed_px_per_sec < 80:','elif speed_px_per_sec <= 80:'),
 ('10','elif speed_px_per_sec < 80:','elif speed_px_per_sec < 81:'),
 ('13','elif speed_px_per_sec < 150:','elif speed_px_per_sec <= 150:'),
 ('14','elif speed_px_per_sec < 150:','elif speed_px_per_sec < 151:')])

# ===== T2 check_approach_depart =====
CAD_MIN = 'min_dist = min(math.sqrt((px - cx) ** 2 + (py - cy) ** 2) for cx, cy in zone_centers)'
def t2(ns):
    f = ns['_check_approach_depart']
    assert f(pts([(100,100),(300,300),(450,450)], iv=3), [E1], 1000, 1000) == 'approaching'
    assert f(pts_d([300,180,250,150,200,100]), [E2], 1000, 1000) == 'approaching'
    assert f(pts_d([100,200,150,250,180,300]), [E2], 1000, 1000) == 'departing'
    assert f(pts_d([200,300,300,100,400,250]), [E2], 1000, 1000) is None
    assert f(pts_d([300,200,200,150,150,250]), [E2], 1000, 1000) is None
    assert f(pts_d([300,200,300,100,300,0]), [E2], 1000, 1000) == 'approaching'
    assert f(pts_d([0,300,100,300,200,300]), [E2], 1000, 1000) == 'departing'
    assert f(pts([(100,100),(100,200),(100,400)], iv=3), [E2], 1000, 1000) == 'departing'
    assert f(pts([(100,100),(100,200)], iv=3), [E2], 1000, 1000) is None
    assert f(pts([(1728,1000),(1728,600),(1728,400)], iv=3), [EZ], 1920, 1080) == 'approaching'
    # y-offset fixture kills min_dist dx-scale mutants (34/37)
    assert f(pts([(100,900),(100,300),(100,100)], iv=3), [E2], 1000, 1000) == 'approaching'  # sanity
verify('T2', t2, [
 ('1','if len(track_points) < 3:','if len(track_points) <= 3:'),
 ('2','if len(track_points) < 3:','if len(track_points) < 4:'),
 ('16','cx = sum(p[0] for p in coords) / len(coords) * video_width','cx = sum(p[1] for p in coords) / len(coords) * video_width'),
 ('42','decreasing = 0','decreasing = 1'),
 ('44','increasing = 0','increasing = 1'),
 ('46','total_segments = len(distances) - 1','total_segments = len(distances) + 1'),
 ('47','total_segments = len(distances) - 1','total_segments = len(distances) - 2'),
 ('50','for i in range(1, len(distances)):','for i in range(len(distances)):'),
 ('52','for i in range(1, len(distances)):','for i in range(2, len(distances)):'),
 ('53','if distances[i] < distances[i - 1]:','if distances[i] <= distances[i - 1]:'),
 ('55','if distances[i] < distances[i - 1]:','if distances[i] < distances[i - 2]:'),
 ('58','decreasing += 1','decreasing += 2'),
 ('59','elif distances[i] > distances[i - 1]:','elif distances[i] >= distances[i - 1]:'),
 ('61','elif distances[i] > distances[i - 1]:','elif distances[i] > distances[i - 2]:'),
 ('64','increasing += 1','increasing += 2'),
 ('67','if decreasing / total_segments >= APPROACH_CONSISTENCY_THRESHOLD:','if decreasing * total_segments >= APPROACH_CONSISTENCY_THRESHOLD:'),
 ('68','if decreasing / total_segments >= APPROACH_CONSISTENCY_THRESHOLD:','if decreasing / total_segments > APPROACH_CONSISTENCY_THRESHOLD:'),
 ('71','if increasing / total_segments >= DEPART_CONSISTENCY_THRESHOLD:','if increasing * total_segments >= DEPART_CONSISTENCY_THRESHOLD:'),
 ('72','if increasing / total_segments >= DEPART_CONSISTENCY_THRESHOLD:','if increasing / total_segments > DEPART_CONSISTENCY_THRESHOLD:')])

# brute force for cad min_dist scale mutants 34/37 and guard eq 65/66
def bf(fn_name, keys, n=20000):
    rnd = random.Random(7)
    found = {k: None for k, _, _ in keys}
    for _ in range(n):
        m = rnd.randint(3, 6)
        c = [(rnd.randint(0,2)*500, rnd.randint(0,2)*500)]
        if rnd.random() < .5: c.append((rnd.randint(0,2)*500, rnd.randint(0,2)*500))
        ps = pts([(rnd.randint(0,1920), rnd.randint(0,1080)) for _ in range(m)], iv=3)
        zc = [{'name':'Z','zone_type':'entry_point','coordinates': c}]
        outs = {}
        for k, o, nn in keys:
            if found[k]: continue
            ns = variant_ns(o, nn)
            try: outs[k] = ns['_check_approach_depart'](ps, [zc], 1000, 1000)
            except Exception as e: outs[k] = type(e).__name__
        if found.get('base'):
            pass
    return found

# targeted brute force helper
def bf_search(mutkey, old, new, fn='_check_approach_depart', n=60000):
    rnd = random.Random(11)
    for _ in range(n):
        m = rnd.choice([3,4,5,6])
        zx, zy = rnd.choice([(500,500),(100,100),(1728,216),(900,500)])
        zw = rnd.choice([0.2, 0.1])
        zz = {'name':'Z','zone_type':'entry_point','coordinates':
              [[(zx-250)/1920,(zy-150)/1080],[(zx+250)/1920,(zy-150)/1080],[(zx+250)/1920,(zy+150)/1080],[(zx-250)/1920,(zy+150)/1080]]}
        ps = pts([(rnd.randint(0,1920), rnd.randint(0,1080)) for _ in range(m)], iv=3)
        try:
            o = BASE[fn](ps, [zz], 1920, 1080)
        except Exception:
            continue
        ns = variant_ns(old, new)
        try:
            mu = ns[fn](ps, [zz], 1920, 1080)
        except Exception as e:
            mu = 'EXC:'+type(e).__name__
        if mu != o:
            return (ps, o, mu)
    return None

print('bf cad 34:', bool(bf_search('34', CAD_MIN, 'min_dist = min(math.sqrt((px - cx) * 2 + (py - cy) ** 2) for cx, cy in zone_centers)')))
print('bf cad 37:', bool(bf_search('37', CAD_MIN, 'min_dist = min(math.sqrt((px - cx) ** 2 + (py - cy) * 2) for cx, cy in zone_centers)')))
print('bf cad 65 (expect None=equivalent):', bf_search('65', 'if total_segments > 0:', 'if total_segments >= 0:'))
print('bf cad 66 (expect None=equivalent):', bf_search('66', 'if total_segments > 0:', 'if total_segments > 1:'))

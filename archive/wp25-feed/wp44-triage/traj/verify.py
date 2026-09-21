"""For each drafted test: assert it PASSES on original and FAILS on each mutant in its cluster."""
import sim

BASE = sim.BASE

def variant_ns(fn_name, old, new):
    ns = dict(BASE)
    body = sim.fn_src(fn_name)
    assert old in body, f'anchor missing in {fn_name}: {old!r}'
    exec(body.replace(old, new), ns)
    return ns

def run(testfn, ns):
    """returns None if passes, failure string if fails"""
    try:
        testfn(ns)
        return None
    except AssertionError as e:
        return f'AssertionError: {e}'
    except Exception as e:
        return f'{type(e).__name__}: {e}'

RESULTS = {}
def verify(cluster, testfn, variants):
    # variants: list of (key_suffix, fn_name, old, new)
    r = run(testfn, BASE)
    RESULTS[cluster] = {'orig': r or 'PASS', 'mutants': {}}
    for suf, f, o, n in variants:
        try:
            ns = variant_ns(f, o, n)
        except AssertionError as e:
            RESULTS[cluster]['mutants'][suf] = 'ANCHOR-MISS: ' + str(e)[:80]
            continue
        res = run(testfn, ns)
        RESULTS[cluster]['mutants'][suf] = res if res else '**NOT KILLED**'

# ---------------------------------------------------------------- fixtures
from datetime import datetime, timedelta
def pts(coords, t0=0.0, iv=5.0):
    base = datetime(2026, 1, 26, 12, 0, 0)
    return [{'x': x, 'y': y, 'timestamp': (base + timedelta(seconds=t0 + i * iv)).isoformat()}
            for i, (x, y) in enumerate(coords)]
def entry(coords=None, name='Front Door'):
    return {'name': name, 'zone_type': 'entry_point',
            'coordinates': coords or [[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]]}
def zone(name='Driveway', coords=None):
    return {'name': name, 'zone_type': 'driveway',
            'coordinates': coords or [[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]]}
A = BASE['TrajectoryAnalysis']

# ================================================================ T1 describe_speed boundaries
def t1(ns):
    f = ns['_describe_speed']
    assert f(4.99) == 'stationary'
    assert f(5.0) == 'slow (walking pace)'
    assert f(29.99) == 'slow (walking pace)'
    assert f(30.0) == 'moderate (brisk walk)'
    assert f(79.99) == 'moderate (brisk walk)'
    assert f(80.0) == 'fast (running)'
    assert f(149.99) == 'fast (running)'
    assert f(150.0) == 'very fast (vehicle speed)'

t1_vars = [
    ('1', '_describe_speed', 'if speed_px_per_sec < 5:', 'if speed_px_per_sec <= 5:'),
    ('2', '_describe_speed', 'if speed_px_per_sec < 5:', 'if speed_px_per_sec < 6:'),
    ('5', '_describe_speed', 'elif speed_px_per_sec < 30:', 'elif speed_px_per_sec <= 30:'),
    ('6', '_describe_speed', 'elif speed_px_per_sec < 30:', 'elif speed_px_per_sec < 31:'),
    ('9', '_describe_speed', 'elif speed_px_per_sec < 80:', 'elif speed_px_per_sec <= 80:'),
    ('10', '_describe_speed', 'elif speed_px_per_sec < 80:', 'elif speed_px_per_sec < 81:'),
    ('13', '_describe_speed', 'elif speed_px_per_sec < 150:', 'elif speed_px_per_sec <= 150:'),
    ('14', '_describe_speed', 'elif speed_px_per_sec < 150:', 'elif speed_px_per_sec < 151:'),
]
verify('describe_speed_boundaries', t1, t1_vars)

# ================================================================ T2 check_approach_depart exact ratio/segments/centers
def t2(ns):
    f = ns['_check_approach_depart']
    e = entry()  # center (0.5,0.5) -> (500,500) px
    # 5 pts monotonically approaching: decreasing 4/4
    p = pts([(100, 100), (200, 200), (300, 300), (400, 400), (450, 450)], iv=3)
    assert f(p, [e], 1000, 1000) == 'approaching'
    # 4 pts, 3 segments, decreasing 2/3 == 0.6667 >= 0.6 boundary-ish; 1 flat
    p = pts([(100, 100), (300, 300), (300, 300), (450, 450)], iv=3)
    assert f(p, [e], 1000, 1000) == 'approaching'
    # exactly at threshold: 3 segments, 2 decreasing 2/3
    # 6 pts: decreasing 3/5 == 0.6 EXACTLY at APPROACH threshold
    p = pts([(0, 0), (200, 200), (400, 400), (480, 480), (490, 490), (600, 600)], iv=3)
    # distances to (500,500): 707.1 424.3 141.4 28.3 14.1 141.4 -> dec: 4/5=0.8 approaching
    assert f(p, [e], 1000, 1000) == 'approaching'
    # exactly-0.6: 5 pts 4 segments, 3 decrease 1 increase = 0.75; use 10 pts 9 seg, 6 dec = 0.667
    # construct EXACT 0.6: 6 pts -> 5 segments -> 3 decreasing = 0.6
    p = pts([(100, 100), (400, 400), (100, 100), (440, 440), (110, 110), (450, 450)], iv=3)
    # d: 565.7 141.4 565.7 84.9 551.5 70.7 -> seq: - + - + -  => decreasing 3/5 = 0.6 EXACT
    assert f(p, [e], 1000, 1000) == 'approaching', 'exact 0.6 ratio must count as approaching (>=)'
    # monotone departing
    e2 = entry(coords=[[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]])  # center (100,100)
    p = pts([(150, 150), (300, 300), (500, 500), (700, 700), (800, 800)], iv=3)
    assert f(p, [e2], 1000, 1000) == 'departing'
    # exact 0.6 departing: same alternating trick -> increasing 2/5=0.4 NO; mirror: 5 seg 2 dec 3 inc = 0.6
    p = pts([(400, 400), (100, 100), (440, 440), (110, 110), (450, 450), (120, 120)], iv=3)
    # d(100,100): 424.3 0 480.8 14.1 494.9 28.3 -> + - + - + => increasing 3/5 = 0.6 EXACT
    assert f(p, [e2], 1000, 1000) == 'departing', 'exact 0.6 must be departing (>=)'
    # guard: 3 pts minimal still works
    p = pts([(100, 100), (300, 300), (450, 450)], iv=3)
    assert f(p, [e], 1000, 1000) == 'approaching'
    # 2 pts -> None
    p = pts([(100, 100), (300, 300)], iv=3)
    assert f(p, [e], 1000, 1000) is None
    # exact 3 pts boundary must return approaching, not None (kills <=3)
    assert f(p + [pts([(450, 450)], iv=3)[0]], [e], 1000, 1000) == 'approaching'

t2_vars = [
    ('1', '_check_approach_depart', 'if len(track_points) < 3:', 'if len(track_points) <= 3:'),
    ('2', '_check_approach_depart', 'if len(track_points) < 3:', 'if len(track_points) < 4:'),
    ('16', '_check_approach_depart', 'cx = sum(p[0] for p in coords) / len(coords) * video_width', 'cx = sum(p[1] for p in coords) / len(coords) * video_width'),
    ('42', '_check_approach_depart', 'decreasing = 0', 'decreasing = 1'),
    ('44', '_check_approach_depart', 'increasing = 0', 'increasing = 1'),
    ('46', '_check_approach_depart', 'total_segments = len(distances) - 1', 'total_segments = len(distances) + 1'),
    ('47', '_check_approach_depart', 'total_segments = len(distances) - 1', 'total_segments = len(distances) - 2'),
    ('50', '_check_approach_depart', 'for i in range(1, len(distances)):', 'for i in range(len(distances)):'),
    ('52', '_check_approach_depart', 'for i in range(1, len(distances)):', 'for i in range(2, len(distances)):'),
    ('53', '_check_approach_depart', 'if distances[i] < distances[i - 1]:', 'if distances[i] <= distances[i - 1]:'),
    ('55', '_check_approach_depart', 'if distances[i] < distances[i - 1]:', 'if distances[i] < distances[i - 2]:'),
    ('58', '_check_approach_depart', 'decreasing += 1', 'decreasing += 2'),
    ('59', '_check_approach_depart', 'elif distances[i] > distances[i - 1]:', 'elif distances[i] >= distances[i - 1]:'),
    ('61', '_check_approach_depart', 'elif distances[i] > distances[i - 1]:', 'elif distances[i] > distances[i - 2]:'),
    ('64', '_check_approach_depart', 'increasing += 1', 'increasing += 2'),
    ('65', '_check_approach_depart', 'if total_segments > 0:', 'if total_segments >= 0:'),
    ('66', '_check_approach_depart', 'if total_segments > 1:', 'if total_segments > 1:'),  # placeholder fixed below
    ('67', '_check_approach_depart', 'if decreasing / total_segments >= APPROACH_CONSISTENCY_THRESHOLD:', 'if decreasing * total_segments >= APPROACH_CONSISTENCY_THRESHOLD:'),
    ('68', '_check_approach_depart', 'if decreasing / total_segments >= APPROACH_CONSISTENCY_THRESHOLD:', 'if decreasing / total_segments > APPROACH_CONSISTENCY_THRESHOLD:'),
    ('71', '_check_approach_depart', 'if increasing / total_segments >= DEPART_CONSISTENCY_THRESHOLD:', 'if increasing * total_segments >= DEPART_CONSISTENCY_THRESHOLD:'),
    ('72', '_check_approach_depart', 'if increasing / total_segments >= DEPART_CONSISTENCY_THRESHOLD:', 'if increasing / total_segments > DEPART_CONSISTENCY_THRESHOLD:'),
]
verify('check_approach_depart_ratios', t2, t2_vars)

# ================================================================ T3 is_approaching_entry_point
def t3(ns):
    f = ns['_is_approaching_entry_point']
    e = entry()  # center (500,500)
    # 3 points (len==3): recent window = all 3. kills <2-><=2/<3 mutants
    p = pts([(100, 100), (300, 300), (450, 450)], iv=3)
    assert f(p, [e], 1000, 1000) is True
    # exactly 2 points
    p = pts([(100, 100), (450, 450)], iv=3)
    assert f(p, [e], 1000, 1000) is True
    # departing is False
    e2 = entry(coords=[[0.05, 0.05], [0.15, 0.05], [0.15, 0.15], [0.05, 0.15]])
    p = pts([(200, 200), (400, 400), (600, 600), (800, 800)], iv=3)
    assert f(p, [e2], 1000, 1000) is False
    # recent-window semantics: 7 pts where EARLY segment approaches but LAST 5 depart
    # recent_points = pts[-5:] -> indices 2..6 must dominate
    p = pts([(900, 900), (850, 850),          # far, getting closer (ignored by window)
            (300, 300), (600, 600), (700, 700), (800, 800), (950, 950)], iv=3)
    # window idx2..6: 300,300 -> 950,950 : first_dist 283, last_dist 636 -> moving away -> False
    assert f(p, [e], 1000, 1000) is False, 'recent-window (last<=5) semantics: early approach must not leak in'
    # equal distances -> False (strict <)
    e3 = entry(coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])  # center 500,500
    p = pts([(0, 500), (300, 900), (1000, 500)], iv=3)
    # d: first (0,500)->500 ; last (1000,500)->500 equal -> False
    assert f(p, [e3], 1000, 1000) is False, 'equal distances must be False (strict <)'
    # zone center denorm: asymmetric zone so cx != cy
    ez = {'name': 'E', 'zone_type': 'entry_point',
          'coordinates': [[0.9, 0.1], [0.95, 0.1], [0.95, 0.3], [0.9, 0.3]]}  # cx=925, cy=200
    p = pts([(925, 900), (925, 500)], iv=3)   # y approaching
    assert f(p, [ez], 1920, 1080) is True
    p = pts([(100, 200), (600, 200)], iv=3)   # x approaching toward cx=925
    assert f(p, [ez], 1920, 1080) is True
    # with w/h swapped in denorm (cx uses height): cy=200*... -> kills mutant 26 via x-approach
    p = pts([(1800, 200), (1000, 200)], iv=3)  # x DEPARTING from 925 if cx correct -> False; cx=200ish -> True
    assert f(p, [ez], 1920, 1080) is False, 'cx must denormalize with video_width'

t3_vars = [
    ('8', '_is_approaching_entry_point', 'if not entry_zones or len(track_points) < 2:', 'if not entry_zones and len(track_points) < 2:'),
    ('10', '_is_approaching_entry_point', 'if not entry_zones or len(track_points) < 2:', 'if not entry_zones or len(track_points) <= 2:'),
    ('11', '_is_approaching_entry_point', 'if not entry_zones or len(track_points) < 2:', 'if not entry_zones or len(track_points) < 3:'),
    ('26', '_is_approaching_entry_point', 'cx = sum(p[0] for p in coords) / len(coords) * video_width', 'cx = sum(p[1] for p in coords) / len(coords) * video_width'),
    ('40', '_is_approaching_entry_point', 'recent_points = track_points[-min(5, len(track_points)) :]', 'recent_points = track_points[-min(6, len(track_points)) :]'),
    ('41', '_is_approaching_entry_point', 'if len(recent_points) < 2:', 'if len(recent_points) <= 2:'),
    ('42', '_is_approaching_entry_point', 'if len(recent_points) < 2:', 'if len(recent_points) < 3:'),
    ('57', '_is_approaching_entry_point', 'first_dist = min_dist_to_entries(recent_points[0]["x"], recent_points[0]["y"])', 'first_dist = min_dist_to_entries(recent_points[1]["x"], recent_points[0]["y"])'),
    ('60', '_is_approaching_entry_point', 'first_dist = min_dist_to_entries(recent_points[0]["x"], recent_points[0]["y"])', 'first_dist = min_dist_to_entries(recent_points[0]["x"], recent_points[1]["y"])'),
    ('68', '_is_approaching_entry_point', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-1]["y"])', 'last_dist = min_dist_to_entries(recent_points[+1]["x"], recent_points[-1]["y"])'),
    ('69', '_is_approaching_entry_point', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-1]["y"])', 'last_dist = min_dist_to_entries(recent_points[-2]["x"], recent_points[-1]["y"])'),
    ('72', '_is_approaching_entry_point', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-1]["y"])', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[+1]["y"])'),
    ('73', '_is_approaching_entry_point', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-1]["y"])', 'last_dist = min_dist_to_entries(recent_points[-1]["x"], recent_points[-2]["y"])'),
    ('76', '_is_approaching_entry_point', 'return last_dist < first_dist', 'return last_dist <= first_dist'),
    ('46', '_is_approaching_entry_point', 'return min(math.sqrt((px - cx) ** 2 + (py - cy) ** 2) for cx, cy in zone_centers)', 'return min(math.sqrt((px - cx) * 2 + (py - cy) ** 2) for cx, cy in zone_centers)'),
    ('49', '_is_approaching_entry_point', 'return min(math.sqrt((px - cx) ** 2 + (py - cy) ** 2) for cx, cy in zone_centers)', 'return min(math.sqrt((px - cx) ** 2 + (py - cy) * 2) for cx, cy in zone_centers)'),
]
verify('is_approaching_entry_point', t3, t3_vars)

for name, r in RESULTS.items():
    print('=' * 20, name)
    print('  orig:', r['orig'])
    for k, v in r['mutants'].items():
        mark = 'KILLED' if not v.startswith(('**NOT', 'ANCHOR')) else v
        print(f'  mut_{k:>3}: {mark}')

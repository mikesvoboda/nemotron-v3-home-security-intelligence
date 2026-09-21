import sys
sys.path.insert(0, '/tmp/wp25/wp44-triage/traj')
from lib import *
from datetime import datetime, timedelta

# ===== T6 build_summary =====
def t6(ns):
    f = ns['_build_summary']; A = ns['TrajectoryAnalysis']
    a = A(track_id=1, dwell_seconds=30.0, movement_pattern='stationary', speed_estimate=1.0)
    s = f(1, 'person', a)
    assert s == "Person #1: stationary for 30s. Speed: stationary."
    a = A(track_id=2, dwell_seconds=0.0, movement_pattern='wandering', speed_estimate=0.0)
    assert f(2, 'car', a) == "Car #2: wandering. Speed: stationary."
    a = A(track_id=3, dwell_seconds=3600.0, movement_pattern='stationary', speed_estimate=0.0)
    assert '60min' in f(3, 'person', a)
    a = A(track_id=4, dwell_seconds=3599.0, movement_pattern='stationary', speed_estimate=0.0)
    assert '3599s' in f(4, 'person', a)
    a = A(track_id=5, dwell_seconds=15.0, movement_pattern='wandering', speed_estimate=20.0,
          zone_transitions=['entered Driveway', 'exited Sidewalk'])
    s = f(5, 'person', a)
    assert 'Zone activity: entered Driveway, exited Sidewalk.' in s
    a = A(track_id=6, dwell_seconds=5.0, movement_pattern='approaching', speed_estimate=50.0, is_approaching_entry=True)
    s = f(6, 'person', a)
    assert s.endswith('WARNING: approaching entry point.')
    a = A(track_id=7, dwell_seconds=10.0, movement_pattern='wandering', speed_estimate=40.0,
          zone_transitions=['entered A'])
    s = f(7, 'person', a)
    assert s == "Person #7: wandering for 10s. Speed: moderate (brisk walk). Zone activity: entered A."

T6V = [
 ('5', 'if dwell > 0:', 'if dwell >= 0:'),
 ('6', 'if dwell > 0:', 'if dwell > 1:'),
 ('10', 'if dwell < 3600 else', 'if dwell <= 3600 else'),
 ('11', 'if dwell < 3600 else', 'if dwell < 3601 else'),
 ('12', 'f"{dwell / 60:.0f}min"', 'f"{dwell * 60:.0f}min"'),
 ('13', 'f"{dwell / 60:.0f}min"', 'f"{dwell / 61:.0f}min"'),
 ('20', '{\', \'.join(analysis.zone_transitions)}', '{\'XX, XX\'.join(analysis.zone_transitions)}'),
 ('22', 'parts.append("WARNING: approaching entry point")', 'parts.append("XXWARNING: approaching entry pointXX")'),
 ('23', 'parts.append("WARNING: approaching entry point")', 'parts.append("warning: approaching entry point")'),
 ('24', 'parts.append("WARNING: approaching entry point")', 'parts.append("WARNING: APPROACHING ENTRY POINT")'),
 ('27', 'return ". ".join(parts) + "."', 'return "XX. XX".join(parts) + "."'),
 ('28', 'return ". ".join(parts) + "."', 'return ". ".join(parts) + "XX.XX"'),
]
r = verify('T6', t6, T6V)
print('== T6'); report(r)

# ===== T7 zone transitions / polygon =====
def t7(ns):
    f = ns['_detect_zone_transitions']; pip = ns['_point_in_polygon']
    DZ = zone('Driveway', coords=[[0.0, 0.0], [0.3, 0.0], [0.3, 0.3], [0.0, 0.3]])
    IN = zone('Porch', coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])
    assert f(pts([(100, 100), (500, 500)], iv=5), [DZ], 1000, 1000) == ['exited Driveway']
    assert f(pts([(100, 100), (500, 500)], iv=5), [IN], 1000, 1000) == ['entered Porch']
    assert f(pts([(500, 500), (100, 100)], iv=5), [IN], 1000, 1000) == ['exited Porch']
    assert f(pts([(100, 100), (150, 150)], iv=5), [DZ], 1000, 1000) == []
    assert f(pts([(1, 1), (2, 2)]), [], 10, 10) == []
    assert f([], [DZ], 10, 10) == []
    assert f(pts([(100, 100), (500, 500)], iv=5), [{'name': 'E', 'zone_type': 'x', 'coordinates': []}], 1000, 1000) == []
    assert f(pts([(100, 100), (500, 500)], iv=5), [{'zone_type': 'x'}], 1000, 1000) == []
    assert f(pts([(100, 100), (500, 500)], iv=5), [{'zone_type': 'x', 'coordinates': [[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]]}], 1000, 1000) == ['entered Unknown']
    zA = zone('Alpha', coords=[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]])
    zB = zone('Beta', coords=[[0.45, 0.45], [0.55, 0.45], [0.55, 0.55], [0.45, 0.55]])
    assert f(pts([(100, 100), (500, 500)], iv=5), [zB, zA], 1000, 1000) == ['entered Alpha', 'entered Beta']
    assert pip(1.0, 0.75, [[0, 0], [1, 0], [1, 1], [0, 1]]) is False
    assert pip(0.5, 0.5, [[0, 0], [1, 0], [1, 1], [0, 1]]) is True
    assert pip(1.5, 0.5, [[0, 0], [1, 0], [1, 1], [0, 1]]) is False
    assert pip(0.5, 1.0, [[0, 0], [4, 0], [1, 2]]) is True

T7V = [
 ('1', 'if not zones or not track_points:', 'if not zones and not track_points:'),
 ('5', 'prev_in_zones: set[str] = set()', 'prev_in_zones: set[str] = None'),
 ('18', 'coords = zone.get("coordinates", [])', 'coords = zone.get("coordinates", None)'),
 ('41', 'if i > 0:', 'if i >= 0:'),
 ('6', 'j = n - 1', 'j = n - 2'),
 ('14', 'and (px < (xj - xi) * (py - yi) / (yj - yi) + xi)', 'and (px <= (xj - xi) * (py - yi) / (yj - yi) + xi)'),
 ('16', 'and (px < (xj - xi) * (py - yi) / (yj - yi) + xi)', 'and (px < (xj - xi) * (py - yi) * (yj - yi) + xi)'),
]
r = verify('T7', t7, T7V)
print('== T7'); report(r)

# ===== T8 parse_timestamps =====
def t8(ns):
    f = ns['_parse_timestamps']
    p = pts([(0, 0), (1, 1)], iv=5)
    p[0]['timestamp'] = 'bogus'
    assert len(f(p)) == 1
    p2 = [{'x': 0, 'y': 0, 'timestamp': None}] + pts([(1, 1), (2, 2)], iv=5)
    assert len(f(p2)) == 2

T8V = [
 ('7', 'continue\n    return timestamps', 'break\n    return timestamps'),
 ('12', '        if ts is None:\n            continue', '        if ts is None:\n            break'),
]
r = verify('T8', t8, T8V)
print('== T8'); report(r)

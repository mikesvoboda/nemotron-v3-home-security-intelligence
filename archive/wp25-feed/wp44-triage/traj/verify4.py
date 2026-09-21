import sys
sys.path.insert(0, '/tmp/wp25/wp44-triage/traj')
from lib import *
from datetime import datetime, timedelta

A = BASE['TrajectoryAnalysis']
TA = BASE['TrajectoryAnalyzer']
SPD = 'result.speed_estimate = round(total_distance / duration, 2) if duration > 0 else 0.0'

# ===================== T5 analyze_trajectory (final) =====================
def t5(ns):
    TA = ns['TrajectoryAnalyzer']
    base = datetime(2026, 1, 26, 12, 0, 0)
    # zero duration: dwell clamped to 0.0, speed 0.0, no ZeroDivisionError
    p = [{'x': 0, 'y': 0, 'timestamp': base.isoformat()}, {'x': 10, 'y': 0, 'timestamp': base.isoformat()}]
    r = TA.analyze_trajectory(track_id=9, track_points=p, object_class='person')
    assert r.dwell_seconds == 0.0
    assert r.speed_estimate == 0.0
    # sub-second real speed: 5px over 0.5s = 10.0 px/s
    r = TA.analyze_trajectory(track_id=9, track_points=pts([(0, 0), (0, 5)], iv=0.5), object_class='person')
    assert r.speed_estimate == 10.0
    # rounded to 2 decimals: 100px / 3s = 33.33 (kills round-places mutants)
    r = TA.analyze_trajectory(track_id=9, track_points=pts([(0, 0), (100, 0)], iv=3), object_class='person')
    assert r.speed_estimate == 33.33
    # 2-point trajectory is NOT the single-observation path
    r = TA.analyze_trajectory(track_id=42, track_points=pts([(0, 0), (0, 10)], iv=5), object_class='person')
    assert r.movement_pattern == 'wandering'
    assert 'single observation' not in r.trajectory_summary
    assert '#42' in r.trajectory_summary
    r = TA.analyze_trajectory(track_id=5, track_points=pts([(100, 200)]), object_class='person')
    assert 'single observation' in r.trajectory_summary
    # zones + only one dimension: graceful skip
    p6 = pts([(100, 100), (500, 500), (900, 900)], iv=5)
    r = TA.analyze_trajectory(track_id=1, track_points=p6, zones=[zone('T')], object_class='person', video_width=1000)
    assert r.zone_transitions == [] and r.is_approaching_entry is False
    r = TA.analyze_trajectory(track_id=1, track_points=p6, zones=[zone('T')], object_class='person', video_height=1000)
    assert r.zone_transitions == [] and r.is_approaching_entry is False
    # full pipeline pass-through
    p7 = pts([(100, 100), (200, 200), (300, 300), (400, 400), (450, 450)], iv=3)
    r = TA.analyze_trajectory(track_id=7, track_points=p7, zones=[zone('Driveway'), E1], object_class='person', video_width=1000, video_height=1000)
    assert r.movement_pattern == 'approaching'
    assert len(r.zone_transitions) > 0
    assert r.is_approaching_entry is True

T5V = [
 ('8', 'if len(track_points) < 2:', 'if len(track_points) <= 2:'),
 ('9', 'if len(track_points) < 2:', 'if len(track_points) < 3:'),
 ('27', 'result.dwell_seconds = max(duration, 0.0)', 'result.dwell_seconds = max(duration, 1.0)'),
 ('32', SPD, 'result.speed_estimate = round(total_distance / duration, 2) if (duration > 0) or True else 0.0'),
 ('34', SPD, 'result.speed_estimate = round(total_distance / duration, None) if duration > 0 else 0.0'),
 ('36', SPD, 'result.speed_estimate = round(total_distance / duration, ) if duration > 0 else 0.0'),
 ('38', SPD, 'result.speed_estimate = round(total_distance / duration, 3) if duration > 0 else 0.0'),
 ('39', SPD, 'result.speed_estimate = round(total_distance / duration, 2) if duration >= 0 else 0.0'),
 ('40', SPD, 'result.speed_estimate = round(total_distance / duration, 2) if duration > 1 else 0.0'),
 ('41', SPD, 'result.speed_estimate = round(total_distance / duration, 2) if duration > 0 else 1.0'),
 ('46', 'track_points, total_distance, duration, zones, video_width, video_height', 'track_points, total_distance, duration, None, video_width, video_height'),
 ('47', 'track_points, total_distance, duration, zones, video_width, video_height', 'track_points, total_distance, duration, zones, None, video_height'),
 ('48', 'track_points, total_distance, duration, zones, video_width, video_height', 'track_points, total_distance, duration, zones, video_width, None'),
 ('55', 'if zones and video_width and video_height:', 'if zones and video_width or video_height:'),
 ('76', 'track_id=track_id,', 'track_id=None,'),
]
r = verify('T5', t5, T5V)
print('== T5'); report(r)

# ===================== T6 build_summary (final) =====================
def t6(ns):
    f = ns['_build_summary']
    A = ns['TrajectoryAnalysis']
    a = A(track_id=1, dwell_seconds=30.0, movement_pattern='stationary', speed_estimate=1.0)
    assert f(1, 'person', a) == "Person #1: stationary for 30s. Speed: stationary."
    a = A(track_id=2, dwell_seconds=0.0, movement_pattern='wandering', speed_estimate=0.0)
    assert f(2, 'car', a) == "Car #2: wandering. Speed: stationary."
    a = A(track_id=3, dwell_seconds=3600.0, movement_pattern='stationary', speed_estimate=0.0)
    assert '60min' in f(3, 'person', a)
    a = A(track_id=4, dwell_seconds=3599.0, movement_pattern='stationary', speed_estimate=0.0)
    assert '3599s' in f(4, 'person', a)
    a = A(track_id=5, dwell_seconds=15.0, movement_pattern='wandering', speed_estimate=20.0,
          zone_transitions=['entered Driveway', 'exited Sidewalk'])
    assert 'Zone activity: entered Driveway, exited Sidewalk.' in f(5, 'person', a)
    a = A(track_id=6, dwell_seconds=5.0, movement_pattern='approaching', speed_estimate=50.0, is_approaching_entry=True)
    assert f(6, 'person', a).endswith('WARNING: approaching entry point.')
    a = A(track_id=7, dwell_seconds=10.0, movement_pattern='wandering', speed_estimate=40.0,
          zone_transitions=['entered A'])
    assert f(7, 'person', a) == "Person #7: wandering for 10s. Speed: moderate (brisk walk). Zone activity: entered A."
    a = A(track_id=8, dwell_seconds=0.5, movement_pattern='wandering', speed_estimate=0.0)
    assert 'for 0s' in f(8, 'person', a)
    a = A(track_id=1, dwell_seconds=45.0, movement_pattern='stationary', speed_estimate=2.1,
          zone_transitions=['entered Front Porch'])
    s = f(1, 'person', a)
    assert 'None' not in s  # (kills pattern/speed None-substitution via a non-stationary speed)
    a = A(track_id=1, dwell_seconds=45.0, movement_pattern='loitering', speed_estimate=2.1)
    assert 'loitering' in f(1, 'person', a)

T6V = [
 ('3', 'pattern = analysis.movement_pattern', 'pattern = None'),
 ('5', 'if dwell > 0:', 'if dwell >= 0:'),
 ('6', 'if dwell > 0:', 'if dwell > 1:'),
 ('9', 'if dwell < 3600 else', 'if (dwell < 3600) or True else'),
 ('10', 'if dwell < 3600 else', 'if dwell <= 3600 else'),
 ('11', 'if dwell < 3600 else', 'if dwell < 3601 else'),
 ('12', 'f"{dwell / 60:.0f}min"', 'f"{dwell * 60:.0f}min"'),
 ('13', 'f"{dwell / 60:.0f}min"', 'f"{dwell / 61:.0f}min"'),
 ('15', 'speed_desc = _describe_speed(analysis.speed_estimate)', 'speed_desc = None'),
 ('20', '{\', \'.join(analysis.zone_transitions)}', '{\'XX, XX\'.join(analysis.zone_transitions)}'),
 ('22', 'parts.append("WARNING: approaching entry point")', 'parts.append("XXWARNING: approaching entry pointXX")'),
 ('23', 'parts.append("WARNING: approaching entry point")', 'parts.append("warning: approaching entry point")'),
 ('24', 'parts.append("WARNING: approaching entry point")', 'parts.append("WARNING: APPROACHING ENTRY POINT")'),
 ('27', 'return ". ".join(parts) + "."', 'return "XX. XX".join(parts) + "."'),
 ('28', 'return ". ".join(parts) + "."', 'return ". ".join(parts) + "XX.XX"'),
]
r = verify('T6', t6, T6V)
print('== T6'); report(r)

# ===================== T7 zone transitions / polygon (final) =====================
def t7(ns):
    f = ns['_detect_zone_transitions']
    pip = ns['_point_in_polygon']
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
    # last-edge wrap (j=n-1) parity: point left of hypotenuse is OUTSIDE
    assert pip(0.25, 0.75, [[0, 0], [1, 0], [1, 1]]) is False

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

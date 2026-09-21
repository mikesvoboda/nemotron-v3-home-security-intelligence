"""Verification harness (READ-ONLY w.r.t. repo; pure local exec of extracted source).
For each surviving mutant key, apply its single-line diff to the original function
source, exec it, and compare outputs against the original across a fixture set."""
import re, json, random, __future__, collections

SRC = open('/agents/agent-nemo2/workspace/backend/services/pose_analysis_service.py').read()

# ---- parse diffs into key -> (old_line, new_line) ----
import json
DIFFS = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))

def apply_diff(s, d):
    lines = s.split('\n')
    idx = [i for i,l in enumerate(lines) if l == d['old']]
    if len(idx) > 1:
        idx = [i for i in idx if i>0 and lines[i-1] == d['prev']]
    assert len(idx) == 1, (d['old'], idx)
    lines[idx[0]] = d['new']
    return '\n'.join(lines)
# ---- extract function sources ----
def extract(fname):
    m = re.search(rf'\ndef {fname}\(.*?(?=\ndef |\Z)', SRC, re.S)
    return m.group(0)

FUNCS = {k: extract(k) for k in
         ['detect_lying_down','detect_hands_raised','detect_fighting_stance','detect_security_alerts','analyze_pose','detect_crouching','normalize_posture','keypoints_to_coco_array','count_valid_keypoints']}

TH = 0.3
class KP:
    def __init__(self, x, y, c=0.9): self.x, self.y, self.confidence = float(x), float(y), float(c)
def gk(kp, name):
    k = kp.get(name)
    return k if (k is not None and k.confidence >= TH) else None
def gk_mutname(kp, name):  # mutant calls it with None/garbage -> dict.get returns None
    k = kp.get(name)
    return k if (k is not None and k.confidence >= TH) else None
POSTURE_MAP = {"standing":"standing","walking":"walking","running":"running","sitting":"sitting",
               "crouching":"crouching","lying":"lying_down","unknown":"unknown"}
KEYPOINT_NAMES = [str(i) for i in range(17)]
class PoseResult:
    def __init__(self, keypoints, pose_class, pose_confidence):
        self.keypoints, self.pose_class, self.pose_confidence = keypoints, pose_class, pose_confidence

def build_ns(func_src):
    ns = dict(KP=KP, gk=gk, KEYPOINT_NAMES=KEYPOINT_NAMES, POSTURE_MAP=POSTURE_MAP,
              PoseResult=PoseResult, Any=dict)
    code = compile(func_src, '<f>', 'exec', __future__.annotations.compiler_flag)
    exec(code, ns)
    return ns

def make_func(fname, old=None, new=None, extra_ns=None):
    src = FUNCS[fname]
    if old is not None:
        assert src.count(old) == 1, f'anchor not unique for {fname}: {old!r} count={src.count(old)}'
        src = src.replace(old, new, 1)
    ns = build_ns(src)
    if extra_ns: ns.update(extra_ns)
    return ns[fname], ns

ALLF = ['keypoints_to_coco_array','count_valid_keypoints','_get_keypoint_if_confident',
        'detect_crouching','detect_lying_down','detect_hands_raised','detect_fighting_stance',
        'detect_security_alerts','normalize_posture','analyze_pose','analyze_poses_batch',
        'create_empty_pose_enrichment']
BASE = dict(KP=KP, KEYPOINT_NAMES=KEYPOINT_NAMES, POSTURE_MAP=POSTURE_MAP,
            PoseResult=PoseResult, Any=dict)
FULL = dict(BASE)
for fn in ALLF:
    exec(compile(FUNCS.get(fn) or '', '<'+fn+'>', 'exec', __future__.annotations.compiler_flag), FULL)
ALL_NAMES = [f'_{p}' for p in ['nose','left_eye','right_eye','left_ear','right_ear','left_shoulder',
    'right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip',
    'left_knee','right_knee','left_ankle','right_ankle']]
FULL['KEYPOINT_NAMES'] = ALL_NAMES
FULL['logger'] = None

def mutant_func(key):
    fname = key.split('.')[-1].rsplit('__mutmut_',1)[0]
    fname = fname.replace('x_','') if fname.startswith('x_') else fname
    old, new = DIFFS[key]
    ns = dict(FULL)
    src = FUNCS[fname]
    assert src.count(old) == 1, (key, old)
    src = src.replace(old, new, 1)
    exec(compile(src, '<m>', 'exec', __future__.annotations.compiler_flag), ns)
    return ns[fname], FULL[fname]

def K(x,y,c=0.9): return KP(x,y,c)
FIX = {}
def add(name, kps): FIX[name] = kps

# lying fixtures
add('L.both_horizontal', dict(left_shoulder=K(50,100), right_shoulder=K(100,105), left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.left_only_horiz', dict(left_shoulder=K(50,100), left_ankle=K(350,100)))
add('L.right_only_horiz', dict(right_shoulder=K(50,100), right_ankle=K(350,100)))
add('L.both_vertical', dict(left_shoulder=K(100,50), right_shoulder=K(150,50), left_ankle=K(105,350), right_ankle=K(145,350)))
add('L.left_only_vert', dict(left_shoulder=K(100,50), left_ankle=K(105,350)))
add('L.right_only_vert', dict(right_shoulder=K(100,50), right_ankle=K(105,350)))
add('L.no_shoulder', dict(left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.no_ankle', dict(left_shoulder=K(50,100), right_shoulder=K(100,105)))
add('L.LL', dict(left_shoulder=K(50,100), left_ankle=K(350,100)))
add('L.RA_only', dict(right_shoulder=K(50,100), left_ankle=K(350,100)))
add('L.aligned_horiz', dict(left_shoulder=K(50,100), right_shoulder=K(100,100), left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.ratio_1_5', dict(left_shoulder=K(0,0), right_shoulder=K(20,0), left_ankle=K(50,40), right_ankle=K(50,40)))  # hs=50 vs=40
add('L.lowconf', dict(left_shoulder=K(50,100,0.2), right_shoulder=K(100,100,0.2), left_ankle=K(350,100,0.2), right_ankle=K(400,100,0.2)))
add('L.zero_all', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(0,0), right_ankle=K(0,0)))
add('L.slight_horiz', dict(left_shoulder=K(0,100), right_shoulder=K(0,100), left_ankle=K(300,110), right_ankle=K(300,110)))  # hs300 vs10
add('L.ratio_20', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(100,50), right_ankle=K(100,50)))
add('L.neg_horiz', dict(left_shoulder=K(-100,100), right_shoulder=K(-100,100), left_ankle=K(300,100), right_ankle=K(300,100)))

# hands fixtures
add('H.raised', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,50), right_wrist=K(220,50)))
add('H.at_shoulder', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,145), right_wrist=K(220,145)))
add('H.one_wrist', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,50)))
add('H.one_up', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,50), right_wrist=K(220,200)))
add('H.no_shoulder', dict(left_wrist=K(80,50), right_wrist=K(220,50)))
add('H.LS_only', dict(left_shoulder=K(100,150), left_wrist=K(80,50), right_wrist=K(220,50)))
add('H.RS_only', dict(right_shoulder=K(200,150), left_wrist=K(80,50), right_wrist=K(220,50)))
add('H.at_margin', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,140), right_wrist=K(220,140)))
add('H.at_m11', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,141), right_wrist=K(220,141)))
add('H.asym', dict(left_shoulder=K(100,100), right_shoulder=K(200,200), left_wrist=K(80,60), right_wrist=K(220,60)))
add('H.asym2', dict(left_shoulder=K(100,100), right_shoulder=K(200,200), left_wrist=K(80,120), right_wrist=K(220,120)))
add('H.Lwrist_only_up', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,139), right_wrist=K(220,141)))
add('H.Rwrist_only_up', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,141), right_wrist=K(220,139)))
add('H.mixed', dict(left_shoulder=K(100,200), right_shoulder=K(200,100), left_wrist=K(80,60), right_wrist=K(220,60)))
add('H.lowconf', dict(left_shoulder=K(100,150,0.2), right_shoulder=K(200,150,0.2), left_wrist=K(80,50), right_wrist=K(220,50)))

# fighting fixtures
add('F.detect', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(50,380), right_ankle=K(200,330)))
add('F.narrow_y', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(50,350), right_ankle=K(200,350)))
add('F.wide_y', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(50,350), right_ankle=K(200,200)))
add('F.standing', dict(left_hip=K(110,150), right_hip=K(140,150), left_ankle=K(115,350), right_ankle=K(135,350)))
add('F.no_hip', dict(left_ankle=K(50,380), right_ankle=K(200,330)))
add('F.LH_only', dict(left_hip=K(100,150), left_ankle=K(50,380), right_ankle=K(200,330)))
add('F.RH_only', dict(right_hip=K(150,150), left_ankle=K(50,380), right_ankle=K(200,330)))
add('F.LA_only', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(50,380)))
add('F.RA_only', dict(left_hip=K(100,150), right_hip=K(150,150), right_ankle=K(200,330)))
add('F.b20', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(200,380), right_ankle=K(100,330)))
add('F.b40', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(300,380), right_ankle=K(100,330)))
add('F.b45', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(325,380), right_ankle=K(100,330)))
add('F.b15', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(175,380), right_ankle=K(100,330)))
add('F.exact_y', dict(left_hip=K(100,150), right_hip=K(150,150), left_ankle=K(50,380), right_ankle=K(200,355)))
add('F.zero_hip', dict(left_hip=K(100,150), right_hip=K(100,150), left_ankle=K(50,380), right_ankle=K(200,330)))
add('F.sub1_hip', dict(left_hip=K(100,150), right_hip=K(100.5,150), left_ankle=K(50,380), right_ankle=K(200,330)))

def call(fn, kps):
    try: return ('ok', fn(kps))
    except Exception as e: return ('err', type(e).__name__)

import itertools, collections as C
results = {}
groups = C.defaultdict(list)
for k in DIFFS: groups[k.split('.')[-1].rsplit('__mutmut_',1)[0]].append(k)
for fnkeys, keys in sorted(groups.items()):
    fname = fnkeys[2:] if fnkeys.startswith('x_') else fnkeys
    base = FULL[fname]
    if fname == 'detect_security_alerts':
        fixs = [(n, dict(kp, ), 'standing') for n,kp in FIX.items()] + [('posture:lying', {}, 'lying'), ('posture:lying_down', {}, 'lying_down'), ('posture:crouching', {}, 'crouching')]
        def invoke(f, fa):
            kp, post = fa
            try: return ('ok', f(kp, post))
            except Exception as e: return ('err', type(e).__name__)
        base_out = {n: invoke(base, fa) for n, fa in fixs}
    elif fname == 'analyze_pose':
        fixs = [(n, kp) for n,kp in FIX.items()] + [('post:standing', {}), ('post:lying', {})]
        def invoke(f, kp):
            pr = PoseResult(kp, 'standing', 0.8)
            try: return ('ok', f(pr))
            except Exception as e: return ('err', type(e).__name__)
        base_out = {n: invoke(base, kp) for n,kp in fixs}
    else:
        fixs = list(FIX.items())
        def invoke(f, kp):
            try: return ('ok', f(kp))
            except Exception as e: return ('err', type(e).__name__)
        base_out = {n: invoke(base, kp) for n,kp in fixs}
    for key in sorted(keys, key=lambda k:int(k.rsplit('__mutmut_',1)[1])):
        mf, _ = mutant_func(key)
        kills = [n for n, fa in ([(n, fa) for n,fa in fixs]) if invoke(mf, fa) != base_out[n]]
        print(f"{key.rsplit('.',1)[-1]:40s} base={set(v[0] for v in base_out.values())} KILLS:{len(kills)} :: {','.join(sorted(kills))[:400]}")

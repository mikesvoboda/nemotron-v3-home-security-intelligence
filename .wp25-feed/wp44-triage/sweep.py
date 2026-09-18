"""Sweep harness: execs REAL function source from the repo file (read-only) with a
per-mutant one-line substitution, compares mutant vs original across fixtures."""
import re, json, collections as C, __future__

SRC = open('/agents/agent-nemo2/workspace/backend/services/pose_analysis_service.py').read()
DIFFS = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))

def extract(fname):
    return re.search(rf'\ndef {fname}\(.*?(?=\ndef |\Z)', SRC, re.S).group(0)

FUNCS = {k: extract(k) for k in
    ['_get_keypoint_if_confident','detect_crouching','detect_lying_down','detect_hands_raised',
     'detect_fighting_stance','detect_security_alerts','normalize_posture','analyze_pose',
     'keypoints_to_coco_array','count_valid_keypoints','analyze_poses_batch',
     'create_empty_pose_enrichment']}

TH = 0.3
class KP:
    def __init__(self, x, y, c=0.9): self.x, self.y, self.confidence = float(x), float(y), float(c)
KEYPOINT_NAMES = [str(i) for i in range(17)]
POSTURE_MAP = {"standing":"standing","walking":"walking","running":"running","sitting":"sitting",
               "crouching":"crouching","lying":"lying_down","unknown":"unknown"}
class PoseResult:
    def __init__(self, keypoints, pose_class, pose_confidence):
        self.keypoints, self.pose_class, self.pose_confidence = keypoints, pose_class, pose_confidence

def apply_diff(s, d):
    lines = s.split('\n')
    idx = [i for i, l in enumerate(lines) if l == d['old']]
    if len(idx) > 1:
        idx = [i for i in idx if i > 0 and lines[i-1] == d['prev']]
    assert len(idx) == 1, (d['old'], idx)
    lines[idx[0]] = d['new']
    return '\n'.join(lines)

FULL = dict(KP=KP, ALERT_CONFIDENCE_THRESHOLD=TH, KEYPOINT_NAMES=KEYPOINT_NAMES,
            POSTURE_MAP=POSTURE_MAP, PoseResult=PoseResult, Any=dict, logger=None)
for fn, s in FUNCS.items():
    exec(compile(s, '<'+fn+'>', 'exec', __future__.annotations.compiler_flag), FULL)
FULL['KEYPOINT_NAMES'] = ['nose','left_eye','right_eye','left_ear','right_ear','left_shoulder',
 'right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip',
 'left_knee','right_knee','left_ankle','right_ankle']

def K(x, y, c=0.9): return KP(x, y, c)
FIX = {}
def add(n, k): FIX[n] = k
# lying
add('L.both_horizontal', dict(left_shoulder=K(50,100), right_shoulder=K(100,105), left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.left_only_horiz', dict(left_shoulder=K(50,100), left_ankle=K(350,100)))
add('L.right_only_horiz', dict(right_shoulder=K(50,100), right_ankle=K(350,100)))
add('L.both_vertical', dict(left_shoulder=K(100,50), right_shoulder=K(150,50), left_ankle=K(105,350), right_ankle=K(145,350)))
add('L.left_only_vert', dict(left_shoulder=K(100,50), left_ankle=K(105,350)))
add('L.right_only_vert', dict(right_shoulder=K(100,50), right_ankle=K(105,350)))
add('L.no_shoulder', dict(left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.no_ankle', dict(left_shoulder=K(50,100), right_shoulder=K(100,105)))
add('L.LS_RA', dict(left_shoulder=K(50,100), right_ankle=K(350,100)))
add('L.RS_LA', dict(right_shoulder=K(50,100), left_ankle=K(350,100)))
add('L.aligned_horiz', dict(left_shoulder=K(50,100), right_shoulder=K(100,100), left_ankle=K(350,100), right_ankle=K(400,100)))
add('L.ratio_1_5', dict(left_shoulder=K(0,0), right_shoulder=K(20,0), left_ankle=K(50,40), right_ankle=K(50,40)))
add('L.lowconf', dict(left_shoulder=K(50,100,0.2), right_shoulder=K(100,100,0.2), left_ankle=K(350,100,0.2), right_ankle=K(400,100,0.2)))
add('L.zero_all', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(0,0), right_ankle=K(0,0)))
add('L.slight_horiz', dict(left_shoulder=K(0,100), right_shoulder=K(0,100), left_ankle=K(300,110), right_ankle=K(300,110)))
add('L.ratio_20', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(100,50), right_ankle=K(100,50)))
add('L.neg_horiz', dict(left_shoulder=K(-100,100), right_shoulder=K(-100,100), left_ankle=K(300,100), right_ankle=K(300,100)))
add('L.vert50', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(0,50), right_ankle=K(0,50)))
add('L.vert100', dict(left_shoulder=K(0,0), right_shoulder=K(0,0), left_ankle=K(0,100), right_ankle=K(0,100)))
add('L.vert0_horiz0', dict(left_shoulder=K(100,100), right_shoulder=K(100,100), left_ankle=K(100,100), right_ankle=K(100,100)))
# hands
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
add('H.Lup_only', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,139), right_wrist=K(220,141)))
add('H.Rup_only', dict(left_shoulder=K(100,150), right_shoulder=K(200,150), left_wrist=K(80,141), right_wrist=K(220,139)))
add('H.mixed', dict(left_shoulder=K(100,200), right_shoulder=K(200,100), left_wrist=K(80,60), right_wrist=K(220,60)))
add('H.lowconf', dict(left_shoulder=K(100,150,0.2), right_shoulder=K(200,150,0.2), left_wrist=K(80,50), right_wrist=K(220,50)))
# fighting
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
add('F.zero_hip_b20', dict(left_hip=K(100,150), right_hip=K(100,150), left_ankle=K(120,380), right_ankle=K(100,330)))

def run(fn, fa):
    try: return ('ok', fn(*fa))
    except Exception as e: return ('err', type(e).__name__)

groups = C.defaultdict(list)
for k in DIFFS: groups[k.split('.')[-1].rsplit('__mutmut_',1)[0]].append(k)
summary = {}
for fnkeys, keys in sorted(groups.items()):
    fname = fnkeys[2:]
    base = FULL[fname]
    if fname == 'detect_security_alerts':
        fixs = [(n, (kp, 'standing')) for n, kp in FIX.items()] + \
               [('posture:lying', ({}, 'lying')), ('posture:lying_down', ({}, 'lying_down')),
                ('posture:crouching', ({}, 'crouching'))]
    elif fname == 'analyze_pose':
        fixs = [(n, (PoseResult(kp, 'standing', 0.8),)) for n, kp in FIX.items()] + \
               [('pr_lying', (PoseResult({}, 'lying', 0.5),)), ('pr_empty', (PoseResult({}, 'standing', 0.5),))]
    else:
        fixs = [(n, (kp,)) for n, kp in FIX.items()]
    base_out = {n: run(base, fa) for n, fa in fixs}
    errs = {n: v for n, v in base_out.items() if v[0] == 'err'}
    if errs: print(f'!! BASE ERR {fname}: {errs}')
    for key in sorted(keys, key=lambda k: int(k.rsplit('__mutmut_', 1)[1])):
        src = apply_diff(FUNCS[fname], DIFFS[key])
        ns = dict(FULL)
        exec(compile(src, '<m>', 'exec', __future__.annotations.compiler_flag), ns)
        mf = ns[fname]
        kills = [n for n, fa in fixs if run(mf, fa) != base_out[n]]
        summary[key] = kills
        num = key.rsplit('__mutmut_', 1)[1]
        print(f"{fname:24s} #{num:<5s} KILLS:{len(kills):3d} :: {','.join(sorted(kills))[:340]}")
json.dump({k.split('.')[-1]: v for k, v in summary.items()},
          open('/tmp/wp25/wp44-triage/killmatrix.json', 'w'))
zero = [k.split('.')[-1] for k, v in summary.items() if not v]
print('\nZERO-KILL (unreachable by these fixtures):', len(zero))
for z in sorted(zero): print('  ', z)

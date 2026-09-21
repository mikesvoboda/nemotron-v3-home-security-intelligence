"""Red/Green SIMULATION of the drafted pytest cases (not pytest — pure eval of the
same asserts) against original + every surviving mutant of the module."""
import re, json, collections as C, __future__

SRC = open('/agents/agent-nemo2/workspace/backend/services/pose_analysis_service.py').read()
DIFFS = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))
def extract(f): return re.search(rf'\ndef {f}\(.*?(?=\ndef |\Z)', SRC, re.S).group(0)
FUNCS = {k: extract(k) for k in ['_get_keypoint_if_confident','detect_crouching','detect_lying_down',
  'detect_hands_raised','detect_fighting_stance','detect_security_alerts','normalize_posture',
  'analyze_pose','keypoints_to_coco_array','count_valid_keypoints','analyze_poses_batch',
  'create_empty_pose_enrichment']}
TH=0.3
class KP:
    def __init__(s,x,y,c=0.9): s.x,s.y,s.confidence=float(x),float(y),float(c)
KEYPOINT_NAMES=[str(i) for i in range(17)]
POSTURE_MAP={"standing":"standing","walking":"walking","running":"running","sitting":"sitting",
             "crouching":"crouching","lying":"lying_down","unknown":"unknown"}
class PoseResult:
    def __init__(s,k,p,c): s.keypoints,s.pose_class,s.pose_confidence=k,p,c
def apply_diff(s,d):
    L=s.split('\n'); idx=[i for i,l in enumerate(L) if l==d['old']]
    if len(idx)>1: idx=[i for i in idx if i>0 and L[i-1]==d['prev']]
    assert len(idx)==1; L[idx[0]]=d['new']; return '\n'.join(L)
FULL=dict(KP=KP,ALERT_CONFIDENCE_THRESHOLD=TH,KEYPOINT_NAMES=KEYPOINT_NAMES,
          POSTURE_MAP=POSTURE_MAP,PoseResult=PoseResult,Any=dict,logger=None)
for fn,s in FUNCS.items(): exec(compile(s,'<f>','exec',__future__.annotations.compiler_flag),FULL)
FULL['KEYPOINT_NAMES']=['nose','left_eye','right_eye','left_ear','right_ear','left_shoulder',
 'right_shoulder','left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip',
 'left_knee','right_knee','left_ankle','right_ankle']

def K(x,y,c=0.9): return KP(x,y,c)
# ================= drafted test cases (case_name -> (func, args, expected)) =================
CASES=[]
def tc(name, fname, args, expected): CASES.append((name, fname, args, expected))

# --- test_lying_down_accepts_either_side_keypoint ---
tc('ly.left_only_lying','detect_lying_down',(dict(left_shoulder=K(100,100),left_ankle=K(300,100)),),True)
tc('ly.right_only_lying','detect_lying_down',(dict(right_shoulder=K(100,100),right_ankle=K(300,100)),),True)
tc('ly.cross_side_lying','detect_lying_down',(dict(right_shoulder=K(100,100),left_ankle=K(300,100)),),True)
tc('ly.right_only_standing','detect_lying_down',(dict(right_shoulder=K(100,100),right_ankle=K(105,500)),),False)
tc('ly.left_only_standing','detect_lying_down',(dict(left_shoulder=K(100,100),left_ankle=K(105,500)),),False)
# --- test_lying_down_uses_mean_of_each_side ---
tc('ly.aligned_lying','detect_lying_down',(dict(left_shoulder=K(50,100),right_shoulder=K(100,100),left_ankle=K(350,100),right_ankle=K(400,100)),),True)
tc('ly.offset_lying','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,200),left_ankle=K(300,100),right_ankle=K(400,100)),),True)
tc('ly.offset_standing','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,200),left_ankle=K(105,500),right_ankle=K(205,500)),),False)
# --- test_lying_down_vertical_span_branch_thresholds ---
tc('ly.zero_vertical','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(250,100),right_ankle=K(150,100)),),False)
tc('ly.ratio_above_1_5','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(300,140),right_ankle=K(400,160)),),True)
tc('ly.ratio_between','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(215,140),right_ankle=K(235,160)),),False)  # hs=75 vs=50 -> ratio exactly 1.5
tc('ly.ratio_2_2_5','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(240,140),right_ankle=K(260,160)),),True)  # hs=100 vs=50 -> 2.0x: above 1.5x, below 2.5x

# --- test_hands_raised_accepts_single_shoulder_and_uses_mean ---
tc('hd.LS_only','detect_hands_raised',(dict(left_shoulder=K(100,150),left_wrist=K(80,50),right_wrist=K(220,50)),),True)
tc('hd.RS_only','detect_hands_raised',(dict(right_shoulder=K(200,150),left_wrist=K(80,50),right_wrist=K(220,50)),),True)
tc('hd.no_shoulder','detect_hands_raised',(dict(left_wrist=K(80,50),right_wrist=K(220,50)),),False)
tc('hd.uneven_mean_true','detect_hands_raised',(dict(left_shoulder=K(100,100),right_shoulder=K(200,200),left_wrist=K(80,120),right_wrist=K(220,120)),),True)
tc('hd.uneven_mean_false','detect_hands_raised',(dict(left_shoulder=K(100,100),right_shoulder=K(200,200),left_wrist=K(80,145),right_wrist=K(220,145)),),False)
# --- test_hands_raised_requires_margin_over_shoulder_line ---
tc('hr.exactly_at_margin','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,140),right_wrist=K(220,140)),),False)
tc('hr.left_at_margin_right_raised','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,140),right_wrist=K(220,100)),),False)
tc('hr.right_at_margin_left_raised','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,100),right_wrist=K(220,140)),),False)
tc('hr.left_raised_right_just_below','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,139),right_wrist=K(220,141)),),False)
tc('hr.right_raised_left_just_below','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,141),right_wrist=K(220,139)),),False)
tc('hr.beyond_margin_by_one','detect_hands_raised',(dict(left_shoulder=K(100,150),right_shoulder=K(200,150),left_wrist=K(80,139),right_wrist=K(220,139)),),True)

# --- test_fighting_stance_requires_both_or_neither_side ---
tc('fs.LH_only','detect_fighting_stance',(dict(left_hip=K(100,150),left_ankle=K(50,380),right_ankle=K(200,330)),),False)
tc('fs.RH_only','detect_fighting_stance',(dict(right_hip=K(150,150),left_ankle=K(50,380),right_ankle=K(200,330)),),False)
tc('fs.LA_only','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(50,380)),),False)
tc('fs.RA_only','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),right_ankle=K(200,330)),),False)
# --- test_fighting_stance_ratio_and_asymmetry_boundaries ---
tc('fs.ratio_2_0','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(200,380),right_ankle=K(100,330)),),False)
tc('fs.ratio_4_0','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(300,380),right_ankle=K(100,330)),),False)
tc('fs.ratio_4_5','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(325,380),right_ankle=K(100,330)),),False)
tc('fs.ratio_1_5','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(175,380),right_ankle=K(100,330)),),False)
tc('fs.exact_y_threshold','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(50,380),right_ankle=K(200,355)),),False)
tc('fs.clamp15','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(101.5,150),left_ankle=K(100,380),right_ankle=K(103.5,380.6)),),False)
tc('fs.detect_wide_asym','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(50,380),right_ankle=K(200,330)),),True)
tc('fs.wide_y','detect_fighting_stance',(dict(left_hip=K(100,150),right_hip=K(150,150),left_ankle=K(50,350),right_ankle=K(200,200)),),True)

# --- test_security_alerts_accepts_normalized_lying_down_posture ---
tc('sa.lying_down','detect_security_alerts',({}, 'lying_down'),['lying_down'])
tc('sa.lying','detect_security_alerts',({}, 'lying'),['lying_down'])
# --- test_analyze_pose_laying_posture_produces_alert ---
tc('ap.lying','analyze_pose',(PoseResult({},'lying',0.5),),None)  # checked via ['alerts'] below


# --- extra discriminating fixtures (right-side drop, max(count,2) divisor, mid-wrist) ---
tc('ly.right_y_dropped_shoulder','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,200),left_ankle=K(250,100),right_ankle=K(290,100)),),True)   # mean sy=150 vs right-only 200
tc('ly.right_x_dropped_ankle','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(350,100),right_ankle=K(390,400)),),False)     # mean ax=370 -> hs=220 < 1.5*150; RA-only ax=390 -> hs=240 > 225
tc('ly.right_y_dropped_ankle','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(350,100),right_ankle=K(390,300)),),True)      # mean ay=200 -> vs=100 hs=220>150; RA-only ay=300 -> vs=200 -> False
tc('ly.den2_single_shoulder_x','detect_lying_down',(dict(left_shoulder=K(100,100),left_ankle=K(140,130)),),False)  # sx=100: hs=40 < 45; divisor-2 mutant sx=50 -> hs=90 -> True
tc('ly.den2_single_shoulder_y','detect_lying_down',(dict(left_shoulder=K(100,100),left_ankle=K(140,40)),),False)   # sy=100 vs=60 -> False; divisor-2 sy=50 -> vs=10 -> hs=40>15 True
tc('ly.den2_single_ankle_y','detect_lying_down',(dict(left_shoulder=K(100,100),left_ankle=K(140,190)),),False)     # ay=190: vs=90 -> False; divisor-2 ay=95 -> vs=5 -> True
tc('hd.LS_only_wrist_mid','detect_hands_raised',(dict(left_shoulder=K(100,150),left_wrist=K(80,120),right_wrist=K(220,120)),),True)  # sy=150 -> 120<140 True; divisor-2 sy=75 -> False


tc('ly.small_vertical_span','detect_lying_down',(dict(left_shoulder=K(100,100),right_shoulder=K(200,100),left_ankle=K(180,100),right_ankle=K(181,101)),),True)  # hs=30.5 vs=0.5 -> branch1 True; branch2 mutant (hs>50) False

def invoke(f, args):
    try: return ('ok', f(*args))
    except Exception as e: return ('err', type(e).__name__)

def check(fn_map):
    """returns list of failing case names"""
    fails=[]
    for name, fname, args, expected in CASES:
        r = invoke(fn_map[fname], args)
        if r[0] != 'ok': fails.append(name+':'+r[1]); continue
        if fname == 'analyze_pose':
            if r[1]['alerts'] != ['lying_down'] or r[1]['posture'] != 'lying_down': fails.append(name)
        elif isinstance(expected, list):
            if r[1] != expected: fails.append(name)
        else:
            if r[1] is not expected: fails.append(name)
    return fails

ORIG={fn: FULL[fn] for fn in set(f for _,f,_,_ in CASES)}
fails = check(ORIG)
print('GREEN on original:', 'PASS' if not fails else f'FAIL {fails}')

groups=C.defaultdict(list)
for k in DIFFS: groups[k.split('.')[-1].rsplit('__mutmut_',1)[0]].append(k)
killed=set()
for key in sorted(DIFFS, key=lambda k:(k.split('.')[-1], int(k.rsplit('__mutmut_',1)[1]))):
    fname=key.split('.')[-1].rsplit('__mutmut_',1)[0][2:]
    if fname not in set(f for _,f,_,_ in CASES): continue
    src=apply_diff(FUNCS[fname], DIFFS[key]); ns=dict(FULL)
    exec(compile(src,'<m>','exec',__future__.annotations.compiler_flag), ns)
    fmap=dict(ORIG); fmap[fname]=ns[fname]
    f2=check(fmap)
    short=key.split('.')[-1].replace('__mutmut_','#')
    if f2:
        killed.add(short)
        print(f'RED  {short:42s} killed_by={",".join(sorted(set(x.split(":")[0] for x in f2)))[:150]}')
    else:
        print(f'live {short}')
print(f'\nkilled {len(killed)} of draft-relevant mutants')
allk=set(k.split('.')[-1] for k in DIFFS)
print('survivors NOT addressed by these drafts:', len(allk-killed))
json.dump(sorted(killed), open('/tmp/wp25/wp44-triage/draft_kills.json','w'))

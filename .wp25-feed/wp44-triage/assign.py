import json, collections
d=json.load(open('/tmp/wp25/wp44-triage/variant_diffs.json'))
PRE='backend.services.depth_anything_loader.'
allkeys={}
for k in d:
    fn=k[len(PRE):].rsplit('__mutmut_',1)[0]
    n=int(k.rsplit('__mutmut_',1)[1])
    allkeys.setdefault(fn,set()).add(n)

def R(fn, nums): return {(fn,n) for n in nums}

C=[]  # (pattern, classification, members, note)
AD='x_analyze_depth'
C.append(("analyze_depth: dict.get key/default mutations on det_id extraction ('id' fallback, empty-string default) — fallback & skip paths never fed to analyze_depth","TEST-GAP",R(AD,[23,25,28,29,30,31,32,33,34]),""))
C.append(("analyze_depth: dict.get key/default mutations on class_name extraction ('label' fallback, 'object' default)","TEST-GAP",R(AD,[35,36,37,38,39,40,41,42,43,44,45,46,47,48,49]),""))
C.append(("analyze_depth: depth_pipeline called with None instead of image — mock returns depth map regardless of argument","TEST-GAP",R(AD,[4]),""))
C.append(("analyze_depth: logger.error call mutations on estimation-failure path (msg->None, exc_info tweaks) — message still logged, re-raise unchanged","EQUIVALENT",R(AD,[10,11,13,14]),""))
C.append(("analyze_depth: logger.error(exc_info=True) drops positional msg — if stdlib logger, TypeError replaces re-raise on pipeline-failure path (never exercised)","TEST-GAP",R(AD,[12]),""))
C.append(("analyze_depth: closest-detection tracking edge seeds/ties (init None->'', min_depth 1.0->2.0, < -> <=)","TEST-GAP",R(AD,[17,19,99]),""))
C.append(("analyze_depth: bbox/id skip-guard and list-arity mutations ('or'->'and', len>=4 'and'->'or', bbox[:4]->[:5]) — short/oversized bbox and missing-id paths untested","TEST-GAP",R(AD,[54,63,68]),""))
C.append(("analyze_depth: to_tuple duck-typing attribute mutations — BoundingBox-like bbox never passed by any test","TEST-GAP",R(AD,[57,61,62]),""))
C.append(("analyze_depth: depth_sampling_method kwarg dropped when calling get_depth_at_bbox — callers never pass a non-default method","TEST-GAP",R(AD,[75]),""))
C.append(("analyze_depth: DetectionDepth record fields set to None / is_approaching flipped — tests never assert per-detection field values","TEST-GAP",R(AD,[82,85,86,87,88,89,97]),""))
C.append(("analyze_depth: is_approaching=False kwarg removed — equals dataclass default","EQUIVALENT",R(AD,[95]),""))
C.append(("analyze_depth: has_close_objects computation mutations (in->not in, label-case literals, ->None, kwarg removed->default False) — has_close_objects never asserted","TEST-GAP",R(AD,[102,104,105,106,107,108,125,130]),""))
C.append(("analyze_depth: average_depth computation mutations (->None, ternary guard collapse, else 0.5->1.5, kwarg ->None/removed) — average_depth never asserted","TEST-GAP",R(AD,[109,110,111,114,126,131]),""))
C.append(("analyze_depth: depth_variance computation mutations (->None, guard flips, >1->>2, else 0.0->1.0, kwarg ->None/removed) — depth_variance never asserted","TEST-GAP",R(AD,[115,116,117,121,122,127,132]),""))
C.append(("analyze_depth: variance guard len>1 -> len>=1 — np.var([x]) == 0.0 equals original else-branch","EQUIVALENT",R(AD,[120]),""))
DF='x_depth_to_feet'
C.append(("depth_to_feet: calibration_points default [] -> None/removed — 'if not calibration_points' early-return makes it identical","EQUIVALENT",R(DF,[4,6]),""))
C.append(("depth_to_feet: bracketing boundary comparisons (<= -> <, >= -> >) — interpolation at an exact calibration node returns the same distance either way","EQUIVALENT",R(DF,[24,29]),""))
C.append(("depth_to_feet: multi-point bracketing degradation (lower/upper assignment & 'first>=depth' guard flips) — every test uses 2-point calibration so edge-pair fallback == bracket pair","TEST-GAP",R(DF,[25,26,30,31]),""))
C.append(("depth_to_feet: below-range extrapolation picks points[1] twice -> depth_range==0 -> returns wrong point's distance","TEST-GAP",R(DF,[34]),""))
C.append(("depth_to_feet: 'elif upper_point is None' -> 'is not None' -> above-range depth dereferences None (TypeError) instead of extrapolating","TEST-GAP",R(DF,[36]),""))
C.append(("depth_to_feet: clamp floor max(0.1, result) -> max(1.1, result)","TEST-GAP",R(DF,[69]),""))
C.append(("estimate_relative_distances: method kwarg dropped when calling get_depth_at_bbox — method pass-through untested","TEST-GAP",R('x_estimate_relative_distances',[6]),""))
FM='x_format_depth_for_nemotron'
C.append(("format_depth_for_nemotron: length-mismatch warning condition inverted / warning msg -> None — logging-only","EQUIVALENT",R(FM,[7,8]),""))
C.append(("format_depth_for_nemotron: zip strict=False -> None / kwarg removed — falsy/default identical","EQUIVALENT",R(FM,[12,15]),""))
C.append(("format_depth_for_nemotron: early-return guard 'not dets or not depths' -> 'and' — one-empty partial input no longer returns the sentinel string","TEST-GAP",R(FM,[1]),""))
WD='x_format_depth_for_nemotron_with_distances'
C.append(("format_depth_for_nemotron_with_distances: early-return guard 'or' -> 'and'","TEST-GAP",R(WD,[1]),""))
C.append(("format_depth_for_nemotron_with_distances: min-count 'count' arg removals & zip strict mutations — slice-to-min then zip-shortest yields identical output; all lists equal length post-slice","EQUIVALENT",R(WD,[4,8,9,10,18,22,23]),""))
C.append(("Nemotron formatters: class_name fallback mutations (key case, 'label'->None/wrong key, 'object' default -> None/wrong string) — fallback path either untested (with_distances) or asserted only via substring","TEST-GAP",R(FM,[30])|R(WD,[26,28,31,32,33,34,35,36,37,38]),""))
C.append(("Nemotron formatters: prompt prefix/join-separator literal mutations pass loose substring asserts (tests check membership, never exact string)","TEST-GAP",R(FM,[36,40])|R(WD,[46,47,48,50]),""))
BB='x_get_depth_at_bbox'
C.append(("get_depth_at_bbox: shape[:2] -> shape[:3] — 2-D contract means slice still yields (h, w)","EQUIVALENT",R(BB,[3]),""))
C.append(("get_depth_at_bbox: upper clamp w-1 -> w+1 / h-1 -> h+1 — oversized x1/y1 always falls into invalid-bbox 0.5 branch anyway","EQUIVALENT",R(BB,[15,28]),""))
C.append(("get_depth_at_bbox: clamp w-1 -> w-2 / h-1 -> h-2 — bbox touching last column/row samples different region","TEST-GAP",R(BB,[16,29]),""))
C.append(("get_depth_at_bbox: x2/y2 lower clamp 0 -> 1 — bbox fully off-image-left returns edge pixel instead of 0.5 sentinel","TEST-GAP",R(BB,[35,48]),""))
C.append(("get_depth_at_point: shape[:2] -> shape[:3] — 2-D contract","EQUIVALENT",R('x_get_depth_at_point',[2]),""))
LD='x_load_depth_model'
C.append(("load_depth_model: logger.info/warning/error message & exc_info/extra mutations — log payloads only; control flow and raised exceptions unchanged","EQUIVALENT",R(LD,[6,11,12,13,14,17,31,32,39,40,41,43,44,45,46,47,48,49,50]),""))
C.append(("load_depth_model: is_local = Path(model_path).is_dir() -> None — local-directory branch (explicit from_pretrained) never taken; no test uses a real local dir","TEST-GAP",R(LD,[15]),""))
C.append(("load_depth_model: CUDA-guard / ImportError exception message case & XX mutations — user-facing text only, tests substring-match the key phrase","LOW-VALUE",R(LD,[3,33,34,36]),""))
NM='x_normalize_depth_map'
C.append(("normalize_depth_map: .get('depth', default) default -> None/removed — dict lacking 'depth' crashes via np.array in both original and mutant (no assertable behavior)","LOW-VALUE",R(NM,[9,11]),""))
C.append(("normalize_depth_map: PIL-detect hasattr 'convert' broken/renamed — both branches execute the identical np.array(depth_data, float32) conversion","EQUIVALENT",R(NM,[15,19,20]),""))
C.append(("normalize_depth_map: 'max-min > 0' -> '> 1' — any depth map with range <=1 is returned as all zeros","TEST-GAP",R(NM,[27]),""))
RK='x_rank_detections_by_proximity'
C.append(("rank_detections_by_proximity: zip strict=True -> None/False/kwarg removed — lengths already equalized by the explicit length check above","EQUIVALENT",R(RK,[10,13,14]),""))
C.append(("rank_detections_by_proximity: ValueError message XX-wrapped — pytest.raises match substring still passes","LOW-VALUE",R(RK,[3]),""))
TDC='xǁDepthAnalysisResultǁto_dict'
C.append(("DepthAnalysisResult.to_dict: 'average_depth'/'depth_variance' output keys renamed/case-changed — test asserts only detection_depths/closest_detection_id/has_close_objects","TEST-GAP",R(TDC,[7,8,9,10]),""))
TCC='xǁDepthAnalysisResultǁto_context_string'
C.append(("to_context_string: sort key removal (key=None / kwarg dropped) — output ordering silently switches from depth-ordered to det_id-ordered; no order assertion","TEST-GAP",R(TCC,[11,13]),""))
C.append(("to_context_string: risk_note default '' -> None/'XXXX' — every non-risk line gains 'None'/'XXXX' garbage; substring asserts never notice","TEST-GAP",R(TCC,[16,17]),""))
C.append(("to_context_string: line joiner '\\n' -> literal 'XX\\nXX' — multi-line layout broken; no structural assert","TEST-GAP",R(TCC,[36]),""))
C.append(("to_context_string: header/risk-marker/blank-line literal mutations — cosmetic prompt text; substring asserts still match","LOW-VALUE",R(TCC,[6,22,25,33]),""))

seen=collections.Counter()
dup=[]
for pat,cls,mem,note in C:
    for m in mem:
        seen[m]+=1
        if seen[m]>1: dup.append(m)
allset={ (fn,n) for fn,s in allkeys.items() for n in s }
missing=allset-set(seen); extra=set(seen)-allset
print('clusters',len(C),'assigned',sum(len(m) for _,_,m,_ in C),'dups',dup)
print('missing:',sorted(missing))
print('extra:',sorted(extra))
tot=collections.Counter(cls for _,cls,_,_ in C)
sg=collections.Counter()
for _,cls,m,_ in C: sg[cls]+=len(m)
print('per-class counts:',dict(sg),'total',sum(sg.values()))
# per-function missing detail
for fn,s in allkeys.items():
    got={n for _,_,m,_ in C for f,n in m if f==fn}
    l=sorted(s-got)
    if l: print('MISSING',fn,l)

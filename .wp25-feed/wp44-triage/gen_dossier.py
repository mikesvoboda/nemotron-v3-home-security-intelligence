import json

PRE='backend.services.depth_anything_loader.'
def R(fn, nums): return {f'{PRE}x{fn[1:] if fn.startswith("x") else fn}' if False else k for k in []}

def keys_for(fn, nums):
    # fn like 'analyze_depth' -> full key
    return [f'backend.services.depth_anything_loader.x_{fn}__mutmut_{n}' for n in nums]
def keys_for_mangled(fn, nums):  # fn includes mangle prefix already
    return [f'backend.services.depth_anything_loader.{fn}__mutmut_{n}' for n in nums]

AD='x_analyze_depth'; DF='x_depth_to_feet'; LD='x_load_depth_model'; FM='x_format_depth_for_nemotron'
WD='x_format_depth_for_nemotron_with_distances'; BB='x_get_depth_at_bbox'; NM='x_normalize_depth_map'
RK='x_rank_detections_by_proximity'; TDC='xǁDepthAnalysisResultǁto_dict'; TCC='xǁDepthAnalysisResultǁto_context_string'

clusters=[
 # (fn_label, pattern, classification, [nums], note)
 ("analyze_depth","det_id extraction: nested .get() key/default mutations ('id' fallback renamed/dropped, default '' -> None/'XXXX') — dicts keyed only by 'id', or lacking both id keys, never fed to analyze_depth","TEST-GAP",[23,25,28,29,30,31,32,33,34],"Detection with only 'id' key is silently dropped by mutants 28/32/33; mutants 23/25/29/30/31 yield det_id 'None'/'XXXX' entries — test_depth_anything_loader.py never builds such input."),
 ("analyze_depth","class_name extraction: nested .get() mutations ('label' fallback / 'object' default broken) — fallback chain never exercised","TEST-GAP",[35,36,37,38,39,40,41,42,43,44,45,46,47,48,49],"Mutant 35 (class_name=None) survives because analyze_depth tests never assert per-detection class_name."),
 ("analyze_depth","depth_pipeline(image) -> depth_pipeline(None): mock pipeline returns its return_value for ANY argument","TEST-GAP",[4],"Only killing route: assert mock_pipeline called with the actual image object."),
 ("analyze_depth","logger.error on pipeline-failure path: msg/exc_info mutations — message None / exc_info None|False still logs and re-raises unchanged","EQUIVALENT",[10,11,13,14],"Log payload only; control flow identical."),
 ("analyze_depth","logger.error(exc_info=True) drops the positional msg argument — stdlib logging raises TypeError inside the except handler, replacing the re-raised pipeline error","TEST-GAP",[12],"No test makes the depth pipeline raise, so the failure path is never entered."),
 ("analyze_depth","closest-detection tracking seeds/edges: init None->'' , min_depth 1.0->2.0 (depth exactly 1.0 then claims closest), < -> <= (tie now picks LAST)","TEST-GAP",[17,19,99],"test_analyze_depth_with_detections uses strictly increasing depths, no 1.0 sample, no tie."),
 ("analyze_depth","detection/bbox validation guards weakened: 'not bbox or not det_id' -> 'and' (no-id detection now stored under empty key), isinstance 'and len>=4' -> 'or' (3-tuple bbox crashes unpacking), bbox[:4] -> bbox[:5] (5-tuple bbox crashes)","TEST-GAP",[54,63,68],"Malformed-bbox path (logger.warning + skip) never fed."),
 ("analyze_depth","bbox duck-typing hasattr(bbox,'to_tuple') broken — BoundingBox-like bbox objects never passed","TEST-GAP",[57,61,62],"Comment in source says bbox 'might be a BoundingBox object'; tests only pass tuples."),
 ("analyze_depth","depth_sampling_method kwarg dropped when calling get_depth_at_bbox — analyze_depth always samples 'center' regardless of caller choice","TEST-GAP",[75],"No analyze_depth test passes a non-default depth_sampling_method."),
 ("analyze_depth","DetectionDepth field mutations: detection_id/class_name/depth_value/proximity_label set None, is_approaching None/True — per-detection field values never asserted","TEST-GAP",[82,85,86,87,88,89,97],"to_dict contract is tested for DetectionDepth directly but not for analyze_depth's produced records."),
 ("analyze_depth","is_approaching=False kwarg removed — equals the dataclass default False","EQUIVALENT",[95],""),
 ("analyze_depth","has_close_objects mutations: in->not in, label literals case/XX-broken, ->None, kwarg removed (default False) — result.has_close_objects never asserted","TEST-GAP",[102,104,105,106,107,108,125,130],"104 survives scenes that contain a close object; killed only by an all-far scene."),
 ("analyze_depth","average_depth mutations: ->None, ternary guard collapsed (and False / or True), else 0.5->1.5, kwarg ->None/removed (default 0.5) — result.average_depth never asserted","TEST-GAP",[109,110,111,114,126,131],"111 (or True) differs only when depth_values is empty -> np.mean([])=nan."),
 ("analyze_depth","depth_variance mutations: ->None, guard collapsed, >1 -> >2, else 0.0->1.0, kwarg ->None/removed — result.depth_variance never asserted","TEST-GAP",[115,116,117,121,122,127,132],"117 (or True) differs only on empty depth_values (np.var([])=nan)."),
 ("analyze_depth","variance guard len(depth_values)>1 -> >=1 — np.var([x]) == 0.0 equals the original else-branch","EQUIVALENT",[120],""),
 ("depth_to_feet","calibration_points .get default [] -> None / dropped — 'if not calibration_points' early-return absorbs the difference","EQUIVALENT",[4,6],""),
 ("depth_to_feet","bracketing boundary comparisons <= -> < and >= -> > — at an exact calibration node linear interpolation returns that node's distance either way (piecewise-linear continuity)","EQUIVALENT",[24,29],"Verified by hand for interior nodes, endpoints, and out-of-range depths."),
 ("depth_to_feet","multi-point bracketing degraded: lower_point/upper_point assignments -> None, 'upper is None' once-guard -> 'is not None' — every existing test uses 2-point calibration where the fallback pair equals the true bracket","TEST-GAP",[25,26,30,31],"Needs 3+ calibration points with depth in the last (or a non-first) segment."),
 ("depth_to_feet","below-range extrapolation picks points[1] twice -> depth_range==0 -> returns wrong point's distance instead of extrapolated value","TEST-GAP",[34],"No test calls depth_to_feet with depth below the first calibration point."),
 ("depth_to_feet","'elif upper_point is None' -> 'is not None' — depth above the calibration range dereferences None (TypeError) instead of extrapolating","TEST-GAP",[36],"No above-range call exists in tests."),
 ("depth_to_feet","clamp floor max(0.1, result) -> max(1.1, result)","TEST-GAP",[69],"Killed by any expected distance in (0.1, 1.1); e.g. below-range 0.1 floor."),
 ("estimate_relative_distances","method kwarg dropped when calling get_depth_at_bbox — method pass-through untested","TEST-GAP",[6],"test_estimate_relative_distances only exercises method='center'."),
 ("format_depth_for_nemotron","length-mismatch warning inverted ( != -> == ) / warning msg -> None — logging-only","EQUIVALENT",[7,8],"test_format_depth_for_nemotron_mismatched_lengths asserts output text, not the warning."),
 ("format_depth_for_nemotron","zip strict=False -> None / kwarg removed — falsy and default are identical","EQUIVALENT",[12,15],""),
 ("format_depth_for_nemotron","early-return guard 'not detections or not depth_values' -> 'and' — one-empty partial input returns 'Spatial context: ' instead of the sentinel","TEST-GAP",[1],""),
 ("format_depth_for_nemotron_with_distances","early-return guard 'or' -> 'and'","TEST-GAP",[1],""),
 ("format_depth_for_nemotron_with_distances","min-count 'count' arg removals and zip strict mutations — slicing to min then zip-shortest is provably identical output; post-slice lists are equal length so strict=True is inert","EQUIVALENT",[4,8,9,10,18,22,23],""),
 ("Nemotron formatters","class_name fallback mutations (key case, 'label'->None/wrong key, 'object' default -> None/'OBJECT'/'XXobjectXX') — with_distances has no fallback test at all; format_depth_for_nemotron's 'object' assert is a substring match that 'XXobjectXX' satisfies","TEST-GAP",[30],'FM:30 only; WD: 26,28,31-38',),
 ("Nemotron formatters","prompt prefix / join-separator literal mutations pass loose membership asserts ('Spatial context:' inside 'XXSpatial context: XX') — formatter output is product-facing LLM prompt text","TEST-GAP",[36,40],'FM:36,40; WD:46,47,48,50'),
 ("get_depth_at_bbox","shape[:2] -> shape[:3] — 2-D contract means the slice still unpacks (h, w)","EQUIVALENT",[3],""),
 ("get_depth_at_bbox","upper clamp w-1 -> w+1 / h-1 -> h+1 — any bbox with x1/h1 beyond the image lands in the invalid-bbox 0.5 branch under both original and mutant","EQUIVALENT",[15,28],"x2/y2 clamp is untouched, so mutant x1 (>= w+1) > x2 (<= w-1) always invalid; original x1=w-1 >= x2 also invalid."),
 ("get_depth_at_bbox","upper clamp w-1 -> w-2 / h-1 -> h-2 — a bbox touching the last column/row (e.g. x1=w-1) samples a real region under the mutant but hits the 0.5 sentinel originally","TEST-GAP",[16,29],""),
 ("get_depth_at_bbox","x2/y2 lower clamp 0 -> 1 — a bbox fully off the left/top edge returns an edge-pixel depth instead of the 0.5 sentinel","TEST-GAP",[35,48],""),
 ("get_depth_at_point","shape[:2] -> shape[:3] — 2-D contract","EQUIVALENT",[2],""),
 ("load_depth_model","logger.info/warning/error message and exc_info/extra mutations — log payloads only, control flow and raised exceptions unchanged","EQUIVALENT",[6,11,12,13,14,17,31,32,39,40,41,43,44,45,46,47,48,49,50],"No test captures log records (caplog unused in this module)."),
 ("load_depth_model","is_local = Path(model_path).is_dir() -> None — the local-directory branch (explicit AutoImageProcessor/AutoModelForDepthEstimation.from_pretrained, the code that exists specifically to dodge huggingface_hub repo-id errors) is never taken in tests","TEST-GAP",[15],"Both existing success tests pass a fake non-dir path."),
 ("load_depth_model","CUDA-guard / ImportError exception message case and XX mutations — substring match('requires a CUDA GPU' / 'Depth Anything V2 requires transformers and torch') still passes; diagnostic prose text","LOW-VALUE",[3,33,34,36],""),
 ("normalize_depth_map",".get('depth', default) default -> None/dropped — a dict without 'depth' raises TypeError via np.array in original AND mutant; unassertable difference","LOW-VALUE",[9,11],""),
 ("normalize_depth_map","PIL-detection hasattr 'convert' broken/renamed — the PIL branch and the fall-through branch execute the identical np.array(depth_data, dtype=float32)","EQUIVALENT",[15,19,20],"ndarray inputs still route to the astype branch in all variants."),
 ("normalize_depth_map","'max_val - min_val > 0' -> '> 1' — any depth map whose raw range is <=1 (typical for already-scaled maps) is returned as an all-zeros map","TEST-GAP",[27],"Existing tests use range-100 and uniform-50 inputs only; analyze_depth tests feed 0.1-0.7 maps but assert only closest_detection_id (all-zeros map preserves the first-winner)."),
 ("rank_detections_by_proximity","zip strict=True -> None/False/kwarg removed — the explicit length check above guarantees equal lengths, so strict is unreachable","EQUIVALENT",[10,13,14],""),
 ("rank_detections_by_proximity","ValueError message XX-wrapped — pytest.raises(match='Detection and depth value counts must match') substring still matches","LOW-VALUE",[3],""),
 ("DepthAnalysisResult.to_dict","output keys 'average_depth'/'depth_variance' renamed or case-changed — test_depth_analysis_result_to_dict asserts only detection_depths/closest_detection_id/has_close_objects","TEST-GAP",[7,8,9,10],"Downstream JSON consumers read these keys."),
 ("to_context_string","depth sort key removed (key=None / kwarg dropped) — line order silently switches from depth-ordered to detection-id-ordered; no ordering assertion exists","TEST-GAP",[11,13],"key=None sorts the (id, DetectionDepth) tuples by id (dataclass is not order=True, so equal ids would TypeError — never reached because ids differ)."),
 ("to_context_string","risk_note default '' -> None / 'XXXX' — every no-risk line gains literal 'None'/'XXXX' garbage; membership asserts never notice","TEST-GAP",[16,17],""),
 ("to_context_string","line joiner '\\n' -> 'XX\\nXX' — multi-line layout carries literal XX between lines; no structural (line-by-line) assertion exists","TEST-GAP",[36],""),
 ("to_context_string","header / risk-marker / blank-summary-line literal XX-wrapped — substring asserts ('Spatial depth analysis:', 'CLOSE TO CAMERA') still match inside the wrapper; prompt cosmetics","LOW-VALUE",[6,22,25,33],""),
]
# fix the tuple that used a trailing comma oddly (the FM30 cluster) — normalize
total=sum(len(c[3]) for c in clusters)
print('total assigned',total)
seen=set(); dup=[]
for fn,pat,cls,nums,*note in clusters:
    for n in nums:
        if (fn,n) in seen: dup.append((fn,n))
        seen.add((fn,n))
print('dups',dup)
# verify against survivor set
d=json.load(open('/tmp/wp25/wp44-triage/variant_diffs.json'))
allsurv={(k[len(PRE):].rsplit('__mutmut_',1)[0], int(k.rsplit('__mutmut_',1)[1])) for k in d}
print('missing',sorted(allsurv-seen)); print('extra',sorted(seen-allsurv))

def full(fn,n):
    return f'backend.services.depth_anything_loader.{fn}__mutmut_{n}'
out=[]
for fn,pat,cls,nums,*note in clusters:
    ex=[full(fn,n) for n in nums[:3]]
    out.append({'pattern':pat,'count':len(nums),'classification':cls,'example_keys':ex,'note':(note[0] if note else '')})
json.dump(out,open('/tmp/wp25/wp44-triage/clusters.json','w'),indent=1)
from collections import Counter
c=Counter()
for o in out: c[o['classification']]+=o['count']
print(dict(c),'sum',sum(c.values()))

import json, re
d = json.load(open('/tmp/wp25/wp44-triage/scratch-osnet/diffs.json'))

def fn(k): return k.split('.osnet_loader.')[1].split('__')[0]
def num(k): return int(k.rsplit('_',1)[1])
def content(k):
    # mutation lines excluding the def-rename line
    return [l for l in d[k].splitlines() if 'def x' not in l and not l.startswith('+++')]

def assign(k):
    f, n = fn(k), num(k)
    L = ' '.join(content(k))
    if f == 'xǁPersonEmbeddingResultǁcosine_similarity':
        return 'C1'
    if f == 'x_match_person_embeddings':
        return 'C5'
    if f == 'x_format_person_reid_context':
        if 'unknown' in L: return 'C9'
        return 'C2'   # 0.9/0.8/0.85 boundary + join sep
    if f == 'x_extract_person_embeddings_batch':
        if 'convert' in L: return 'C15'
        if re.search(r'width < 3[23]|width <= 32|height <=? 6[45]|width < 64 and|width <= 64', L): return 'C14'
        if re.search(r'transform|stack|device|to\(None\)|model\(None\)', L): return 'C10'
        return 'C11'  # dim/normalize/result-build
    # load_osnet_model
    if re.search(r'logger\.(info|debug|error|warning)\(|package not installed|Failed to load OSNet model|exc_info|extra=|verified critical', L):
        # but 153 exc_info False: still log arg -> C13
        return 'C13'
    if re.search(r'must_exist|Invalid model path', L): return 'C3'
    if 'build_model' in L or 'osnet_ain_x1_0' in L or 'num_classes' in L or 'pretrained' in L: return 'C4'
    if 'torch.load' in L or 'weights_file,' in L or 'map_location' in L: return 'C6'
    if 'load_state_dict' in L: return 'C7'
    if 'critical_prefixes' in L or 'critical_missing' in L or 'startswith' in L: return 'C8'
    if 'XXmodel.pthXX' in L or 'MODEL.PTH' in L or 'weights_file.exists' in L: return 'C12'
    if 'transforms' in L or 'Resize' in L or 'mean=' in L or 'std=' in L or 'transform = None' in L: return 'C16'
    return 'UNASSIGNED:'+k

from collections import defaultdict
cl = defaultdict(list)
for k in d: cl[assign(k)].append(k)
tot=0
for name in sorted(cl):
    print(name, len(cl[name]))
    tot+=len(cl[name])
print('TOTAL', tot)
for name in sorted(cl):
    if name.startswith('UNASSIGNED'):
        print('???', name, d[cl[name][0]])
json.dump({k: assign(k) for k in d}, open('/tmp/wp25/wp44-triage/scratch-osnet/assign.json','w'), indent=0)

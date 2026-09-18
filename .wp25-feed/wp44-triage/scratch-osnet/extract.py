import ast, json, re, difflib, sys

ORIG = '/agents/agent-nemo2/workspace/backend/services/osnet_loader.py'
MUT  = '/agents/agent-nemo2/workspace/mutants/backend/services/osnet_loader.py'
META = '/agents/agent-nemo2/workspace/mutants/backend/services/osnet_loader.py.meta'

for attempt in range(2):
    try:
        meta = json.load(open(META))
        break
    except json.JSONDecodeError:
        if attempt: sys.exit('meta unreadable')

surv = {k for k,v in meta['exit_code_by_key'].items() if v == 0}

src = open(MUT).read()
# Find all variant function defs: names like x<func>__mutmut_N or xǁClassǁmethod__mutmut_N
# Capture each variant: from its def line until the next top-level def/decorator/assignment at same indent... simpler: parse whole mutated file with ast.
tree = ast.parse(src)

def func_source(node, lines):
    seg = ast.get_source_segment(src, node)
    return seg.splitlines() if seg else []

orig_tree = ast.parse(open(ORIG).read())
orig_src = open(ORIG).read()
orig_funcs = {}
def collect(t, prefix=''):
    for node in t.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            orig_funcs[prefix+node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    orig_funcs[prefix+'ǁ'+node.name+'ǁ'+sub.name] = sub
collect(orig_tree)

lines_orig = orig_src.splitlines()
def orig_body(funcname):
    # strip decorators: get lines from def line
    node = None
    for k,v in orig_funcs.items():
        if k == funcname or k.endswith('ǁ'+funcname) or k == funcname:
            node = v; break
    if node is None: return None
    seg = ast.get_source_segment(orig_src, node)
    return seg.splitlines()

# In mutated tree, find variant defs (top-level and inside class)
variants = {}
def collect_mut(t, in_class=None):
    for node in t.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            variants[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    variants[sub.name] = sub
collect_mut(tree)

# Map variant name -> (base function key in original)
# variant name form: x_<func>__mutmut_N  or  xǁ<Class>ǁ<method>__mutmut_N
out = {}
for name, node in variants.items():
    m = re.match(r'^x(?:_|ǁ)(?P<fn>.+?)__mutmut_(?P<n>\d+)$', name)
    if not m: continue
    fn = m.group('fn'); n = int(m.group('n'))
    if '__mutmut_' not in fn:  # skip __mutmut_orig copies
        pass
    # build key
    if 'ǁ' in fn:
        parts = fn.split('ǁ')  # Class, method
        key = f"backend.services.osnet_loader.xǁ{parts[0]}ǁ{parts[1]}__mutmut_{n}"
    else:
        key = f"backend.services.osnet_loader.x_{fn}__mutmut_{n}"
    if key not in surv: continue
    # original body
    if 'ǁ' in fn:
        ofn = 'ǁ'+fn
    else:
        ofn = fn
    olines = orig_body(ofn)
    vlines = func_source(node, None)
    if olines is None or not vlines: 
        out[key] = '<<no-source>>'; continue
    diff = list(difflib.unified_diff(olines, vlines, lineterm='', n=1))
    # keep only +/- content lines
    body = [l for l in diff if (l.startswith('-') or l.startswith('+')) and not l.startswith('---') and not l.startswith('+++')]
    out[key] = '\n'.join(body)

json.dump(out, open('/tmp/wp25/wp44-triage/scratch-osnet/diffs.json','w'), indent=1)
print('extracted', len(out), 'of', len(surv))
missing = surv - set(out)
print('missing:', list(missing)[:10])

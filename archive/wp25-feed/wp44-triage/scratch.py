# Pure arithmetic reimplementation for hand-verification ONLY. No repo imports, no pytest.
# Each MUT[key] = (fixture_key, mutated_output_expected) computed by applying the mutant's change.
TH = 0.3
class KP:
    def __init__(self, x, y, c=0.9): self.x, self.y, self.confidence = float(x), float(y), c
def gk(kp, name):
    k = kp.get(name)
    return k if (k is not None and k.confidence >= TH) else None

# ---------- detect_lying_down ----------
def lying(kp, *, drop=(), guard='or_or', guard2='or_or', pre=None,
          ops=None, den=None, hs='diff', cond='gt0', ratio=1.5, tail='gt50'):
    def get(n):
        return None if n in drop else gk(kp, n)
    L,R,LA,RA = get('left_shoulder'),get('right_shoulder'),get('left_ankle'),get('right_ankle')
    s_ok = (L or R) if guard=='or' else (L and R)
    a_ok = (LA or RA) if guard2=='or' else (LA and RA)
    if not s_ok or not a_ok: return False
    acc = {'sx':0.0,'sy':0.0,'sc':0,'ax':0.0,'ay':0.0,'ac':0}
    if pre:
        for k,v in pre.items():
            k,mode = k.split(':')
            acc[k] = v
    ops = ops or {}
    for src, xk, yk, ck in ((L,'sx','sy','sc'),(R,'sx','sy','sc')):
        if src is None: continue
        pass
    # sequential application, order matters (matches source order)
    sx,sy,sc = 0.0,0.0,0
    if pre and 'shoulder_x' in pre: sx = pre['shoulder_x']
    if pre and 'shoulder_y' in pre: sy = pre['shoulder_y']
    if pre and 'shoulder_count' in pre: sc = pre['shoulder_count']
    for side, S in (('left',L),('right',R)):
        if S is None: continue
        sx = {'=': (lambda a,b: b), '-': (lambda a,b: a-b), '+': (lambda a,b: a+b)}[ops.get(side+'x','+')](sx,S.x)
        sy = {'=': (lambda a,b: b), '-': (lambda a,b: a-b), '+': (lambda a,b: a+b)}[ops.get(side+'y','+')](sy,S.y)
        op = ops.get(side+'c','+')
        if op == '=': sc = 1
        elif op == '-': sc -= 1
        elif op == '+2': sc += 2
        else: sc += 1
    dd = den or {}
    sden = dd.get('shoulder_den', 1)
    sx = dd.get('shoulder_x_op','/')
    if sx == '=': sxv = max(sc, sden)
    elif sx == '*': sxv = sxv_mul(sc,sden,sx)
    else: sxv = sx / max(sc, sden)
    return None

import json, re, collections, difflib, os

os.chdir('/agents/agent-nemo2/workspace')
p='mutants/backend/services/batch_aggregator.py.meta'
try: d=json.load(open(p))
except json.JSONDecodeError:
    import time; time.sleep(1); d=json.load(open(p))
surv=set(k for k,v in d['exit_code_by_key'].items() if v==0)

clusters=json.load(open('/tmp/wp25/wp44-triage/clusters_struct.json'))
MF='mutants/backend/services/batch_aggregator.py'
src=open(MF,encoding='utf-8').read().splitlines()
defre=re.compile(r'^(\s*)(?:async\s+)?def\s+(x\S+?__mutmut_(?:orig|\d+))\s*\(')
defs=[(i,m.group(2)) for i,l in enumerate(src) if (m:=defre.match(l))]
blocks={}
for j,(s,n) in enumerate(defs):
    e=defs[j+1][0] if j+1<len(defs) else len(src)
    b=src[s:e]
    for k,l in enumerate(b):
        if l.startswith('mutants_'): b=b[:k]; break
    blocks[n]=b
def fam(n): return n.rsplit('__mutmut_',1)[0]
def sdl(body):
    out=[];started=False;depth=0
    for l in body:
        if not started:
            depth+=l.count('(')-l.count(')')
            if depth<=0 and l.rstrip().endswith(':'): started=True
            continue
        out.append(l)
    while out and not out[-1].strip(): out.pop()
    return out
FRAGC={}
def frags(key):
    if key in FRAGC: return FRAGC[key]
    tail=key.rsplit('.',1)[-1]; f=fam(tail)
    ob=sdl(blocks[f+'__mutmut_orig']); vb=sdl(blocks[tail])
    out=[]
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,ob,vb).get_opcodes():
        if tag=='equal': continue
        out.append(' | '.join(x.strip() for x in ob[i1:i2])+' ## '+' | '.join(x.strip() for x in vb[j1:j2]))
    FRAGC[key]=out
    return out
def jx(keys):
    parts=[]
    for k in keys[:2]:
        parts.extend(frags(k))
    return ' '.join(parts)

def log_kind(jn):
    if re.search(r'\bextra\b', jn) or 'exc_info' in jn or re.search(r'"[a-zA-Z_]+"\s*:', jn):
        return 'LOGEXTRA'
    return 'LOGMSG'

agg=collections.defaultdict(list)
for c in clusters:
    f,role,kind,kt,keys=c['f'],c['role'],c['kind'],c['kt'],c['keys']
    fs=f.replace('xǁBatchAggregatorǁ','').replace('x_','')
    jn=jx(keys)
    role_eff=role
    if role.startswith('MULTI'):
        parts=[q for q in eval(role[6:]) if q!='UNK']
        role_eff=parts[0] if parts else 'UNK'
    if role_eff=='LOG': cls=log_kind(jn)
    elif role_eff=='RAISE': cls='RAISEMSG'
    elif role_eff.startswith('CALL:pipe.set'): cls='PIPE-TTL'
    elif role_eff=='CALL:self._redis.delete': cls='DEL-KEYS'
    elif role_eff=='CALL:self._redis._client.set': cls='CLOSEFLAG'
    elif role_eff.startswith('PAYLOAD'): cls='PAYLOAD'
    elif role_eff.startswith(('CALL:self._broadcast','CALL:broadcaster')) or ('broadcaster' in role_eff) or (role_eff=='CODE:if not self._redis:' and 'broadcast' in fs): cls='PAYLOAD'
    elif role_eff.startswith(('CALL:self._process_threat_fast_path','CALL:self._process_smoke_fire_fast_path')): cls='DISPATCH-ARGS'
    elif role_eff.startswith('CALL:service.') or role_eff.startswith('CODE:service = '): cls='SERVICE-ARGS'
    elif role_eff.startswith('CALL:self._create_batch_metadata_atomic'): cls='PIPE-TTL'
    elif role_eff=='CALL:self._redis.set' or role_eff.startswith('CODE:ttl = self.BATCH_KEY_TTL'): cls='TTL2'
    elif role_eff.startswith('CODE:if await self.should_bypass_ba'): cls='BYPASS-OBJTYPE'
    elif role_eff.startswith('CALL:batch_aggregator.add_detection'): cls='ORPHAN-KW'
    elif role_eff.startswith(('CODE:stmt = (','CODE:cutoff_time','CODE:result = await session')): cls='ORPHAN-Q'
    elif role_eff.startswith(('CODE:self._use_redis_streams','CODE:self._analyzer')): cls='INIT'
    elif role_eff.startswith(('CODE:if _gpu_monitor','CODE:_gpu_monitor')): cls='GPU-WIRE'
    elif 'log_context' in role_eff: cls='LCTX'
    elif 'batch_duration_ms' in role_eff: cls='DURATION'
    elif 'camera_lock' in role_eff: cls='LOCKWIRE'
    elif role_eff.startswith('CODE:raw_detections'): cls='LRANGE-ARGS'
    elif role_eff.startswith(('CODE:if not self._redis or not self','CALL:detections.append','CODE:batch_id = None')): cls='MISC-EQUIV'
    elif fs=='check_batch_timeouts':
        if kind=='OPFLIP': cls='TB-OPFLIP'
        elif 'metadata_results[' in jn: cls='TB-IDX'
        elif re.search(r'\- ',jn) and '+ ' in jn: cls='TB-NEG'
        elif 'should_close' in jn or 'close_reason' in jn: cls='TB-DEAD'
        else: cls='TB-WIRE'
    elif fs=='close_batch':
        if role_eff.startswith('CODE:return'): cls='CLOSE-ALREADY-DICT'
        elif role_eff.startswith('CODE:started_at = float'): cls='CLOSE-FALLBACK'
        elif role_eff.startswith(('CODE:detections: list','CODE:pipeline_start_time: str','CODE:started_at_str: str')): cls='CLOSE-STATE-EQUIV'
        else: cls='CLOSE-WIRE'
    elif fs=='_close_batch_for_size_limit': cls='SIZE-STATE'
    elif fs=='add_detection': cls='ADD-STATE'
    else: cls='MISC2:'+fs
    agg[cls].extend(keys)

print('pre-split', sum(len(v) for v in agg.values()), len(agg))
def split_frag(cls, pred, dest):
    keep=[]; moved=[]
    for k in agg[cls]:
        (moved if pred(jx([k])) else keep).append(k)
    agg[cls]=keep
    agg[dest]+=moved
split_frag('ADD-STATE', lambda j: 'raise RuntimeError' in j, 'RAISEMSG')
split_frag('SIZE-STATE', lambda j: 'raise RuntimeError' in j, 'RAISEMSG')
split_frag('ADD-STATE', lambda j: 'create_batch_metadata_atomic' in j, 'PIPE-TTL')
split_frag('SIZE-STATE', lambda j: 'add_to_queue_safe' in j or 'QueueOverflowPolicy' in j, 'SIZE-QUEUE')
split_frag('CLOSE-WIRE', lambda j: 'log_context' in j, 'LCTX')
split_frag('SIZE-STATE', lambda j: 'log_context' in j, 'LCTX')
split_frag('CLOSE-WIRE', lambda j: 'batch_duration_ms' in j, 'DURATION')
split_frag('SIZE-STATE', lambda j: 'batch_duration_ms' in j, 'DURATION')
split_frag('ADD-STATE', lambda j: 'broadcaster' in j or 'get_broadcaster' in j, 'PAYLOAD')
split_frag('SIZE-STATE', lambda j: 'lrange' in j or 'raw_detections' in j, 'LRANGE-ARGS')

tot=sum(len(v) for v in agg.values())
print('TOTAL',tot)
assert tot==710, tot
json.dump({k:sorted(v) for k,v in agg.items()}, open('/tmp/wp25/wp44-triage/ba44_final.json','w'))
for cls,ks in sorted(agg.items(),key=lambda x:-len(x[1])):
    print(f'{len(ks):4d} {cls:16s}')

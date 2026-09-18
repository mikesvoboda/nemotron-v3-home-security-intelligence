import json, re, difflib, collections

MF='/agents/agent-nemo2/workspace/mutants/backend/services/batch_aggregator.py'
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
def delta(key):
    tail=key.rsplit('.',1)[-1]; f=fam(tail)
    ob=sdl(blocks[f+'__mutmut_orig']); vb=sdl(blocks[tail])
    fr=[]
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,ob,vb).get_opcodes():
        if tag=='equal': continue
        fr.append((' | '.join(x.strip() for x in ob[i1:i2]), ' | '.join(x.strip() for x in vb[j1:j2])))
    return fr

clusters=json.load(open('/tmp/wp25/wp44-triage/clusters_struct.json'))

def classify_cluster(c):
    f,role,kind,kt,keys=c['f'],c['role'],c['kind'],c['kt'],c['keys']
    fam_s=f.replace('xǁBatchAggregatorǁ','').replace('x_','')
    # strip UNK artifacts
    if role.startswith('MULTI'):
        parts=eval(role[6:])
        parts=[p for p in parts if p!='UNK']
        role=parts[0] if len(parts)==1 else 'MULTI-REAL:'+str(parts)
    # per-mutant fragment-level classification for LOG message vs extra
    def frag_class(fr):
        joined=' '.join(a+' '+b for a,b in fr)
        # UNK artifact fragments: additions of registry/decorator lines
        real=[(a,b) for a,b in fr if '@_mutmut_mutated' not in b and 'def _' not in b and 'mutants_' not in b and '# ===' not in b and 'async def x' not in b]
        return real if real else fr
    # role-based
    if role=='LOG' or role.startswith('MULTI:[\'LOG\''):
        if kt=='': return 'LOGMSG'
        return 'LOGEXTRA'
    if role=='RAISE': return 'RAISEMSG'
    if role.startswith('CALL:pipe.set'): return 'PIPE-TTL'
    if role=='CALL:self._redis.delete': return 'DEL-KEYS'
    if role=='CALL:self._redis._client.set': return 'CLOSEFLAG'
    if role.startswith('PAYLOAD'): return 'PAYLOAD'
    if role in ('CALL:self._broadcast_detection_new','CALL:self._broadcast_detection_batch','CALL:broadcaster.broadcast_detection_new','CALL:broadcaster.broadcast_detection_batch'): return 'PAYLOAD'
    if role=='CODE:if not self._redis:' and 'broadcast' in f: return 'PAYLOAD'
    if role.startswith('CALL:self._process_threat_fast_path') or role.startswith('CALL:self._process_smoke_fire_fast_path'): return 'DISPATCH-ARGS'
    if role.startswith('CALL:service.'): return 'SERVICE-ARGS'
    if role.startswith('CODE:service = '): return 'SERVICE-ARGS'
    if role.startswith('CALL:self._create_batch_metadata_atomic'): return 'PIPE-TTL'
    if role=='CALL:self._redis.set': return 'TTL2'
    if role=='CODE:ttl = self.BATCH_KEY_TTL_SECONDS': return 'TTL2'
    if role=='CODE:ttl = self.BATCH_KEY_TTL_SECON': return 'TTL2'
    if role=='CALL:batch_aggregator.add_detection': return 'ORPHAN-KW'
    if role=='CODE:stmt = (': return 'ORPHAN-Q'
    if role.startswith('CODE:cutoff_time'): return 'ORPHAN-Q'
    if role.startswith('CODE:result = await session.execute'): return 'ORPHAN-Q'
    if 'log_context' in role: return 'LCTX'
    if 'batch_duration_ms' in role: return 'DURATION'
    if role=='CODE:self._use_redis_streams: bool' or role=='CODE:self._use_redis_streams: bool ' or 'use_redis_streams' in role or role.startswith('CODE:self._analyzer'): return 'INIT'
    if role=='CODE:if _gpu_monitor is None:' or role.startswith('CODE:_gpu_monitor ='): return 'GPU-WIRE'
    if 'should_bypass_ba' in role: return 'BYPASS-OBJTYPE'
    if role=='CODE:batch_id = None': return 'MISC-EQUIV'
    if 'camera_lock' in role: return 'LOCKWIRE'
    if role=='CODE:raw_detections: list[bytes | s' or role.startswith('CODE:raw_detections'): return 'LRANGE-ARGS'
    if role.startswith('CALL:detections.append'): return 'MISC-EQUIV'
    if 'check_batch_timeouts' in fam_s:
        # timeout-logic code mutants
        return 'TB-CORE'
    if 'close_batch' in fam_s:
        return 'CLOSE-STATE'
    if 'add_detection' in fam_s:
        return 'ADD-STATE'
    if 'atomic' in fam_s and role=='CODE:if not self._redis or not self': return 'MISC-EQUIV'
    return 'OTHER:'+fam_s+'|'+role+'|'+kind+'|'+kt

agg=collections.defaultdict(list)
for c in clusters:
    cls=classify_cluster(c)
    agg[cls].extend(c['keys'])

print('per-mutant check for suspicious:')
# verify fragment-level split for LOG with kt=='' contains no extra= edits
for c in clusters:
    if c['role']=='LOG' and c['kt']=='':
        for k in c['keys'][:1]:
            for a,b in delta(k):
                if 'extra' in b and 'extra' not in a:
                    print('  MISPLIT?',k,a[:60],'=>',b[:60])
tot=0
for cls,ks in sorted(agg.items(),key=lambda x:-len(x[1])):
    tot+=len(ks)
    print(f'{len(ks):4d} {cls:15s} {ks[:2]}')
print('TOTAL',tot)
json.dump({k:v for k,v in agg.items()},open('/tmp/wp25/wp44-triage/final_clusters.json','w'))

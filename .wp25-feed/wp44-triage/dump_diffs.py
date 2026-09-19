import json, subprocess
p='/agents/agent-nemo2/workspace/mutants/backend/services/face_detector.py.meta'
d=json.load(open(p))
eb=d.get('exit_code_by_key', d)
surv=[k for k,v in eb.items() if v==0]
out=[]
for k in surv:
    try:
        r=subprocess.run(['uv','run','mutmut','show',k],capture_output=True,text=True,timeout=45,cwd='/agents/agent-nemo2/workspace')
        out.append('==== '+k)
        out.append(r.stdout.strip())
        if r.returncode!=0:
            out.append('STDERR: '+r.stderr.strip()[:300])
    except Exception as e:
        out.append('==== '+k)
        out.append('ERROR '+repr(e))
open('/tmp/wp25/wp44-triage/fd_survivor_diffs.txt','w').write('\n'.join(out))
print('wrote', len(out), 'lines')

import json
d=json.load(open('/tmp/wp25/wp44-triage-work/diffs.json'))
from collections import defaultdict
byfunc=defaultdict(list)
for k,v in d.items(): byfunc[v['func']].append((v['num'],v['diff']))
for fn in sorted(byfunc):
    print(f"\n########## {fn}  ({len(byfunc[fn])} survivors)")
    for num,diff in sorted(byfunc[fn]):
        print(f"--- mutmut_{num}:")
        for dl in diff: print("   ",dl)

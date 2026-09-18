import json, re, collections
c=json.load(open('/tmp/wp25/wp44-triage/clusters_named.json'))
P1=c['P1 window arg dropped (equiv)'] if 'P1 window arg dropped (equiv)' in c else c['P1']
# re-split current P1(12) which is actually window-dropped only? verify by diff text
# current P1 = E1 minus batch_events_15 = 24 items earlier named P1... check size
print({k:len(v) for k,v in c.items()})

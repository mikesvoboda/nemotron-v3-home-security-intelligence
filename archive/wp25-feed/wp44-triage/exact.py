import json, re, collections

raw = json.load(open('/tmp/wp25/wp44-triage/raw_diffs.json'))
recs=[]
for o in raw:
    # join non-def hunks; but need original text preserved => rebuild from blocks
    pass

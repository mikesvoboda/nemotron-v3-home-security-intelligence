import json, collections

d = json.load(open('/tmp/wp25/wp44-triage/export_service_diffs.json'))
surv = collections.defaultdict(list)
for k in d:
    tail = k.split('export_service.')[1]
    fn, num = tail.rsplit('__mutmut_', 1)
    surv[fn].append(int(num))

P = 'xǁExportServiceǁexport_events_with_progress'
W = 'xǁExportServiceǁexport_events_with_websocket'
E = 'x_events_to_excel'

clusters = {}
def C(cid, cls, fn, nums):
    clusters[cid] = {'class': cls, 'fn': fn, 'nums': set(nums)}

# ---- progress method ----
C('PROG-ERRMSG','LOW-VALUE',P,[3])
C('SQL-FILTER','TEST-GAP',P,[7,11,13,14,15,17,18,30,31,43,44,45,47,48,78])
C('SQL-COUNT','TEST-GAP',P,[49,51,53])
C('ZREPLACE','EQUIVALENT',P,[26,27,39,40])
C('PROG-PCT','TEST-GAP',P,[54,56,59,60,62,63,64,65,76,126,127,128,129,130,137,221])
C('PROG-MSG','LOW-VALUE',P,[61,66,67,68,72,75,133,136,138,217,220,222,223,224])
C('ROW-FIELDS-P','TEST-GAP',P,[85,86,87,88,90,91,92,93,94,95,96,97,98,99,
                              100,101,102,103,104,105,106,107,108,109,110,120,121,122,123,124,125])
C('FILENAME-P','TEST-GAP',P,[139,142,143])
C('TZNIVE','LOW-VALUE',P,[141])
C('COLUMNS','TEST-GAP',P,[145,146,152,154])
C('FILE-CONTENT-P','TEST-GAP',P,[153,167,168,169,179,190,191,210])
C('ENCODING','EQUIVALENT',P,[159,161,163,176,178,185])
C('JSON-INDENT','LOW-VALUE',P,[180,182,183,211,213,214])
C('ZIP-METHOD','LOW-VALUE',P,[203])
C('LOG-EXTRA-P','LOW-VALUE',P,[226,227,229,230,231,232,233,234,235,236,237,238,239,240])

# ---- websocket method ----
C('WS-ERRMSG','LOW-VALUE',W,[3])
C('SQL-FILTER-W','TEST-GAP',W,[22,26,27,30,58])
C('SQL-COUNT-W','TEST-GAP',W,[31,33,35])
C('WS-META','TEST-GAP',W,[9,10,11,12,13,14,15,16,17,18,19,20])
C('WS-PROG','TEST-GAP',W,[38,39,40,41,42,43,44,45,46,106,108,109,110,111,112,113,115,117,118,
                          119,121,122,123,124,125,158,160,161,162,163,164,199])
C('WS-MSG','LOW-VALUE',W,[114,116,120,126,127,159,165,166,167,168])
C('WS-EMPTY','TEST-GAP',W,[51,52,53,54,55,56])
C('ROW-FIELDS-W','TEST-GAP',W,[65,66,67,68,70,71,72,73,74,75,76,77,78,79,
                               80,81,82,83,84,85,86,87,88,89,90,100,101,102,103,104,105])
C('FILENAME-W','TEST-GAP',W,[128,131,132])
C('TZ-NAIVE-W','LOW-VALUE',W,[130])
C('FILE-CONTENT-W','TEST-GAP',W,[139,140,141])
C('ENCODING-W','EQUIVALENT',W,[146,148,150])
C('FMT-BRANCH','TEST-GAP',W,[152,153,155,156])
C('WS-RESULT','TEST-GAP',W,[169,172,173,174,175,176,177,178,179])
C('LOG-EXTRA-W','LOW-VALUE',W,[182,183,185,186,187,188,189,190,191,192,193,194,195,196,197,198])
C('WS-FAIL','TEST-GAP',W,[201,204])
C('WS-FAIL-EQ','EQUIVALENT',W,[203])

# ---- excel ----
C('XL-STYLE','LOW-VALUE',E,[6,7,8,9,10,11,13,15,16,17,18,19,20,22,24,27,28,29,30,31,32,33,38,
                            39,40,41,42,43,44,45,46,47,48,51,54,57,61,62,63,64,65,66,68,70,
                            87,89,90,136,166,168])
C('XL-CELLS','TEST-GAP',E,[112,113,114,115,116,117,118,119,120,121,124])
C('XL-WIDTH','LOW-VALUE',E,[101,102,143,144,145,146,148,150,151,156,161,164,165])
C('XL-STRIPE','LOW-VALUE',E,[137,138,139,140])
C('XL-GETATTR','EQUIVALENT',E,[111])

# ---- helpers ----
C('DJ-COLS','TEST-GAP','x_detections_to_json',[1,2])
C('DJ-CONTENT','TEST-GAP','x_detections_to_json',[3,4])
C('DJ-INDENT','LOW-VALUE','x_detections_to_json',[5,7,8])
C('CSV-SEEK','TEST-GAP','x_events_to_csv_streaming',[10,19])
C('FD-VALUE','TEST-GAP','x_filter_row_to_dict',[2,4,5,11])
C('FD-GETATTR','EQUIVALENT','x_filter_row_to_dict',[9])
C('FEV-GETATTR','EQUIVALENT','x_format_export_value',[6])
C('FILENAME-GEN','TEST-GAP','x_generate_export_filename',[1])
C('SINGLETON','TEST-GAP','x_get_export_service',[1,2])
C('SINGLETON-R','TEST-GAP','x_reset_export_service',[1])
C('ACCEPT','TEST-GAP','x_parse_accept_header',[6,7,10])
C('ACCEPT-WILD','EQUIVALENT','x_parse_accept_header',[11,12,13])
C('INIT-MKDIR','EQUIVALENT','xǁExportServiceǁ__init__',[2,4,6])
C('EMPTY-CONTENT','TEST-GAP','xǁExportServiceǁ_create_empty_export',[15,22,35,57])
C('EMPTY-ENC','EQUIVALENT','xǁExportServiceǁ_create_empty_export',[18,20,24,32,34,37])
C('EMPTY-FILENAME','TEST-GAP','xǁExportServiceǁ_create_empty_export',[1,4,5])
C('EMPTY-TZ','LOW-VALUE','xǁExportServiceǁ_create_empty_export',[3])
C('EMPTY-ZIP','LOW-VALUE','xǁExportServiceǁ_create_empty_export',[50])
C('EE-COLUMNS','TEST-GAP','xǁExportServiceǁexport_events',[3,5,7,9])
C('GF-PREFIX','TEST-GAP','xǁExportServiceǁget_filename',[1])

# verify coverage
assigned = collections.defaultdict(set)
for cid, c in clusters.items():
    assigned[c['fn']] |= c['nums']

problems = 0
for fn, nums in surv.items():
    a = assigned.get(fn, set())
    missing = set(nums) - a
    extra = a - set(nums)
    if missing or extra:
        problems += 1
        print(f'!! {fn}: unassigned={sorted(missing)} phantom={sorted(extra)}')
print('problems:', problems)

# totals
tot = sum(len(c['nums']) for c in clusters.values())
bycls = collections.Counter()
for c in clusters.values():
    bycls[c['class']] += len(c['nums'])
print('total assigned:', tot)
print('by class:', dict(bycls))
for cid, c in sorted(clusters.items(), key=lambda x: -len(x[1]['nums'])):
    print(f"{len(c['nums']):4d} {c['class']:12s} {cid:16s} {c['fn']}")

with open('/tmp/wp25/wp44-triage/clusters_assigned.json','w') as f:
    json.dump({cid: {'class': c['class'], 'fn': c['fn'],
                     'keys': ['backend.services.export_service.' + c['fn'] + '__mutmut_' + str(n) for n in sorted(c['nums'])]}
               for cid, c in clusters.items()}, f, indent=1)

import collections

txt = open('/tmp/wp25/wp44-triage/diffs.txt').read()
blocks = txt.split('===KEY ')[1:]

CL = collections.defaultdict(list)
for b in blocks:
    lines = b.split('\n')
    key = lines[0]
    fn = key.split('ǁ')[-1]
    fname = fn.split('__mutmut')[0]
    num = int(fn.split('__mutmut_')[-1])
    minus = ' '.join(l[1:].strip() for l in lines if l.startswith('-') and not l.startswith('---'))
    plus = ' '.join(l[1:].strip() for l in lines if l.startswith('+') and not l.startswith('+++'))

    def is_log_payload():
        return ('extra=' in minus or 'Bulk inserted' in minus or 'Bulk insert failed' in minus
                or '"inserted_count"' in minus or '"detection_count"' in minus
                or '"failed_count"' in minus or '"error"' in minus)

    c = None
    if fname == '_detection_to_dict':
        c = 'A'
    elif fname == 'validate_detection':
        c = 'F' if 'valid_media_types = ' in minus else 'E'
    elif fname in ('__init__', 'reset_stats'):
        c = 'D'
    elif fname == 'get_performance_stats':
        if '"XX' in plus or '": self._stats' in minus or '": round' in minus and '+' not in plus[:1]:
            c = 'Q'
        if '"XX' in plus:
            c = 'Q'
        elif 'avg_' in minus:
            c = 'S'
        elif 'total_duration_ms' in minus:
            c = 'R'
    elif fname == 'bulk_insert_chunked':
        if 'for i in range' in minus or 'validate: bool' in minus or (
                'bulk_insert(chunk' in minus and 'validate=None' not in plus):
            c = 'M'
        elif 'bulk_insert(chunk' in minus and 'validate=None' in plus:
            c = 'P'
        elif 'total_inserted' in minus:
            c = 'N'
        elif 'perf_counter' in minus:
            c = 'I'
        else:
            c = 'O'
    elif fname == 'bulk_insert':
        if is_log_payload():
            c = 'T' if num < 85 else 'U'
        elif 'on_conflict' in minus or 'index_elements' in minus:
            c = 'B'
        elif 'execute' in minus:
            c = 'C'
        elif 'perf_counter' in minus:
            c = 'I'
        elif 'self._stats' in minus:
            c = 'J' if 'failed_inserts' not in minus else 'L'
        elif 'failed_inputs.append' in minus:
            c = 'H'
        elif 'duration_ms=0.0' in minus or 'duration_ms=1.0' in plus or (
                'duration_ms' in minus and 'duration_ms=' in minus and num <= 12):
            c = 'G'
        elif 'inserted_count' in minus or 'inserted_ids=' in minus or 'duration_ms=duration_ms' in minus or 'failed_inputs=' in minus:
            c = 'K'
    if c is None:
        print('UNCLASSIFIED', fn, '|', minus, '=>', plus)
    else:
        CL[c].append(fn)

tot = 0
for k in sorted(CL):
    print(k, len(CL[k]))
    tot += len(CL[k])
print('TOTAL', tot)

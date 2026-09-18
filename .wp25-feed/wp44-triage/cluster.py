import json, re
from collections import defaultdict

meta = json.load(open("mutants/backend/services/retry_handler.py.meta"))
surv = [k for k,v in meta["exit_code_by_key"].items() if v == 0]

def fn_and_num(key):
    mangled = key.split(".")[-1]
    m = re.match(r'x(?:ǁRetryHandlerǁ)?(\w+)__mutmut_(\d+)$', mangled)
    return m.group(1), int(m.group(2))

clusters = {
 "C01 get_retry_handler: singleton guard and->or": ("TEST-GAP", lambda f,n: f=="_get_retry_handler"),
 "C02 _capture_system_context: captured context values clobbered to None (depths + cb state, redis arg -> None)": ("TEST-GAP", lambda f,n: f=="_capture_system_context" and n in {2,3,4,5,6,9,13}),
 "C03 _capture_system_context: debug log message -> None": ("EQUIVALENT", lambda f,n: f=="_capture_system_context" and n==12),
 "C04 _extract_error_context: truncation suffix text mutations (case/XX padding)": ("TEST-GAP", lambda f,n: f=="_extract_error_context" and n in {12,13,15,16}),
 "C05 _extract_error_context: format_exception type-arg mutants (output identical, proven)": ("EQUIVALENT", lambda f,n: f=="_extract_error_context" and n in {20,26}),
 "C06 _extract_error_context: trace content mutants (None exc / None tb / XXXX join sep)": ("TEST-GAP", lambda f,n: f=="_extract_error_context" and n in {19,21,22}),
 "C07 _extract_error_context: > vs >= truncation boundary flip": ("TEST-GAP", lambda f,n: f=="_extract_error_context" and n in {27,39}),
 "C08 _move_to_dlq: JobFailure payload kwargs clobbered to None (original_job/error/attempt_count/first_failed_at/last_failed_at/queue_name)": ("TEST-GAP", lambda f,n: f=="_move_to_dlq" and n in {38,39,40,41,42,43}),
 "C09 _move_to_dlq: datetime.now(UTC) -> datetime.now(None) for last_failed_at": ("TEST-GAP", lambda f,n: f=="_move_to_dlq" and n==62),
 "C10 _move_to_dlq: overflow_policy REJECT -> None / kwarg removed": ("TEST-GAP", lambda f,n: f=="_move_to_dlq" and n in {66,69}),
 "C11 _move_to_dlq: return False -> True on queue-full and exception paths": ("TEST-GAP", lambda f,n: f=="_move_to_dlq" and n in {91,116}),
 "C12 _move_to_dlq: DATA-LOSS (circuit-open) ERROR audit extra key mutations": ("TEST-GAP", lambda f,n: f=="_move_to_dlq" and n in set(range(12,33))),
 "C13 _move_to_dlq: queue-full ERROR log payload key mutations": ("LOW-VALUE", lambda f,n: f=="_move_to_dlq" and n in {71,72,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90}),
 "C14 _move_to_dlq: success INFO log message/extra mutations": ("LOW-VALUE", lambda f,n: f=="_move_to_dlq" and n in {92,93,95,96,97,98,99,100,101,102,103}),
 "C15 _move_to_dlq: warning/exception-path ERROR log message & extra mutations": ("LOW-VALUE", lambda f,n: f=="_move_to_dlq" and n in {3,105,106,108,109,110,111,112,113,114,115}),
 "C16 move_dlq_job_to_queue: call-arg mutations (requeue arg -> None, overflow_policy DLQ -> None / removed)": ("TEST-GAP", lambda f,n: f=="move_dlq_job_to_queue" and n in {4,8,11}),
 "C17 move_dlq_job_to_queue: failure/backpressure/success/exception log payload mutations": ("LOW-VALUE", lambda f,n: f=="move_dlq_job_to_queue" and n not in {4,8,11}),
 "C18 requeue_dlq_job: INFO/ERROR log payload mutations": ("LOW-VALUE", lambda f,n: f=="requeue_dlq_job"),
 "C19 reset_dlq_circuit_breaker: INFO log message/extra mutations": ("LOW-VALUE", lambda f,n: f=="reset_dlq_circuit_breaker"),
 "C20 clear_dlq: INFO/ERROR log payload mutations": ("LOW-VALUE", lambda f,n: f=="clear_dlq"),
 "C21 get_dlq_jobs: ERROR log payload mutations": ("LOW-VALUE", lambda f,n: f=="get_dlq_jobs"),
 "C22 get_dlq_stats: ERROR log payload mutations": ("LOW-VALUE", lambda f,n: f=="get_dlq_stats" and n in {13,14}),
 "C23 get_dlq_stats: queue-name args -> None (wrong queue read)": ("TEST-GAP", lambda f,n: f=="get_dlq_stats" and n in {3,5}),
}

assign = defaultdict(list)
unassigned = []
for k in surv:
    f,n = fn_and_num(k)
    hit = []
    for c,(cls,pred) in clusters.items():
        if pred(f,n):
            hit=[c]; break
    if len(hit)==1: assign[hit[0]].append(k)
    elif len(hit)==0: unassigned.append((k,f,n))
    else: unassigned.append((k,f,n,"MULTI:"+",".join(hit)))

total=0
for c,(cls,_) in clusters.items():
    ks = assign[c]
    nums = sorted(int(re.search(r'mutmut_(\d+)$', k).group(1)) for k in ks)
    total += len(ks)
    print(f"{cls:12} {len(ks):3}  {c}")
    print(f"      nums: {nums}")
print("TOTAL", total, "of", len(surv))
print("UNASSIGNED:", unassigned)

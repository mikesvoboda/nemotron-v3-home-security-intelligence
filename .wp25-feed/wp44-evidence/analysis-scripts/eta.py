import json, sys
from pathlib import Path
from mutmut.utils.format_utils import mangled_name_from_mutant_name

root = Path(".")
stats = json.loads((root/"mutants/mutmut-stats.json").read_text())
dur = stats["duration_by_test"]
tests_by_fn = {k: v for k, v in stats["tests_by_mangled_function_name"].items()}

def est(key):
    tests = tests_by_fn.get(mangled_name_from_mutant_name(key), set())
    return sum(dur.get(t, 0.0) for t in tests)

unchecked = []
checked_est = 0.0
n_checked = 0
unmatched = 0
for meta_path in root.joinpath("mutants").glob("backend/**/*.py.meta"):
    meta = json.loads(meta_path.read_text())
    for key, code in meta["exit_code_by_key"].items():
        e = est(key)
        if not tests_by_fn.get(mangled_name_from_mutant_name(key)):
            unmatched += 1
        if code is None:
            unchecked.append(e)
        else:
            checked_est += e
            n_checked += 1

unchecked.sort()
total_unchecked = sum(unchecked)
print(f"checked={n_checked} (est test-time {checked_est/3600:.2f}h)")
print(f"unchecked={len(unchecked)} (est test-time {total_unchecked/3600:.2f}h)")
print(f"unmatched-to-stats mutants: {unmatched}")
import statistics
if unchecked:
    n = len(unchecked)
    print(f"unchecked est per mutant: p50={unchecked[n//2]:.2f}s mean={total_unchecked/n:.2f}s max={unchecked[-1]:.0f}s")
    # wall at 12 workers with C seconds of fixed boot per mutant
    for C in (0, 8.5):
        wall = sum(e + C for e in unchecked) / 12 / 3600
        print(f"wall @12 workers, boot={C}s: {wall:.1f}h")
    # how far does 240min@12 get us (boot 8.5)
    cap = 240*60*12
    acc = 0; cnt = 0
    for e in unchecked:
        acc += e + 8.5
        if acc > cap: break
        cnt += 1
    print(f"240-min CI step @12 covers ~{cnt} unchecked mutants ({cnt/n*100:.1f}%)")

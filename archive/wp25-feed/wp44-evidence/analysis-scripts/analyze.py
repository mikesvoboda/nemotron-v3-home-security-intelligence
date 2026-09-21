"""Scratch analysis importing the SHIPPED selector (read-only). No repo writes."""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "/tmp/wp25clone/scripts")
import fast_select as fs  # noqa: E402

root = Path("/tmp/wp25clone")
tests = fs.test_files(root)
index = defaultdict(list)
for t in tests:
    for ref in fs.dotted_refs(root, t):
        index[ref].append(t)
inv = fs.producers_of(root)  # inv[X] = importers of X


def direct(dotted):
    return fs.referrers(index, dotted)


# ===== T2: bare-package-only importers (change to __init__ must pull them) =====
print("===== T2 bare-package-only importers =====")
for pkg in [
    "backend.models",
    "backend.api.schemas",
    "backend.api.middleware",
    "backend.services",
    "backend.jobs",
]:
    bare = set(index.get(pkg, []))
    deeper = set()
    for k, v in index.items():
        if k.startswith(pkg + "."):
            deeper.update(v)
    only = sorted(bare - deeper)
    if only:
        print(f"{pkg}: {len(only)} bare-only tests e.g. {only[:3]}")

# ===== T4: clean 2-hop leaf -> inter -> top, top has direct test =====
print("\n===== T4 clean 2-hop chains (leaf probed; top has direct test) =====")
rows = []
for leaf in inv:
    if not leaf.startswith(("backend.services.", "backend.core.", "backend.models.")):
        continue
    for inter in inv[leaf]:
        if inter.startswith("backend.tests") or inter.startswith("backend.api.routes.__init__"):
            continue
        for top in inv.get(inter, ()):
            if top.startswith("backend.tests"):
                continue
            if leaf in inv.get(top, ()):  # top also directly imports leaf -> depth1
                continue
            d = direct(top)
            if not d:
                continue
            # prefer: leaf itself is NOT directly referenced by top's tests
            rows.append((leaf, inter, top, sorted(d)[0]))

# de-dupe and show a handful with short names (cleaner as playbook cases)
seen = set()
shown = 0
for leaf, inter, top, t in sorted(rows, key=lambda r: (len(r[0]), len(r[2]))):
    key = (leaf, top)
    if key in seen:
        continue
    seen.add(key)
    print(f"leaf={leaf}\n  inter={inter}\n  top={top}  direct-test={t}")
    shown += 1
    if shown >= 30:
        break

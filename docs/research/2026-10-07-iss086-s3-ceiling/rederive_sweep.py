#!/usr/bin/env python3
"""ISS-086 S3-ceiling re-derivation, PART 1 — the committed-corpus half.

Re-derives, from git-tracked data only (no GPU, no store, no network), the exact-row
claims the ISS-086 charter carries as `[A]` agent analysis:

  C1 score polarization     (claimed: 68% of scores in {0,5,10}, 23% >=75, 8% in 20..70)
  C2 AUROC incident vs benign (claimed ~0.70)
  C3 best single threshold  (claimed 42% TPR @ 5% FPR)
  C4 miss anatomy           (claimed 148/153 confirmed, 127/153 <=10)
  C5 A-group recovery       (claimed 8B 2/64, flagship ~7/64)
  C6 the ceiling            (B+C perfect -> S3 <= 177/241 = 73.4%)
  C7 twin-pair AUROC        (A-scenario incident vs its zone-sharing benign look-alike)

Data sources (both committed; read read-only):
  docs/benchmarks/synthbench/sweep-2026-10-03/items.csv   per-item scores+verdicts, 15 arms
  synthbench/taxonomy/tier_b_v0.yaml                      risk bands, zones (for twin pairing)

The pre-rubric control arm (`control-q4km`) is the cell that reproduces the charter's
`[A]` numbers. The fourteen model arms bound the ceiling across sizes and quantizations.
Run from anywhere; paths are resolved relative to this file.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ITEMS = REPO / "docs/benchmarks/synthbench/sweep-2026-10-03/items.csv"
TAXO = REPO / "synthbench/taxonomy/tier_b_v0.yaml"

# The charter's "stranger or intent" group (its A-scenarios): visually indeterminate from
# a benign look-alike because intent, not appearance, is what separates them.
A_GROUP = {"package_theft", "loitering", "peering_into_windows",
           "trying_car_doors", "casing_with_phone", "tailgating"}
# For each A-scenario, the benign twin(s) that share its zone (the twin-pair test).
CONTROL_ARM = "control-q4km"


def level_of(score: int) -> int:
    """S3 floor rank, mirroring backend/evaluation/levels.py: low<=29, medium<=59, high<=84, else crit."""
    if score <= 29:
        return 0
    if score <= 59:
        return 1
    if score <= 84:
        return 2
    return 3


def auroc(pos: list[int], neg: list[int]) -> tuple[float, int, int]:
    """Mann-Whitney AUROC with ties counted at 0.5."""
    if not pos or not neg:
        return float("nan"), len(pos), len(neg)
    wins = ties = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1
            elif p == n:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg)), len(pos), len(neg)


def load_taxonomy_zones() -> dict[str, dict]:
    """Minimal parse: per-scenario label + zones, for C7 twin pairing."""
    out: dict[str, dict] = {}
    cur = None
    for line in TAXO.read_text().splitlines():
        if (m := re.match(r"\s*- id: (\S+)", line)):
            cur = {"label": None, "zones": []}
            out[m.group(1)] = cur
        elif cur is not None and (m := re.match(r"\s*label: (\S+)", line)):
            cur["label"] = m.group(1)
        elif cur is not None and (m := re.match(r"\s*zones: \[([^\]]*)\]", line)):
            cur["zones"] = [z.strip() for z in m.group(1).split(",") if z.strip()]
    return out


def main() -> None:
    taxo = load_taxonomy_zones()
    rows = list(csv.DictReader(ITEMS.open()))
    arms = sorted({c.rsplit("__", 1)[0] for c in rows[0] if c.endswith("__score")})
    print(f"# rows={len(rows)} arms={len(arms)} taxonomy_scenarios={len(taxo)}")

    for arm in arms:
        items = []
        for r in rows:
            sc = r.get(f"{arm}__score", "")
            sc = 0 if sc in ("", None) else int(sc)  # refusal/null folds to miss at floor 0
            fl = r["floor_level"]
            items.append({"scen": r["scenario"], "label": r["label"], "score": sc,
                          "verdict": r.get(f"{arm}__verdict", ""),
                          "floor": level_of(int(fl)) if fl else 0})
        inc = [i for i in items if i["label"] == "incident"]
        ben = [i for i in items if i["label"] == "benign"]
        n = len(items)

        # C1 polarization
        pol = sum(1 for i in items if i["score"] in (0, 5, 10))
        hi = sum(1 for i in items if i["score"] >= 75)
        mid = sum(1 for i in items if 20 <= i["score"] <= 70)

        # C2 AUROC incident vs benign
        au, npos, nneg = auroc([i["score"] for i in inc], [i["score"] for i in ben])

        # C3 max TPR s.t. FPR <= 5%, over every observed score as the cut
        thr_tpr = 0.0
        for t in sorted({i["score"] for i in items}):
            if sum(1 for i in ben if i["score"] >= t) / len(ben) <= 0.05:
                thr_tpr = max(thr_tpr, sum(1 for i in inc if i["score"] >= t) / len(inc))

        # C4 miss anatomy
        misses = [i for i in inc if level_of(i["score"]) < i["floor"]]
        n_hit = len(inc) - len(misses)
        conf = sum(1 for i in misses if i["verdict"] == "confirmed")
        low10 = sum(1 for i in misses if i["score"] <= 10)

        # C5 A-group recovery, C6 ceiling (B+C perfect, A at this arm's recovery)
        a_hit = a_n = 0
        for i in inc:
            if i["scen"] in A_GROUP:
                a_n += 1
                if level_of(i["score"]) >= i["floor"]:
                    a_hit += 1
        bc_n = len(inc) - a_n

        print(f"\n== {arm} ==")
        print(f"  n={n} inc={len(inc)} ben={len(ben)}")
        print(f"  S3={n_hit}/{len(inc)} = {n_hit/len(inc):.1%}")
        print(f"  C1 pol{{0,5,10}}={pol/n:.1%}  >=75={hi/n:.1%}  20..70={mid/n:.1%}")
        print(f"  C2 AUROC={au:.3f} (n+={npos} n-={nneg})")
        print(f"  C3 TPR@FPR<=5% = {thr_tpr:.3f}")
        print(f"  C4 misses={len(misses)} confirmed={conf} ({conf/max(1,len(misses)):.0%}) "
              f"score<=10: {low10} ({low10/max(1,len(misses)):.0%})")
        print(f"  C5 A(stranger/intent)={a_hit}/{a_n}")
        print(f"  C6 ceiling if B+C perfect = {bc_n + a_hit}/{len(inc)} = {(bc_n+a_hit)/len(inc):.1%}")

    # C7 twin-pair AUROC on the control arm: incident scenario vs zone-sharing benign twin
    print(f"\n=== C7 twin pairs on {CONTROL_ARM} (incident vs zone-sharing benign look-alike) ===")
    by_scen: defaultdict[str, list[int]] = defaultdict(list)
    for r in rows:
        sc = r.get(f"{CONTROL_ARM}__score", "")
        if sc not in ("", None):
            by_scen[r["scenario"]].append(int(sc))
    seen_pairs: set[tuple[str, str]] = set()
    for inc_s in sorted(A_GROUP):
        zones = set(taxo.get(inc_s, {}).get("zones", []))
        cands = []
        for ben_s, meta in taxo.items():
            if meta["label"] != "benign":
                continue
            shared = zones & set(meta["zones"])
            if shared and by_scen.get(ben_s):
                cands.append((len(shared), ben_s, sorted(shared)))
        cands.sort(reverse=True)
        for _, ben_s, shared in cands[:3]:
            seen_pairs.add((inc_s, ben_s))
            a, p, q = auroc(by_scen[inc_s], by_scen[ben_s])
            print(f"    {inc_s} vs {ben_s}: AUROC={a:.3f} (n={p}/{q}) zones={','.join(shared)}")
    print("  the charter's two named twin pairs (doc 20 section 2):")
    for inc_s, ben_s in (("package_theft", "delivery_driver"), ("loitering", "neighbor_passing")):
        if (inc_s, ben_s) not in seen_pairs:
            a, p, q = auroc(by_scen[inc_s], by_scen[ben_s])
            print(f"    {inc_s} vs {ben_s}: AUROC={a:.3f} (n={p}/{q}) (charter-named)")


if __name__ == "__main__":
    main()

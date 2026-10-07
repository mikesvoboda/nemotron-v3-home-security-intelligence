#!/usr/bin/env python3
"""ISS-086 S3-ceiling re-derivation, PART 2 — the eval-store half (shipped arm B).

Same C1-C7 measurements as `rederive_sweep.py`, against the CURRENTLY SHIPPED path:
the OD-29 dogfood replay of the arm-B rubric prompt (build b7972 @ commit 8107ee63),
store run `663da001ab5840ab85e672dba777d801`. Scenarios join through the committed
`items.csv`; the dev/holdout roster comes from the store's own `splits` table.

Run:  AGENT_GPU_DIR=/path/to/gpu/out python3 rederive_shipped.py [--store PATH]

Needs the eval store (it survives on the GPU host at
`$AGENT_GPU_DIR/out/sbroot/eval/tierb-v0/eval.sqlite`, same as the register says). If it
is gone, the part-1 numbers still stand — only the shipped-arm overlay is lost, which is
exactly the fragility the register warns about.
"""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rederive_sweep import A_GROUP, REPO, TAXO, auroc, level_of, load_taxonomy_zones  # exact shared defs

RUN = "663da001ab5840ab85e672dba777d801"  # pragma: allowlist secret  (eval run id, not a credential)
ITEMS_CSV = REPO / "docs/benchmarks/synthbench/sweep-2026-10-03/items.csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=os.environ.get(
        "AGENT_GPU_DIR", "") + "/out/sbroot/eval/tierb-v0/eval.sqlite")
    args = ap.parse_args()
    if not Path(args.store).is_file():
        sys.exit(f"eval store not found at {args.store}\n"
                 f"set $AGENT_GPU_DIR or pass --store; part 1 does not need it")

    meta = {r["item_id"]: r for r in csv.DictReader(ITEMS_CSV.open())}
    c = sqlite3.connect(f"file:{args.store}?mode=ro", uri=True)
    rows = c.execute("select item_id, verdict, risk_score from results where run_id=?",
                     (RUN,)).fetchall()
    holdout = {r for (r,) in c.execute(
        "select scenario from splits where arm='holdout'")}

    items, unmatched = [], 0
    for item_id, verdict, score in rows:
        m = meta.get(item_id)
        if m is None:
            unmatched += 1
            continue
        sc = int(score) if score not in (None, "") else 0  # refusal -> miss at floor 0
        fl = m["floor_level"]
        items.append({"scen": m["scenario"], "label": m["label"], "score": sc,
                      "verdict": verdict, "floor": level_of(int(fl)) if fl else 0})

    print(f"# store rows={len(rows)} matched={len(items)} unmatched={unmatched} "
          f"holdout_scenarios={len(holdout)}")
    inc = [i for i in items if i["label"] == "incident"]
    ben = [i for i in items if i["label"] == "benign"]
    n = len(items)

    misses = [i for i in inc if level_of(i["score"]) < i["floor"]]
    hits = len(inc) - len(misses)
    print(f"S3(shipped, whole corpus) = {hits}/{len(inc)} = {hits/len(inc):.1%}")
    for arm_name, pool in (("dev", [i for i in items if i["scen"] not in holdout]),
                           ("holdout", [i for i in items if i["scen"] in holdout])):
        p_ = [i for i in pool if i["label"] == "incident"]
        h_ = sum(1 for i in p_ if level_of(i["score"]) >= i["floor"])
        a_ = sum(1 for i in p_ if i["scen"] in A_GROUP)
        print(f"  {arm_name}: S3 {h_}/{len(p_)} = {h_/len(p_):.1%} "
              f"(A-group share of incidents: {a_}/{len(p_)} = {a_/len(p_):.1%})")

    print(f"C1 pol{{0,5,10}}={sum(1 for i in items if i['score'] in (0,5,10))/n:.1%}  "
          f">=75={sum(1 for i in items if i['score']>=75)/n:.1%}  "
          f"20..70={sum(1 for i in items if 20<=i['score']<=70)/n:.1%}")
    au, np_, nn_ = auroc([i["score"] for i in inc], [i["score"] for i in ben])
    print(f"C2 AUROC={au:.3f} (n+={np_} n-={nn_})")
    thr_tpr = 0.0
    for t in sorted({i["score"] for i in items}):
        if sum(1 for i in ben if i["score"] >= t) / len(ben) <= 0.05:
            thr_tpr = max(thr_tpr, sum(1 for i in inc if i["score"] >= t) / len(inc))
    print(f"C3 TPR@FPR<=5% = {thr_tpr:.3f}")
    print(f"C4 misses={len(misses)} confirmed={sum(1 for i in misses if i['verdict']=='confirmed')} "
          f"score<=10: {sum(1 for i in misses if i['score']<=10)}")

    print("C5 per-A-scenario (shipped arm, whole corpus):")
    a_hits = 0
    gsc: defaultdict[str, list[int]] = defaultdict(lambda: [0, 0])
    for i in inc:
        if i["scen"] in A_GROUP:
            gsc[i["scen"]][1] += 1
            if level_of(i["score"]) >= i["floor"]:
                gsc[i["scen"]][0] += 1
                a_hits += 1
    for s in sorted(gsc):
        h, t = gsc[s]
        print(f"    {s:24s} {h}/{t}")
    bc = len(inc) - sum(t for _, t in gsc.values())
    print(f"  A total = {a_hits}/{sum(t for _, t in gsc.values())}")
    print(f"C6 ceiling (B+C perfect, A as measured) = {bc + a_hits}/{len(inc)} "
          f"= {(bc+a_hits)/len(inc):.1%}")

    print("C7 twin pairs (shipped arm), zone-sharing pairs as in part 1 (top 3 per incident):")
    by_scen: defaultdict[str, list[int]] = defaultdict(list)
    for i in items:
        by_scen[i["scen"]].append(i["score"])
    taxo = load_taxonomy_zones()
    seen_pairs: set[tuple[str, str]] = set()
    for inc_s in sorted(A_GROUP):
        zones = set(taxo.get(inc_s, {}).get("zones", []))
        cands = []
        for ben_s, meta_ in taxo.items():
            if meta_["label"] != "benign":
                continue
            shared = zones & set(meta_["zones"])
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

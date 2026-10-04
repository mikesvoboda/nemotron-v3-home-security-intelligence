#!/usr/bin/env python3
"""Recompute every reading of the model sweep from items.csv and arms.csv, and apply the selection rule (OD-26).

Stdlib only. Usage: analysis.py [DIR] [--markdown] ; DIR holds items.csv and arms.csv (default: this file's folder).

SELECTION RULE (OD-26; set 2026-10-04 at the owner's direction, AFTER the readings were seen - see report.md). Output: a SHORTLIST for
confirmation on a frozen holdout, never a pick. Yardstick: the shipped model (control-q4km) on the same build and conditions.
  Gates (all must hold)
    G1  the arm scored all 450 items on the shared build and conditions
    G2  refusals <= the control's refusal count (spec S5 asks for zero unparseable verdicts; the control has 2, both budget truncations)
    G3  peak VRAM at the shipped shape <= 18.4 GiB (S1's 20.4 GiB for the whole resident set minus a 2 GiB allowance for the detector,
        specialists and runtime; an assumption to be replaced by the S1 re-take on 24 GB-class hardware, ISS-046)
  Paired test against the control (95% scenario-cluster bootstrap, 10,000 resamples of the 31 scenarios, seed 20261004;
  dS2 = S2(arm) - S2(control) in points, dS3 = S3(arm) - S3(control) in points)
    (a) no clear harm:     upper(dS2) <= +2.0  AND  lower(dS3) >= -5.0
    (b) clear benefit:     upper(dS2) <  0     OR   lower(dS3) >  0
  An arm advances iff G1, G2, G3, (a) and (b) all hold. The margins (2 and 5 points) were fixed before this script was first run.
"""
import csv, json, math, random, sys
from pathlib import Path

HERE = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else Path(__file__).resolve().parent
CONTROL = "control-q4km"
VRAM_CAP_MIB = int(18.4 * 1024)
HARM_S2, HARM_S3 = 2.0, -5.0
B, SEED = 10_000, 20261004


def wilson(k, n, z=1.959963984540054):
    if n == 0: return (0.0, 1.0)
    p = k / n; z2 = z * z; d = 1 + z2 / n; c = p + z2 / (2 * n); m = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


items = list(csv.DictReader(open(HERE / "items.csv")))
arms = list(csv.DictReader(open(HERE / "arms.csv")))
names = [a["arm"] for a in arms]
A = {a["arm"]: a for a in arms}


def score(row, arm):
    s = row[f"{arm}__score"]
    return None if s == "" else int(float(s))


def flags(arm):
    """Per item: (false_alarm, hit). A refusal (no score) is neither: it stays in the denominator as a non-event."""
    out = {}
    for r in items:
        s = score(r, arm)
        if r["label"] == "benign": out[r["item_id"]] = (1 if (s is not None and s >= 30) else 0, None)
        else: out[r["item_id"]] = (None, 1 if (s is not None and s >= int(r["floor_level"])) else 0)
    return out


F = {a: flags(a) for a in names}
benign = [r["item_id"] for r in items if r["label"] == "benign"]; incident = [r["item_id"] for r in items if r["label"] == "incident"]


def auroc_recall(arm):
    pos = [(-1 if score(r, arm) is None else score(r, arm)) for r in items if r["label"] == "incident"]
    neg = [(-1 if score(r, arm) is None else score(r, arm)) for r in items if r["label"] == "benign"]
    vals = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg]); ranks = {}; i = 0
    while i < len(vals):
        j = i
        while j < len(vals) and vals[j][0] == vals[i][0]: j += 1
        for k in range(i, j): ranks[k] = (i + j - 1) / 2 + 1
        i = j
    sp = sum(ranks[k] for k, (v, l) in enumerate(vals) if l == 1); n1, n0 = len(pos), len(neg)
    au = (sp - n1 * (n1 + 1) / 2) / (n1 * n0)
    best = 0.0
    for t in sorted(set(pos + neg) | {101}):
        if sum(1 for v in neg if v >= t) / len(neg) <= 0.05: best = max(best, sum(1 for v in pos if v >= t) / len(pos))
    return au, 100 * best


# ---- readings, recomputed and cross-checked against the harness's own counts ---------------------------------------------------
R = {}
for a in names:
    fa = sum(F[a][i][0] for i in benign); hit = sum(F[a][i][1] for i in incident); au, rec = auroc_recall(a)
    ref = sum(1 for r in items if score(r, a) is None)
    assert fa == int(A[a]["s2_false_alarms"]) and hit == int(A[a]["s3_hits"]), (a, fa, hit, A[a]["s2_false_alarms"], A[a]["s3_hits"])
    assert ref == int(A[a]["refusals"]), (a, ref)
    assert abs(au - float(A[a]["auroc"])) < 0.0006 and abs(rec - float(A[a]["recall_at_5pct_fpr"])) < 0.06, (a, au, rec)
    R[a] = {"fa": fa, "nb": len(benign), "hit": hit, "ni": len(incident), "refusals": ref, "auroc": au, "recall5": rec, "vram_mib": int(A[a]["vram_peak_mib"])}

# ---- paired scenario-cluster bootstrap against the control ----------------------------------------------------------------------
scen = sorted({r["scenario"] for r in items})
rows_by_s = {s: [r["item_id"] for r in items if r["scenario"] == s] for s in scen}
kind = {r["item_id"]: r["label"] for r in items}


def cluster_table(arm):
    t = []
    for s in scen:
        ids = rows_by_s[s]
        nb = sum(1 for i in ids if kind[i] == "benign"); ni = len(ids) - nb
        t.append((nb, sum(F[CONTROL][i][0] for i in ids if kind[i] == "benign"), sum(F[arm][i][0] for i in ids if kind[i] == "benign"),
                  ni, sum(F[CONTROL][i][1] for i in ids if kind[i] == "incident"), sum(F[arm][i][1] for i in ids if kind[i] == "incident")))
    return t


def bootstrap(arm):
    t = cluster_table(arm); rng = random.Random(SEED); d2 = []; d3 = []
    for _ in range(B):
        nb = fc = fa = ni = hc = ha = 0
        for _ in range(len(t)):
            x = t[rng.randrange(len(t))]; nb += x[0]; fc += x[1]; fa += x[2]; ni += x[3]; hc += x[4]; ha += x[5]
        if nb == 0 or ni == 0: continue
        d2.append(100 * (fa - fc) / nb); d3.append(100 * (ha - hc) / ni)
    d2.sort(); d3.sort(); q = lambda v, p: v[int(p * (len(v) - 1))]
    return {"dS2": [q(d2, 0.025), q(d2, 0.975)], "dS3": [q(d3, 0.025), q(d3, 0.975)]}


def mcnemar_p(x, y):
    """Exact two-sided binomial p for discordant counts x, y (H0: each discordant pair is a fair coin). Treats items as independent."""
    n = x + y
    if n == 0: return 1.0
    k = min(x, y); tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


# paired item counts (descriptive, not clustered)
def discordant(arm):
    b = sum(1 for i in benign if F[arm][i][0] == 1 and F[CONTROL][i][0] == 0); c = sum(1 for i in benign if F[arm][i][0] == 0 and F[CONTROL][i][0] == 1)
    d = sum(1 for i in incident if F[arm][i][1] == 1 and F[CONTROL][i][1] == 0); e = sum(1 for i in incident if F[arm][i][1] == 0 and F[CONTROL][i][1] == 1)
    return {"fa_only_arm": b, "fa_only_control": c, "hit_only_arm": d, "hit_only_control": e,
            "p_s2_items_unclustered": mcnemar_p(b, c), "p_s3_items_unclustered": mcnemar_p(d, e)}


MODEL_ARMS = [a for a in names if A[a]["role"] == "model"]
out = {}
for a in MODEL_ARMS:
    bs = bootstrap(a); r = R[a]
    g1 = True; g2 = r["refusals"] <= R[CONTROL]["refusals"]; g3 = r["vram_mib"] <= VRAM_CAP_MIB
    harm_ok = bs["dS2"][1] <= HARM_S2 and bs["dS3"][0] >= HARM_S3
    benefit = bs["dS2"][1] < 0 or bs["dS3"][0] > 0
    out[a] = {**r, **bs, **discordant(a), "G1": g1, "G2": g2, "G3": g3, "no_clear_harm": harm_ok, "clear_benefit": benefit,
              "advances": bool(g1 and g2 and g3 and harm_ok and benefit)}

# Pareto frontier on (S2 low, S3 high), all 13 arms including the control (descriptive)
pts = {a: (100 * R[a]["fa"] / R[a]["nb"], 100 * R[a]["hit"] / R[a]["ni"]) for a in ["control-q4km"] + MODEL_ARMS}
front = [a for a in pts if not any(b != a and pts[b][0] <= pts[a][0] and pts[b][1] >= pts[a][1] and (pts[b][0] < pts[a][0] or pts[b][1] > pts[a][1]) for b in pts)]

json.dump({"control": CONTROL, "rule": {"vram_cap_mib": VRAM_CAP_MIB, "harm_s2_pts": HARM_S2, "harm_s3_pts": HARM_S3, "bootstrap": B, "seed": SEED},
           "arms": {a: R[a] for a in names}, "paired": out, "pareto_frontier": front}, open(HERE / "stats.json", "w"), indent=1)

# ---- print -----------------------------------------------------------------------------------------------------------------------
def pct(k, n): lo, hi = wilson(k, n); return f"{100*k/n:.1f}% [{100*lo:.1f}-{100*hi:.1f}]"
def vs_bar(k, n, bar, low_is_good):
    lo, hi = wilson(k, n); p = 100 * k / n; lo *= 100; hi *= 100
    if low_is_good: return "meets, interval straddles" if p <= bar and hi > bar else "meets" if p <= bar else "misses, interval straddles" if lo <= bar else "misses"
    return "meets" if lo >= bar else "misses"

print("| Arm | S2 false alarms | S3 incident hits | AUROC | Recall at 5% false alarms | Refusals | Peak VRAM (GiB) | Identical to control |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
for a in names:
    r = R[a]; ident = A[a]["identical_to_control_items"] or "-"
    print(f"| {a} | {r['fa']}/{r['nb']} = {pct(r['fa'], r['nb'])} | {r['hit']}/{r['ni']} = {pct(r['hit'], r['ni'])} | {r['auroc']:.3f} | {r['recall5']:.1f}% | {r['refusals']} | {r['vram_mib']/1024:.1f} | {ident}/450 |")
print()
print("| Arm | dS2 vs control, points [95% cluster CI] | dS3 vs control, points [95% cluster CI] | G2 refusals | G3 VRAM | No clear harm | Clear benefit | ADVANCES |")
print("| --- | --- | --- | --- | --- | --- | --- | --- |")
yn = lambda x: "yes" if x else "no"
for a in MODEL_ARMS:
    o = out[a]
    print(f"| {a} | {o['dS2'][0]:+.1f} to {o['dS2'][1]:+.1f} | {o['dS3'][0]:+.1f} to {o['dS3'][1]:+.1f} | {yn(o['G2'])} | {yn(o['G3'])} | {yn(o['no_clear_harm'])} | {yn(o['clear_benefit'])} | **{yn(o['advances'])}** |")
print()
print("| Arm | S2: false alarms only in arm / only in control | exact p (items independent) | S3: hits only in arm / only in control | exact p (items independent) |")
print("| --- | --- | --- | --- | --- |")
for a in MODEL_ARMS:
    o = out[a]
    print(f"| {a} | {o['fa_only_arm']} / {o['fa_only_control']} | {o['p_s2_items_unclustered']:.3g} | {o['hit_only_arm']} / {o['hit_only_control']} | {o['p_s3_items_unclustered']:.3g} |")
print("\nadvancing:", [a for a in MODEL_ARMS if out[a]["advances"]])
print("pareto frontier (S2 low, S3 high; control included):", front)
print("S2 vs the 5% bar / S3 vs the 90% bar:")
for a in names: print(f"  {a:22s} S2 {vs_bar(R[a]['fa'], R[a]['nb'], 5.0, True):28s} S3 {vs_bar(R[a]['hit'], R[a]['ni'], 90.0, False)}")

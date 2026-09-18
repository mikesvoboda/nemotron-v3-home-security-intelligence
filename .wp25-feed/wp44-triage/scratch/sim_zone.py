"""Pure-math simulation of zone_service geometry for mutant classification.

No repo imports, no pytest. Functions copied verbatim (original) from
backend/services/zone_service.py; mutants applied per-variant as flags.
"""
import math

RECT = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]
TRI = [[0.5, 0.1], [0.9, 0.1], [0.7, 0.5]]
CONC = [[0.1, 0.5], [0.4, 0.5], [0.4, 0.7], [0.2, 0.7], [0.2, 0.9], [0.1, 0.9]]
SMALL = [[0.5, 0.5], [0.501, 0.5], [0.501, 0.501], [0.5, 0.501]]
ALLIMG = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
THIN = [[0.0, 0.499], [1.0, 0.499], [1.0, 0.501], [0.0, 0.501]]
FIG8 = [[0.2, 0.2], [0.8, 0.8], [0.2, 0.8], [0.8, 0.2]]
BOW = [[0.3, 0.3], [0.7, 0.3], [0.3, 0.7], [0.7, 0.7]]
COLL = [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]]
# new candidate probes (NOT in current suite)
SLANT = [[0.1, 0.1], [0.5, 0.15], [0.45, 0.6], [0.12, 0.5]]  # first edge non-horizontal
UNIT = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
TALL = [[0.2, 0.05], [0.35, 0.05], [0.35, 0.8], [0.2, 0.8]]  # non-square rect

# ---- test-suite point probes (from test_zone_service.py assertions) ----
PIZ_PROBES = [
    (RECT, 0.25, 0.25), (RECT, 0.6, 0.25),
    (TRI, 0.7, 0.2), (TRI, 0.7, 0.6),
    (CONC, 0.15, 0.85), (CONC, 0.35, 0.6), (CONC, 0.35, 0.8),
    (RECT, 0.25, 0.1), (RECT, 0.1, 0.25), (RECT, 0.1, 0.1),
    (RECT, 0.5005, 0.5005) if False else (SMALL, 0.5005, 0.5005), (SMALL, 0.502, 0.502),
    (RECT, 0.0, 0.0), (RECT, 1.0, 1.0), (RECT, -0.1, -0.1), (RECT, 1.5, 1.5),
    (ALLIMG, 0.5, 0.5), (ALLIMG, 0.01, 0.01), (ALLIMG, 0.99, 0.99),
    (THIN, 0.5, 0.5), (THIN, 0.5, 0.4), (THIN, 0.5, 0.6),
    (FIG8, 0.5, 0.5), (BOW, 0.5, 0.5), (COLL, 0.5, 0.5),
    ([[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]], 0.1 + 1e-10, 0.15),
]
# probes an added test could use
PROBE_SET_B = [
    (SLANT, 0.3, 0.3), (SLANT, 0.05, 0.05), (SLANT, 0.9, 0.9),
    (RECT, 0.4, 0.25), (RECT, 0.4, 0.15),  # x == right edge
    (TRI, 0.5, 0.15), (TRI, 0.9, 0.15),    # x at max vertex
    (TALL, 0.3, 0.5), (TALL, 0.3, 0.95),
    (RECT, 0.25, 0.4), (RECT, 0.4, 0.4),
]


def point_in_zone(x, y, coords, *, m_start=0, m_rng=None, m_xmax=0, m_xint=0, m_cmp=0, guard="or"):
    coordinates = coords
    if guard == "or":
        if not coordinates or len(coordinates) < 3:
            return False
    else:  # mutant: `and`
        if not coordinates and len(coordinates) < 3:
            return False
    n = len(coordinates)
    inside = False
    if m_start:
        p1x, p1y = coordinates[m_start]
    else:
        p1x, p1y = coordinates[0]
    rng = range(1, n + 1) if m_rng is None else m_rng(n)
    for i in rng:
        p2x, p2y = coordinates[i % n]
        xmax_cmp = (x <= max(p1x, p2x)) if m_xmax == 0 else (x < max(p1x, p2x))
        if y > min(p1y, p2y) and y <= max(p1y, p2y) and xmax_cmp:
            if p1y != p2y:
                if m_xint == 0:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                else:
                    xinters = (y - p1y) * (p2x - p1x) * (p2y - p1y) + p1x
            if p1x == p2x:
                flip = True
            elif m_cmp == 0:
                flip = x <= xinters
            else:
                flip = x < xinters
            if flip:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _distance(p1, p2):
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def seg_dist(px, py, x1, y1, x2, y2, *, m4=0, m25=0, m26=0, m28=0, m30=0, m31=0, m38=0):
    dx = x2 - x1
    dy = (y2 + y1) if m4 else (y2 - y1)
    if dx == 0 and dy == 0:
        return _distance((px, py), (x1, y1))
    num = ((px + x1) if m28 else (px - x1)) * dx + (((py + y1) if m30 else (py - y1)) * ((-dy if m26 else dy)))
    den = (dx * dx - dy * dy) if m31 else (dx * dx + dy * dy)
    if m25:
        t = max(0, min(1, num * den))
    else:
        t = max(0, min(1, num / den))
    closest_x = x1 + t * dx
    closest_y = (y1 - t * dy) if m38 else (y1 + t * dy)
    return _distance((px, py), (closest_x, closest_y))


def dist_to_boundary(x, y, coords, *, m25=0, m26=0, guard="or", infm=0):
    coordinates = coords
    bad = (not coordinates or len(coordinates) < 3) if guard == "or" else (not coordinates and len(coordinates) < 3)
    if bad:
        return float("INF") if infm else float("inf")
    if point_in_zone(x, y, coordinates):
        return 0.0
    min_distance = float("INF") if infm else float("inf")
    n = len(coordinates)
    for i in range(n):
        x1, y1 = coordinates[i]
        if m25:
            x2, y2 = coordinates[(i - 1) % n]
        elif m26:
            x2, y2 = coordinates[(i + 2) % n]
        else:
            x2, y2 = coordinates[(i + 1) % n]
        d = seg_dist(x, y, x1, y1, x2, y2)
        min_distance = min(min_distance, d)
    return min_distance


def report(name, results):
    diff = [(c, x, y, a, b) for (c, x, y), (a, b) in results.items() if a != b]
    killed_by_suite = [d for d in diff if d[0] in {tuple(map(tuple, p[0])) if isinstance(p[0], list) else p[0] for p in []} or True]
    print(f"### {name}: inputs differing: {len(diff)}")
    for c, x, y, a, b in diff[:6]:
        print(f"    coords={c[:2]}... pt=({x},{y})  orig={a} mut={b}")
    return diff


if __name__ == "__main__":
    print("== sanity: original matches a few known assertions ==")
    assert point_in_zone(0.25, 0.25, RECT) is True
    assert point_in_zone(0.6, 0.25, RECT) is False
    assert point_in_zone(0.7, 0.2, TRI) is True
    assert point_in_zone(0.15, 0.85, CONC) is True
    assert point_in_zone(0.35, 0.8, CONC) is False
    assert point_in_zone(0.5005, 0.5005, SMALL) is True
    assert abs(dist_to_boundary(0.6, 0.25, RECT) - 0.2) < 1e-9
    assert seg_dist(0.5, 0.0, 0.0, 0.0, 1.0, 0.0) == 0.0
    assert seg_dist(2.0, 0.0, 0.0, 0.0, 1.0, 0.0) == 1.0
    print("   ok")

    def key(c, x, y):
        return (repr(c), x, y)
    ALL = PIZ_PROBES + PROBE_SET_B
    suite_pts = {key(c, x, y) for (c, x, y) in PIZ_PROBES}

    variants = {
        "piz__13 start=v1": dict(m_start=1),
        "piz__16 range(n+1)": dict(m_rng=lambda n: range(n + 1)),
        "piz__20 range(1,n+2)": dict(m_rng=lambda n: range(1, n + 2)),
        "piz__35 x<max": dict(m_xmax=1),
        "piz__43 xinters*": dict(m_xint=1),
        "piz__50 x<xinters": dict(m_cmp=1),
        "piz__4 guard and": dict(guard="and"),
    }
    print("\n== point_in_zone mutants: does suite input differ? / can NEW probes differ? ==")
    for name, kw in variants.items():
        res = {}
        err = None
        for (c, x, y) in ALL:
            try:
                a = point_in_zone(x, y, c)
                b = point_in_zone(x, y, c, **kw)
            except Exception as e:  # noqa
                err = repr(e)
                break
            res[key(c, x, y)] = (a, b)
        if err:
            print(f"### {name}: ERROR {err}")
            continue
        d_suite = [k for k, (a, b) in res.items() if a != b and k in suite_pts]
        d_new = [k for k, (a, b) in res.items() if a != b and k not in suite_pts]
        print(f"### {name}: differ-on-suite={len(d_suite)} differ-on-new={len(d_new)}")
        for k in (d_suite + d_new)[:5]:
            print("     ", k, res[k])

    print("\n== segment mutants: suite uses ONLY horizontal segment y1=y2=0 through origin ==")
    suite_seg = [(0.5, 0.0, 0, 0, 1, 0), (0.0, 0.0, 0, 0, 1, 0), (0.5, 1.0, 0, 0, 1, 0), (2.0, 0.0, 0, 0, 1, 0), (1.0, 0.0, 0, 0, 0, 0)]
    new_seg = [
        (0.5, 0.5, 1, 1, 3, 3),      # diagonal, off-origin: point projects onto interior
        (4.0, 4.0, 1, 1, 3, 3),      # beyond end
        (0.0, 3.0, 1, 0, 3, 2),      # oblique
        (2.0, 2.0, 1, 2, 1, 5),      # vertical, off-origin
    ]
    seg_kw = {"m4": 4, "m25": 25, "m26": 26, "m28": 28, "m30": 30, "m31": 31, "m38": 38}
    for mk, mv in seg_kw.items():
        res = {}
        err = None
        for pt in suite_seg + new_seg:
            try:
                a = seg_dist(*pt)
                b = seg_dist(*pt, **{mk: 1})
            except Exception as e:  # noqa
                b = f"ERR:{type(e).__name__}"
            res[pt] = (a, b)
        ds = [k for k, v in res.items() if k in suite_seg and v[0] != v[1]]
        dn = [k for k, v in res.items() if k not in suite_seg and v[0] != v[1]]
        print(f"### seg__{mv}: suite-differ={len(ds)} new-differ={len(dn)}")
        for k in dn[:3]:
            print("     ", k, res[k])

    print("\n== boundary mutants ==")
    suite_b = [(RECT, 0.25, 0.25), (RECT, 0.6, 0.25), ([], 0.5, 0.5)]
    new_b = [(TALL, 0.6, 0.4), (TRI, 0.7, 0.7), (SLANT, 0.6, 0.3)]
    for name, kw in {"b__4/5 len<=3/<4": None, "b__8 INF str": dict(infm=1), "b__19 INF str": dict(infm=1), "b__25 i-1": dict(m25=1), "b__26 i+2": dict(m26=1), "b__2 guard and": dict(guard="and")}.items():
        if kw is None:
            continue
        res = {}
        for (c, x, y) in suite_b + new_b:
            a = dist_to_boundary(x, y, c)
            b = dist_to_boundary(x, y, c, **(kw or {}))
            res[(str(c), x, y)] = (round(a, 6), round(b, 6))
        ds = [k for k, v in res.items() if v[0] != v[1] and any(str(c) == k[0] and x == xx and y == yy for (c, xx, yy) in suite_b)]
        print(f"### {name}: suite-differ={[k for k in ds]}")
        # note float("INF") raises ValueError -> check separately
    for name, kw in {"b__8/19": dict(infm=1)}.items():
        try:
            dist_to_boundary(0.6, 0.25, RECT, **kw)
            print(f"### {name}: no error")
        except Exception as e:  # noqa
            print(f"### {name}: raises {type(e).__name__}")

    print("\n== candidate exact-value asserts for kill tests ==")
    print("boundary(TALL, 0.6, 0.4) =", dist_to_boundary(0.6, 0.4, TALL))
    print("boundary(TRI, 0.7, 0.7) =", dist_to_boundary(0.7, 0.7, TRI))
    print("seg(0.5,0.5; (1,1)-(3,3)) =", seg_dist(0.5, 0.5, 1, 1, 3, 3))
    print("seg(4,4; (1,1)-(3,3)) =", seg_dist(4, 4, 1, 1, 3, 3))
    print("seg(0,3; (1,0)-(3,2)) =", seg_dist(0, 3, 1, 0, 3, 2))
    print("seg(2,2; (1,2)-(1,5)) =", seg_dist(2, 2, 1, 2, 1, 5))

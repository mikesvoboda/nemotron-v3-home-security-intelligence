#!/usr/bin/env python3
"""The lane cell's whole tick reading in one read-only call (ruling 181; roles/lane.md "The tick").

    uv run python scripts/uplevel/lane_tick.py --sandbox <name> [--repo OWNER/REPO]

Prints, in tick order: my heartbeat id and age, the coordinator's age (UR-162), disk use of `/` and
`/var/lib/docker` (UR-180 pointer above 90%), the live ``BINDING NOW`` records the ruling map does not
carry (ruling 177), the PRs labelled ``review:<lane>`` and my own open PRs with their one CI read
(UR-38), and the next claimable package on my own roster queue (UR-52). It drives
``coordinator_snapshot.Snapshot`` minus that role's own three sections -- ``status_draft.py`` is the
sibling precedent for driving it -- and adds the lane's deltas.

Everything it reads arrives through one seam: ``build(run, clock, repo, sandbox)`` takes the runner,
the clock, the repo and the sandbox, so a test needs no monkeypatching and ``main`` cannot hand the
renderer a different type than it expects. Every call goes through that runner; a failed
``gh``/``git``/``df`` call prints ``ERROR <section>``, never an empty section.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: the shared readers, helpers and the one runner

PKGS, MAP = (
    "origin/main:docs/uplevel/packages/{}.md",
    "origin/main:docs/uplevel/history/ruling-map.md",
)
ROSTER = "origin/main:docs/uplevel/roles/lane.md"
# The snapshot's own list query omits these two; the digest needs the head ref (to know which PRs
# are mine) and the body (for its Plan text line). One extra read, not one per PR.
HEADJ = "number,title,headRefName,body"
MOUNTS = ("/", "/var/lib/docker")
CAP_LINES = 80  # ops.md's "at most 80 lines" for this tool -- read on the printed digest, below.
URGENT_LIFE = timedelta(hours=1)  # UR-162's one-raise-per-hour dedup window.
PLAN_TEXT = re.compile(r"^[ \t>*_#`-]*\*{0,2}Plan text:\*{0,2}[ \t]*(.*)$", re.IGNORECASE | re.M)
# A roster row is | agent | tier | queue | review label |, and the label column reads `none` for a
# cell with no review queue (coordinator, heavy-a, heavy-b, operator) -- a fact, not a missing read.
ROW = re.compile(r"\|\s*`([\w.-]+)`\s*\|[^|]*\|(.*)\|\s*`?(review:[\w-]+|none)`?\s*\|")
# A queue entry's token: the BACKTICKED NAME AT THE START of the entry (see ``queue_entries`` -- a
# backtick anywhere else in the cell is prose referring to some other package, not a slot).
QUEUE_TOKEN = re.compile(r"\s*`\[?([\w.]+)\]?`")
# The header wraps: `[r96i11]`'s and a frontend package's `**PR:**` value sits on the NEXT line.
# Bounded by the blank line after the header, so the value is the field's own continuation.
PKG_FIELD = re.compile(r"\*\*PR:\*\*([\s\S]*?)(?:\n\s*\n|\Z)", re.I)
NONE_YET = re.compile(r"[^\n#]*none yet", re.I)
# The number a package block's `**PR:**` field names. `NONE_YET`'s `[^#]` class is the proof the
# field's value carries a literal `#`, so the number is read from the same captured text.
PR_NUMBER = re.compile(r"#(\d+)")
# The package header line, as it stands AFTER splitting on "### " (the marker is gone).
BLOCK = re.compile(r"\[?([\w.]+)\]?\s")


class LaneSnap(snap.Snapshot):
    """The snapshot minus the coordinator's own three reads. ``_main`` shrinks to the ``git fetch``
    the later sections assume (UR-38's lane CI read is the gate inside ``_prs``); ``_legs`` and the
    ``_merged_audit`` are the coordinator's update-branch and merge verdicts, never a lane's.
    ``_comments`` is kept because it sets ``self.now``, which ``_binding_now``/``_heartbeats`` read."""

    def _main(self) -> None:
        self.data["main"] = {"errors": []}
        try:
            self.git("fetch", "-q", "origin")  # keep origin/main fresh for the behind count
        except Exception as exc:  # reported, not fatal
            self.data["main"]["errors"].append(f"fetch origin: {snap.error_text(exc)}")

    def _legs(self, item: dict) -> None:
        """UR-102's no-update legs are the coordinator's merge decision, not the lane's tick."""

    def _merged_audit(self) -> None:
        self.data["merged"] = {"items": [], "errors": []}


# --- the lane's own readings -----------------------------------------------------------------


def identities(roster: str, sandbox: str) -> dict[str, str]:
    """My lane/cell/review-label and my queue, from the roster row keyed by the sandbox name.

    Every agent signs with the owner's login (UR-168), so the roster row -- not the author -- is
    what decides which lane's work is mine and which review label routes to me.
    """
    for line in roster.splitlines():
        row = ROW.search(line)
        if row and sandbox.endswith(row.group(1)):
            # Lane and cell come from the row's NAME through the snapshot's own agent_key, so the
            # digest and box 2's signed-activity rule cannot disagree about what an agent is.
            lane, cell = snap.agent_key(row.group(1))
            label = row.group(3)
            return {
                "lane": lane,
                "cell": cell or "",
                "review_label": None if label == "none" else label,
                "queue": queue_entries(row.group(2)),
            }
    raise snap.CommandError(f"no roster row for sandbox {sandbox}")


def plan_text(body: str | None) -> str:
    """The PR body's ``Plan text:`` line, read through the markdown decoration that wraps it.

    Measured on the live open PRs: the line is written ``- **Plan text:** none.``, so a
    ``startswith("Plan text:")`` scan finds it on none of them. UR-92 puts the load-bearing copy in
    the *review* body, not the PR body, so a PR nobody has reviewed yet says ``not stated`` -- it
    does not claim UR-92's default, which depends on the diff's paths.
    """
    match = PLAN_TEXT.search(body or "")
    if not match:
        return "Plan text: not stated"
    value = match.group(1).replace("`", "").strip().rstrip(".").strip()
    return f"Plan text: {snap.truncate(value or 'none', 60)}"


def raises_urgent(record: dict, now) -> bool:
    """A live UR-162 raise on #6854 -- a RAISE, not a close.

    Measured live: closes begin ``**URGENT PATH closed — coordinator stale`` and share the first
    eleven characters with a raise, so a prefix test reads a close as a live raise and stays silent
    while the coordinator is stale with no raise on record.
    """
    head = snap.undecorated(snap.first_line(record.get("text")))
    return (
        head.startswith("URGENT PATH")
        and not head.startswith("URGENT PATH closed")
        and (now - snap.parse_time(record["created_at"])) <= URGENT_LIFE
    )


def uncarried(items: list[dict], maptext: str) -> list[str]:
    """Ruling 177: a live record whose ruling number AND comment id both miss the map's rows."""
    out = []
    for b in items:
        num = re.search(r"ruling (\d+)", b["first_line"])
        # Only a `| 188 |` row means the map plans for it: the file quotes ruling numbers in prose
        # too, and a prose mention would otherwise read as carriage and hide a live ruling.
        if not (
            (num and re.search(rf"^\|\s*{num[1]}\s*\|", maptext, re.M)) or str(b["id"]) in maptext
        ):
            out.append(f"  BINDING NOW id={b['id']} not in the ruling map: {b['first_line']}")  # fmt: skip
    return out


def disk(df: str | None, mounts: Sequence[str] = MOUNTS) -> list[str]:
    """UR-180's two mounts; above 90% point at its cleanup ORDER, never a routine full prune.

    A mount the answer does not carry is named as unread rather than dropped: an absent line reads
    as "no disk problem" to a lane that does not know the line was never there.
    """
    rows = {}
    for row in (df or "").splitlines()[1:]:
        cols = row.split()
        if len(cols) >= 5 and cols[4].endswith("%"):
            rows[cols[-1]] = cols[4]
    out = []
    for mount in mounts:
        use = rows.get(mount)
        if use is None:
            out.append(f"  disk {mount} unread (not in df's answer)")
            continue
        over = int(use.rstrip("%")) > 90
        out.append(
            f"  disk {mount} {use}" + (" — over 90%: UR-180's cleanup order" if over else "")
        )
    return out  # fmt: skip


def queue_entries(column: str) -> list[str]:
    """The queue tokens of a roster cell, read as ENTRIES -- not as every backticked word.

    The column is a comma/semicolon-separated list where each entry is a token plus prose, and prose
    legitimately backticks other packages: ops-b's `F2.3` row says "after `[r157]`'s runner is ready
    for the owner" (measured on the live digest, which then reported [r157] held twice), and
    heavy-b's row says "`B2.3` once `O2.4` passes". A ``findall`` over the whole cell turns both of
    those references into queue slots -- and a reference that becomes a queue entry is a package the
    digest will OFFER TO CLAIM, including one that belongs to another lane. So: split on top-level
    separators only (a comma inside `(OP-3, after ...)` separates prose, not entries), then take the
    FIRST token of each entry, because the prose that follows it can name anything.
    """
    entries, depth, cur = [], 0, ""
    for ch in column:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            entries.append(cur)
            cur = ""
            continue
        cur += ch
    entries.append(cur)
    out = []
    for entry in entries:
        # LEADING token only (measured: every real entry in main's roster starts with its token). An
        # entry whose backtick appears mid-prose is routing prose -- "`B2.3` once `O2.4` passes" and
        # "then assigned `heavy` PRs" -- and skipping it can only OMIT a slot, never INVENT one.
        # That asymmetry is the point: an invented slot gets OFFERED for claim, another lane's work.
        if m := QUEUE_TOKEN.match(entry):
            out.append(m.group(1))
    return out


def held_claims(packages: str, mine: list[dict]) -> list[str]:
    """Every package in MY lane's file that I already hold -- the open claims UR-52 counts.

    UR-52 lets an agent claim only "on any tick where it has no open package", so an open package is
    what closes the claim leg. The scan walks the **package file**, not the roster queue: the two
    sources disagree in both directions and a hold the queue does not name is still a hold. Measured
    on ``main``: ops-a holds ``[r162]`` (#7114 open, titled ``[r162]``, and ``ops.md``'s own field
    reads ``**PR:** #7114 (open)``) while its roster column at ``roles/lane.md:23`` carries no
    ``[r162]`` token at all -- so a queue-driven scan answered "no holds" and the digest offered
    ``next claimable: r164a`` mid-flight, the exact queue-jump UR-52 forbids. Gating on the queue was
    the defect: an index built from one file used to answer a question the other file defines.
    ``next_claimable`` stays queue-ordered -- a FRESH claim must be a queue slot -- only eligibility
    widens to file-wide holds. Cannot over-suppress across a lane's cells, because ``mine`` is
    already branch-filtered upstream.

    Two independent hold readings, because either can be the only live one: the ``[<pkg>]`` **title
    token** of an open PR (authoritative; a ``[UR-nn]`` defect fix -- UR-48, no package number --
    titles no package and gates nothing), or the block's own ``**PR:**`` number naming a PR of mine.
    A ``**PR:** none yet`` block is never a field-hold even when its prose cites a ``#`` issue:
    ``[r172]`` reads ``none yet. (ruling 172; issue #7102)`` on main, and an issue reference is not
    a claim, so ``NONE_YET`` is honoured here exactly as ``next_claimable`` honours it.
    """
    numbers = {str(p.get("number")) for p in mine}
    titles = " ".join(p.get("title", "") for p in mine)
    held = []
    for block in packages.split("### ")[1:]:
        m = BLOCK.match(block)
        if not m:
            continue
        token = m.group(1)
        if f"[{token}]" in titles:
            held.append(token)
            continue
        field = PKG_FIELD.search(block)
        if field and NONE_YET.match(field.group(1).lstrip()):
            continue
        named = PR_NUMBER.search(field.group(1)) if field else None
        if named and named.group(1) in numbers:
            held.append(token)
    return held


def next_claimable(packages: str, queue: list[str], mine: list[dict]) -> str | None:
    """First package on MY roster queue that carries no PR and that no open PR of mine titles.

    Three readings the file's shapes force. (1) The queue, not the file: ``ops.md`` carries ops-a's
    ``[r164a]`` with ``**PR:** none yet`` ahead of mine, so a scan of the file offers another cell's
    package. (2) The title, not the row: the ``**PR:**`` field is coordinator-owned and lags the
    claim, so the package would be offered to me while I am mid-flight on it. (3) Only on a tick
    with no open package, which ``held_claims`` enforces in ``build`` -- a claimable line printed
    beside an open package is an invitation to queue-jump, which UR-52 forbids.
    """
    titles = " ".join(p.get("title", "") for p in mine)
    blocks = {m.group(1): b for b in packages.split("### ")[1:] if (m := BLOCK.match(b))}
    for token in queue:
        block = blocks.get(token)
        if block is None:
            continue  # a queue entry that is not a package block here (an F2.3 batch, a trigger)
        field = PKG_FIELD.search(block)
        if field and NONE_YET.match(field.group(1).lstrip()) and token not in titles:
            return token
    return None


def behind(run, repo: str, number: int) -> str:
    """Commits ``origin/main`` has that this head lacks -- the number a rebase decision needs.

    The reversed range (``head..origin/main``) counts the head's own work ahead of main, which is a
    different number and the wrong one here.
    """
    return run(
        ["git", "rev-list", "--count", f"refs/remotes/origin/pr/{number}..origin/main"]
    ).strip()


# --- rendering ------------------------------------------------------------------------------


def build(
    run: Callable[[Sequence[str]], str], clock: Callable[[], object], repo: str, sandbox: str
) -> list[str]:
    """The tick's readings, in tick order, from one runner and one clock. Read-only."""
    s = LaneSnap(repo, run, clock, None)
    data = s.build()
    extra: list[str] = []

    def call(cmd: Sequence[str], tag: str) -> str | None:
        try:
            return run(cmd)
        except Exception as exc:  # reported in its section, never a silent empty one
            extra.append(f"  ERROR {tag}: {snap.error_text(exc)}")
            return None

    def api(path: str, tag: str) -> list:
        return snap.parse_json_stream(call(["gh", "api", path, "--paginate"], tag) or "")

    def show(path: str, tag: str) -> str:
        return call(["git", "show", path], tag) or ""

    def packages(lane: str) -> str:
        """This lane's package file, or ``""`` when the lane has none. A lane with no package file on ``main``
        is a fact about the programme, not a failed read, and prints a NOTE rather than an ERROR.

        ``main`` carries package files for backend/docs/frontend/ops only (measured: 4 files), and
        the roster's coordinator, heavy-a, heavy-b and operator rows have work that is never
        packaged -- so this case is one of the two roles box 3 points here. Existence is asked
        positively, by ``ls-tree``'s answer, because a failing ``git show`` cannot tell "no package
        file for this lane" apart from "the read broke": both arrive as a non-zero exit, and
        reading git's stderr to separate them makes the classification depend on the wording of an
        error message. A NOTE is safe either way -- the lane's next package comes from its roster
        row, which is the same answer the file would have given.
        """
        ref = PKGS.format(lane)
        try:
            # `:/` makes the pathspec top-level-relative, so the answer does not depend on which
            # directory the tick happened to run from (git show's `<rev>:<path>` form already is).
            listed = run(["git", "ls-tree", "origin/main", "--", f":/{ref.partition(':')[2]}"])
            if not listed.strip():
                extra.append(f"  NOTE no package file for lane {lane}: next claimable not read")
                return ""
            return run(["git", "show", ref])
        except Exception as exc:
            extra.append(f"  ERROR packages: {snap.error_text(exc)}")
            return ""

    try:
        # Read directly, not through call(): this is the one failure that ends the report, and a
        # call() that already logged it would put one cause in the report twice under two names.
        ids = identities(run(["git", "show", ROSTER]), sandbox)
    except Exception as exc:  # without the lane nothing downstream can be keyed
        return [f"ERROR identities: {snap.error_text(exc)}"]
    now = snap.parse_time(data["cursor"]["now"])
    beats = {h["agent"]: h for h in data["heartbeats"].get("items", [])}
    # Matched by AGENT IDENTITY, not by the string an agent happened to pass. The roster row lookup
    # above already does this deliberately (`.endswith`), because `--sandbox` arrives either as the
    # hostname (`agent-uplevel-ops-b`, what `$SANDBOX_NAME`/`hostname` give and so what the role
    # docs' `<your-sandbox>` resolves to) or as the marker name (`uplevel-ops-b`), and BOTH spellings
    # are live on #6958 -- measured: `uplevel-ops-a`, `uplevel-ops-b` and `uplevel-operator` beat
    # bare while `agent-uplevel-backend`, `-frontend`, `-docs`, `-coordinator` and `-heavy-a/b` beat
    # prefixed. A plain `beats.get(sandbox)` therefore missed a lane's OWN beat whenever the two
    # spellings disagreed: the digest printed `ERROR heartbeats` AND, worse, fell through to the
    # coordinator's cursor as the comment window, silently re-labelling step 4's `Nc/Nr since beat`.
    # `agent_key` is the snapshot's existing normalization -- the same one box 2's signed-activity
    # rule uses -- so the two readings cannot disagree about which agent an argument names.
    my_key = snap.agent_key(sandbox)
    # Freshest, not first: an agent is supposed to keep ONE beat (the role docs edit it in place) but
    # the marker spelling is not stable, so two rows can collapse to one identity -- and the
    # heartbeat endpoint is not reliably sorted, so "first match" would be an arbitrary pick.
    mine_beats = [h for h in beats.values() if snap.agent_key(h["agent"]) == my_key]
    mybeat = max(mine_beats, key=lambda h: h["updated_at"]) if mine_beats else None
    # Same tie-break for the coordinator's row, whose age is the UR-162 trigger: a stale duplicate
    # picked first would raise a URGENT PATH that is not owed. The `.endswith` SELECTOR is unchanged,
    # so this only chooses among rows it already found -- it cannot lose the row it finds today.
    coord_beats = [h for a, h in beats.items() if a.endswith("coordinator")]
    coord = max(coord_beats, key=lambda h: h["updated_at"]) if coord_beats else None
    owner = data.get("owner_records", {}).get("items", [])
    urgent = [r for r in owner if raises_urgent(r, now)]
    who = f"{ids['lane']}-{ids['cell']}" if ids["cell"] else ids["lane"]
    out = [f"# lane tick {sandbox} {data['cursor']['now']} agent={who}"]
    out.append(
        f"  heartbeat id={mybeat['id']} age {mybeat['age_min']}m {snap.truncate(mybeat['head'], 70)}"
        if mybeat
        else f"  ERROR heartbeats: no beat for {sandbox} on #{snap.HEARTBEATS_ISSUE}"
    )
    since = mybeat["updated_at"] if mybeat else data["cursor"].get("cursor", "")
    if coord:
        flag = " — UR-162: post one URGENT PATH on #6854" if coord["stale"] and not urgent else ""
        rested = f" (a live URGENT PATH already on record: #{urgent[-1]['id']})" if coord["stale"] and urgent else ""  # fmt: skip
        out.append(f"  coordinator age {coord['age_min']}m{rested}{flag}")
    out += disk(call(["df", "-h", *MOUNTS], "disk"))
    pkgs, maptext = packages(ids["lane"]), show(MAP, "ruling map")
    out += uncarried(data["binding_now"].get("items", []), maptext)

    cmd = ["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "300", "--json", HEADJ]  # fmt: skip
    listed = json.loads(call(cmd, "heads") or "[]")
    heads = {p["number"]: p for p in listed}
    branches = set((call(["git", "branch", "--format=%(refname:short)"], "branches") or "").split())

    def gate(p: dict) -> str:
        """The gate's verdict, named by its in-flight jobs when it is still running."""
        if p["gate"] != "IN_PROGRESS" or not p.get("gate_run"):
            return p["gate"]
        rows = api(f"repos/{repo}/actions/runs/{p['gate_run']}/jobs?per_page=100", "jobs")
        jobs = rows[0].get("jobs", []) if rows and isinstance(rows[0], dict) else []
        # The gate is a leg of its OWN run, so it is never the thing a lane is waiting on.
        running = ",".join(
            j.get("name", "?")
            for j in jobs
            if j.get("status") != "completed" and j.get("name") != snap.GATE_CHECK
        )
        return f"IN_PROGRESS({snap.truncate(running, 60)})" if running else p["gate"]

    def row(p: dict, tail: str = "") -> str:
        errs = "".join(f" ERROR {e}" for e in p.get("errors", []))
        return (
            f"  #{p['number']} {snap.truncate(p['title'], 40)} head={p['head'][:9]}"
            f" {p['merge_state']} gate={gate(p)}{tail}{errs}"
        )

    items = data["prs"].get("items", [])
    label = ids["review_label"]
    queue = [p for p in items if label and label in p["labels"]]
    out.append(f"== {label or 'no review queue'} ({len(queue)})")
    for p in queue:
        body = heads.get(p["number"], {}).get("body")
        out.append(row(p, f" {plan_text(body)}"))
    # Ownership by BRANCH, not label or author: two-cell lanes carry no cell row on some of their
    # own PRs and every PR has the owner's login behind it (UR-168).
    mine = [p for p in items if heads.get(p["number"], {}).get("headRefName") in branches]
    out.append(f"== mine ({len(mine)})")
    for p in mine:
        tail = " DIRTY" if p["merge_state"] == "DIRTY" else ""
        try:
            tail += f" behind {behind(run, repo, p['number'])}"
        except Exception as exc:
            extra.append(f"  ERROR behind #{p['number']}: {snap.error_text(exc)}")
            tail += " behind ?"
        cmts = api(f"repos/{repo}/issues/{p['number']}/comments?since={since}&per_page=100", "comments")  # fmt: skip
        revs = [
            r
            for r in api(f"repos/{repo}/pulls/{p['number']}/reviews?per_page=100", "reviews")
            if (r.get("submitted_at") or r.get("created_at") or "") >= since
        ]
        out.append(row(p, f"{tail} {len(cmts)}c/{len(revs)}r since beat"))
    # UR-52's precondition, printed: an agent holding an open package is not claim-eligible, and a
    # `next claimable` line beside a held package invites the queue-jump the rule forbids. The gate
    # reads the whole lane file, not the queue column, because a package the roster never lists is
    # still an open package ([r162] on ops-a's row is that shape). Silence would be worse than either
    # line -- it could mean "nothing claimable" or "not eligible" -- so the digest says which it read.
    if held := held_claims(pkgs, mine):
        names = ", ".join(f"[{t}]" for t in held)
        out.append(
            f"  holding open claim: {names} (UR-52: nothing to claim while a package is open)"
        )
    elif nxt := next_claimable(pkgs, ids["queue"], mine):
        out.append(f"  next claimable: {nxt}")
    for name in ("cursor", "comments", "binding_now", "main", "heartbeats", "prs"):
        out += [f"  ERROR {name}: {e}" for e in data.get(name, {}).get("errors", [])]
    out += extra
    if (
        len(out) > CAP_LINES
    ):  # the cap reports, it does not cut: status_draft's over_limit does the same
        out.append(f"  NOTE {len(out) - CAP_LINES} lines over this tool's {CAP_LINES}-line cap")
    return out


def main(
    argv: Sequence[str] | None = None,
    run: Callable[[Sequence[str]], str] = snap.run_command,
    clock: Callable[[], object] = snap.utc_now,
) -> int:
    ap = argparse.ArgumentParser(description="the lane tick's readings in one read-only call")
    ap.add_argument("--sandbox", required=True)
    ap.add_argument("--repo", default=snap.DEFAULT_REPO, type=snap._repo_arg)
    a = ap.parse_args(argv)
    print("\n".join(build(run, clock, a.repo, a.sandbox)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

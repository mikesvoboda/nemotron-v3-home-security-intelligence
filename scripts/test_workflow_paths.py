#!/usr/bin/env python3
"""Workflow-path existence gate (O1.4, D9): every repo path a CI config addresses exists.

The configs in scope — ``.github/workflows/*.yml`` and ``.pre-commit-config.yaml``
— are programs that address repository files. When such an address goes stale
the failure is SILENT: an ``upload-artifact`` with a dead ``path:`` uploads
nothing and succeeds, a pre-commit ``exclude:`` regex for a directory that no
longer exists quietly matches nothing forever, and an artifact step pointed at
a deleted doc ships green (the class is this package's own: deploy.yml
carried ``path: docs/DEPLOYMENT_VERIFICATION_CHECKLIST.md`` and an echo
pointing at ``docs/DEPLOYMENT.md`` — both deleted by the docs reorg 29d900b46,
the citations swept only by 4cb551fb7. O1.4 item 2 is verified fixed; this
gate keeps the class from re-rotting).

Not every slash is an address. Prose compounds (``Bandit/Semgrep``,
``application/json``, ``CI/CD``), git refs (``refs/heads/main``,
``origin/main``), run-id lists (``35482667110/35484007823``), wrapped line
fragments (``.github/ai-parity-`` at ci.yml:135) and ``${{ ... }}``-built
paths are not repository claims, and a checker that flags them gets its
findings ignored — a drowned gate is a dead gate. So lines are classified
FIRST, and only address-shaped text is checked:

    comment        comment TEXT is literature, skipped wherever it sits: a
                   YAML-level ``#`` line never enters a checked domain, and a
                   ``#``-to-EOL tail (full-line or trailing) is stripped from
                   command/yaml text before tokenizing. Records inside
                   workflows — ci.yml's run-run-id prose, deploy.yml's
                   historical triton comment — keep their references, which is
                   why comments must not be scanned at all.
    command        ``run:``/``entry:``/``args:`` bodies — real commands; a
                   token is an address unless it is absolute (runner fs), a
                   tool-name compound (``curl/jq``), a git ref, all-numeric,
                   host-named, globbed/expressed, or allowlisted below.
                   Relative addresses resolve against the repo root OR any
                   directory the file ``cd``s into / sets as
                   ``working-directory`` — mutation-testing.yml runs
                   ``node scripts/mutation-guard.mjs`` after ``cd frontend``
                   and the file lives at frontend/scripts/: a root-only
                   checker would false-red a live guard. (Anchor set is
                   file-wide: block boundaries are invisible to a text parse;
                   the widening is one-directional, and a genuinely broken
                   ``cd`` dies in the step's own ``set -e``.)
    yaml           every other config line: ``path:``, ``dockerfile:``,
                   ``context:``, ``files:``, trigger ``paths:`` — values are
                   addresses, root-relative, globs checked only at their
                   fixed directory prefix. ``name:``/``description:``/``if:``
                   values are prose-like and exempt.
    pattern        pre-commit ``files:``/``exclude:``/``include:`` values:
                   regexes split into ``|`` alternatives, each walked over
                   literal characters only (``\\.`` is a literal dot; any
                   other metachar stops the walk). The assertion each shape
                   LICENSES is checked, and only that: a ``^``-anchored
                   alternative asserts its literal prefix from the repo root
                   (``^\\.wp25-feed/`` ⇒ directory ``.wp25-feed/``), an
                   end-anchored unanchored one asserts some path ENDS with
                   its literal (``vehicle_classifier_loader\\.py$`` ⇒ that
                   file, anywhere), an unanchored one asserts some path
                   CONTAINS it. This is the whole tooth for O1.4 item 3: the
                   dead excludes fail HERE, and fail again if re-added.

One shape hides in the skip domain: ``uses:``/``image:`` values are skipped
wholesale (external actions are ``owner/repo@ref`` claims, not paths), EXCEPT
a ``uses: ./…`` local reusable-workflow call — that IS a repository address,
checked directly by LOCAL_USES_RE (dot-led paths never survive PATH_TOKEN_RE,
so it is read off the KEY).

MISSING_OK / PATTERN_OK: named paths that legitimately cannot exist as
committed files (run-time build output, files a step CREATES, git-ignored
scratch dirs the excludes still guard, bot-prompt example paths). Both lists
are pinned ALIVE by test_allowlists_stay_fully_earned: an entry must still be
missing AND still be named, so neither list can fossilize (hollowness
doctrine, ops-A review on #6907).

Scan basis: the git INDEX (``git ls-files``), not the worktree filesystem —
the honest claim is "named paths are COMMITTED", which is what a clean CI
checkout has. A filesystem basis let laptop state move the gate: a built
``frontend/dist`` reads green over a path CI lacks, and a laptop with a local
``foo.tsbuildinfo`` would read that PATTERN_OK entry "earned" while CI reads
it unearned (or vice versa) — same command, opposite answers. Index view +
fs walk off a git root (the self-test's tmp_path) keeps every caller on one
basis, so the earned check and the main check can never disagree about what
the tree holds.

Known conservative gaps (each one-directional: the gate misses, never
false-reds): comment text is literature — a stale path in prose is invisible
(this head's instance, ci.yml's shard comment naming
scripts/merge-shard-coverage.mjs, verified to resolve through its own step's
``cd frontend``, so nothing rots today; a future stale comment waits for a
reader); an extensionless name whose first segment is not a live directory
(``docs-site/api``) is indistinguishable from ``CI/CD`` prose and stays
silent — the live-parent anchor keeps ``frontend/dst``-style dead dirs under a
REAL parent checkable; a regex alternative that breaks on an unescaped dot
(``tsconfig.*\\.json$``) earns only the checks its literal prefix licenses —
the repo measured ZERO real claims of that shape, so buying it would mean a
fossil allow entry, which the pinned-alive test forbids by design.

Parses as TEXT on purpose (doctrine from scripts/test_precommit_config.py):
PyYAML is not a declared dependency and ``uv sync`` demonstrably prunes
undeclared packages — a guard that dies on a prune goes red for the wrong
reason.

Runs as pytest (wired into ci.yml's anti-rot list; its presence there is
pinned by test_gate_is_wired_into_ci — a gate deletable from CI without a red
is already dead) and standalone:

    uv run python scripts/test_workflow_paths.py   # exit 1 + findings, else OK
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- classifier

COMMENT_RE = re.compile(r"^\s*#")
RUN_BLOCK_RE = re.compile(r"^\s*(?:-\s+)?(?:run|entry|script|args):\s*[|>]\d?[+-]?\s*(?:#.*)?$")
COMMAND_KEY_RE = re.compile(r"""^\s*(?:-\s+)?(run|entry|args|script):\s*(?![|>])['"]?(.*)$""")
PATTERN_KEY_RE = re.compile(r"^\s*(files|exclude|include):\s*(.+)$")
WORKING_DIR_RE = re.compile(r"^\s*working-directory:\s*['\"]?([A-Za-z0-9_./-]+)")

# YAML keys whose VALUES are prose or opaque, not addresses.
YAML_EXEMPT_KEYS = re.compile(
    r"^\s*(?:-\s+)?(name|description|label|message|title|subject|if|shell|timeout-minutes|"
    r"if-no-files-found|python-version|node-version|profile|fetch-depth|lfs|submodules|"
    r"key|restore-keys|token|url|repository|cron|branches|branches-ignore|tags|"
    r"repo|rev|language|alias|stages|types|exclude-types|require-serial|pass-filenames|"
    r"always-run|additional-dependencies|default|group|cancel-in-progress|"
    r"needs|permissions|contents|actions|pull-requests|packages|checks|statuses|"
    r"id-token|issues|discussions)\b"
)
# Top-level-ish keys skipped wholesale (uses/image lines are action/image coords).
SKIP_LINE_RE = re.compile(r"^\s*(?:-\s+)?(uses|image|container|registry):\s")
# A ``uses:`` value starting ``./`` is a local reusable-workflow CALL — a real
# repository address (GitHub rejects the call at parse time if the target is
# gone, but only once the calling workflow is dispatched, and an orphaned
# callee is precisely the broken-workflow shape O1.4 sweeps). Such lines get
# a direct existence check (LOCAL_USES_RE, applied in find_missing) instead of
# the wholesale skip: dot-led tokens never survive PATH_TOKEN_RE, so the
# address has to be read off the KEY, not the token stream.
LOCAL_USES_RE = re.compile(r"""^\s*(?:-\s+)?uses:\s*['"]?(\./[^\s'"]+)['"]?\s*$""")

# Token that begins with a dot: "./frontend" is "frontend"; "../x" climbs
# outside any addressable claim the gate can verify — skip.
DOT_LEAD_RE = re.compile(r"^\.\.*/")

PATH_TOKEN_RE = re.compile(
    r"(?<![\w./@$:%-])"                    # not a fragment of a longer token (%: percent-encoded URL halves)
    r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*"  # segment
    r"(?:/[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)+"  # ... + >=1 more
    r"/?"
    r"(?![\w./@-])"                          # not the head of a longer token
)

REGEX_METACHARS = set(".*+?()[]{}|^$")
GLOB_METACHARS = set("*?[]")

# First segment is a CLI tool: a following slash is prose ("curl/jq"), not a
# path under the tool. (Command domains see the PATH after the tool as its own
# token anyway — node scripts/x.py yields scripts/x.py.)
TOOL_FIRST = {
    "curl", "wget", "jq", "yq", "node", "npm", "npx", "pnpm", "yarn", "python", "python3",
    "uv", "pip", "pip3", "pytest", "ruff", "black", "bash", "sh", "zsh", "git", "gh", "docker",
    "podman", "docker-compose", "compose", "grep", "sed", "awk", "tar", "zip", "unzip", "find",
    "xargs", "mkdir", "rm", "cp", "mv", "cat", "echo", "make", "cargo", "go", "java", "gradle",
    "semgrep", "bandit", "trivy", "grype", "gitleaks", "snyk", "alembic", "celery", "gunicorn",
    "uvicorn", "playwright", "stryker", "lhci", "tsc", "eslint", "prettier", "vitest", "knip",
    "typedoc", "mkdocs", "sphinx-build", "redocly", "openssl", "mysql", "psql", "redis-cli",
    "kubectl", "helm", "aws", "az", "gcloud", "huggingface-cli", "hf", "mutmut", "vulture",
    "lychee",  # user_agent "lychee/0.14" is tool/version prose, not a path
}

# Last dotted part of seg0 that makes seg0 a hostname (scheme-less URLs
# survive URL stripping: ghcr.io/mikesvoboda/python:... in an image: line that
# ISN'T the image key, docker.io/... in run text, api.github.com in gh api).
TLD_SUFFIXES = {"com", "org", "io", "net", "dev", "sh", "co", "edu", "gov"}

# First segment is (part of) a local service host without a TLD shape.
HOST_FIRST = {"grype-db-server", "localhost", "host.docker.internal"}

GIT_REF_FIRST = {"refs", "origin", "upstream", "heads", "remotes", "tags", "FETCH_HEAD"}

# Directory names skipped by the tree-suffix scan (VCS, deps, caches).
SKIP_DIR_NAMES = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache",
                  ".pytest_cache", ".ruff_cache", ".next"}

# Command/YAML-domain named paths that cannot be committed files. Each entry
# states the evidence it was earned with; pinned alive by
# test_allowlists_stay_fully_earned.
MISSING_OK: dict[str, str] = {
    # (Authoring lesson, learned the hard way and paid for by
    # test_allowlists_stay_fully_earned: entries seeded from GREP output are
    # fossils unless the raw classifier actually REPORTS them. Three
    # mechanisms make a name invisible to the gate, so an entry naming it
    # earns nothing and was deleted: (1) single-segment names —
    # PATH_TOKEN_RE needs an interior slash to tell an address from a word,
    # so coverage-reports, benchmark-results, docs-output, results,
    # build-stats.json, .lighthouseci (dot-led besides) never tokenize;
    # (2) extensionless-under-dead-parent — the live-parent rule that keeps
    # CI/CD silent also silences dist/setup-linux, application/json,
    # docs-output/api, dist/assets (the accepted gap, documented at
    # token_ok); (3) comment-domain mentions — pyproject.toml/uv.lock and
    # the "Skip if only frontend/docs changed" compounds live in literature
    # the gate deliberately does not scan. Each deletion is safe because the
    # CHILD form (coverage-merged/coverage-summary.json, listed below)
    # extracts, flags, and earns its own entry — a typo'd generated dir
    # name lands on a child path and still reddens.)
    # --- CI build output: created by the run, never committed. ---
    "frontend/dist": "vite build output uploaded by artifact steps",
    "frontend/coverage": "vitest coverage output",
    "frontend/playwright-report": "playwright HTML report",
    "frontend/test-results": "playwright JSON results",
    "frontend/reports/mutation": "stryker mutation report dir (frontend)",
    "coverage-merged/coverage-summary.json": "merged coverage summary (generated)",
    "frontend/build-stats.json": "frontend build stats artifact",
    "frontend/size-report.json": "size-limit report artifact",
    "docs-output/api/openapi.json": "openapi spec copy (generated)",
    "docs-output/api-html/index.html": "redoc HTML bundle (generated)",
    "openapi-archive/openapi.json": "archived openapi copy (generated)",
    "openapi-versions/manifest.json": "openapi version manifest (generated)",
    "openapi-versions/openapi-latest.json": "openapi latest copy (generated)",
    "reports/flaky-test-report.json": "flaky-report job output (generated)",
    "reports/weekly-test-report.json": "weekly report job output (generated)",
    "reports/mutation/mutation.json": "stryker report file (generated)",
    "frontend/reports/mutation/mutation-report.html": "stryker HTML report (generated)",
    "frontend/lighthouse-output.txt": "lhci stdout capture (generated)",
    "frontend/npm-audit-results.json": "npm audit JSON (generated)",
    "results/k6-output.txt": "k6 stdout redirect (generated)",
    "results/k6-results.json": "k6 JSON results (generated)",
    "results/k6-summary.json": "k6 summary JSON (generated)",
    "memory-stress-results/load-test-output.txt": "memory-stress stdout redirect (generated)",
    "dist/setup.exe": "PyInstaller output (build-setup.yml), git-ignored dist/",
    "artifacts/setup.exe": "copied PyInstaller output artifact dir (build-setup.yml)",
    "benchmark-results/benchmark-output.txt": "benchmark stdout redirect (generated)",
    "benchmark-results/benchmark-results.json": "benchmark results artifact (generated)",
    "memory-results/memory-output.txt": "memory benchmark stdout redirect (generated)",
    # --- files a workflow itself writes at run time. ---
    "backend/tests/unit/test_o112_hooks_selftest.py": "ci.yml writes it via heredoc, then runs it",
    # --- bot-prompt example paths (pr-review-bot.yml prose in run: text).
    # Media types need NO entry: application/json is invisible via mechanism
    # (2) above, text/html and text/plain too (no text/ dir), and
    # image/svg+xml never tokenizes (+ is off-class). ---
    "backend/api/routes/your_file.py": "pr-review-bot.yml example path in bot prompt prose",
    "frontend/src/components/YourComponent.tsx": "pr-review-bot.yml example path in bot prompt prose",
}

# Pattern-domain alternatives that may legitimately match nothing at commit
# time (git-ignored scratch the excludes still guard while it exists locally).
# Earned the same way, pinned the same way.
PATTERN_OK: dict[str, str] = {
    "^mutants/": "mutmut scratch dir (gitignored; .gitignore mutants/) — the exclude"
                 " guards local runs, exactly the live-convention case .wp25-feed/"
                 " lost when its contents moved to archive/",
    r"\.tsbuildinfo$": "tsc incremental build cache suffix (gitignored build output)",
}

# ---------------------------------------------------------------- extraction


def workflow_files(root: Path) -> list[Path]:
    wd = root / ".github" / "workflows"
    return sorted(wd.glob("*.yml")) + sorted(wd.glob("*.yaml"))


def config_sources(root: Path) -> list[tuple[str, Path]]:
    """(repo-relative label, path) for every file the gate reads."""
    out = [(p.relative_to(root).as_posix(), p) for p in workflow_files(root)]
    config = root / ".pre-commit-config.yaml"
    if config.is_file():
        out.append((".pre-commit-config.yaml", config))
    return out


def classify(path: Path, is_precommit: bool) -> list[tuple[str, str]]:
    """(domain, text) per line; domain in {comment, command, yaml, pattern, skip}.

    A run/entry/script block scalar swallows the deeper-indented lines that
    follow it into ``command``. YAML comments (any ``#``-lead line) are the
    literary domain.
    """
    out: list[tuple[str, str]] = []
    block_indent: int | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if block_indent is not None:
            indent = len(raw) - len(raw.lstrip())
            if stripped and indent > block_indent:
                out.append(("command", raw))
                continue
            block_indent = None  # block ended; fall through to normal rules
        if not stripped:
            out.append(("skip", raw))
            continue
        if COMMENT_RE.match(raw):
            out.append(("comment", raw))
            continue
        if SKIP_LINE_RE.match(raw):
            out.append(("skip", raw))
            continue
        m = RUN_BLOCK_RE.match(raw)
        if m:
            block_indent = len(raw) - len(raw.lstrip())
            out.append(("command", raw))  # the `run: |` line itself carries no body
            continue
        if is_precommit:
            pm = PATTERN_KEY_RE.match(raw)
            if pm:
                out.append(("pattern", pm.group(2)))
                continue
        cm = COMMAND_KEY_RE.match(raw)
        if cm:
            out.append(("command", cm.group(2)))
            continue
        if YAML_EXEMPT_KEYS.match(raw):
            out.append(("skip", raw))
            continue
        out.append(("yaml", raw))
    return out


def cd_anchors(lines: list[tuple[str, str]]) -> list[str]:
    """Directories relative paths in this file may resolve against.

    ``cd X`` words inside command lines plus every ``working-directory: X``
    (yaml lines). File-wide on purpose — see module docstring.
    """
    anchors: list[str] = []
    for domain, text in lines:
        if domain == "command":
            for m in re.finditer(r"\bcd\s+['\"]?([A-Za-z0-9_./-]+)", text):
                t = m.group(1).rstrip("/")
                if t and not t.startswith("."):
                    anchors.append(t)
        elif domain == "yaml":
            m = WORKING_DIR_RE.match(text)
            if m:
                t = m.group(1).rstrip("/")
                if t and not t.startswith("."):
                    anchors.append(t)
    return anchors


def strip_comment_value(text: str) -> str:
    """Drop a trailing `` #...`` YAML comment from a value line, quote-aware."""
    quote = None
    for i, c in enumerate(text):
        if quote:
            if c == quote:
                quote = None
        elif c in "\"'":
            quote = c
        elif c == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i]
    return text


def token_ok(tok: str, root: Path, anchors: list[str]) -> bool:
    """Shared rejection rules for command/yaml candidate tokens.

    Every rejection here is a DELIBERATE conservative gap (documented at
    module top): the gate misses these shapes rather than drowning its
    findings in prose compounds it cannot tell from directories.
    """
    if "@" in tok or "$" in tok or "{" in tok or "\\" in tok:
        return False
    if DOT_LEAD_RE.match(tok):
        return False  # ./x duplicates x (checked unled); ../x climbs outside the tree
    segs = tok.strip("/").split("/")
    if any(seg.startswith("-") or seg.endswith("-") or seg.startswith(".") or not seg for seg in segs):
        return False  # flag-like (--maxkb=1 truncated), truncated (shard-, ai-parity-)
    if all(re.fullmatch(r"[\d.]+[a-z%]*", s) for s in segs):
        return False  # numbers/metrics prose (1/2, 25.3m/20.7m, run-id lists)
    if segs[0] in GIT_REF_FIRST:
        return False
    if segs[0] in TOOL_FIRST:
        return False
    if len(segs[0]) == 1:
        return False  # single-letter namespace shorthand (semgrep p/python) — no 1-char top-level dir at head
    if "." in segs[0] and segs[0].rsplit(".", 1)[-1] in TLD_SUFFIXES:
        return False  # scheme-less URL / image coordinate (ghcr.io/x/y, api.github.com/…)
    if segs[0] in HOST_FIRST:
        return False
    if not has_glob(tok) and not any("." in s for s in segs):
        # Extensionless compound. With no extension shape to key on, CI/CD,
        # pass/fail, linux/amd64 and mikesvoboda/python are indistinguishable
        # from directories by STRUCTURE — so anchor on the tree instead: the
        # token stays checkable only when its first segment IS a directory at
        # the root or under a cd anchor (frontend/scripts alive, CI/CD,
        # linux/amd64, docs-site/api silent). A dead extensionless dir under a
        # LIVE first segment (path: frontend/dst) still flags; one under a
        # generated root is the accepted gap (also caught via that root's own
        # path:-key/glob-prefix claims when those are extension-shaped).
        head = segs[0]
        _paths, dirs = tree_facts(root)
        if not (head in dirs or any(f"{a}/{head}" in dirs for a in anchors)):
            return False
    return True


def has_glob(tok: str) -> bool:
    return any(c in GLOB_METACHARS for c in tok)


def fixed_dir_of(tok: str) -> str | None:
    """Deepest COMPLETE directory of a possibly-globbed token (no regex walk)."""
    body = tok.rstrip("/")
    parts = body.split("/")[:-1]
    for i in range(len(parts) - 1, -1, -1):
        if any(c in GLOB_METACHARS for c in "/".join(parts[: i + 1])):
            continue
        seg = parts[i]
        if seg and not any(c in GLOB_METACHARS for c in seg):
            return "/".join(parts[: i + 1])
    return None


def literal_prefix(pattern: str) -> tuple[str, bool]:
    """Walk a regex alternative over literal chars; ``\\.`` counts as a dot.

    Returns (prefix, fully_literal). Leading/trailing anchors are stripped by
    the caller's flags, not here.
    """
    out: list[str] = []
    i = 0
    p = pattern
    while i < len(p):
        c = p[i]
        if c == "\\":
            if i + 1 < len(p) and p[i + 1] in ".+?()[]{}|^$/-":
                out.append(p[i + 1])
                i += 2
                continue
            return "".join(out), False
        if c in REGEX_METACHARS:
            return "".join(out), False
        out.append(c)
        i += 1
    return "".join(out), True


def split_alternatives(value: str) -> list[str]:
    """Split a pre-commit pattern value into ``|`` alternatives.

    Splits on UNPARENTHESIZED ``|`` only — ``^(backend|synthbench)/`` is one
    alternative that walks to ``^(backend``, not two tokens ``^(backend`` +
    ``synthbench)/`` (the naive split mis-names halves of group alternations;
    measured on all 28 pattern lines at head). A wrapping-paren VALUE (a whole
    group) with no top-level ``|`` is walked as its inner text.
    """
    v = value.strip()
    parts: list[str] = []
    depth, cur = 0, []
    for c in v:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == "|" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    parts.append("".join(cur))
    if len(parts) == 1 and v.startswith("(") and v.endswith(")"):
        return split_alternatives(v[1:-1])  # unwrap ONE group layer, then split its alternatives
    return [p for p in parts if p]


# ---------------------------------------------------------------- tree facts


def clear_tree_caches() -> None:
    """Drop the tree caches. The real scan treats the tree as static during a
    run; a test that mutates a miniature tree mid-test must call this first,
    or the cached listing answers for the tree as it was."""
    for fn in (tree_entries, tree_facts):
        if getattr(fn, "_cache", None):
            del fn._cache  # type: ignore[attr-defined]


def tree_entries(root: Path) -> list[str]:
    """Every repo-relative path under root (files+dirs), minus SKIP dirs. Cached."""
    cached = getattr(tree_entries, "_cache", None)
    if cached and cached[0] == root:
        return cached[1]
    git = git_entries(root)
    if git is not None:
        out = git
    else:
        out = []
        stack = [root]
        while stack:
            d = stack.pop()
            try:
                children = list(d.iterdir())
            except OSError:
                continue
            for c in children:
                rel = c.relative_to(root).as_posix()
                if c.is_dir():
                    if c.name in SKIP_DIR_NAMES:
                        continue
                    stack.append(c)
                    out.append(rel)
                else:
                    out.append(rel)
    tree_entries._cache = (root, out)  # type: ignore[attr-defined]
    return out


def git_entries(root: Path) -> list[str] | None:
    """Index contents (``git ls-files``), or None when root isn't a git root.

    The index — not the worktree — is the scan basis, because the index (via
    the checkout) is what CI sees. A bare ``fs.exists()`` passes the moment a
    build populates ``frontend/dist`` locally, so a build-abstract allow entry
    could read earned on CI and unearned on a laptop (or a MISSING_OK entry
    leg-(a)-dead on a laptop while still load-bearing on CI) — the tree view
    must not move with local build state. Untracked files (new or leftover
    output) stay invisible: the honest claim is "named paths are COMMITTED",
    and ``ls-files`` already includes tracked-but-worktree-deleted entries,
    so a half-finished local deletion cannot flip an entry's earned-ness.
    The self-test's non-git tmp_path → None → plain fs walk.
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=True,
        ).stdout.strip()
        if Path(os.fsdecode(top)) != root.resolve():
            return None  # root is a SUBDIR of a repo: index paths are relative
            # to the toplevel, not to root — the fs walk is the honest view here
        raw = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    # -z = NUL-separated, NEVER quoted: plain ls-files escapes non-ASCII names
    # (core.quotepath) into "…\\307\\201…" strings that match no real path —
    # this repo's archive/ is full of such names. surrogateescape mirrors
    # os.fsdecode so undecodable names compare equal to Path-relative paths.
    out = [os.fsdecode(b) for b in raw.split(b"\0") if b]
    if not out:
        # a listing this empty means git is misbehaving, not an empty repo —
        # fail loud rather let a blip read as "the tree is empty"
        raise RuntimeError(f"git ls-files returned nothing in {root}; refusing the git view")
    return sorted(set(out))


def tree_facts(root: Path) -> tuple[set[str], set[str]]:
    """(paths, dir-prefixes) under root. Cached with tree_entries.

    ONE scan basis for every claim: a file claim is exact membership of
    ``paths``; a directory claim is membership of ``dir-prefixes`` (derived
    from real entries — never from bare file names, or ``package`` would read
    as a directory from package.json and license ``package/x`` claims). On a
    git toplevel that basis is the tracked view; elsewhere the fs walk. CI's
    clean checkout is (nearly) the tracked view, so laptop and CI now answer
    identically — build-populated or build-abstract differences were the
    false-red/false-green split the fs-first check let open.
    """
    cached = getattr(tree_facts, "_cache", None)
    if cached and cached[0] == root:
        return cached[1]
    entries = tree_entries(root)
    paths = set(entries)
    dirs: set[str] = set()
    for p in entries:
        segs = p.split("/")
        for i in range(1, len(segs)):
            dirs.add("/".join(segs[:i]))
    # fs-walk only: directory entries carry no slash-children of their own
    # when empty, and off-git the walk knows which entries ARE dirs.
    if git_entries(root) is None:
        for p in entries:
            if (root / p).is_dir():
                dirs.add(p)
    tree_facts._cache = (root, (paths, dirs))  # type: ignore[attr-defined]
    return tree_facts._cache[1]


def resolve(token: str, root: Path, anchors: list[str]) -> bool:
    """Does this metachar-free token exist at the root or under a cd anchor?"""
    clean = token.rstrip("/")
    if clean.startswith("/"):
        return True  # runner filesystem, not the repo — not our claim
    paths, dirs = tree_facts(root)
    if clean in paths or clean in dirs:
        return True
    return any(
        f"{a}/{clean}" in paths or f"{a}/{clean}" in dirs for a in anchors
    )


def tree_ends_with(root: Path, suffix: str) -> bool:
    """Any path under root ends with this literal suffix?"""
    suffix = suffix.rstrip("/")
    for rel in tree_entries(root):
        if rel == suffix or rel.endswith("/" + suffix) or rel.endswith(suffix):
            return True
    return False


def tree_contains(root: Path, frag: str) -> bool:
    """Any path under root contains this literal fragment anywhere?"""
    frag = frag.strip("/")
    return any(frag in rel for rel in tree_entries(root))


def deepest_closed_dir(prefix: str) -> str | None:
    """Deepest complete directory inside a literal pattern prefix.

    ``docs/`` -> ``docs``; ``backend/tests/.*`` -> ``backend/tests`` (the
    prefix broke mid-segment after that slash); ``config/docker-compose`` ->
    None (never a closed slash — a lone partial segment licenses nothing).
    """
    cut = prefix.rfind("/")
    return prefix[:cut] if cut > 0 else None


# ---------------------------------------------------------------- checking


def check_address(
    tok: str, root: Path, anchors: list[str], allow: dict[str, str] | None = None
) -> str | None:
    """Command/yaml-domain token: None when fine, a finding when dead.

    ``allow`` defaults to MISSING_OK; the pin test passes {} to measure
    whether an entry is still EARNED (its absence would produce a finding).
    """
    allow = MISSING_OK if allow is None else allow
    if tok in allow or tok.rstrip("/") in allow:
        return None
    if has_glob(tok):
        fixed = fixed_dir_of(tok)
        if fixed and not resolve(fixed, root, anchors):
            return f"{tok} — glob's fixed directory {fixed}/ does not exist"
        return None
    if resolve(tok, root, anchors):
        return None
    return f"{tok} — named, but does not exist (nor under any cd anchor)"


def check_pattern_alt(alt: str, root: Path, allow: dict[str, str] | None = None) -> str | None:
    """One pre-commit regex alternative: assert only what its shape licenses."""
    allow = PATTERN_OK if allow is None else allow
    if alt in allow:
        return None
    anchored_start = alt.startswith("^")
    anchored_end = alt.endswith("$")
    body = alt[1:] if anchored_start else alt
    if anchored_end:
        body = body[:-1]
    prefix, fully = literal_prefix(body)
    if not prefix:
        return None  # metachar-led: no literal anything
    if anchored_start:
        if fully:
            if not resolve(prefix, root, []):
                return f"{alt} — fully literal, anchored pattern names nothing"
            return None
        fixed = deepest_closed_dir(prefix)
        if fixed and not resolve(fixed, root, []):
            return f"{alt} — anchored pattern's fixed directory {fixed}/ does not exist"
        return None
    # unanchored: substring/suffix claim over the whole tree
    if fully:
        if not tree_ends_with(root, prefix) and not tree_contains(root, prefix):
            return f"{alt} — unanchored literal matches no path in the tree"
        return None
    p = deepest_closed_dir(prefix)
    if p and not tree_contains(root, p):
        return f"{alt} — pattern's fixed directory {p}/ matches no path in the tree"
    return None


def find_missing(root: Path, use_allowlists: bool = True) -> list[str]:
    """All findings as ``config: token — reason``, deduped per config, sorted.

    ``use_allowlists=False`` ignores MISSING_OK/PATTERN_OK — the pin test's
    view of what the raw classifier reports.
    """
    addr_allow = MISSING_OK if use_allowlists else {}
    pat_allow = PATTERN_OK if use_allowlists else {}
    findings: list[str] = []
    for label, path in config_sources(root):
        is_precommit = label == ".pre-commit-config.yaml"
        lines = classify(path, is_precommit)
        anchors = [] if is_precommit else cd_anchors(lines)
        seen: set[tuple[str, str]] = set()
        for domain, text in lines:
            if domain == "skip":
                # one shape hides in the skip domain: a ``uses: ./…`` local
                # reusable-workflow call IS an address (see LOCAL_USES_RE)
                um = LOCAL_USES_RE.match(text)
                if um:
                    target = um.group(1)
                    rel = target[2:] if target.startswith("./") else target
                    if ("addr", rel) not in seen:
                        seen.add(("addr", rel))
                        if not resolve(rel, root, anchors):
                            findings.append(
                                f"{label}: {target} — local reusable-workflow"
                                " call names nothing"
                            )
                continue
            if domain == "comment":
                continue
            if domain == "pattern":
                for raw_alt in split_alternatives(strip_comment_value(text)):
                    alt = raw_alt.strip().strip("'\"")
                    if not alt or ("pattern", alt) in seen:
                        continue
                    seen.add(("pattern", alt))
                    f = check_pattern_alt(alt, root, pat_allow)
                    if f:
                        findings.append(f"{label}: {f}")
                continue
            # command / yaml
            body = strip_comment_value(text)
            for m in PATH_TOKEN_RE.finditer(body):
                tok = m.group(0)
                if not token_ok(tok, root, anchors) or ("addr", tok) in seen:
                    continue
                seen.add(("addr", tok))
                f = check_address(tok, root, anchors, addr_allow)
                if f:
                    findings.append(f"{label}: {f}")
    return sorted(findings)


# ---------------------------------------------------------------- pytest face


def test_workflow_files_are_found() -> None:
    names = [p.name for p in workflow_files(REPO_ROOT)]
    assert len(names) > 20, f"expected dozens of workflows, found {len(names)}"
    assert "ci.yml" in names and "deploy.yml" in names, "the gate's own targets vanished"
    assert len(config_sources(REPO_ROOT)) == len(names) + 1, "pre-commit config missing from sources"


@pytest.mark.timeout(120)  # the tree-suffix scans walk the repo once (~seconds)
def test_every_named_path_exists() -> None:
    missing = find_missing(REPO_ROOT)
    assert not missing, (
        "CI configs address repository paths that do not exist (fix the config,"
        " or if the path is run-time output/prose, add it to MISSING_OK/PATTERN_OK"
        " with a measured reason):\n" + "\n".join(missing)
    )


def test_gate_is_wired_into_ci() -> None:
    """Self-pin (mirrors scripts/test_retired_paths.py): a gate that can be
    deleted from its only CI invocation without a red is already dead."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in ci.splitlines()]
    selfpin = [ln for ln in lines if ln == "scripts/test_workflow_paths.py"]
    # exact-line membership, not a substring: a substring survives the line's
    # deletion (the string lingers in a comment elsewhere) and even a rename —
    # this is the gate's ONLY invocation, so it must die loudly
    assert selfpin, "this gate must ride ci.yml's anti-rot list (exact-line pin)"


@pytest.mark.timeout(120)  # pin (a) consults the tree scan for PATTERN_OK shapes
def test_allowlists_stay_fully_earned() -> None:
    """Every allowlist entry must be (a) still unable to exist as a committed
    path and (b) still EARNED: without it, the raw classifier (allowlists
    off) reports a finding naming exactly that entry.

    (a) stops an allowance outliving its need: the day ``ai/pyproject.toml``
    is committed its exemption must die with it. (b) stops every quieter rot —
    an entry whose path stopped being NAMED, one whose shape fell out of the
    scanned domains (comment-only mentions earn nothing — the gate never sees
    them), and one hollowed by a filter change, all read as "no raw finding
    mentions you" and fail here. Measured during authoring: this is the test
    that caught two of my own speculative entries (ai/triton, ai/pyproject
    appear only in comments the gate does not scan).
    """
    for token, reason in MISSING_OK.items():
        assert reason, f"MISSING_OK entry {token!r} has no reason"
        paths, dirs = tree_facts(REPO_ROOT)
        sharp = token.rstrip("/")
        assert sharp not in paths and sharp not in dirs, (
            f"MISSING_OK entry {token!r} is COMMITTED (index view; {reason}) — "
            "remove the exemption (a locally built dir proves nothing — the "
            "claim the entry licenses is about the tracked tree)"
        )
        raw = find_missing(REPO_ROOT, use_allowlists=False)
        earned = any(f": {token} " in f or f": {token.rstrip('/')}/ " in f for f in raw)
        assert earned, (
            f"MISSING_OK entry {token!r} is not earned — the un-allowlisted gate "
            f"reports no finding for it (no longer named in scanned text, or a "
            f"filter now rejects it): delete it ({reason})"
        )
    for alt, reason in PATTERN_OK.items():
        assert reason, f"PATTERN_OK entry {alt!r} has no reason"
        assert alt in (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"), (
            f"PATTERN_OK entry {alt!r} is no longer named — delete it"
        )
        raw = find_missing(REPO_ROOT, use_allowlists=False)
        earned = any(alt in f for f in raw)
        assert earned, f"PATTERN_OK entry {alt!r} is not earned — the un-allowlisted gate reports no finding for it; delete it"


def test_selftest_discriminates(tmp_path: Path) -> None:
    """Rule-set teeth, pinned both ways on a miniature tree (mutation doctrine,
    ops-A review on #6907: every branch gets a flag AND a near-miss)."""
    (tmp_path / "frontend" / "scripts").mkdir(parents=True)
    (tmp_path / "frontend" / "scripts" / "guard.mjs").write_text("x\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "tests").mkdir()
    (tmp_path / "live").mkdir()
    (tmp_path / "live" / "keeper.tsbuildinfo").write_text("x\n")  # earn a suffix here
    anchors = ["frontend"]

    # addresses: live, dead, anchored, absolute
    assert check_address("docs", tmp_path, []) is None
    assert check_address("docs/", tmp_path, []) is None
    assert check_address("docs/gone.md", tmp_path, []) is not None
    assert check_address("/github/workspace/x", tmp_path, []) is None
    assert check_address("scripts/guard.mjs", tmp_path, []) is not None
    assert check_address("scripts/guard.mjs", tmp_path, anchors) is None
    # globs: fixed dir checked both ways
    assert check_address("frontend/**", tmp_path, []) is None
    assert check_address("nope/**/*.ts", tmp_path, []) is not None
    assert check_address("docs/*", tmp_path, []) is None
    # patterns: anchored-literal (dead dir), anchored-literal (live dir),
    # anchored-partial, end-anchored suffix (dead + live), unanchored contains
    assert check_pattern_alt(r"^\.wp25-feed/", tmp_path) is not None
    assert check_pattern_alt("^docs/", tmp_path) is None
    assert check_pattern_alt("^frontend/scripts$", tmp_path) is None
    assert check_pattern_alt(r"^backend/tests/.*test_x\.py$", tmp_path) is None
    assert check_pattern_alt(r"^nope/deep/.*\.py$", tmp_path) is not None
    assert check_pattern_alt(r"services/vehicle_classifier_loader\.py$", tmp_path) is not None
    assert check_pattern_alt(r"scripts/guard\.mjs$", tmp_path) is None
    assert check_pattern_alt(r"\.tsbuildinfo$", tmp_path) is None
    assert check_pattern_alt(r"nomatch\.json$", tmp_path) is not None
    assert check_pattern_alt(r"docs/.*", tmp_path) is None
    assert check_pattern_alt(r"ghostly/.*", tmp_path) is not None
    # token filter: refs, numbers, tools, hosts, flags, truncations, expressions
    assert not token_ok("refs/heads/main", tmp_path, [])
    assert not token_ok("origin/main", tmp_path, [])
    assert not token_ok("1/2", tmp_path, []) and not token_ok("25.3m/20.7m", tmp_path, [])
    assert not token_ok("curl/jq", tmp_path, [])
    assert not token_ok("github.com/a/b", tmp_path, []) and not token_ok("api.github.com/x/y", tmp_path, [])
    assert not token_ok("coverage/shard-", tmp_path, []) and not token_ok(".github/ai-parity-", tmp_path, [])
    assert not token_ok("--exclude/x", tmp_path, [])
    assert token_ok("frontend/scripts", tmp_path, []) and token_ok("docs/x.md", tmp_path, [])
    # extensionless: prose compounds silent, dead dir under a LIVE parent still a candidate
    assert not token_ok("CI/CD", tmp_path, [])  # CI is no dir: prose class
    assert token_ok("frontend/nope", tmp_path, [])  # frontend IS a dir: stays checkable
    assert check_address("frontend/nope", tmp_path, []) is not None  # …and flags when dead
    # line classification end-to-end through a miniature workflow file
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "t.yml").write_text(
        "# comment with a/b path: docs/gone.md must NOT flag\n"
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: Upload\n"
        "        uses: actions/upload-artifact@v4\n"
        "        with:\n"
        "          path: docs\n"
        "      - run: |\n"
        "          cd frontend\n"
        "          node scripts/guard.mjs\n"
        "          cat docs/gone.md\n",
        encoding="utf-8",
    )
    lines = classify(wf / "t.yml", is_precommit=False)
    domains = [d for d, _ in lines]
    assert "comment" in domains and "command" in domains and "yaml" in domains
    assert cd_anchors(lines) == ["frontend"]
    toks = [
        m.group(0)
        for d, t in lines if d in ("command", "yaml")
        for m in [PATH_TOKEN_RE.search(strip_comment_value(t))] if m
    ]
    assert "docs" in toks or "scripts/guard.mjs" in toks
    # local reusable-workflow calls: live callee silent, dead callee flagged,
    # external actions still skipped (near-miss both directions)
    assert LOCAL_USES_RE.match("    uses: ./.github/workflows/x.yml").group(1) == "./.github/workflows/x.yml"
    assert LOCAL_USES_RE.match("  - uses: './a/b.yml'").group(1) == "./a/b.yml"
    assert LOCAL_USES_RE.match("    uses: actions/checkout@v4") is None
    assert LOCAL_USES_RE.match("    uses: ./.github/workflows/x.yml  # comment") is None
    (wf / "callee.yml").write_text("on:\n  workflow_call: {}\njobs: {}\n")
    clear_tree_caches()
    (wf / "caller.yml").write_text(
        "jobs:\n"
        "  a:\n    uses: ./.github/workflows/callee.yml\n"
        "  b:\n    uses: ./.github/workflows/ghost.yml\n"
        "  c:\n    uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    hits = [x for x in find_missing(tmp_path) if "caller.yml" in x]
    assert len(hits) == 1 and "ghost.yml" in hits[0], hits


# --------------------------------------------------------------- standalone


def main() -> int:
    sources = config_sources(REPO_ROOT)
    missing = find_missing(REPO_ROOT)
    if missing:
        print(f"FAIL: {len(missing)} addressed path(s) missing:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(f"OK: every repository path addressed in {len(sources)} CI config(s) exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())

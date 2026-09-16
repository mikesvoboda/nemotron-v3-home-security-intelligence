#!/usr/bin/env bash
# ABOUTME: Runtime-version consistency gate — catches "the 3.11 fiction" class of bug.
# ABOUTME: Every version declaration must agree with the SSOT files (.nvmrc, .python-version).
#
# Source-of-truth files:
#   .nvmrc            — Node major for CI, dev boxes, validate.sh, Dockerfile base
#   .python-version   — Python X.Y line for uv (hence every uv-based job)
#   pyproject.toml    — requires-python floor (must agree with .python-version)
#
# Everything else either interpolates these at runtime or is a literal this
# script checks. A drifting literal fails the build — that is the point: ci.yml
# python-version labels said 3.11 for months while uv actually ran 3.14, and
# triage paid for it (ledger 2026-09-15, annotation-hazard entry).
#
# Usage: check-version-consistency.sh [REPO_ROOT]   (default: parent of scripts/)
# Exit:  0 = consistent, 1 = drift (one FAIL line per finding on stderr).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
DRIFT="$(mktemp)"
trap 'rm -f "$DRIFT"' EXIT

fail() { echo "FAIL: $*" >> "$DRIFT"; }

# ── Source-of-truth values ────────────────────────────────────────────────────
[ -f "$ROOT/.nvmrc" ] || { echo "FAIL: .nvmrc missing at repo root" >&2; exit 1; }
NODE_MAJOR=$(tr -dc '0-9' < "$ROOT/.nvmrc")
[ -n "$NODE_MAJOR" ] || { echo "FAIL: .nvmrc has no numeric version" >&2; exit 1; }

[ -f "$ROOT/.python-version" ] || { echo "FAIL: .python-version missing at repo root" >&2; exit 1; }
PY_LINE=$(tr -dc '0-9.' < "$ROOT/.python-version")
[ -n "$PY_LINE" ] || { echo "FAIL: .python-version has no numeric version" >&2; exit 1; }

# Deliberate off-runtime setup-python tooling pins (raw setup-python, not uv;
# these jobs do not run the app). Changing one = edit this list in the same
# commit so the swap is reviewed. "file:version" pairs.
PYTHON_ALLOWLIST="
.github/workflows/agents-md.yml:3.11
.github/workflows/build-setup.yml:3.12
.github/workflows/vulnerability-management.yml:3.11
.github/workflows/linear-github-sync.yml:3.12
"

# ── pyproject requires-python vs .python-version ──────────────────────────────
REQUIRES=$(sed -n 's/^requires-python *= *">=\([0-9.]*\)".*/\1/p' "$ROOT/pyproject.toml" 2>/dev/null | head -1)
if [ -n "$REQUIRES" ] && [ "$REQUIRES" != "$PY_LINE" ]; then
    fail "pyproject.toml requires-python >=$REQUIRES disagrees with .python-version ($PY_LINE)"
fi

# ── ci.yml: matrix labels + PYTHON_VERSION env must equal .python-version ────
CI_YML="$ROOT/.github/workflows/ci.yml"
while IFS=: read -r lineno content; do
    ver=$(echo "$content" | sed "s/.*python-version: \['\([0-9.]*\)'\].*/\1/")
    [ "$ver" != "$PY_LINE" ] && fail "ci.yml:$lineno python-version: ['$ver'] != .python-version ($PY_LINE) — uv runs $PY_LINE; make the label honest"
done < <(grep -n "python-version: \['" "$CI_YML" 2>/dev/null)

ENV_PY=$(sed -n "s/^  PYTHON_VERSION: '\([0-9.]*\)'.*/\1/p" "$CI_YML" 2>/dev/null | head -1)
if [ -n "$ENV_PY" ] && [ "$ENV_PY" != "$PY_LINE" ]; then
    fail "ci.yml env PYTHON_VERSION '$ENV_PY' != .python-version ($PY_LINE)"
fi

# ── other workflows: raw setup-python literals, minus the allowlist ───────────
for f in "$ROOT"/.github/workflows/*.yml; do
    [ "$f" = "$CI_YML" ] && continue
    rel="${f#"$ROOT"/}"
    while IFS=: read -r lineno content; do
        ver=$(echo "$content" | sed "s/.*python-version: '\([0-9.]*\)'.*/\1/")
        if [ "$ver" != "$PY_LINE" ] && ! echo "$PYTHON_ALLOWLIST" | grep -q "^${rel}:${ver}$"; then
            fail "$rel:$lineno pins setup-python $ver (truth: $PY_LINE; not allowlisted)"
        fi
    done < <(grep -n "python-version: '[0-9]" "$f" 2>/dev/null)
done

# ── backend Dockerfile python: base must sit on the .python-version line ─────
while IFS=: read -r lineno content; do
    ver=$(echo "$content" | sed 's/.*FROM python:\([0-9][0-9.]*\).*/\1/')
    case "$ver" in
        "$PY_LINE"*) ;;
        *) fail "backend/Dockerfile:$lineno base python:$ver != .python-version line $PY_LINE" ;;
    esac
done < <(grep -n "^FROM python:" "$ROOT/backend/Dockerfile" 2>/dev/null)

# ── Node literals in workflows must equal .nvmrc major ────────────────────────
for f in "$ROOT"/.github/workflows/*.yml; do
    rel="${f#"$ROOT"/}"
    while IFS=: read -r lineno content; do
        ver=$(echo "$content" | grep -oE "'[0-9]+ ?'" | tr -d "' ")
        [ "$ver" != "$NODE_MAJOR" ] && fail "$rel:$lineno pins Node $ver != .nvmrc ($NODE_MAJOR)"
    done < <(grep -nE "NODE_VERSION: '[0-9]+'|node-version: '[0-9]+'" "$f" 2>/dev/null)
done

# ── frontend/package.json engines must admit the .nvmrc major ─────────────────
if [ -f "$ROOT/frontend/package.json" ] && ! grep -q ">=${NODE_MAJOR}\.0\.0" "$ROOT/frontend/package.json"; then
    fail "frontend/package.json engines does not admit Node >=${NODE_MAJOR}.0.0 (.nvmrc = $NODE_MAJOR)"
fi

# ── frontend Dockerfile node: base major must equal .nvmrc ────────────────────
while IFS=: read -r lineno content; do
    ver=$(echo "$content" | sed 's/.*FROM node:\([0-9]*\).*/\1/')
    [ "$ver" != "$NODE_MAJOR" ] && fail "frontend/Dockerfile:$lineno base node:$ver != .nvmrc major ($NODE_MAJOR)"
done < <(grep -n "^FROM node:" "$ROOT/frontend/Dockerfile" 2>/dev/null)

# ── validate.sh: any numeric REQUIRED_NODE_MAJOR literal must equal .nvmrc ────
# (validate.sh normally derives the value from .nvmrc — no numeric literal, no
# check. A hardcoded literal that someone re-introduces must agree.)
while IFS=: read -r lineno content; do
    ver=${content#REQUIRED_NODE_MAJOR=}
    [ "$ver" != "$NODE_MAJOR" ] && fail "scripts/validate.sh:$lineno REQUIRED_NODE_MAJOR=$ver != .nvmrc ($NODE_MAJOR)"
done < <(grep -n '^REQUIRED_NODE_MAJOR=[0-9]' "$ROOT/scripts/validate.sh" 2>/dev/null)

# ── Verdict ───────────────────────────────────────────────────────────────────
if [ -s "$DRIFT" ]; then
    cat "$DRIFT" >&2
    n=$(wc -l < "$DRIFT")
    echo "" >&2
    echo "Version consistency: $n drift finding(s). Truth: .nvmrc=$NODE_MAJOR, .python-version=$PY_LINE." >&2
    echo "Fix the literal to match — or change the truth file AND everything it governs, same commit." >&2
    exit 1
fi

echo "Version consistency OK — Node $NODE_MAJOR (.nvmrc), Python $PY_LINE (.python-version): all declarations agree."

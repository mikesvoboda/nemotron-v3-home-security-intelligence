#!/bin/sh
# Runs the fast tier's selected backend tests (spec 4.1). Deterministic order
# (-p no:randomly) because selection is position-blind while randomly is not:
# selection and run must agree on ordering or a green --fast proves nothing
# about the same selection re-run. No coverage args at all (fast tier has no
# coverage proof - that is the full gate's identity).
#
# WP2.3 MANIFEST CONTRACT (spec §Phase 2, "non-negotiable"): every run ends
# with MANIFEST lines distinguishing
#   NOT-SELECTED   "not selected for this diff"  — NORMAL, visible
#   CANNOT-RUN     collection error / import failure / missing file /
#                  zero-test file                  — DEFECT, non-zero exit
# If those two ever render alike, this runner has rebuilt the trap the revival
# escaped. CANNOT-RUN fires from three detectors:
#   1. selection-time static: listed file missing or defines no test_* def
#      (a map pointing at a zero-test file is drift, not silence)
#   2. runtime ERROR lines: 'ERROR <file>[::node]' from pytest's own summary
#   3. runtime 'no tests ran' with a NON-empty selection: rc 5/Collect death
# A plain test FAILURE (rc 1, no ERROR) is a third category (FAILING) — it
# fails the run too, but under its own name; a failure is not a defect in
# the selection machinery.
# PYTEST_CMD env overrides the pytest invocation (default: uv run pytest) —
# the seam scripts/test_fast_runners_manifest.py drives with canned fakes.
set -eu

LIST="${1:?usage: fast-backend-runner.sh LISTFILE}"
# No cd: callers (validate.sh, playbook, pre-push) run this with cwd = repo
# root, same as the pre-WP2.3 runner did — selection paths and the universe
# below are cwd-relative BY CONTRACT (git ls-files resolves against cwd).

# Universe: every tracked test file — the same set fast_select selects from
# (git ls-files, test_*.py under backend/tests). 'not selected' is only
# meaningful against a declared universe.
UNIVERSE=$(git ls-files "backend/tests" | grep -E '/test_[^/]*\.py$' | sort -u || true)

# Selection, normalized (sorted, unique, non-empty lines)
if [ -s "$LIST" ]; then
    SELECTED=$(tr -d '\r' < "$LIST" | grep -v '^$' | sort -u || true)
else
    SELECTED=""
fi
N_SEL=$(printf '%s' "$SELECTED" | grep -c . || true)

# Detector 1: static cannot-run over the selection (missing / zero-test def)
CANNOT_STATIC=""
if [ -n "$SELECTED" ]; then
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        if [ ! -f "$f" ]; then
            CANNOT_STATIC="${CANNOT_STATIC}${f}	missing (selected but absent on disk)
"
        elif ! grep -qE '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+test_|^[[:space:]]*class[[:space:]]+Test' "$f"; then
            CANNOT_STATIC="${CANNOT_STATIC}${f}	defines no test functions or Test classes
"
        fi
    done <<EOF
$SELECTED
EOF
fi

MANIFEST_DIR=$(mktemp -d "${TMPDIR:-/tmp}/fbr-manifest.XXXXXX")
trap 'rm -rf "$MANIFEST_DIR"' EXIT
LOG="$MANIFEST_DIR/pytest.log"

RC=0
if [ "$N_SEL" -gt 0 ]; then
    # Paths come from git ls-files (no spaces - repo convention; the selector
    # emits them newline-separated; the while-read below loads them as
    # positionals quoting-safely, replacing the older xargs form so the
    # PYTEST_CMD seam can receive them as "$@").
    # -o addopts= REPLACES the pyproject addopts wholesale - that is why -m
    # 'not gpu' and -v are restated inside it (validate.sh's own comment
    # documents the same trap).
    set --
    while IFS= read -r f; do [ -n "$f" ] && set -- "$@" "$f"; done <<EOF
$SELECTED
EOF
    # The script text ends in "$@", which sh -c expands to the positional
    # operands after $0 (the placeholder `x`) — the selected files, verbatim.
    CMD="${PYTEST_CMD:-uv run pytest} --dist=loadgroup -p no:randomly -o addopts=\"-v -m 'not gpu' --timeout=60\" \"\$@\""
    set +e
    sh -c "$CMD" x "$@" > "$LOG" 2>&1
    RC=$?
    set -e
    cat "$LOG"
else
    : > "$LOG"
fi

# Detector 2: file-level ERROR lines in pytest's summary (shape: pytest 8
# emits 'ERROR backend/tests/unit/test_b.py' or '::node' suffixed variants;
# bare 'ERROR backend/...' matches both, the file part is before any ::).
CANNOT_RT=$(grep -E '^ERROR (backend|ai|setup_lib)/' "$LOG" 2>/dev/null \
    | sed -E 's/^ERROR //; s/::.*$//; s/[[:space:]].*$//' | sort -u \
    | sed 's/$/\tcollection or import error reported by pytest/' || true)
# Detector 3: non-empty selection, zero tests ran (rc>=2 collect death or
# explicit 'no tests ran') — every selected file is then unevaluable.
if [ "$N_SEL" -gt 0 ] && [ "$RC" -ge 2 ] && grep -qE 'no tests ran|no tests collected' "$LOG"; then
    CANNOT_RT=$(printf '%s' "$SELECTED" | sed 's/$/\tselection collected zero tests (rc '"$RC"')/' | sort)
fi

CANNOT=$(printf '%s%s' "$CANNOT_STATIC" "$CANNOT_RT" | grep -v '^$' | sort -u || true)
N_CR=$(printf '%s' "$CANNOT" | grep -c . || true)

# Not-selected = universe minus the selection, minus the cannot-run files
# (a file cannot be both "normal, unselected" and "defect" — the contract
# forbids rendering the two alike, including simultaneously).
CR_FILES=$(printf '%s\n' "$CANNOT" | cut -f1 -d'	' | grep -v '^$' | sort -u || true)
printf '%s\n' "$SELECTED" "$CR_FILES" | grep -v '^$' | sort -u > "$MANIFEST_DIR/excl"
printf '%s\n' "$UNIVERSE" | grep -v '^$' | sort -u > "$MANIFEST_DIR/universe"
NOT_SEL=$(comm -23 "$MANIFEST_DIR/universe" "$MANIFEST_DIR/excl" || true)
N_NS=$(printf '%s\n' "$NOT_SEL" | grep -c . || true)

# ---- emit manifest (every run, green or red — "the manifest is emitted on
# every run" is part of the acceptance text) ----
printf 'MANIFEST SELECTED: %s\n' "$N_SEL"
printf 'SELECTED-BACKEND-FILES: %s\n' "$N_SEL"   # playbook greps this line
printf 'MANIFEST NOT-SELECTED: %s (not selected for this diff)\n' "$N_NS"
if [ "$N_NS" -gt 0 ]; then
    printf '%s\n' "$NOT_SEL" | head -20 | sed 's/^/  not-selected: /'
    [ "$N_NS" -gt 20 ] && printf '  not-selected: +%s more\n' "$((N_NS - 20))"
fi
if [ "$N_CR" -gt 0 ]; then
    printf '%s\n' "$CANNOT" | sed 's/\t/ — /; s/^/MANIFEST CANNOT-RUN: /'
fi
if [ "$N_SEL" -eq 0 ]; then
    echo "fast(backend): 0 files selected - nothing affected"
fi

# Exit: cannot-run is a defect; pytest rc != 0 with no cannot-run is failing
# tests (also red, under its own name); green selection exits 0.
if [ "$N_CR" -gt 0 ]; then
    exit 1
fi
if [ "$RC" -ne 0 ]; then
    printf 'MANIFEST FAILING: pytest exited %s — see FAILED lines above\n' "$RC"
    exit "$RC"
fi
exit 0

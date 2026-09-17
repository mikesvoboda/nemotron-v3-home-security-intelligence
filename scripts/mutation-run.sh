#!/usr/bin/env bash
#
# WP4.3: mutation run for the WIDENED set (backend/services/ + backend/api/routes/).
#
# Why this file exists: the old invocation style (mutation-test.sh and
# mutation-testing.yml passing --paths-to-mutate/--tests-dir/--runner per
# module) died when the repo moved to mutmut 3.x -- those flags no longer
# exist ("Error: No such option '--paths-to-mutate'"), and every call site
# was `|| true`-shielded, so the weekly schedule silently produced nothing
# for months. mutmut 3 is CONFIG-DRIVEN: [tool.mutmut] in pyproject.toml owns
# the target set, the test selection and the pytest args. This script is the
# only runner; the workflow and the docs point here, so they cannot rot
# independently again.
#
# API (mutmut 3.8): `mutmut run [MUTANT_NAMES...]` -- positional args are
# fnmatch filters over mutant keys (fnmatch semantics verified against the
# installed package); NO match is a hard assert (loud), never a silent pass.
# `mutmut run` exits 0 after completing whatever it checked -- survivors are
# reported data, not a run failure; the SCORE comes from scripts/
# mutation-score.py reading mutmut's own verdict cache (mutants/*.py.meta).
#
# Usage:
#   ./scripts/mutation-run.sh                     # full widened set
#   ./scripts/mutation-run.sh severity            # one module's mutants
#   MUTMAX=6 ./scripts/mutation-run.sh            # cap parallel workers
#
# The mutants/ tree is the run cache (gitignored); the per-module score JSON
# and the committed history live OUTSIDE it (.github/mutation-history.json),
# written by the score step in the CI job, not here.
#
# See docs/developer/patterns/mutation-testing.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

MUTMAX="${MUTMAX:-}"        # empty -> mutmut default (cpu_count)
MODULE="${1:-}"

if ! command -v uv >/dev/null 2>&1; then
    echo "[ERROR] uv not found" >&2
    exit 1
fi

# mutmut 3 reads [tool.mutmut]; warn loudly if the dead 2.x flags come back.
uv run python - <<'EOF'
import tomllib, sys
cfg = tomllib.load(open("pyproject.toml", "rb"))["tool"]["mutmut"]
dead = {"paths_to_mutate", "tests_dir"} & set(cfg)
if dead:
    sys.exit(f"[tool.mutmut] carries deprecated keys {dead} -- mutmut 3 renames them source_paths / pytest_add_cli_args_test_selection")
EOF

RUN_ARGS=()
if [ -n "$MUTMAX" ]; then
    RUN_ARGS=(--max-children "$MUTMAX")
fi

# mutmut's also_copy uses copytree for DIRS (parents included) but plain
# copy2 for FILES -- which FileNotFoundError's if the destination parent
# doesn't exist yet. also_copy carries frontend/nginx.conf & co, so the
# parent must pre-exist. (No wholesale frontend/ copy: node_modules is
# 493MB and copytree has no ignore.)
mkdir -p mutants/frontend

if [ -n "$MODULE" ]; then
    # Mutant keys are <dotted.module.path>.<mangled-fn>: the pattern below
    # selects one module's mutants, and the trailing-dot match keeps
    # `severity` from selecting `severity_something`. A module lives in
    # exactly one of the two trees, so we try services, then routes; a zero
    # match in either is mutmut's own assert -- loud, never silent.
    echo "[mutation-run] module filter: backend.{services,api.routes}.${MODULE}.*"
    # shellcheck disable=SC2086
    uv run mutmut run "${RUN_ARGS[@]}" "backend.services.${MODULE}.*" \
        || uv run mutmut run "${RUN_ARGS[@]}" "backend.api.routes.${MODULE}.*"
else
    echo "[mutation-run] full widened set ([tool.mutmut] source_paths)"
    uv run mutmut run "${RUN_ARGS[@]}"
fi

echo "[mutation-run] done -- per-module scores:"
SCORE_JSON="$(mktemp)"
trap 'rm -f "$SCORE_JSON"' EXIT
uv run python scripts/mutation-score.py > "$SCORE_JSON"
python3 - "$SCORE_JSON" <<'PY'
import json, sys

r = json.load(open(sys.argv[1]))
t = r["totals"]
print(f"  modules with results: {len(r['modules'])} / {len(r['target_modules'])} targets")
print(
    f"  TOTAL: {t['score']:.1f}%  (killed {t['killed']}, survived {t['survived']}, "
    f"timeout {t['timeout']}, no_tests {t['no_tests']}, skipped {t['skipped']}, "
    f"suspicious {t['suspicious']}, unchecked {t['not_checked']})"
)
worst = sorted((m for m in r["modules"] if m["score"] is not None), key=lambda m: m["score"])[:10]
for m in worst:
    print(f"    {m['score']:6.1f}%  {m['module']}")
PY

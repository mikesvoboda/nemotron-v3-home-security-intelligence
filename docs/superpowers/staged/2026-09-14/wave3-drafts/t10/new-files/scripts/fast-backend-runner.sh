#!/bin/sh
# Runs the fast tier's selected backend tests (spec 4.1). Deterministic order
# (-p no:randomly) because selection is position-blind while randomly is not:
# selection and run must agree on ordering or a green --fast proves nothing
# about the same selection re-run. No coverage args at all (fast tier has no
# coverage proof - that is the full gate's identity).
set -eu

LIST="${1:?usage: fast-backend-runner.sh LISTFILE}"
if [ ! -s "$LIST" ]; then
    echo "fast(backend): 0 files selected - nothing affected"
    exit 0
fi
# Paths come from git ls-files (no spaces - repo convention; fast_select emits
# them newline-separated and xargs consumes them quoting-safely).
# -o addopts= REPLACES the pyproject addopts wholesale - that is why -m 'not
# gpu' and -v are restated inside it (validate.sh's own comment documents the
# same trap).
xargs -a "$LIST" -d '\n' -r uv run pytest \
    --dist=loadgroup -p no:randomly \
    -o addopts="-v -m 'not gpu' --timeout=60"

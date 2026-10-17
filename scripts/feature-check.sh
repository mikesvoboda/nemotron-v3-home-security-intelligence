#!/usr/bin/env bash
# The feature-check harness (O2.2): golden paths against a test deployment.
#
#   scripts/feature-check.sh --fake [--seeded] [--image-tag <tag>]
#   scripts/feature-check.sh --real --seeded [--image-tag <tag>]   # ruling 235
#   scripts/feature-check.sh drop <image> <camera>    # inside a golden spec
#
# --seeded is a BOOT SHAPE, not a mode (ruling 235): it rides on --fake or --real,
# and is refused only with --prod-shape, because production never runs DEBUG=true.
#
# --fake brings up the CI stack with the fake-AI overlay under its own compose
# project, runs the harness smoke check and the golden paths, collects
# artifacts and tears down; a preflight and a postflight prove it touched
# nothing else on the machine. The logic is scripts/feature_check.py (standard
# library only); usage and the golden-path contract are in
# docs/developer/testing.md, "Feature check".
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/feature_check.py" "$@"

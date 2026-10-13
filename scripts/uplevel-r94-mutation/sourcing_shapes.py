"""What does `set -e; . ./.env` actually do to each shape of an API_KEYS value?

Four shapes = {unquoted, single-quoted} x {compact JSON, spaced JSON}. This is the
measurement behind the serialization note on `convert_monitoring_key`
(`setup_lib/core.py`) and behind `[r94]`'s claim that the QUOTE, not the compactness, is
what makes a converted line sourceable. Contract rule 3 (UR-10) says a measurement a PR
quotes lives in the repo, so it lives here next to the battery.

    uv run python scripts/uplevel-r94-mutation/sourcing_shapes.py

Reads as: `rc=127` is bash word-splitting an unquoted value and trying to EXECUTE a
piece of it; `rc=0 / JSON REJECTED` is the quieter failure, where the value arrives
stripped of its quotes and every JSON reader downstream rejects it; `parses` is the
outcome a converted line must land on. Both quoted rows parse, which is why compactness
is a consistency choice (match `merge_api_keys`) and the quote is the correctness one.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

COMPACT = '["ops-laptop-key",{"key":"hsi_machine_key_ABC123","scope":"monitoring"}]'
SPACED = '["ops-laptop-key", {"key": "hsi_machine_key_ABC123", "scope": "monitoring"}]'

# Label -> the API_KEYS line as it would sit in an operator's file.
SHAPES = {
    "unquoted-compact": f"API_KEYS={COMPACT}",
    "unquoted-spaced": f"API_KEYS={SPACED}",
    "quoted-compact": f"API_KEYS='{COMPACT}'",
    "quoted-spaced": f"API_KEYS='{SPACED}'",
}

# How the repo's own scripts read the file: quick-rebuild.sh and
# verify-observability.sh both `source` it under `set -e`.
SOURCE_AND_PRINT = ["bash", "-c", 'set -e; . "$1"; printf "%s\\n" "$API_KEYS"']


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        for name, line in SHAPES.items():
            env_path.write_text(line + "\nBACKEND_PORT=8000\n", encoding="utf-8")
            proc = subprocess.run(  # real: bash is the thing under test
                [*SOURCE_AND_PRINT, "bash", str(env_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            value = (proc.stdout + proc.stderr).strip()
            try:
                verdict = f"parses, {len(json.loads(value))} entries"
            except Exception as exc:  # the failure shape IS the result
                verdict = f"JSON REJECTED ({type(exc).__name__})"
                failures += 1
            print(f"{name:17} rc={proc.returncode:<3} {verdict}")
            print(f"    value: {value[:92]}")
    print(
        "\nexpected: both quoted rows parse; unquoted-compact rc=0 but mangled; "
        "unquoted-spaced rc=127"
    )
    print(f"rows that did not parse: {failures} (2 is the expected count)")
    return 0 if failures == 2 else 1


if __name__ == "__main__":
    sys.exit(main())

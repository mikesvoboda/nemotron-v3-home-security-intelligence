"""B3.3 ratchet: every settings field is read outside config.py, or allowlisted with a reason.

The allowlist is the honest residue of the B3.3 sweep: fields the committed census
(``scripts/audit/settings_orphans.py``) reports as unread-outside-config.py because their
ONLY reader lives inside config.py itself -- a derivation validator reading ``info.data``
or ``self`` cannot use a field it imports by name, and the census deliberately reads only
OUTSIDE the file so its orphan list stays safe to delete against. Each entry carries the
use site that keeps it alive.

Doctrine (shared with scripts/ratchet-check.py): the census is RE-RUN here rather than
compared to a committed count -- a baseline that is never re-measured launders the next
re-addition. A new orphan fails naming the field; a stale allowlist entry fails too (if
the field gained an outside reader or was deleted, the entry must go in the same PR).
The scan walks the whole repo, so it runs ONCE per module, not per test.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNER = REPO_ROOT / "scripts" / "audit" / "settings_orphans.py"

# name -> why the census cannot see its reader (it lives inside config.py)
ALLOWED_UNREAD_OUTSIDE_CONFIG: dict[str, str] = {
    "llama_slot_count": "feeds _derive_slot_context_window (info.data.get) which divides "
    "the CTX_SIZE pool into the per-request budget",
    "vlm_slot_count": "read by the VLM slot-context validator (info.data.get) that divides "
    "vlm_context_window across parallel slots",
    "violence_definitive_threshold": "compared against violence_suspected_threshold by the "
    "ordering model_validator (definitive > suspected)",
    "violence_suspected_threshold": "compared against violence_definitive_threshold by the "
    "ordering model_validator (definitive > suspected)",
}


@pytest.fixture(scope="module")
def orphans() -> dict[str, str]:
    """Orphan name -> declared_at, from the committed census (single repo walk)."""
    proc = subprocess.run(  # noqa: S603  # intentional - runs our own committed script, fixed argv list
        [sys.executable, str(SCANNER), "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        check=False,
        timeout=240,  # under the 300s pytest cap so the failure names the scan, not the harness
    )
    assert proc.returncode == 0, f"census failed: {proc.stderr[-400:]}"
    payload = json.loads(proc.stdout)
    return {entry["name"]: entry["declared_at"] for entry in payload["orphan_fields"]}


@pytest.mark.timeout(300)  # module fixture runs the full-repo census once (~90s measured)
def test_no_unread_field_outside_the_allowlist(orphans: dict[str, str]):
    new = sorted(set(orphans) - set(ALLOWED_UNREAD_OUTSIDE_CONFIG))
    assert not new, (
        f"settings fields read nowhere outside config.py: {new}. Delete them with their "
        ".env.example lines (B3.3), or add a REASONED allowlist entry -- the reason must "
        "name the reader inside config.py that a whole-word scan outside cannot see."
    )


@pytest.mark.timeout(300)  # reuses the module-scoped census; no second scan
def test_allowlist_carries_no_zombies(orphans: dict[str, str]):
    zombies = sorted(set(ALLOWED_UNREAD_OUTSIDE_CONFIG) - set(orphans))
    assert not zombies, (
        f"allowlisted fields are no longer orphans: {zombies}. Either an outside reader "
        "appeared or the field was deleted -- remove the entry in the same PR (a zombie "
        "entry launders the next unreasoned addition, scripts/ratchet-check.py doctrine)."
    )


def test_allowlist_entries_carry_a_reason():
    bare = sorted(n for n, why in ALLOWED_UNREAD_OUTSIDE_CONFIG.items() if not why.strip())
    assert not bare, f"allowlist entries without a reason: {bare}"

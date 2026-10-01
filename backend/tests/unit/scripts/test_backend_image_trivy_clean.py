"""Guard: the backend prod image scans Trivy-clean for what this repo can fix.

Measured at main tip ``f9778503`` (job 110209886127, the first push after
PR #6750 merged): ``Security - Trivy / Scan Backend Image`` went red with 6
HIGH ``libexpat1`` findings (debian target, installed ``2.5.0-1+deb12u3``,
fixed ``2.5.0-1+deb12u4``) and 2 HIGH ``urllib3`` findings (python-pkg,
installed ``2.7.0``, fixed ``2.8.0``). It had been green at the two previous
tips ``67ca4870``/``cc1fde32`` — the Trivy DB caught up, the image did not.

The two findings are different in kind, and the split is measured, not
assumed:

* ``libexpat1`` is a real OS package with an available fix — the prod stage
  must upgrade it (first test; RED until the Dockerfile carries the step).
* the 2.7.0 ``urllib3`` is NOT the app's: the app venv scanned
  ``urllib3-2.8.0.dist-info`` with ZERO findings (job log line
  ``+ urllib3==2.8.0`` in the uv sync, and the scan table row with count 0).
  The 2.7.0 pair sits under the bare ``Python`` target — pip's VENDORED
  copy, ``pip/_vendor/vendor.txt`` reads ``urllib3==2.7.0`` for pip 26.2.1
  (measured: wheel unzipped here). Same no-action class as the msgpack/
  setuptools entries in ``.trivyignore``: only upstream pip can revendor.
  So this file carries dated entries (second test; RED until they exist) —
  this is a review act, flagged for the owner in the PR, never silent.

The third test is a forward guard, GREEN today: if a future lock change ever
downgrades the APP's urllib3 below the 2.8.0 fix, the real dependency would
silently re-enter the finding range — that is ours to catch, and it is not a
vendored problem.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
TRIVYIGNORE = REPO_ROOT / ".trivyignore"
UV_LOCK = REPO_ROOT / "uv.lock"

# The six HIGH expat CVEs from the f9778503 scan (debian target)
LIBEXPAT_CVES = (
    "CVE-2024-28757",
    "CVE-2025-59375",
    "CVE-2026-25210",
    "CVE-2026-45186",
    "CVE-2026-66046",
    "CVE-2026-93990",
)

# pip 26.2.1's vendored urllib3 findings (python-pkg, bare "Python" target)
VENDORED_URLLIB3_CVES = ("CVE-2026-97687", "CVE-2026-97689")


def _prod_stage() -> str:
    text = DOCKERFILE.read_text()
    m = re.search(r"^FROM python:.*AS prod\b", text, re.MULTILINE)
    assert m, "prod stage not found in backend/Dockerfile"
    return text[m.start() :]


class TestProdStagePatchesLibexpat:
    def test_prod_stage_upgrades_libexpat1(self) -> None:
        """The prod stage must carry a targeted libexpat1 upgrade.

        The base image pins the vulnerable 2.5.0-1+deb12u3; the fix exists in
        the bookworm security pocket, so unlike the vendored-pip findings
        this one is OURS to apply.
        """
        stage = _prod_stage()
        assert re.search(
            r"apt-get[^\n]*(install[^\n]*--only-upgrade[^\n]*libexpat1|upgrade[^\n]*libexpat1)",
            stage,
        ), (
            "backend/Dockerfile prod stage has no libexpat1 upgrade — the "
            "f9778503 Trivy scan flagged six HIGH CVEs on 2.5.0-1+deb12u3 "
            f"({', '.join(LIBEXPAT_CVES)}); fixed version 2.5.0-1+deb12u4"
        )


class TestVendoredUrllib3Documented:
    def test_trivyignore_carries_vendored_urllib3_ids(self) -> None:
        """.trivyignore must carry the two vendored urllib3 CVEs, dated.

        These are pip's private copy (pip/_vendor/vendor.txt: urllib3==2.7.0
        for pip 26.2.1 — verified from the wheel, not inferred). There is no
        repo-side fix short of stripping pip from the image; the file's own
        msgpack/setuptools section already records that class. Silent ignores
        are forbidden: every entry needs the mechanism comment and a
        REVIEW BY date the expiry checker can police.
        """
        text = TRIVYIGNORE.read_text()
        for cve in VENDORED_URLLIB3_CVES:
            assert re.search(rf"{cve}.*REVIEW BY: (\d{{4}}-\d{{2}}-\d{{2}})", text), (
                f"{cve} missing from .trivyignore (or undated) — it is a pip-vendored finding and must be an explicitly-reviewed entry"
            )


class TestAppUrllib3StaysPatched:
    def test_lock_urllib3_at_or_above_fix(self) -> None:
        """Forward guard (GREEN today): the APP's urllib3 stays >= 2.8.0.

        The app venv scanned clean because uv.lock pins 2.8.0; a downgrade
        would put the real dependency into the finding range, which is NOT a
        vendored false-positive and must fail here instead of in CI.
        """
        lock = UV_LOCK.read_text()
        m = re.search(r'^name = "urllib3"\nversion = "([0-9.]+)"', lock, re.MULTILINE)
        assert m, "urllib3 package block not found in uv.lock"
        parts = tuple(int(p) for p in m.group(1).split("."))
        assert parts >= (2, 8, 0), (
            f"uv.lock pins urllib3 {m.group(1)} < 2.8.0 — the app's own "
            "urllib3 would re-enter the CVE-2026-97687/97689 range; that is "
            "a real finding, not pip's vendored copy"
        )

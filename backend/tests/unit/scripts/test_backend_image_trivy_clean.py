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

2026-10-04 extension (the upgradeable-CVE sweep). Measured against main tip
``6b33a2af`` (backend job 111453726523, frontend job 111453726564): BOTH image
scans are RED with exactly one finding each — CVE-2026-103111 on pcre2
(backend ``libpcre2-8-0`` 10.42-1+deb12u1 → u2; frontend ``pcre2`` 10.48-r0 →
10.49-r0, alpine 3.24.2). Everything else the scans carry is zero: the thirteen
bookworm ``resolved`` entries in ``.trivyignore`` are already fixed at the
installed versions (amd64 CI install log + base-image dpkg status), so this
sweep (a) adds the two pcre2 upgrades and (b) deletes the dead ignores on
measured evidence. The classes below pin both halves so a regression is caught
here rather than in a push-only image scan: the prod stages keep their
upgrade lines, the deleted IDs stay deleted, and the entries the tracker still
marks ``open`` don't claim a shipped fix.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
FRONTEND_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile"
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

# pcre2 CVE-2026-103111 (HIGH, out-of-bounds write) is the ONE finding both
# image scans carried RED at tip 6b33a2af — the fix exists on both distros, so
# unlike the vendored-pip entries it is OURS to apply, in the backend prod
# stage (Debian) and the frontend prod stage (Alpine) alike.
PCRE2_CVE = "CVE-2026-103111"

# The Debian binary packages the prod stage pins forward. Every one of these is
# bookworm "resolved" in the Debian tracker with a fix version at/below what the
# image already installs — so this line is a no-op TODAY and only earns its keep
# as regression cover: if a base-digest or cache-layer move ever carries an older
# copy, --only-upgrade moves it back past the fix, and once the base absorbs the
# fix it no-ops (rc 0). It can only ever touch packages already present (an
# uninstalled real name is skipped, rc 0), so it cannot grow the image.
TRIGGER_RESOLVED_PKGS = (
    "libpcre2-8-0",
    "libc6",
    "libc-bin",
    "libpng16-16",
    "libglib2.0-0",
    "libgdk-pixbuf-2.0-0",
    "libzvbi0",
    "libzvbi-common",
    "libssh-gcrypt-4",
    "libpam-modules",
    "libpam0g",
    "gpgv",
)

# The .trivyignore entries this sweep DELETES because the image measurably
# carries the fix (or, for the minizip/zlib pair, the package is not present in
# the runtime image and the reportable half is already handled). They are listed
# here so a future edit cannot silently re-add a dead ignore — that is a review
# act, not something to slide back in without the measured evidence this sweep
# gathered.
UPGRADED_OUT_OF_IGNORE = (
    # bookworm "resolved", installed at/above the fix (amd64 CI install log +
    # base-image dpkg status):
    "CVE-2025-2173",  # libzvbi
    "CVE-2025-2174",  # libzvbi
    "CVE-2025-2176",  # libzvbi
    "CVE-2025-13601",  # libglib2.0-0
    "CVE-2025-68973",  # gpgv
    "CVE-2025-7345",  # libgdk-pixbuf-2.0-0
    "CVE-2025-5318",  # libssh-gcrypt-4
    "CVE-2025-5372",  # libssh-gcrypt-4
    "CVE-2025-5987",  # libssh-gcrypt-4
    "CVE-2025-6020",  # libpam
    "CVE-2026-0861",  # libc6 / libc-bin
    "CVE-2026-22695",  # libpng16-16
    "CVE-2026-22801",  # libpng16-16
    # minizip (the only libminizip1 carrier) is not installed in the runtime
    # image (its reverse-deps are chromium, not ffmpeg) and the reportable half
    # — Alpine zlib — is mapped to secfixes "0" (never reported) while the
    # Debian zlib half is open + filtered by the backend scan's ignore-unfixed:
    "CVE-2023-45853",
    # Alpine busybox: the frontend image ships busybox 1.37.0-r31, past the
    # r24/r27 fixes in Alpine's secdb, so Trivy stopped reporting these; the
    # ignores are dead. (Debian's busybox entries stay open — but busybox is not
    # in the Debian runtime image, so they were never matched there either.)
    "CVE-2024-58251",
    "CVE-2025-46394",
)

# Entries the Debian tracker STILL marks "open" (no bookworm fix) whose current
# rationale wrongly claims a fix already shipped. These stay in the register —
# they are genuine no-fix accepted risks — but the wording must be corrected,
# so this asserts the stale claim does not come back.
OPEN_ENTRIES = ("CVE-2025-48965", "CVE-2025-52496", "CVE-2025-7458")

# The five files AVD-DS-0002 actually suppresses, attributed by deleting the ID
# alone and re-running the CI-pinned scanner (aquasec/trivy:0.74.0 =
# .github/workflows/trivy.yml:280; repo-wide config scan like trivy.yml:93-108).
# Each reason is measured, not assumed — see .trivyignore's rationale and the
# 2026-10-04 ledger row: two published BASE images (a base with USER breaks every
# consumer's first apt-get/uv install), one image that runs under ROOTLESS PODMAN
# with no --user (synthbench/generate/comfy/serve.py:106-136 — container root is
# already the host UID, so an in-image USER strands its rw host binds at
# serve.py:131,133), one GPU SERVICE deferred with a fix recipe (ai/gateway needs
# host-side ownership of the rw model bind before it can drop privileges, and
# nothing in CI builds it), and one ARCHIVED file no job builds.
MISCONFIG_TARGETS = (
    "ai/gateway/Dockerfile",
    "archive/Dockerfile.yolo26-benchmark",
    "docker/base.Dockerfile",
    "docker/python-freethreaded/Dockerfile",
    "synthbench/generate/comfy/Containerfile",
)

# Substrings identifying the two images this repo PUBLISHES but nobody here
# builds FROM. Measured 2026-10-04 across every tracked Dockerfile.
BASE_IMAGE_MARKERS = ("nemotron-base", "3.14t")

# Directories a Dockerfile walk must skip: dependency trees and build output.
# (Measured: 12 image definitions found, matching `git ls-files`, in 20 ms.)
_WALK_PRUNE = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "mutants",
    "node_modules",
}


def _prod_stage() -> str:
    text = DOCKERFILE.read_text()
    m = re.search(r"^FROM python:.*AS prod\b", text, re.MULTILINE)
    assert m, "prod stage not found in backend/Dockerfile"
    return text[m.start() :]


def _frontend_prod_stage() -> str:
    text = FRONTEND_DOCKERFILE.read_text()
    m = re.search(r"^FROM .*nginx-unprivileged.*AS prod\b", text, re.MULTILINE)
    assert m, "prod stage not found in frontend/Dockerfile"
    return text[m.start() :]


def _logical_lines(text: str) -> list[str]:
    """Join Dockerfile backslash continuations into logical (single) lines."""
    logical: list[str] = []
    buf = ""
    for raw in text.splitlines():
        stripped = raw.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
        else:
            buf += stripped
            logical.append(buf)
            buf = ""
    if buf:
        logical.append(buf)
    return logical


def _only_upgrade_pkgs(stage: str) -> set[str]:
    """Binary package names carried on the prod stage's --only-upgrade line.

    Only RUN-instruction lines count — the rationale comment above the RUN
    mentions --only-upgrade too, so a bare substring match would find prose
    first.
    """
    for line in _logical_lines(stage):
        if line.lstrip().startswith("#"):
            continue
        if "--only-upgrade" in line and "apt-get" in line:
            frag = line.split("--only-upgrade", 1)[1].split("&&", 1)[0]
            return set(re.findall(r"[a-z][a-z0-9+.-]*[0-9a-z]", frag))
    return set()


def _entry_comment_block(text: str, cve: str) -> str:
    """The contiguous comment lines directly above a CVE's bare entry line."""
    m = re.search(rf"^{re.escape(cve)}$", text, re.MULTILINE)
    assert m, f"{cve} has no bare entry line in .trivyignore"
    block: list[str] = []
    for line in reversed(text[: m.start()].splitlines()):
        if line.startswith("#"):
            block.append(line)
        elif line.strip() == "":
            break
        else:
            break
    return "\n".join(reversed(block))


def _stages_with_from(text: str) -> list[dict[str, str | None]]:
    """Per-stage FROM image + org.opencontainers.image.base.name label.

    A stage's image is recorded with its tag stripped of a registry prefix only
    when the label carries one (the frontend pins docker.io/...); both sides are
    compared as-written so the check stays textual — no registry lookup, which a
    unit test must not need.
    """
    stages: list[dict[str, str | None]] = []
    current: dict[str, str | None] | None = None
    for line in _logical_lines(text):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", stripped, re.IGNORECASE)
        if m:
            image = m.group(1)
            # --platform=... and other FROM options are not part of the image
            image = image.split("=", 1)[-1] if image.startswith("--platform") else image
            current = {
                "name": m.group(2) or image,
                "from": image,
                "label": None,
            }
            stages.append(current)
            continue
        if current is not None and "org.opencontainers.image.base.name" in stripped:
            m2 = re.search(r"org\.opencontainers\.image\.base\.name=\"?([^\s\"]+)", stripped)
            if m2:
                current["label"] = m2.group(1)
    return stages


def _from_consumers_of(markers: tuple[str, ...]) -> list[str]:
    """Repo-relative paths of Dockerfiles whose FROM names one of `markers`.

    Walks the tree rather than shelling out to git — the test runs under mutmut
    against copied paths where a git subprocess may not resolve the way it does
    in a checkout.
    """
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _WALK_PRUNE]
        for name in filenames:
            low = name.lower()
            if not (
                low.startswith("dockerfile")
                or low.endswith(".dockerfile")
                or "containerfile" in low
            ):
                continue
            path = Path(dirpath) / name
            try:
                text = path.read_text(errors="replace")
            except OSError:  # pragma: no cover - unreadable file is not a consumer
                continue
            for line in _logical_lines(text):
                stripped = line.strip()
                if stripped.startswith("#") or not stripped.upper().startswith("FROM "):
                    continue
                image = stripped.split(None, 1)[1].split()[0]
                if any(marker in image for marker in markers):
                    hits.append(str(path.relative_to(REPO_ROOT)))
                    break
    return hits


class TestProdStagePatchesLibexpat:
    def test_prod_stage_upgrades_libexpat1(self) -> None:
        """The prod stage must carry a targeted libexpat1 upgrade.

        The base image pins the vulnerable 2.5.0-1+deb12u3; the fix exists in
        the bookworm security pocket, so unlike the vendored-pip findings
        this one is OURS to apply.
        """
        stage = _prod_stage()
        joined = " ".join(_logical_lines(stage))
        assert re.search(
            r"apt-get[^\n]*(install[^\n]*--only-upgrade[^\n]*libexpat1|upgrade[^\n]*libexpat1)",
            joined,
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


class TestProdStageUpgradesPcre2:
    def test_prod_stage_upgrades_libpcre2(self) -> None:
        """The backend prod stage must carry the libpcre2-8-0 upgrade.

        Tip 6b33a2af scan (job 111453726523): exactly one finding, HIGH
        CVE-2026-103111 on libpcre2-8-0 installed 10.42-1+deb12u1, fixed
        10.42-1+deb12u2 (bookworm "resolved"). The base digest predates the
        point release, so this one is NOT already carried — it is the sweep's
        only backend line that changes what the image installs.
        """
        stage = _prod_stage()
        pkgs = _only_upgrade_pkgs(stage)
        assert "libpcre2-8-0" in pkgs, (
            "backend/Dockerfile prod stage has no libpcre2-8-0 upgrade — the "
            f"6b33a2af scan flagged {PCRE2_CVE} (HIGH) at 10.42-1+deb12u1; "
            "fixed 10.42-1+deb12u2"
        )


class TestFrontendProdStageUpgradesPcre2:
    def test_frontend_prod_stage_upgrades_pcre2(self) -> None:
        """The frontend prod stage must upgrade pcre2 (Alpine leg).

        Same CVE on the other distro: the frontend scan (job 111453726564,
        alpine 3.24.2, ignore-unfixed FALSE — the stronger witness) is RED with
        pcre2 10.48-r0 against secdb fix 10.49-r0. The base tag is a moving
        :stable-alpine-slim, so this must be an explicit apk upgrade rather than
        a hope that the tag caught up.
        """
        stage = _frontend_prod_stage()
        joined = " ".join(_logical_lines(stage))
        assert re.search(r"apk\s+upgrade[^\n&]*pcre2", joined), (
            "frontend/Dockerfile prod stage has no 'apk upgrade ... pcre2'"
        )
        assert re.search(r"apk\s+upgrade[^\n&]*--no-cache", joined), (
            "frontend apk upgrade must use --no-cache like the apk add beside it"
        )


class TestProdStageCoversTrackerResolvedPkgs:
    def test_only_upgrade_line_names_every_resolved_pkg(self) -> None:
        """Regression cover for the thirteen bookworm-resolved packages.

        Each is already at/above its fix in today's image, so naming it costs
        nothing (--only-upgrade skips uninstalled names and no-ops on
        already-newest, rc 0); the line matters only if a base-digest move ever
        carries an older copy back in. The names are pin-able because a typo or
        a dropped package is invisible until a push-only image scan (or not at
        all — the backend scan runs ignore-unfixed).
        """
        pkgs = _only_upgrade_pkgs(_prod_stage())
        missing = sorted(p for p in TRIGGER_RESOLVED_PKGS if p not in pkgs)
        assert not missing, (
            "backend/Dockerfile prod --only-upgrade line is missing: "
            f"{', '.join(missing)} — these carry bookworm-resolved fixes per "
            "the 2026-10-04 tracker pull; see .trivyignore REMOVED block"
        )


class TestUpgradedEntriesStayOutOfIgnore:
    def test_trivyignore_does_not_carry_upgraded_ids(self) -> None:
        """The sixteen measured-fixed IDs stay OUT of .trivyignore.

        They were deleted on image evidence (amd64 install log + base-image
        dpkg status + Alpine secdb / installed r31), which is exactly the file's
        own rule ("Remove entries when fixes become available") and its
        2026-09-16 NOTE ("DELETED at that rebuild, not at the calendar date").
        Re-adding one without that evidence would hide a regression from the
        push-only scans; if the image genuinely regressed, the right fix is the
        Dockerfile line, not a new ignore.
        """
        text = TRIVYIGNORE.read_text()
        alive = set(re.findall(r"^(CVE-[0-9]{4}-[0-9]+)$", text, re.MULTILINE))
        back = sorted(set(UPGRADED_OUT_OF_IGNORE) & alive)
        assert not back, (
            f".trivyignore re-grew deleted entries: {', '.join(back)} — "
            "these were proven fixed on 2026-10-04; re-adding needs that "
            "quality of evidence"
        )

    def test_removed_block_records_the_sweep(self) -> None:
        """The REMOVED history block names the 2026-10-04 date and members.

        Deleting an entry without a trace is how registers rot — the history
        block is where the deletion + its reason survive.
        """
        text = TRIVYIGNORE.read_text()
        m = re.search(r"^# REMOVED.*?\n# =+\n", text, re.MULTILINE | re.DOTALL)
        assert m, "REMOVED history block missing from .trivyignore"
        block = m.group(0)
        assert "2026-10-04" in block, "REMOVED block does not record the 2026-10-04 sweep"
        # one Debian member + one Alpine member of the deleted set. (The
        # pcre2 CVE is NOT listed here — it was a live finding, never an
        # ignore, so it has no deletion to record.)
        for cve in ("CVE-2026-0861", "CVE-2024-58251"):
            assert cve in block, f"REMOVED block does not mention deleted {cve}"


class TestOpenEntriesDoNotClaimShippedFixes:
    def test_open_entries_wording_matches_tracker(self) -> None:
        """Tracker-open entries must not claim a fix shipped in bookworm.

        CVE-2025-48965/-52496 (mbedtls) and CVE-2025-7458 (sqlite3) sat under
        comments saying a fix "shipped in bookworm" and should "remove once the
        rebuild proves it". The 2026-10-04 tracker pull says all three are
        ``open`` with no fix version — the cited versions are just the current
        published ones. They stay in the register as no-fix risks, but a future
        reviewer must not be sent hunting a fix that does not exist.
        """
        text = TRIVYIGNORE.read_text()
        for cve in OPEN_ENTRIES:
            block = _entry_comment_block(text, cve)
            assert re.search(r"no fix|open|not fixed|no upstream fix", block, re.IGNORECASE), (
                f"{cve}'s comment block does not say the fix is missing"
            )
            assert not re.search(
                r"[Ff]ix shipped|[Ff]ix(es)? (in|landed|available) (bookworm|Debian)", block
            ), (
                f"{cve} comment claims a shipped fix again — the Debian "
                "tracker marks it open (2026-10-04 pull); do not re-add the claim"
            )


class TestDeadMisconfigIgnoreStaysDeleted:
    def test_avd_ds_0001_is_not_an_active_entry(self) -> None:
        """AVD-DS-0001 (":latest base tag") must stay out of the register.

        Measured 2026-10-04 with the CI-pinned scanner (aquasec/trivy:0.74.0,
        .github/workflows/trivy.yml:280) running the same repo-wide config scan
        CI runs (trivy.yml:93-108): deleting the ID reveals NOTHING — it
        suppressed zero findings, so it was dead register. Its stated premise is
        gone too: no FROM line in the repo builds FROM nemotron-base anymore
        (backend/Dockerfile:36 is python:3.14-slim-bookworm), and the docker
        checks do not flag :latest on a COPY --from= (the two uv:latest lines,
        backend/Dockerfile:51,236, are unsuppressed and unreported).
        """
        text = TRIVYIGNORE.read_text()
        alive = set(re.findall(r"^(AVD-[A-Z]+-[0-9]+)$", text, re.MULTILINE))
        assert "AVD-DS-0001" not in alive, (
            "AVD-DS-0001 is back in .trivyignore — it suppressed zero findings "
            "(measured by deletion, trivy 0.74.0 = the CI pin). If a FROM "
            "nemotron-base line ever comes back, re-argue it with that scan output"
        )

    def test_removed_block_records_the_deletion(self) -> None:
        """The deletion survives as a dated record in the history block.

        Same discipline as the CVE sweep: an entry that leaves the register
        leaves a trace naming what was removed and the evidence, or the next
        reviewer repeats the audit.
        """
        text = TRIVYIGNORE.read_text()
        m = re.search(r"^# REMOVED.*?\n# =+\n", text, re.MULTILINE | re.DOTALL)
        assert m, "REMOVED history block missing from .trivyignore"
        assert "AVD-DS-0001" in m.group(0), "REMOVED block does not record the AVD-DS-0001 deletion"


class TestMisconfigIgnoreNamesRealTargets:
    def test_avd_ds_0002_block_names_every_suppressed_file(self) -> None:
        """The blanket non-root ignore must name what it actually silences.

        AVD-DS-0002 suppresses FIVE HIGH "no USER directive" findings —
        measured by deleting the ID alone and attributing the result
        (trivy 0.74.0, repo-wide config scan):

            ai/gateway/Dockerfile
            archive/Dockerfile.yolo26-benchmark
            docker/base.Dockerfile
            docker/python-freethreaded/Dockerfile
            synthbench/generate/comfy/Containerfile

        The rationale this replaces described vsftpd instead — a file that is
        NOT flagged (archive/vsftpd/Dockerfile:48 carries USER ftpsecure). One
        ID covering five files is forced, not lazy: the docker checks report at
        file level with no line number, and neither an INI-section ignore file
        (ids+paths, both ID spellings, globs, paths=["*"]) nor an inline
        '# trivy:ignore:' comment suppressed anything in measurement — so
        path-scoping does not exist for config scans.
        """
        text = TRIVYIGNORE.read_text()
        block = _entry_comment_block(text, "AVD-DS-0002")
        missing = sorted(p for p in MISCONFIG_TARGETS if p not in block)
        assert not missing, (
            ".trivyignore's AVD-DS-0002 rationale does not name: "
            f"{', '.join(missing)} — those files are what the entry actually "
            "suppresses; a rationale that names other files is how a register "
            "rots silently"
        )
        assert not re.search(r"vsftpd requires root|needs root privileges", block), (
            "AVD-DS-0002's rationale re-claims vsftpd as the reason — that file "
            "is clean (USER ftpsecure at archive/vsftpd/Dockerfile:48) and is "
            "not one of the five suppressed targets"
        )

    def test_entry_stays_dated(self) -> None:
        """Every accepted risk keeps a REVIEW BY date the owner can police.

        The expiry script only parses CVE-shaped lines, so a dated AVD entry is
        unpoliced by CI — which makes the date a human contract and worth
        pinning here.
        """
        text = TRIVYIGNORE.read_text()
        assert re.search(r"AVD-DS-0002.*REVIEW BY: (\d{4}-\d{2}-\d{2})", text), (
            "AVD-DS-0002 must keep its dated review comment"
        )


class TestBaseLabelMatchesFrom:
    def test_base_name_label_matches_the_stage_from(self) -> None:
        """An OCI base.name label must name the image its stage actually uses.

        The base stage labels itself ghcr.io/mikesvoboda/python:3.14t-slim-bookworm
        (backend/Dockerfile:46) while its own FROM (backend/Dockerfile:36) is
        python:3.14-slim-bookworm — a GIL-enabled build, not the free-threaded
        one. The free-threaded image is a documented OPTION in the comment above
        (:22-35), not the current base. A wrong base label misreports provenance
        to every scanner and every SBOM that reads the built image.
        """
        text = DOCKERFILE.read_text()
        mismatches: list[str] = []
        for stage in _stages_with_from(text):
            if stage["label"] is None or stage["label"] == stage["from"]:
                continue
            # an internal multi-stage reference (FROM base AS builder) is not a
            # registry base and carries no label; only flag registry mismatches
            if ":" in stage["from"] and stage["from"] != stage["label"]:
                mismatches.append(
                    f"stage {stage['name']!r}: FROM {stage['from']} vs "
                    f"base.name label {stage['label']}"
                )
        assert not mismatches, "backend/Dockerfile OCI base label drift: " + "; ".join(mismatches)


class TestNoRepoConsumerOfPublishedBases:
    def test_no_dockerfile_builds_from_the_published_bases(self) -> None:
        """Tripwire: the two published bases have ZERO in-repo FROM consumers.

        Measured 2026-10-04 over every tracked Dockerfile/Containerfile: nothing
        builds FROM ghcr.io/mikesvoboda/nemotron-base or the free-threaded
        python:3.14t image — backend builds FROM python:3.14-slim-bookworm
        directly. That fact is the load-bearing premise of three statements: the
        two bases' non-root deferral rationale, the AVD-DS-0001 deletion, and the
        corrected comments in backend/Dockerfile and setup_lib/deploy_phases.py.
        If a future PR wires one in as a real dependency, those rationales must
        be re-argued — which is the point of failing here.
        """
        consumers = _from_consumers_of(BASE_IMAGE_MARKERS)
        assert not consumers, (
            "a Dockerfile now builds FROM a published base image: "
            f"{', '.join(consumers)} — the AVD-DS-0002 rationale for those two "
            "files (and the AVD-DS-0001 deletion) assume they have no "
            "in-repo consumers; re-measure and re-argue before merging"
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

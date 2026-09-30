"""R8 slice S5: the five enrichment panels retire with their tables, and the
empty state the design left in their place retires too. ABOUTME: this file is
S5's red-first guard -- it pins the END STATE the owner's ruling of 2026-09-29
mandates, written (and proven red) BEFORE any deletion, per the goal prompt's
"TDD red-first" hard rule.

The owner ruling this file encodes, asked because two authorities disagreed:
the design spec §6 says the R8:108 panels get an empty state instead of a
deletion (PR #6681 shipped that empty state), while the roadmap
`docs/vss-integration/12-postponed-roadmap.md:120-121` says "the design's empty
states become deletions".  Owner answer: **"Delete the 5 panels now"** -- the
roadmap wins, so this slice removes the five named sources AND the
`enrichment-retired-state` tombstone that #6681 shipped in their place.

The deletion set is the goal prompt's closed list (scope `:46-47`), plus what
mechanically dies with it (measured, not assumed -- its size is pinned by
`test_the_deletion_set_is_measurable_now`):

  frontend/src/components/enrichment/            whole directory (Viewer + barrel + AGENTS.md + test)
  frontend/src/components/events/EnrichmentBadges.tsx        (+ .test.tsx)
  frontend/src/components/events/EnrichmentPanel.tsx         (+ .test.tsx)
  frontend/src/components/events/EventEnrichmentSummary.tsx  (+ .test.tsx)
  frontend/src/utils/poseVisualization.ts                    (+ .test.ts)

`types/enrichment.ts` STAYS: the goal prompt names it as kept, and it is still
imported by `types/index.ts` and by its own surviving tests.

Deliberately NOT deleted, and the most likely over-reach a reader would commit:
`EnrichmentProgressBadge.tsx`, `useDetectionEnrichment.ts`,
`useEventEnrichmentsQuery.ts`, `useEnrichmentProgress.ts`,
`useEventEnrichmentWebSocket.ts` and their tests. The scope doc has ZERO
mentions of the hooks or that badge, and the goal prompt's S5 sentence names
five files, not nine. They form a real zero-live-consumer island (measured:
their only edges are each other plus `hooks/index.ts` re-exports) and I will
REPORT that island rather than silently fold it into S5.

Why pins rather than greps, per this repo's recurring lesson: prose is allowed
to name the dead. Every "X is gone" check reads source TEXT for LIVE forms only
(import specifiers, JSX element usage, `data-testid` attributes) or uses file
absence, so a docblock that explains the retirement cannot fail this file. And
every scan pins its own non-vacuity -- `TestS5SurfaceIsRealBeforeItIsGone`
carries the red-side witness, and the tree-wide import-resolution pin asserts it
resolved thousands of specifiers rather than zero.

One hazard this file pins explicitly, because it is invisible from inside the
frontend: `scripts/check-api-coverage.sh` greps `frontend/src` for the
BACKEND's literal route string, and the backend declares
`@router.get("\\n    \\"/{event_id}/enrichments\\"` as a MULTI-LINE decorator the
script's single-line grep never extracts -- so that route is not in the script's
input at all (measured: 0 of 79 extracted paths contain "enrichments"). The
literal `/{event_id}/enrichments` currently appears in exactly one file OUTSIDE
the deletion set, `hooks/useEventEnrichmentsQuery.ts`, which S5 keeps. If the
backend ever moves that decorator to one line, deleting
`EventEnrichmentSummary.tsx`'s docblock is what would surface a red there -- so
the survivor is pinned by name and the post-slice run of the script is reported,
not silently "fixed".
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import ClassVar

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

# The five sources the goal prompt names, plus the barrel and AGENTS.md that
# cannot survive their directory.
SOURCES = [
    "frontend/src/components/enrichment/EnrichmentViewer.tsx",
    "frontend/src/components/enrichment/index.ts",
    "frontend/src/components/enrichment/AGENTS.md",
    "frontend/src/components/events/EnrichmentBadges.tsx",
    "frontend/src/components/events/EnrichmentPanel.tsx",
    "frontend/src/components/events/EventEnrichmentSummary.tsx",
    "frontend/src/utils/poseVisualization.ts",
]

TESTS = [
    "frontend/src/components/enrichment/__tests__/EnrichmentViewer.test.tsx",
    "frontend/src/components/events/EnrichmentBadges.test.tsx",
    "frontend/src/components/events/EnrichmentPanel.test.tsx",
    "frontend/src/components/events/EventEnrichmentSummary.test.tsx",
    "frontend/src/utils/poseVisualization.test.ts",
]

# What must still be here. Each of these is a NON-VACUITY for the deletion
# above: without a live file to grep, an absence pin is theatre.
SURVIVORS = [
    "frontend/src/types/enrichment.ts",
    "frontend/src/components/events/EventDetailModal.tsx",
    "frontend/src/components/events/EventDetailModal.test.tsx",
    "frontend/src/components/detection/PoseSkeletonOverlay.tsx",
    "frontend/src/components/detection/DetectionImage.tsx",
    "frontend/src/components/detection/PoseSkeletonOverlay.test.tsx",
    "frontend/src/components/detection/__snapshots__/PoseSkeletonOverlay.test.tsx.snap",
    "frontend/src/components/events/EnrichmentProgressBadge.tsx",
    "frontend/src/hooks/useEventEnrichmentsQuery.ts",
]


def _src(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


def _dotted(node: ast.expr) -> str:
    """`pytest.skip` as written -- the census's own _decorator_name reduction,
    copied in behaviour (not imported: suppression-census.py is a script, and a
    guard that imports the tool it audits couples them for no benefit)."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _live_ts(rel: str) -> str:
    """Source text with comments stripped, so a retirement docblock cannot
    satisfy -- or fail -- a LIVE-form pin. Stripping both block and line
    comments is what makes the "prose may name the dead" claim mechanical."""
    text = _src(rel)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return text


def _ts_files(root: str = "frontend/src") -> list[Path]:
    return [
        p
        for p in sorted((REPO_ROOT / root).rglob("*"))
        if p.suffix in (".ts", ".tsx") and "__mocks__" not in p.parts
    ]


def _relative_specifiers(path: Path) -> list[str]:
    """Import/export specifiers in LIVE code of one file (comments stripped)."""
    text = path.read_text()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return re.findall(r"""(?:from|import)\s*['"](\.[^'"]+)['"]""", text)


# Specifier suffixes that are resolved by the bundler, not by a sibling .ts
# file (measured pre-slice: `main.tsx -> ./styles/index.css` and
# `ToastProvider.tsx -> ../../styles/toast.css`). Scanning them would make the
# pin red for a reason that has nothing to do with a deleted component.
BUNDLER_SUFFIXES = (".css", ".json", ".svg", ".png", ".jpg", ".webp", ".woff", ".woff2")


def _resolves(spec: str, importer: Path) -> bool:
    if spec.endswith(BUNDLER_SUFFIXES):
        return (importer.parent / spec).exists()
    base = importer.parent / spec
    return any(
        candidate.exists()
        for candidate in (
            base.with_suffix(".ts"),
            base.with_suffix(".tsx"),
            base / "index.ts",
            base / "index.tsx",
        )
    )


class TestS5SurfaceIsRealBeforeItIsGone:
    """Vacuity guard, written FIRST. Every absence pin below means something
    only if the surface it scans exists on BOTH sides of the change -- the S2b
    compose lesson S3's guard restates. On the pre-deletion tree these pass
    because the panels are here; if a future slice deletes a file this class
    still expects, it reddens rather than going quietly vacuous."""

    def test_the_deletion_set_is_measurable_now(self) -> None:
        """The red-side witness. Before the slice every named source exists;
        after it, the same list is what `TestRetiredPanelsAreGone` asserts is
        absent. A pin that cannot observe the thing it removes asserts nothing,
        so the two halves share one list rather than two hand-maintained ones."""
        for rel in SOURCES + TESTS:
            path = REPO_ROOT / rel
            if path.exists():
                assert path.stat().st_size > 0, f"{rel} exists but is empty"
        # Non-vacuity of the list itself: the scope prompt names five panels and
        # a helper; a list that had silently shrunk to nothing would make every
        # deletion pin pass on an empty loop.
        assert len(SOURCES) == 7
        assert len(TESTS) == 5

    def test_the_survivors_this_slice_must_not_touch_exist(self) -> None:
        for rel in SURVIVORS:
            assert (REPO_ROOT / rel).exists(), f"{rel} missing -- absence pins below are theatre"
            assert (REPO_ROOT / rel).stat().st_size > 0, f"{rel} is empty"

    def test_the_modal_is_the_live_surface_the_pins_scan(self) -> None:
        """Every `EventDetailModal.tsx` absence pin scans this file. If it were
        empty or gone, "no import of EnrichmentViewer" would be true of nothing.
        The floor is a magnitude floor on a file with a known shape -- not a
        count that a future edit must preserve."""
        modal = _live_ts("frontend/src/components/events/EventDetailModal.tsx")
        assert "Modal" in modal
        assert len(modal) > 20_000, "the modal is unexpectedly small; the pins below scan nothing"


class TestRetiredPanelsAreGone:
    """The owner ruling's deletion side, pinned by path."""

    @pytest.mark.parametrize("rel", SOURCES)
    def test_retired_source_is_absent(self, rel: str) -> None:
        assert not (REPO_ROOT / rel).exists(), f"{rel} survives S5"

    @pytest.mark.parametrize("rel", TESTS)
    def test_retired_test_is_absent(self, rel: str) -> None:
        assert not (REPO_ROOT / rel).exists(), f"{rel} tests a component that no longer exists"

    def test_the_enrichment_component_directory_is_gone_entirely(self) -> None:
        """A directory left behind holding only a stray file is the failure mode
        a per-file absence list cannot see -- so the directory is pinned too, and
        the pin is stated as a two-sided witness rather than a bare `.exists()`
        on a path that may never have existed in any commit (the phantom-presence
        mistake S3's guard names)."""
        d = REPO_ROOT / "frontend/src/components/enrichment"
        if d.exists():
            left = sorted(p.name for p in d.rglob("*") if p.is_file())
            pytest.fail(f"components/enrichment/ still holds {left}")
        assert (REPO_ROOT / "frontend/src/components/events").exists(), (
            "events/ must survive -- this pin is about enrichment/, not components/"
        )


class TestModalIsSevered:
    """`EventDetailModal.tsx` is the only shipped consumer of four of the five
    (measured pre-slice: `:24`, `:26`, `:699`, `:1041-1044`, `:1047-1077`). Its
    removal is the slice's real edit surface, so it is pinned LIVE-FORM ONLY:
    import specifier, JSX element, `data-testid` attribute. The comment the
    slice leaves behind explains the retirement and names the dead -- which is
    exactly why a bare substring pin here would be wrong."""

    MODAL: ClassVar[str] = "frontend/src/components/events/EventDetailModal.tsx"

    def test_no_import_of_a_retired_panel(self) -> None:
        modal = _live_ts(self.MODAL)
        for gone in (
            "EnrichmentViewer",
            "EventEnrichmentSummary",
            "EnrichmentBadges",
            "EnrichmentPanel",
        ):
            assert gone not in modal, f"{gone} still named in live code"

    def test_no_jsx_of_a_retired_panel(self) -> None:
        modal = _src(self.MODAL)
        for tag in ("<EnrichmentViewer", "<EventEnrichmentSummary"):
            assert tag not in modal, f"{tag} still rendered"

    def test_the_retired_state_tombstone_is_gone(self) -> None:
        """Owner ruling: the roadmap's "the design's empty states become
        deletions" beats the design's empty state. Pinned on the ATTRIBUTE,
        which is live code, not on the sentence inside it."""
        assert "enrichment-retired-state" not in _src(self.MODAL)

    def test_the_summary_wrapper_testid_is_gone(self) -> None:
        assert "enrichment-summary-section" not in _src(self.MODAL)

    def test_the_modal_keeps_rendering_everything_that_survives(self) -> None:
        """Two-sided: the deletion must not have taken the modal's remaining
        sections with it. These are the neighbours of the deleted block --
        `ActionEventsPanel` sits immediately after it and shares the same
        `!isNaN(eventIdNumber) && event.camera_id` guard shape, so a careless
        brace removal here is the likely bug."""
        modal = _live_ts(self.MODAL)
        for kept in ("ActionEventsPanel", "DetectionImage", "EntityTrackingPanel"):
            assert kept in modal, f"{kept} gone with the enrichment block"
        assert 'data-testid="action-events-section"' in _src(self.MODAL)

    def test_the_modal_still_reads_enrichment_data_on_its_detection_type(self) -> None:
        """The goal prompt keeps `types/enrichment.ts`, and the modal's exported
        `Detection` interface keeps its optional `enrichment_data` member --
        deleting the PANEL is not deleting the API field. Two consumers import
        `Event as ModalEvent` from this file (`EventTimeline.tsx:75`,
        `AlertsPage.tsx:24`), so the exported shape is pinned."""
        modal = _live_ts(self.MODAL)
        assert "enrichment_data" in modal, (
            "Detection.enrichment_data dropped: the backend still returns it and "
            "EventTimeline/AlertsPage import this type"
        )
        assert "import type { EnrichmentData } from '../../types/enrichment'" in modal


class TestTreeIsNotLeftDangling:
    """The structural pin, derived rather than hand-listed: EVERY relative
    specifier in `frontend/src` (all .ts/.tsx outside `__mocks__`, comments
    stripped) must resolve to a real file. Measured before the slice: 4315
    relative specifiers over 1695 files, zero unresolved -- so after deleting
    files and pruning imports, unresolved must still be zero AND the scan must
    still have resolved thousands of specifiers (otherwise this test is passing
    on an empty set, the vacuity this repo keeps learning). The floor is 2000
    rather than 4315 because the slice deletes ~12 files; a floor the slice must
    "restore" by re-adding imports is the wrong kind of pin.

    Two specifiers resolve to CSS (`main.tsx`, `ToastProvider.tsx`), which is
    why `BUNDLER_SUFFIXES` exists: without it this pin is red on a clean tree
    for a reason that has nothing to do with the retirement -- and a pin that is
    red at HEAD gets "fixed" by whoever notices it, which is how guard files
    quietly stop asserting anything.
    """

    def test_no_relative_import_points_at_a_deleted_file(self) -> None:
        unresolved: list[str] = []
        resolved = 0
        for path in _ts_files():
            for spec in _relative_specifiers(path):
                if _resolves(spec, path):
                    resolved += 1
                else:
                    unresolved.append(f"{path.relative_to(REPO_ROOT)}: {spec}")
        assert resolved > 2000, f"scan resolved only {resolved} specifiers -- it is vacuous"
        assert not unresolved, "dangling relative imports: " + "; ".join(unresolved)

    def test_no_surviving_file_references_a_retired_panel(self) -> None:
        """The name-based twin of the resolution pin. A surviving file can
        reference a retired component through a barrel, a `React.lazy()`, a
        string in a `data-testid`, or a re-export that no import currently
        resolves -- none of which the resolution scan catches. Pinned on live
        text only, so the modal's retirement comment does not fail it.

        The scan excludes the test files that were deleted WITH their subjects
        (asserted above) and the doc files, which prose doctrine protects."""
        hits: list[str] = []
        for path in _ts_files():
            rel = str(path.relative_to(REPO_ROOT))
            if any(rel.endswith(gone.rsplit("/", 1)[-1]) for gone in SOURCES + TESTS):
                continue  # its own file, pinned absent above
            if path.name.endswith((".test.ts", ".test.tsx")):
                # surviving tests are scanned; retired ones are pinned absent
                if any(name in rel for name in ("EnrichmentViewer", "EnrichmentBadges")):
                    continue
            live = _live_ts(rel)
            for name in ("EnrichmentViewer", "EventEnrichmentSummary"):
                if name in live:
                    hits.append(f"{rel}: {name}")
        assert not hits, "retired panel still referenced: " + "; ".join(hits)

    def test_pose_visualization_has_no_surviving_importer(self) -> None:
        """`utils/poseVisualization.ts` had exactly one importer pre-slice -- its
        own test (measured) -- so this is the cleanest deletion in the slice, and
        the one most likely to be wrongly entangled with `PoseSkeletonOverlay`
        by a reader who assumes the overlay draws the skeleton from it. It does
        not: the overlay imports `BODY_PART_COLORS` from `constants/chartColors`
        and re-exports it, and never mentions poseVisualization. Both halves
        pinned, because an overlay that stopped rendering would be a silent
        behaviour regression dressed up as a clean deletion."""
        overlay = _live_ts("frontend/src/components/detection/PoseSkeletonOverlay.tsx")
        assert "poseVisualization" not in overlay
        assert "BODY_PART_COLORS" in overlay, "the overlay's own colour surface is gone"
        detection_image = _live_ts("frontend/src/components/detection/DetectionImage.tsx")
        assert "PoseSkeletonOverlay" in detection_image, (
            "PoseSkeletonOverlay is NOT in S5's scope; if it lost its consumer, "
            "say so in the report -- do not delete it here"
        )


class TestTheKeptIslandIsUntouched:
    """The scope boundary, pinned so a later reader cannot quietly widen S5.

    The enrichment hooks (`useDetectionEnrichment`, `useEventEnrichmentsQuery`,
    `useEnrichmentProgress`, `useEventEnrichmentWebSocket`) and
    `EnrichmentProgressBadge.tsx` form a real zero-LIVE-consumer island: their
    only edges are each other plus `hooks/index.ts` re-exports (knip ignores
    `src/**/index.ts`, which is why it never reported them). They are NOT in the
    goal prompt's S5 sentence and the scope doc never mentions them, so S5
    leaves them alone and REPORTS them. Pinning them present is what makes that
    boundary enforceable instead of a paragraph in a docstring."""

    ISLAND: ClassVar[list[str]] = [
        "frontend/src/hooks/useDetectionEnrichment.ts",
        "frontend/src/hooks/useEventEnrichmentsQuery.ts",
        "frontend/src/hooks/useEnrichmentProgress.ts",
        "frontend/src/hooks/useEventEnrichmentWebSocket.ts",
        "frontend/src/components/events/EnrichmentProgressBadge.tsx",
    ]

    @pytest.mark.parametrize("rel", ISLAND)
    def test_out_of_scope_survivor_still_ships(self, rel: str) -> None:
        assert (REPO_ROOT / rel).exists(), (
            f"{rel} is outside S5's scope (goal prompt :46-47 names five files; "
            "the scope doc never mentions the hooks). Deleting it here is the "
            "over-reach this pin exists to catch."
        )

    def test_the_enrichment_types_module_survives_as_the_goal_prompt_orders(self) -> None:
        types = REPO_ROOT / "frontend/src/types/enrichment.ts"
        assert types.exists()
        assert "hasAnyEnrichment" in types.read_text()
        # Non-vacuity: something still imports it, so "it survives" is not
        # "it is orphaned dead weight that should have gone with the panels".
        importers = [
            p
            for p in _ts_files()
            if "types/enrichment" in _live_ts(str(p.relative_to(REPO_ROOT)))
            and "types/enrichment.ts" not in str(p)
        ]
        assert importers, "types/enrichment.ts has no live importer; kept-but-dead"

    def test_this_guard_file_adds_no_suppression_marker(self) -> None:
        """Whole-repo census equality against `.github/suppression-baseline.json`
        is CI's gate (ci.yml:121 runs `suppression-census.py --expect`), and this
        slice leaves the committed baseline correct: of the twelve deleted files,
        exactly one carried a suppression marker -- an `eslint-disable-next-line`
        in EnrichmentBadges.test.tsx (measured against the base-commit blobs) --
        and the census counts only `it.skip/only/todo`-style frontend modifiers
        and pytest forms, never eslint directives (suppression-census.py's
        _FRONTEND_SUPPRESSION_RE). No registry regeneration is needed, and this
        slice must not CAUSE one.

        What this file can pin cheaply is its own contribution. An earlier draft
        of this very test guarded a missing-baseline-file branch with
        ``pytest.skip(...)`` -- which the census counts as an imperative skip and
        bumped `pytest_skip_imperative` 99 -> 100, reddening the exact gate the
        test was written to protect. (The draft also asked the registry to name
        deleted files; the registry is fifteen integers, no paths, so that pin
        could never be violated -- vacuity the same shape as the ones S3's guard
        names.) The census itself takes ~25s against this repo and the unit tier
        times out at 5s, so a full census call from a test is structurally
        impossible here -- which is precisely why the self-pin lives in this
        file's own AST, where it costs one parse.

        The scan is AST-based for the same reason the census is: a substring
        search for ``pytest.skip(`` matches this docstring's own prose and the
        marker tuple below, so a naive version of this test fails against the
        file it lives in. ``ast.Call`` nodes only -- string literals and
        comments cannot trip it, exactly like ``count_pytest_skip_imperative``.
        """
        tree = ast.parse(Path(__file__).read_text())
        trips = [
            f"{node.lineno}: {_dotted(node.func)}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _dotted(node.func) in ("pytest.skip", "pytest.xfail", "pytest.skipif")
        ]
        assert not trips, (
            f"imperative skip/xfail calls {trips} in this guard file shift "
            "pytest_skip* in the generated census -- assert the fact directly instead"
        )

"""Unit tests for scripts/check-vss-docs-currency.py.

ABOUTME: The stale-status guard for docs/vss-integration/ — the defect class where a meta-doc's own
Status line outlives the code (README:6 and AGENTS:6 both said "nothing implemented yet" for six
days after 4bfd6fa4 shipped the VLM path as the default). Tests build throwaway doc trees and assert
the gate passes when a dated correction naming the stale sentence precedes it, and fails, naming the
file, when it does not.

The two hazard cases are ones this gate had and lost: a correction that QUOTES the stale sentence
must not create a false failure (the quote is the first hit, so "is there a banner above it?" is
asked of the banner itself), and an unrelated dated banner at the top of a doc (00-context.md's
Errata line) must not be read as correcting a claim it never mentions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "check-vss-docs-currency.py"

README = "docs/vss-integration/README.md"
AGENTS = "docs/vss-integration/AGENTS.md"
CONTEXT = "docs/vss-integration/00-context.md"

# The claim each doc carries, as the gate's CLAIMS table states it.
CLAIMS = {
    README: "nothing implemented yet",
    AGENTS: "Nothing is implemented yet",
    CONTEXT: "Research in progress",
}


def banner_for(claim: str) -> str:
    """A correction in the form the gate accepts: dated, and it names the sentence it retires."""
    return (
        f'> **Currency (2026-09-29) [V].** The line below ("{claim}") is stale. See the ledger.\n\n'
    )


def corrected_doc(rel: str) -> str:
    """A doc in the passing shape: dated banner naming the claim, then the claim standing below it."""
    claim = CLAIMS[rel]
    return banner_for(claim) + f"# {Path(rel).name}\n\n**{claim}.** The record of 2026-09-23.\n"


def make_tree(tmp_path: Path, *, banners: bool = True) -> Path:
    """A doc tree in the shape the gate reads: the false claim, optionally corrected above it."""
    tree = tmp_path / "docs" / "vss-integration"
    tree.mkdir(parents=True)
    stale = {
        README: "# VSS Integration\n\n> **Status (2026-09-23): design approved, nothing implemented yet.**\n",
        AGENTS: "# Agent Guide\n\n**Nothing is implemented yet.** Pick your branch.\n",
        CONTEXT: "# Context\n\n**Status:** Research in progress. Nothing here is a commitment.\n",
    }
    for rel, body in stale.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((banner_for(CLAIMS[rel]) if banners else "") + body, encoding="utf-8")
    return tmp_path


def run_gate(tree: Path) -> subprocess.CompletedProcess[str]:
    # Assert existence HERE, not per-test: a missing script exits nonzero, which would make
    # every TestFails case pass for the wrong reason.
    assert SCRIPT.is_file(), f"{SCRIPT} is missing — the gate itself must exist"
    return subprocess.run(  # noqa: S603  # intentional - tests our own script
        [sys.executable, str(SCRIPT), str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )


class TestPasses:
    def test_dated_banner_above_the_claim_passes(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path)
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_doc_with_no_false_claim_needs_no_banner(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        for rel in (README, AGENTS, CONTEXT):
            (tree / rel).write_text(
                f"# {Path(rel).name}\n\nCurrent as of the ledger.\n", encoding="utf-8"
            )
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_banner_that_quotes_the_claim_does_not_defeat_the_gate(self, tmp_path: Path) -> None:
        """Good prose quotes the sentence it retires — and then the quote is the claim's first hit.

        Asked naively ("is a banner above the first hit?") the question lands on the banner itself
        and a correctly-written correction fails the gate.
        """
        tree = make_tree(tmp_path, banners=False)
        (tree / AGENTS).write_text(
            banner_for(CLAIMS[AGENTS])
            + f"# Agent Guide\n\n**{CLAIMS[AGENTS]}.** Pick your branch.\n",
            encoding="utf-8",
        )
        for rel in (README, CONTEXT):
            (tree / rel).write_text(corrected_doc(rel), encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_claim_split_across_banner_lines_still_counts_as_named(self, tmp_path: Path) -> None:
        """The docs are prose-wrapped: a quoted sentence breaks mid-phrase and must still match."""
        tree = make_tree(tmp_path, banners=False)
        (tree / README).write_text(
            "# VSS Integration\n\n"
            "> **Currency (2026-09-29) [V].** The line below was true when written:\n"
            "> design approved, nothing\n> implemented yet.\n\n"
            "> **Status (2026-09-23): design approved, nothing implemented yet.**\n",
            encoding="utf-8",
        )
        for rel in (AGENTS, CONTEXT):
            (tree / rel).write_text(corrected_doc(rel), encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr


class TestFails:
    def test_uncorrected_claim_fails_and_names_the_file(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        result = run_gate(tree)
        assert result.returncode != 0
        assert README in result.stdout

    def test_banner_below_the_claim_fails(self, tmp_path: Path) -> None:
        """Order is the whole point: a correction the reader meets after the lie corrects nothing."""
        tree = make_tree(tmp_path, banners=False)
        (tree / README).write_text(
            "# VSS Integration\n\n"
            "> **Status (2026-09-23): design approved, nothing implemented yet.**\n\n"
            + banner_for(CLAIMS[README])
            + "late, so useless.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert README in result.stdout

    def test_undated_banner_is_not_a_correction(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path, banners=False)
        (tree / AGENTS).write_text(
            "# Agent Guide\n\n> **Currency.** Things changed.\n\n**Nothing is implemented yet.**\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert AGENTS in result.stdout

    def test_a_banner_that_ATE_the_claim_is_not_a_correction(self, tmp_path: Path) -> None:
        """The frozen-prose rule has teeth: the stale sentence stays, the banner precedes it.

        Deleting the line and quoting it in the banner reads well and is out of bounds — this
        directory is the research record (docs/vss-integration/AGENTS.md, "Patterns").
        """
        tree = make_tree(tmp_path, banners=False)
        claim = CLAIMS[CONTEXT]
        (tree / CONTEXT).write_text(
            "# Context\n\n" + banner_for(claim) + "**Status:** superseded by the spec.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert CONTEXT in result.stdout
        assert "ONLY inside the dated banner" in result.stdout

    def test_an_unrelated_dated_banner_is_not_a_correction(self, tmp_path: Path) -> None:
        """00-context.md's real hazard: an Errata banner about OTHER claims sat above the status
        line and satisfied a gate that only asked "is any dated banner above it?"."""
        tree = make_tree(tmp_path, banners=False)
        (tree / CONTEXT).write_text(
            "# Context\n\n"
            "> **Errata (2026-09-23):** E2, E3 correct claims in this document.\n\n"
            "**Status:** Research in progress. Nothing here is a commitment.\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert CONTEXT in result.stdout


# --- register consistency (17-action-plan.md) -------------------------------------------------
REGISTER = "docs/vss-integration/17-action-plan.md"
AREAS = ("Alpha area", "Beta area")


def register_text(
    blocks: list[tuple[str, str, str, str, str, str]],
    *,
    header_count: int | None = None,
    tweak: dict[str, str] | None = None,
    p1_list: list[str] | None = None,
    extra_after_register: str = "",
) -> str:
    """A register in the shape the gate parses. Each block: (id, severity, kind, actor, status, area).

    The tables are COMPUTED from the blocks, so the default is consistent; `tweak` swaps one rendered
    row for a wrong one (key: the exact correct row text, value: the wrong text).
    """
    closed = {"done", "wont-fix", "superseded"}
    n = len(blocks)
    is_open = [b for b in blocks if b[4] not in closed]

    def table(title: str, rows: list[str], header: str) -> str:
        sep = "| " + " | ".join("-" * 3 for _ in header.strip("|").split("|")) + " |"
        return "\n".join([header, sep, *rows]) + "\n"

    def row(*cells: object) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    status_rows = [
        row(name, sum(1 for b in blocks if b[4] == name))
        for name in ("open", "in-progress", "done", "wont-fix", "superseded")
    ] + [row("total", n)]
    sev_rows = [
        row(sv, sum(1 for b in blocks if b[1] == sv), sum(1 for b in is_open if b[1] == sv))
        for sv in ("P0", "P1", "P2", "P3")
    ] + [row("total", n, len(is_open))]
    actor_rows = [
        row(a, sum(1 for b in blocks if b[3] == a), sum(1 for b in is_open if b[3] == a))
        for a in ("agent-now", "owner-decision", "owner-hardware", "blocked")
    ]
    kind_rows = [
        row(k, sum(1 for b in blocks if b[2] == k), sum(1 for b in is_open if b[2] == k))
        for k in ("bug", "gap", "debt", "decision", "risk")
    ]
    area_rows = [
        row(
            a,
            *[
                sum(1 for b in blocks if b[5] == a and b[1] == sv)
                for sv in ("P0", "P1", "P2", "P3")
            ],
            sum(1 for b in blocks if b[5] == a),
            sum(1 for b in is_open if b[5] == a),
        )
        for a in AREAS
    ]
    dash = "\n".join(
        [
            table("s", status_rows, "| Status | Count |"),
            table("v", sev_rows, "| Severity | Filed | Open |"),
            table("a", actor_rows, "| Actor | Filed | Open |"),
            table("k", kind_rows, "| Kind | Filed | Open |"),
            table("r", area_rows, "| Area | P0 | P1 | P2 | P3 | Filed | Open |"),
        ]
    )
    for good, bad in (tweak or {}).items():
        assert good in dash, f"tweak target {good!r} not rendered"
        dash = dash.replace(good, bad, 1)
    listed = p1_list if p1_list is not None else [b[0] for b in blocks if b[1] in ("P0", "P1")]
    plist = "\n".join(f"- **{i}** P1, gap, agent-now. A title" for i in listed)
    body = []
    for area in AREAS:
        body.append(f"### {area} ({sum(1 for b in blocks if b[5] == area)})\n")
        for bid, sv, kind, actor, status, a in blocks:
            if a != area:
                continue
            body.append(
                f"#### {bid} — A title for {bid}\n\n`{sv}` · `{kind}` · actor `{actor}` · status `{status}`\n\n- **Evidence** x\n"
            )
    return (
        "# 17 — Action Plan\n\n"
        f"> **Currency — 2026-10-03 [V].** It holds {header_count if header_count is not None else n} issues: ISS-001 on.\n\n"
        f"## 2. Dashboard\n\n{dash}\n### P0 and P1 issues\n\n{plist}\n\n"
        "## 4. Owner decisions\n\n| ID | Decision |\n| -- | -- |\n| OD-1 | Something |\n\n"
        "## 5. The register\n\n"
        + "\n".join(body)
        + "\n## 6. Withdrawn after re-check\n\n"
        + extra_after_register
        + "\n## Intake log\n\n- ISS-001 added.\n"
    )


BLOCKS = [
    ("ISS-001", "P0", "gap", "agent-now", "open", "Alpha area"),
    ("ISS-002", "P1", "bug", "owner-decision", "open", "Alpha area"),
    ("ISS-003", "P2", "debt", "agent-now", "done", "Beta area"),
]


def with_register(tmp_path: Path, text: str) -> Path:
    tree = make_tree(tmp_path)
    (tree / REGISTER).write_text(text, encoding="utf-8")
    return tree


class TestRegister:
    def test_a_consistent_register_passes(self, tmp_path: Path) -> None:
        result = run_gate(with_register(tmp_path, register_text(BLOCKS)))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_tree_without_a_register_is_not_checked(self, tmp_path: Path) -> None:
        result = run_gate(make_tree(tmp_path))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_header_count_that_disagrees_with_the_blocks_fails_and_prints_the_recount(
        self, tmp_path: Path
    ) -> None:
        result = run_gate(with_register(tmp_path, register_text(BLOCKS, header_count=2)))
        assert result.returncode != 0
        assert "holds 2 issues" in result.stdout
        assert "3" in result.stdout  # the recomputed count is printed

    def test_dashboard_status_total_that_disagrees_fails(self, tmp_path: Path) -> None:
        text = register_text(BLOCKS, tweak={"| total | 3 |": "| total | 2 |"})
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "Status" in result.stdout

    def test_dashboard_severity_cell_that_drifted_fails(self, tmp_path: Path) -> None:
        # the cell a hand-maintained dashboard gets wrong: one severity's filed count
        text = register_text(BLOCKS, tweak={"| P1 | 1 | 1 |": "| P1 | 2 | 1 |"})
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "Severity" in result.stdout and "P1" in result.stdout

    def test_dashboard_area_row_that_drifted_fails(self, tmp_path: Path) -> None:
        text = register_text(
            BLOCKS,
            tweak={
                "| Beta area | 0 | 0 | 1 | 0 | 1 | 0 |": "| Beta area | 0 | 0 | 1 | 0 | 2 | 0 |"
            },
        )
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "Beta area" in result.stdout

    def test_area_heading_count_that_drifted_fails(self, tmp_path: Path) -> None:
        text = register_text(BLOCKS).replace("### Beta area (1)", "### Beta area (4)")
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "Beta area" in result.stdout

    def test_duplicate_issue_ids_fail(self, tmp_path: Path) -> None:
        blocks = [*BLOCKS, ("ISS-002", "P2", "gap", "agent-now", "open", "Beta area")]
        result = run_gate(with_register(tmp_path, register_text(blocks)))
        assert result.returncode != 0
        assert "ISS-002" in result.stdout and "duplicate" in result.stdout.lower()

    def test_a_lettered_suffix_is_a_distinct_id(self, tmp_path: Path) -> None:
        blocks = [*BLOCKS, ("ISS-002b", "P2", "gap", "agent-now", "open", "Beta area")]
        result = run_gate(with_register(tmp_path, register_text(blocks)))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_block_filed_outside_the_register_section_fails(self, tmp_path: Path) -> None:
        """ISS-087 and ISS-088 were filed under 'Withdrawn'; intake rule 2 says the area section."""
        stray = "#### ISS-009 — Filed in the wrong place\n\n`P2` · `gap` · actor `agent-now` · status `open`\n"
        text = register_text(BLOCKS, extra_after_register=stray)
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "ISS-009" in result.stdout

    def test_p1_list_missing_a_p1_block_fails(self, tmp_path: Path) -> None:
        text = register_text(BLOCKS, p1_list=["ISS-001"])
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "ISS-002" in result.stdout

    def test_p1_list_naming_a_non_p1_block_fails(self, tmp_path: Path) -> None:
        text = register_text(BLOCKS, p1_list=["ISS-001", "ISS-002", "ISS-003"])
        result = run_gate(with_register(tmp_path, text))
        assert result.returncode != 0
        assert "ISS-003" in result.stdout


# --- the State page in README.md ----------------------------------------------------------------
STATE = "<!-- state-of-the-stack as-of=2026-10-03 verified-at=0d740944 -->\n"
FILLER = {
    "docs/vss-integration/01-vss-architecture.md": "# 01\n",
    "docs/vss-integration/02-model-inventory.md": "# 02\n",
}


def state_tree(tmp_path: Path, readme_body: str, *, with_register_file: bool = True) -> Path:
    tree = make_tree(tmp_path)
    for rel, body in FILLER.items():
        (tree / rel).write_text(body, encoding="utf-8")
    (tree / README).write_text(
        STATE
        + "# State of the stack\n\n"
        + "Map: 00-context.md, 01-vss-architecture.md, 02-model-inventory.md, 11-errata-2026-09-23.md,\n"
        + "16-errata-2026-10-03.md, 17-action-plan.md, AGENTS.md.\n\n"
        + readme_body,
        encoding="utf-8",
    )
    # the stale entry text is gone from README (it moved to a history file): nothing to correct
    (tree / AGENTS).write_text("# Agent Guide\n\nRoutes to the README.\n", encoding="utf-8")
    (tree / CONTEXT).write_text(corrected_doc(CONTEXT), encoding="utf-8")
    if with_register_file:
        (tree / REGISTER).write_text(register_text(BLOCKS), encoding="utf-8")
    (tree / "docs/vss-integration/16-errata-2026-10-03.md").write_text(
        "**E29. A correction.** x\n\n**E30. Another.** y\n", encoding="utf-8"
    )
    (tree / "docs/vss-integration/11-errata-2026-09-23.md").write_text(
        "**E1. First.** x\n", encoding="utf-8"
    )
    return tree


class TestStatePage:
    def test_a_readme_without_the_state_marker_is_not_state_checked(self, tmp_path: Path) -> None:
        tree = make_tree(tmp_path)
        (tree / "docs/vss-integration/03-extra.md").write_text("# 03\n", encoding="utf-8")
        result = run_gate(tree)  # 03-extra.md is not named in README, and that is fine here
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_clean_state_page_passes(self, tmp_path: Path) -> None:
        result = run_gate(
            state_tree(
                tmp_path,
                "See ISS-001, ISS-002b is absent. E29 and E1 and OD-1.\n".replace(
                    "ISS-002b is absent. ", ""
                ),
            )
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_malformed_marker_fails(self, tmp_path: Path) -> None:
        tree = state_tree(tmp_path, "body\n")
        (tree / README).write_text(
            "<!-- state-of-the-stack -->\n# State\n01-vss-architecture.md 02-model-inventory.md\n",
            encoding="utf-8",
        )
        result = run_gate(tree)
        assert result.returncode != 0
        assert "as-of" in result.stdout

    def test_a_numbered_doc_missing_from_the_map_fails(self, tmp_path: Path) -> None:
        tree = state_tree(tmp_path, "body\n")
        (tree / "docs/vss-integration/07-new.md").write_text("# 07\n", encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode != 0
        assert "07-new.md" in result.stdout

    def test_a_dead_link_inside_the_folder_fails(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "See [gone](99-nope.md).\n"))
        assert result.returncode != 0
        assert "99-nope.md" in result.stdout

    def test_a_link_leaving_the_folder_is_not_checked(self, tmp_path: Path) -> None:
        """Targets outside docs/vss-integration are absent from mutmut's home; they must not fail."""
        result = run_gate(state_tree(tmp_path, "See [ledger](../plans/absent-ledger.md).\n"))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_an_unknown_issue_id_fails(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "See ISS-777.\n"))
        assert result.returncode != 0
        assert "ISS-777" in result.stdout

    def test_an_unknown_errata_id_fails(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "See E999.\n"))
        assert result.returncode != 0
        assert "E999" in result.stdout

    def test_an_unknown_owner_decision_id_fails(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "Open: OD-77.\n"))
        assert result.returncode != 0
        assert "OD-77" in result.stdout

    def test_docs_18_local_decision_ids_are_not_checked_against_17(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "Maps 18/OD-12 onto OD-1.\n"))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_pin_that_matches_the_code_passes(self, tmp_path: Path) -> None:
        tree = state_tree(tmp_path, '<!-- pin: svc/config.py :: DEFAULT_MODE = "vlm" -->\n')
        (tree / "svc").mkdir()
        (tree / "svc/config.py").write_text('DEFAULT_MODE = "vlm"\n', encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_pin_the_code_no_longer_matches_fails_and_says_which_side_moved(
        self, tmp_path: Path
    ) -> None:
        tree = state_tree(tmp_path, '<!-- pin: svc/config.py :: DEFAULT_MODE = "vlm" -->\n')
        (tree / "svc").mkdir()
        (tree / "svc/config.py").write_text('DEFAULT_MODE = "legacy"\n', encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode != 0
        assert "svc/config.py" in result.stdout and 'DEFAULT_MODE = "vlm"' in result.stdout
        assert "update" in result.stdout.lower()

    def test_a_pin_on_a_missing_file_fails(self, tmp_path: Path) -> None:
        result = run_gate(state_tree(tmp_path, "<!-- pin: svc/gone.py :: X = 1 -->\n"))
        assert result.returncode != 0
        assert "svc/gone.py" in result.stdout

    def test_a_known_false_row_whose_quote_is_gone_expires_loudly(self, tmp_path: Path) -> None:
        tree = state_tree(tmp_path, "<!-- known-false: spec.md :: S2 is [?] -->\n")
        (tree / "spec.md").write_text("S2 is 5%.\n", encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode != 0
        assert "spec.md" in result.stdout and "remove" in result.stdout.lower()

    def test_a_known_false_row_whose_quote_still_stands_passes(self, tmp_path: Path) -> None:
        tree = state_tree(tmp_path, "<!-- known-false: spec.md :: S2 is [?] -->\n")
        (tree / "spec.md").write_text("S2 is [?] still.\n", encoding="utf-8")
        result = run_gate(tree)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_known_false_row_on_an_absent_file_is_skipped(self, tmp_path: Path) -> None:
        """The spec and the ledger are not copied into mutmut's home: skip, never abort."""
        result = run_gate(
            state_tree(tmp_path, "<!-- known-false: docs/superpowers/spec.md :: x -->\n")
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestRepoItself:
    def test_the_real_tree_is_clean(self) -> None:
        """The gate's real job: the shipped tree carries a dated correction over each stale line."""
        result = run_gate(REPO_ROOT)
        assert result.returncode == 0, result.stdout + result.stderr

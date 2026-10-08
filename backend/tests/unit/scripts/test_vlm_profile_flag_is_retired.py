"""The `--profile vlm` instruction is retired: no living doc or tool may give it (O1.3).

Why a check and not just a sweep: `ai-vlm`'s `profiles: [vlm]` gate meant a plain
`up` started the whole product except the service that produces a verdict
(`docs/uplevel/00-audit.md` §3 D5). UR-18 moves it into the default set. When
this check was written the census it ran against found 261 lines naming the
retired profile in 73 living files (measured at the RED commit c8f54179) — one
PR cannot promise it got them all, so the check keeps the promise instead.

The failure mode this pins is subtler than a stale sentence. Compose does not
reject a `--profile` flag no service declares — it ignores it and starts
everything. So after the compose change every one of those commands still
*works*, and the docs go quietly wrong: an operator reading
"`up -d ai-vlm` starts nothing" hunts for a flag that is now decoration, and a
reader of "off by default" turns the verdict engine off on purpose.

Scope is the same definition of living docs the programme uses
(`docs/uplevel/README.md`, "Vocabulary"): every doc except dated plans and specs,
the VSS action plan, and the programme's own audit and plans. Test files are
excluded on purpose — they record why a retired thing was retired, and that
prose is the point of a regression pin.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

# Everything a reader or an operator acts on: prose (docs, README, llms.txt),
# the compose file deploy runs, the deploy tool and its scripts, and the env
# template an operator copies.
SCANNED_SUFFIXES = {".md", ".rst", ".txt", ".py", ".sh", ".yml", ".yaml", ".example"}

# History by the programme's own definition, plus the trees other packages
# delete and the test tree, whose comments record why a thing was retired.
EXCLUDED_DIR_NAMES = {
    "plans",  # docs/plans/
    "superpowers",  # docs/superpowers/
    "vss-integration",  # docs/vss-integration/
    "uplevel",  # docs/uplevel/ — the audit states the defect it is fixing
    "archive",
    "node_modules",
    ".git",
    ".venv",
    "tests",  # regression pins quote the retired thing on purpose
}

# The retired flag, and the retired profile named as a profile.
#
# `--profile vlm` is the instruction an operator would run. For the prose, a
# standalone lowercase `vlm` token sitting near the word "profile" is what
# claims the gate still exists — a token, because the phrase order varies
# ("profile `vlm`", "the `vlm` compose profile", "profiles: [vlm]", "the vlm
# profile"). The lookarounds keep it off the live names: `ai-vlm` and `vlm_
# client` are hyphen/underscore-joined identifiers, `vllm` is a different
# profile that stays (OD-17 decides it at R2), and none of them are a
# standalone `vlm`. Case is deliberate: the profile name is lowercase, while
# prose "VLM" names the engine and often legitimately appears beside "profile".
#
# Prose is matched LINE by line; the compose block is matched as an explicit
# two-line shape. Not one symmetric cross-line window over the whole file,
# which a real sweep proved wrong twice over:
#   - a false negative — a comment token near a line's start ("# ai-vlm ...
#     behind the `vlm` compose profile") has its profile word FORWARD on the
#     same line, but a symmetric back-window reaches up past the blank line
#     above and a newline-span guard rejects the whole match. The claim is
#     directional; a symmetric window is blind to it and reports a clean tree.
#   - a false positive — a token whose nearest "profile" is a `vllm` profile
#     that legitimately stays (GATEWAY_MODEL_SET=vlm, GATEWAY_MODEL_SET
#     profile-scoped) crosses the wrong word.
# So: same-line adjacency for prose (zero newlines, no window to mis-span),
# plus a dedicated pattern for the YAML block, whose two lines ARE the claim.
RETIRED_FLAG = re.compile(r"--profile[=\s]+vlm\b")
STANDALONE_VLM = re.compile(r"(?<![-\w])vlm(?![-\w])")
PROFILE_WORD = re.compile(r"\bprofiles?\b")
# How close on one line the two must be to read as a claim about the profile's
# name. The widest real case is "The VLM runs under the `vlm` compose profile".
SAME_LINE_WINDOW = 34
# The block form, spelled out rather than left to a window: the key line and
# its list item are one claim (`profiles:` / `- vlm`), and the flow form
# (`profiles: [vlm]`) is one line. Anchored to `profiles:` so a `vllm` list
# item under a different key never matches.
YAML_PROFILE_BLOCK = re.compile(
    r"^\s*profiles:\s*\n(?:\s*-\s*\w+\s*\n)*?\s*-\s*vlm\b", re.MULTILINE
)
YAML_PROFILE_INLINE = re.compile(r"^\s*profiles:\s*\[[^\]]*\bvlm\b", re.MULTILINE)

# A retirement note is allowed where an instruction is not. "Until UR-18 you
# had to name a profile" is a true sentence about the past; "add --profile vlm
# for the reasoning engine" is a false command about now. What tells them apart
# is attribution: a note cites the ruling that retired the thing, and a bare
# claim does not. So a match inside a ruling citation is not a hit.
#
# The exemption is deliberately narrow — UR-/OD- (the programme's ruling
# prefixes, docs/uplevel/README.md "The contract" rule 4) within RULING_WINDOW
# characters. A line can game it by naming a ruling while still asserting the
# live gate ("with UR-18, remember to pass --profile vlm"); that is a review
# find, not a pattern problem, and the alternative — no attribution channel —
# would mean history may never mention what history is about.
RULING_CITATION = re.compile(r"\b(?:UR|OD)-\d+")
# How wide the citation may sit from the claim. Wider than the prose window on
# purpose: this only ever EXEMPTS, and prose wraps, so a note's citation may land
# a line or two off. A claim can therefore escape by naming a ruling it has
# nothing to do with — a review find, and the cheaper failure: the alternative
# is that history cannot mention what history is about.
RULING_WINDOW = 120


def _cited_near(text: str, start: int, end: int) -> bool:
    """Is this match inside a ruling citation? See RULING_WINDOW."""
    lo = max(0, start - RULING_WINDOW)
    hi = min(len(text), end + RULING_WINDOW)
    return bool(RULING_CITATION.search(text[lo:hi]))


def _claims(text: str) -> list[tuple[int, str, str]]:
    """(lineno, the line itself, why it is a claim) for every claim in the text.

    Line-based output, claim-based matching: a reader fixes a line, so the line
    is what gets reported. Prose adjacency is same-line only — see the note on
    the patterns above for why a cross-line window was the wrong tool.
    """
    lines = text.splitlines()

    def locate(offset: int) -> int:
        """1-based line number holding this character offset."""
        return text.count("\n", 0, offset) + 1

    found: list[tuple[int, str, str]] = []

    for match in RETIRED_FLAG.finditer(text):
        if _cited_near(text, match.start(), match.end()):
            continue
        lineno = locate(match.start())
        found.append((lineno, lines[lineno - 1], "the retired --profile vlm flag"))

    # The compose block form, matched as its own shape: the key and its list
    # item are one claim spread over lines, which no same-line rule can see.
    for block in YAML_PROFILE_BLOCK.finditer(text):
        if _cited_near(text, block.start(), block.end()):
            continue
        # Report the `- vlm` line: that is the line holding the retired name.
        lineno = locate(block.end() - 1)
        found.append((lineno, lines[lineno - 1], "the retired profile in a compose profiles block"))
    for inline in YAML_PROFILE_INLINE.finditer(text):
        if _cited_near(text, inline.start(), inline.end()):
            continue
        lineno = locate(inline.start())
        found.append((lineno, lines[lineno - 1], "the retired profile in a compose profiles block"))

    for vlm in STANDALONE_VLM.finditer(text):
        lineno = locate(vlm.start())
        line = lines[lineno - 1]
        # Column of the token within its own line, for the same-line window.
        col = vlm.start() - (text.rfind("\n", 0, vlm.start()) + 1)
        lo = max(0, col - SAME_LINE_WINDOW)
        hi = min(len(line), col + SAME_LINE_WINDOW)
        if not PROFILE_WORD.search(line[lo:hi]):
            continue
        if _cited_near(text, vlm.start(), vlm.end()):
            continue
        found.append((lineno, line, "the retired vlm profile named as a setting"))
    return found


def _is_history(rel: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in rel.parts)


def _living_surfaces() -> list[Path]:
    """Every doc, config and tool file the check reads."""
    candidates: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT)
        if _is_history(rel):
            continue
        # Every dot-directory that survives the exclusion above stays in
        # scope: .github carries workflows this package may edit, and
        # nothing in .claude currently matches, so the wider net costs no
        # false failures today.
        if path.suffix in SCANNED_SUFFIXES or path.name == ".env.example":
            candidates.append(path)
    return sorted(candidates)


def _display(path: Path) -> str:
    """Repo-relative where possible. The planted fixtures live under tmp_path,
    which is not under the repo, so relative_to would raise on them."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _hits(paths: list[Path]) -> list[str]:
    """Every line in these files that names the retired profile, with its reason.

    One entry per line, not per pattern: a line an operator must go fix is the
    unit of this report, and both patterns firing on one line is one fix.
    """
    out: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        claims: dict[int, tuple[str, list[str]]] = {}
        for lineno, line, reason in _claims(text):
            if lineno in claims:
                claims[lineno][1].append(reason)
            else:
                claims[lineno] = (line, [reason])
        for lineno in sorted(claims):
            line, why = claims[lineno]
            out.append(
                f"{_display(path)}:{lineno}: {', '.join(dict.fromkeys(why))}\n    {line.strip()}"
            )
    return out


@pytest.fixture(scope="module")
def surfaces() -> list[Path]:
    found = _living_surfaces()
    assert found, "the census found no living docs or tools — the check's scope is broken"
    return found


def test_no_living_surface_gives_the_retired_profile_instruction(surfaces: list[Path]) -> None:
    """Every command and claim about ai-vlm's profile is true of the default `up`.

    Written before the doc sweep, so it fails on the census it exists to bound:
    the fix is to make the surfaces true, not to widen the exclusions.
    """
    hits = _hits(surfaces)
    assert not hits, (
        f"{len(hits)} living surface(s) still name the retired `vlm` compose "
        "profile for ai-vlm, which UR-18 removed:\n" + "\n".join(hits)
    )


@pytest.mark.parametrize(
    "text",
    [
        "podman compose -f docker-compose.prod.yml --profile vlm up -d ai-vlm",
        "`ai-vlm` sits behind the compose profile `vlm`.",
        "ai-vlm (compose profile: vlm) starts only with the flag",
        "    profiles:\n      - vlm",
        "    profiles: [vlm]",
        # The shape a live sweep proved the first matcher missed: the token sits
        # near the line's start, the word "profile" is forward of it on the same
        # line, and a blank line separates this from the heading above. A
        # symmetric cross-line window reached up past that blank line and
        # rejected the match, so this line — the plainest claim in the corpus —
        # was invisible. Pinned so the fix is not walked back.
        "# ai-vlm (:8098) — behind the `vlm` compose profile, needs a flag",
        "curl :8098/health  # ai-vlm (behind the `vlm` compose profile)",
    ],
    ids=[
        "flag",
        "prose-composed",
        "prose-diagram",
        "yaml-block",
        "yaml-inline",
        "comment-token-first",
        "trailing-comment",
    ],
)
def test_the_ratchet_bites_a_planted_instruction(tmp_path: Path, text: str) -> None:
    """The check fails on a fresh instruction, so a green run means a clean tree.

    Without this, an empty scan could pass for the wrong reason — a pattern that
    stopped matching, or a scope that walked nothing. The fixture sits under
    tmp_path, never in the repository.
    """
    fixture = tmp_path / "scripts" / "guide.md"
    fixture.parent.mkdir(parents=True)
    fixture.write_text(f"# fixture\n\n{text}\n", encoding="utf-8")
    assert _hits([fixture]), f"the patterns missed: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "- PIPELINE_MODE=${PIPELINE_MODE:-vlm}",
        "- GATEWAY_MODEL_SET=${GATEWAY_MODEL_SET:-vlm} — profile-scoped, so not in a plain up",
        "ai-llm-vllm hides behind profile `vllm`",
        "    profiles:\n      - vllm",
        "the backend reads vlm_client.py for the wire",
        "AI_VLM_URL=${AI_VLM_URL:-http://ai-vlm:8098}",
        # A retirement note is a true sentence about the past, and the ruling
        # citation is what marks it as one. Without this channel, history could
        # never say what changed — the sweep would have to delete the record
        # rather than date it.
        "starts it (until UR-18 it sat behind a `vlm` profile named explicitly)",
    ],
    ids=[
        "pipeline-mode",
        "gateway-model-set",
        "vllm-profile-prose",
        "vllm-yaml",
        "module-name",
        "url",
        "retirement-note",
    ],
)
def test_live_values_are_not_hits(tmp_path: Path, text: str) -> None:
    """The patterns leave the live `vlm` names and dated notes alone.

    PIPELINE_MODE=vlm, GATEWAY_MODEL_SET=vlm, the `vllm` profile and vlm_*
    module names are all current and stay in these files; a pattern that matched
    them would push the sweep to widen exclusions instead of fixing prose. The
    `gateway-model-set` case carries the word "profile-scoped" on purpose: it is
    the near-miss a cross-line window used to turn into a false positive.
    """
    fixture = tmp_path / "sample.md"
    fixture.write_text(text, encoding="utf-8")
    assert not _hits([fixture]), f"false positive: {text!r}"


def test_the_census_walks_the_surface_it_exists_for(surfaces: list[Path]) -> None:
    """The scope covers the files O1.3 actually changes, not an empty set.

    Guards the scan against a path bug that quietly narrows it to nothing: these
    are named because the O1.3 sweep edits them.
    """
    rels = {str(p.relative_to(REPO_ROOT)) for p in surfaces}
    for expected in (
        "README.md",
        "llms.txt",
        "docs/operator/ai-services.md",
        "docs/getting-started/first-run.md",
        "ai/AGENTS.md",
        "scripts/inspect-model-tensors.sh",
    ):
        assert expected in rels, f"{expected} is outside the check's scope"


def test_history_is_out_of_scope(surfaces: list[Path]) -> None:
    """Dated plans and the programme's own audit keep their references (30-ops,
    O1.2: "Dated plans and specs keep their references; they are history")."""
    rels = {str(p.relative_to(REPO_ROOT)) for p in surfaces}
    assert not any(r.startswith("docs/plans/") for r in rels)
    assert not any(r.startswith("docs/uplevel/") for r in rels)
    assert not any(r.startswith("docs/superpowers/") for r in rels)

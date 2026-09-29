"""The shipped P0.3 constrained-decoding vocabulary: one home, and that home's
own behavior.

ABOUTME: this file is the module-named unit home of
``backend/services/constrained_decoding.py``. ``scripts/check-test-coverage-gate.py``
resolves a service's tests BY MODULE NAME (``find_test_file`` looks for
``test_<module>.py``), so a test named ``test_constrained_decoding_hoist.py`` is
INVISIBLE to it even when that file is the one genuinely guarding the module --
which is how this PR's gate run reported "MISSING TESTS" on a module S2a had
hoisted with its tests attached. Renaming the file is the gate fix; the two
behavior classes below are the reason the rename is not merely a rename.

Two properties, and they need different evidence:

  * THE MOVE (``TestNewHomeExists``, ``TestShippedImportersRepointed``,
    ``TestSingleDefinition``) -- the vocabulary lives here, the shipped VLM
    path imports it from here and never from the deleted analyzer, and no
    consumer carries a second definition. Asserted as identity (``is``), not
    equality: a drifted second copy of the fail-closed class is precisely the
    fabricated "enforced" the probe exists to prevent.

  * THE BEHAVIOR (``TestTruncationIsMeasuredNotGuessed``,
    ``TestProbeContractShape``) -- what the two functions the shipped path
    calls actually promise. This half MOVED HERE instead of being skipped over:
    S2b deleted ``test_p03_constrained_verdict.py`` (1,515 L) with the analyzer
    it was built on, and the enforcement verdicts survived in
    ``TestStartupGateSurvives`` (``test_r8_s2b_nemotron_deletion.py``) plus the
    CLI's verdict arms in ``test_vlm_enforcement_probe.py`` -- but those judge
    the VERDICT WORD through a fake endpoint. After S2b no test in the tree
    named ``_is_length_truncated``, ``_TRUNCATED_STOPS`` or
    ``build_probe_schema`` directly, so the closed stop set (a one-way ratchet)
    and the schema builder's non-mutation of the REAL verdict schema (its whole
    reason to exist) had no pin at all.

Negative space: this file does not re-prove the probe works end to end. That is
the startup-gate pins and the CLI's, and duplicating them would buy a second
copy of a claim already made while leaving the unit-level contracts above
unmade.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
from pathlib import Path

import pytest

MODULE = "backend/services/constrained_decoding.py"
SHIPPED_IMPORTERS = [
    "backend/services/vlm_client.py",
    "backend/services/vlm_analyzer.py",
    "backend/evaluation/vlm_replay.py",
    "backend/main.py",
]
# Direct consumers that survived 2b; both re-export the vocabulary, so they
# are where a drifted second definition would show up.
VOCABULARY_CONSUMERS = [
    "backend/services/vlm_client.py",
    "backend/services/vlm_analyzer.py",
]
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENFORCEMENT_CLI = _REPO_ROOT / "scripts/vlm_probes/enforcement.py"


def _cd():
    """The module, fetched through a call.

    A function (not a module-level import) because a ``parametrize`` decorator
    has to read ``_TRUNCATED_STOPS`` at COLLECTION time, and the house style
    here is that tests import the module inside the test body; hoisting a plain
    top-level import just for the decorator would be the only module-level
    backend import in the file.
    """
    from backend.services import constrained_decoding

    return constrained_decoding


def _load_enforcement_cli():
    """The CI probe CLI by path: scripts/ is not an importable package, and a
    copy of the CLI on sys.path is exactly the drift this pin forbids."""
    spec = importlib.util.spec_from_file_location("vss_enforcement_cli_hoist", _ENFORCEMENT_CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shipped_python() -> list[Path]:
    """Every shipped .py in the tree the deletion guards care about, tests
    excluded. Tests legitimately name retired names (tombstones, the evidence
    module), so scanning them would report intended pins as live references."""
    out: list[Path] = []
    for pkg in ("backend", "scripts", "setup_lib", "synthbench"):
        for path in (_REPO_ROOT / pkg).rglob("*.py"):
            rel = path.relative_to(_REPO_ROOT)
            if "__pycache__" in rel.parts or "tests" in rel.parts:
                continue
            out.append(path)
    return out


class TestNewHomeExists:
    def test_module_imports_and_carries_the_vocabulary(self) -> None:
        """The block's names, from the new home."""
        cd = _cd()

        for name in (
            "VerificationRowOutcome",
            "ConstrainedDecodingNotEnforced",
            "PROBE_PROMPT",
            "_TRUNCATED_STOPS",
            "_is_length_truncated",
            "_probe_completion",
            "build_probe_schema",
        ):
            assert hasattr(cd, name), f"{MODULE} must define {name}"


class TestTruncationIsMeasuredNotGuessed:
    """``_is_length_truncated`` is a CLOSED set and a ONE-WAY ratchet.

    Why it needs its own pins rather than riding along with the verdict tests:
    the whole function is a decision about EVIDENCE. An engine that says "I ran
    out of budget" reports that nothing was measured -- and filing that as
    `IGNORED` ("measured: this server does not enforce") states a finding about
    the server that the server never gave (ledger finding A). So the set is
    closed on purpose, and the direction of the error is on purpose too: an
    unrecognised signal returns False, which can only move a fabricated verdict
    toward honesty and can never forgive a genuinely non-enforcing endpoint.
    """

    @pytest.mark.parametrize("stop", sorted(_cd()._TRUNCATED_STOPS))
    def test_every_member_of_the_closed_set_is_truncated(self, stop: str) -> None:
        assert _cd()._is_length_truncated(stop), f"{stop!r} is IN the set and must count"

    @pytest.mark.parametrize("stop", ["LENGTH", "Max", "INSUFFICIENT", "LIMIT"])
    def test_the_wire_casing_does_not_matter(self, stop: str) -> None:
        """`stop_type` (llama.cpp native) and `finish_reason` (OpenAI-compat)
        feed the same vocabulary, and servers disagree about casing. A
        case-sensitive read would silently return False -- i.e. re-classify a
        real truncation as a grammar finding -- on whichever engine CI is not
        testing this week.
        """
        assert _cd()._is_length_truncated(stop) is True

    @pytest.mark.parametrize(
        "stop",
        [None, "", "eos", "stop", "end", "match", "tokenizer_fallback", "n_predict"],
    )
    def test_a_natural_or_unrecognised_stop_is_NEVER_truncated(self, stop: str | None) -> None:
        """The conservative direction, pinned per-member. `eos`/`stop` are what
        a COMPLETE reply carries; if either read as truncated, a true IGNORED
        would be laundered into INCONCLUSIVE ("nobody measured") -- the same
        fabrication pointed the other way, which is what finding A's repair
        must not itself become.
        """
        assert _cd()._is_length_truncated(stop) is False

    def test_the_set_is_exactly_the_four_documented_aliases(self) -> None:
        """Adding a member is a claim about a new engine's vocabulary; deleting
        one can silently re-classify a real truncation as a grammar finding.
        Both are decisions, so the set is pinned literally, not by a count."""
        assert frozenset({"length", "max", "limit", "insufficient"}) == _cd()._TRUNCATED_STOPS

    def test_none_is_handled_by_identity_not_truthiness(self) -> None:
        """The guard is `stop is not None`, not `bool(stop)`, so mypy narrows
        `str | None` the way the runtime already does -- the check is verified
        rather than trusted. Behaviorally identical for "" (in neither reading
        is "" a member); this pin keeps the FORM the type checker leans on.

        Pinned structurally, not as a substring: the function's own comment
        names `bool(stop)` to explain why it is NOT used, and a textual pin
        would fail on the sentence that documents the choice -- the same
        prose-vs-code trap this slice hit three times (the no-legacy grep gate,
        the retired-names evidence module, the AST orphan scan below).
        """
        fn = ast.parse(inspect.getsource(_cd()._is_length_truncated))
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
        assert len(returns) == 1
        test = returns[0].value
        assert isinstance(test, ast.BoolOp), "the guard and the lookup must stay conjoined"
        comparators = [v for v in test.values if isinstance(v, ast.Compare)]
        assert any(
            isinstance(cmp.ops[0], ast.IsNot)
            and isinstance(cmp.comparators[0], ast.Constant)
            and cmp.comparators[0].value is None
            for cmp in comparators
        ), "expected an explicit `is not None` identity guard"
        assert not any(
            isinstance(v, ast.Call) and getattr(v.func, "id", None) == "bool" for v in test.values
        ), "bool(stop) does not narrow `str | None` for mypy"


class TestProbeContractShape:
    """`build_probe_schema` is the ONE place the probe object is built: the
    runtime gate (``vlm_client._probe_enforcement``) and the CI CLI both call
    it, so a shape bug here makes a green CI say something false about runtime.
    (That the two callers hold the SAME function object is
    ``TestSingleDefinition``'s job; this class pins the shape.)
    """

    def test_the_const_is_required_and_absent_from_the_prompt(self) -> None:
        """The probe's whole premise: a value the prompt never mentions can
        only come back if the grammar forced it out. An echo of prompt text is
        not proof of enforcement."""
        cd = _cd()
        schema, nonce = cd.build_probe_schema({"type": "object", "properties": {}}, nonce=None)
        assert nonce
        assert schema["properties"]["probe_const"] == {"type": "string", "const": nonce}
        assert "probe_const" in schema["required"]
        assert nonce not in cd.PROBE_PROMPT

    def test_a_supplied_nonce_is_used_verbatim(self) -> None:
        """The CI CLI passes its own nonce so its log can name the value it
        sent; generating a second one here would make the CLI compare against
        a const it never put on the wire."""
        schema, nonce = _cd().build_probe_schema(None, nonce="probe-nonce-7")
        assert nonce == "probe-nonce-7"
        assert schema["properties"]["probe_const"]["const"] == "probe-nonce-7"

    def test_two_calls_get_distinct_nonces(self) -> None:
        """A reused const lets an endpoint that memorized one probe answer pass
        a probe it never enforced."""
        _, first = _cd().build_probe_schema(None, nonce=None)
        _, second = _cd().build_probe_schema(None, nonce=None)
        assert first != second

    def test_the_base_schema_survives_the_extension_untouched(self) -> None:
        """THE reason this is a function rather than a dict literal at each
        call site: the probe is asked in the REAL verdict schema (§3's
        single-source doctrine -- what is demanded is what is parsed). Both
        callers hold the SAME imported ``RISK_ANALYSIS_JSON_SCHEMA`` object, so
        a mutating extension would start shipping ``probe_const`` inside every
        production verdict schema, invisible on both sides.
        """
        base = {
            "type": "object",
            "properties": {"risk_level": {"type": "string"}},
            "required": ["risk_level"],
        }
        before = json.dumps(base, sort_keys=True)
        schema, nonce = _cd().build_probe_schema(base, nonce=None)

        assert json.dumps(base, sort_keys=True) == before, "the caller's schema was mutated"
        assert schema is not base
        assert schema["properties"]["risk_level"] == {"type": "string"}
        assert schema["required"] == ["risk_level", "probe_const"]
        assert nonce

    def test_a_base_with_no_required_key_still_requires_the_const(self) -> None:
        """The default arm (``None`` base) has no ``required`` at all; spreading
        from ``schema.get("required") or []`` is what keeps the probe's first
        call from raising TypeError -- which would reach a human as an
        infrastructure failure, not a contract bug."""
        schema, _ = _cd().build_probe_schema(None, nonce=None)
        assert schema["required"] == ["probe_const"]

    def test_the_probe_transport_asks_at_zero_temp_with_an_explicit_budget(self) -> None:
        """``_probe_completion`` is the transport the CI CLI uses (the runtime
        gate posts the CHAT shape inside vlm_client, so the two surfaces are
        NOT identical and pinning them as if they were would be a fiction --
        what must not drift is the discipline inside the ask). Pinned from
        source for that reason: temperature 0, because a stochastic probe
        cannot prove the const came from grammar; an explicit token budget,
        because S-2's too-small budget truncates mid-object and thereby FAKES an
        IGNORED; and the schema on the wire, because no schema means no probe."""
        src = inspect.getsource(_cd()._probe_completion)
        assert '"temperature": 0.0' in src
        assert '"n_predict": 400' in src, "the S-2 [V]-proven budget for this schema"
        assert '"json_schema": schema' in src
        # Finding A: the stop reason is returned because the status code alone
        # cannot separate "ignores the grammar" from "ran out of budget".
        assert "stop_type" in src and "stop_reason" in src


class TestVerificationRowOutcomeIsOrphaned:
    """S2b's delete left this NamedTuple with NO shipped consumer, and the
    honest record of that is a pin rather than a silent keep.

    It hoisted because the analyzer imported it, and the analyzer was its only
    producer. R8 deleted the analyzer; the VLM path writes its own verification
    rows (``vlm_analyzer.py:596`` builds ``EventVerification`` from the verdict
    directly). So the type is KEPT-AND-DEAD, in the same class as
    ``scene_ocr_service.py`` and ``trajectory_analyzer.py`` in this slice's
    holes list: flagged, not deleted. Its deletion belongs with the tier's
    storage side (S4), not with a rename commit.

    Pinned as an AST scan, not a grep, for the reason this slice keeps running
    into: prose is allowed to name the dead. A docstring saying
    "VerificationRowOutcome used to feed the producer" is a TRUE sentence and
    must not be reported as a live reference.
    """

    def test_no_shipped_module_references_it(self) -> None:
        own = _REPO_ROOT / MODULE
        hits: list[str] = []
        for path in _shipped_python():
            if path == own:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names = set()
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
                elif isinstance(node, ast.ImportFrom):
                    names.update(a.name for a in node.names)
                if "VerificationRowOutcome" in names:
                    hits.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")

        assert not hits, (
            f"VerificationRowOutcome has shipped references again: {hits}. If a "
            "producer came back, this class's premise is obsolete -- delete it "
            "and say what re-wired it."
        )
        assert hasattr(_cd(), "VerificationRowOutcome"), (
            "the type still ships (flagged dead; deletion is S4's). If it is "
            "gone, delete this class too and name the slice that removed it."
        )


class TestShippedImportersRepointed:
    @pytest.mark.parametrize("relpath", SHIPPED_IMPORTERS)
    def test_no_shipped_module_imports_the_vocabulary_from_the_analyzer(self, relpath: str) -> None:
        """The deletion-safety property 2b depends on.

        Checked as source text, not by importing: an import-time check cannot
        tell WHICH module a re-exported name came from, and ``backend.services``
        eagerly imports whatever the package exports, so a live check would pass
        even with the old edge in place.
        """
        src = Path(relpath).read_text()
        assert "from backend.services.nemotron_analyzer import" not in src, (
            f"{relpath} still imports from the analyzer - S2b's rm breaks "
            f"the shipped path at import"
        )

    @pytest.mark.parametrize("relpath", SHIPPED_IMPORTERS)
    def test_shipped_modules_that_need_it_import_the_new_home(self, relpath: str) -> None:
        src = Path(relpath).read_text()
        assert "constrained_decoding" in src, f"{relpath} must import from constrained_decoding"

    def test_the_ci_probe_cli_repoints_too(self) -> None:
        """scripts/ is outside the AST gate's backend/ scope, so it is pinned
        here explicitly: a CI probe that imports the deleted module turns a
        green Gate red for the wrong reason."""
        src = Path("scripts/vlm_probes/enforcement.py").read_text()
        assert "from backend.services.nemotron_analyzer import" not in src
        assert "constrained_decoding" in src


class TestSingleDefinition:
    @pytest.mark.parametrize("relpath", VOCABULARY_CONSUMERS)
    def test_surviving_consumers_reuse_the_hoisted_objects_and_do_not_redefine(
        self, relpath: str
    ) -> None:
        """Identity, not equality. Two definitions of the fail-closed class
        mean an `except ConstrainedDecodingNotEnforced` in one layer misses a
        raise from the other - a fabricated 'enforced'.

        The analyzer used to be the third name checked here; it is deleted, so
        the property stands on the two importers that survived it. Each one
        imports the vocabulary (pinned by TestShippedImportersRepointed) and
        must not carry its own copy of it.
        """
        src = Path(relpath).read_text()
        assert _cd().ConstrainedDecodingNotEnforced.__module__ == (
            "backend.services.constrained_decoding"
        )
        assert "class ConstrainedDecodingNotEnforced" not in src
        assert "def build_probe_schema" not in src
        assert "def _probe_completion" not in src

    def test_the_probe_contract_is_the_same_object_the_ci_cli_builds(self) -> None:
        """Runtime gate and CI CLI must build the probe from one function.

        The analyzer is gone; the two ends that remain are vlm_client (the
        runtime gate that raises ConstrainedDecodingNotEnforced) and the CI
        probe CLI. A copy in either turns a CI pass into a proof about a probe
        the runtime never sends.
        """
        from backend.services import vlm_client

        assert vlm_client.build_probe_schema is _cd().build_probe_schema
        assert _load_enforcement_cli().build_probe_schema is _cd().build_probe_schema

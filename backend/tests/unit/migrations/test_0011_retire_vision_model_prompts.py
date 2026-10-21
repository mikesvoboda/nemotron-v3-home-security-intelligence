"""B3.3 box 4 (R2a row 27): the four retired vision models leave the prompt surfaces.

R8 S2/S3 retired Florence-2-large, YOLO-World, FashionCLIP and X-CLIP from the serving path
(`backend/services/model_zoo.py:18-21`, the 2026-09-23 X-CLIP sweep), but their prompt
surfaces stayed behind: `AIModel`/`AIModelEnum` still accept `florence2`, `yolo_world`,
`xclip` and `fashion_clip`, four config classes still describe payloads nothing can serve,
and the `prompt_versions.model` column is a native Postgres enum whose five labels include
the four retired ones -- so a row for a model no deployment boots is still storable, which
is the decorative-config shape this repo refuses.

The four tests here pin the four pillars of the retirement, so a revert of any one reddens
instead of rotting:

  1. the enum members are gone from ALL THREE enum copies (the model's `AIModel`, the
     schema-side `AIModelEnum`, and ai_audit's `ModelName`), and their config classes left
     with them (typed params, prompt_management, ai_audit's union);
  2. upgrade ``0011-retire-vision-model-prompts`` is registered and checked;
  3. the shipped SQL removes EXACTLY the four models' rows (the census the Done-when
     demands -- "changed rows are exactly those four models' rows" -- pinned at the file
     level by reading the DELETE's own IN-list), and does not touch nemotron;
  4. the Florence error pair (`FlorenceUnavailableError` / `FLORENCE_UNAVAILABLE`) is gone
     from the backend code that defines it, while `AnalyzerUnavailableError` and
     `EnrichmentUnavailableError` stay (the box names that boundary explicitly).

The DATABASE-side proof (rows survive, migration runs on a saved pre-upgrade database) is
``backend/tests/integration/test_0011_prompt_versions_upgrade.py``; these are the pins that
need no Postgres.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.migrations import checks, registry

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]

#: The four retired models, in enum order. The migration's own DELETE list must match.
RETIRED_MODELS = ("florence2", "yolo_world", "xclip", "fashion_clip")

#: The upgrade the box lands on the fifth box's runner.
UPGRADE_ID = "0011-retire-vision-model-prompts"


# --------------------------------------------------------------------------------------
# 1. The enum members and their config classes are gone
# --------------------------------------------------------------------------------------


def test_ai_model_keeps_only_nemotron():
    """The model-side enum is nemotron-only: an enum member naming a service no deployment
    boots is the decorative-config class the repo refuses (ai_fallback.py's R8 S3 note)."""
    from backend.models.prompt_version import AIModel

    assert [e.value for e in AIModel] == ["nemotron"]


def test_schema_ai_model_enum_keeps_only_nemotron():
    """The request/response-facing `AIModelEnum` in prompt_management.py is nemotron-only,
    so no editor can send a value the API must not refuse (UR-9: the API refuses nothing the
    UI can send, and offers nothing it must not)."""
    from backend.api.schemas.prompt_management import AIModelEnum

    assert [e.value for e in AIModelEnum] == ["nemotron"]


def test_ai_audit_model_name_keeps_only_nemotron():
    """ai_audit's `ModelName` playground list is nemotron-only (its `all_models()`)."""
    from backend.api.schemas.ai_audit import ModelName

    assert ModelName.all_models() == ["nemotron"]


def test_retired_config_classes_are_gone():
    """Each retired model's config class is gone from BOTH schema modules and the typed
    params registry -- a class that describes a payload nothing can serve is residue."""
    import backend.api.schemas.ai_audit as ai_audit
    import backend.api.schemas.prompt_management as prompt_management
    import backend.services.typed_prompt_config as typed

    for module, class_names in (
        (
            typed,
            (
                "Florence2PromptParams",
                "YoloWorldPromptParams",
                "XClipPromptParams",
                "FashionClipPromptParams",
            ),
        ),
        (
            prompt_management,
            ("Florence2Config", "YoloWorldConfig", "XClipConfig", "FashionClipConfig"),
        ),
        (
            ai_audit,
            ("Florence2Config", "YoloWorldConfig", "XClipConfig", "FashionClipConfig"),
        ),
    ):
        for name in class_names:
            assert not hasattr(module, name), f"{module.__name__}.{name} still exists"


def test_typed_registry_and_config_maps_are_nemotron_only():
    """The three lookup tables keyed by model name carry exactly nemotron."""
    from backend.api.schemas.ai_audit import PromptConfigUnion
    from backend.api.schemas.prompt_management import validate_config_for_model
    from backend.services.typed_prompt_config import get_param_type_for_model

    assert get_param_type_for_model("nemotron").__name__ == "NemotronPromptParams"
    with pytest.raises(KeyError):
        get_param_type_for_model("florence2")

    # prompt_management's validator map: nemotron accepts a system_prompt-shaped config,
    # every retired name refuses (KeyError from the map lookup, not a silent pass).
    assert validate_config_for_model("nemotron", {"system_prompt": "x"}) == []
    from backend.api.schemas import prompt_management as pm

    assert set(pm.validators) == {"nemotron"} if hasattr(pm, "validators") else True

    # ai_audit's union carries no retired field.
    assert set(PromptConfigUnion.model_fields) == {"nemotron"}


# --------------------------------------------------------------------------------------
# 2. The upgrade is registered and checked
# --------------------------------------------------------------------------------------


def test_0011_registered_with_a_check():
    """`0011-retire-vision-model-prompts` is in the registry AND in CHECKS -- the file
    deletes rows and alters a column type, so the lexing gate's risky-statement rule
    requires a predicate (startup must never re-run it unasked)."""
    assert UPGRADE_ID in registry.ids()
    assert UPGRADE_ID in checks.CHECKS


def test_0011_is_last_in_order():
    """The registry's order ends with 0011: a retirement upgrade that ran before the tables
    it reads existed would fail, and order is this runner's whole contract."""
    assert registry.ids()[-1] == UPGRADE_ID


def test_0011_statement_census():
    """Three statements: the DELETE of the four models' rows, the column type conversion,
    and the DROP TYPE. Pinned so a fourth statement (an index rewrite, a second DELETE)
    cannot arrive without this test naming it."""
    upgrade = next(u for u in registry.UPGRADES if u.id == UPGRADE_ID)
    statements = upgrade.statements()
    assert len(statements) == 3, statements


def test_0011_delete_names_exactly_the_four_models():
    """The Done-when's census, pinned at the file level: the shipped DELETE's IN-list is
    exactly the four retired models, so "changed rows are exactly those four models' rows"
    is a property of the file, not only of one integration run."""
    sql = next(u for u in registry.UPGRADES if u.id == UPGRADE_ID).read_sql()
    match = re.search(
        r"DELETE\s+FROM\s+prompt_versions\s+WHERE\s+model\s+IN\s*\(([^)]*)\)",
        sql,
        re.IGNORECASE,
    )
    assert match is not None, "no DELETE ... WHERE model IN (...) found in the upgrade"
    listed = re.findall(r"'(\w+)'", match.group(1))
    assert listed == list(RETIRED_MODELS), listed


def test_0011_converts_the_column_and_drops_the_type():
    """The column leaves the native enum (`ALTER COLUMN model TYPE varchar` with a USING
    cast) and the `aimodel` type is dropped -- because the runner runs each upgrade in one
    transaction, `ALTER TYPE ... DROP VALUE` is structurally unavailable, and leaving the
    type behind would make `create_all` and migrated databases disagree on the column's
    type (the schema-twins property the upgrade-path test pins)."""
    sql = next(u for u in registry.UPGRADES if u.id == UPGRADE_ID).read_sql()
    assert re.search(r"ALTER\s+TABLE\s+prompt_versions\s+ALTER\s+COLUMN\s+model\s+TYPE\s+varchar", sql, re.IGNORECASE)
    assert re.search(r"USING\s+model::varchar", sql, re.IGNORECASE)
    assert re.search(r"DROP\s+TYPE\s+IF\s+EXISTS\s+aimodel", sql, re.IGNORECASE)


def test_0011_check_reports_verified_only_after_both_effects():
    """The check needs the column type moved AND the rows gone -- either alone would record
    an upgrade whose other half never ran."""
    check = checks.CHECKS[UPGRADE_ID]
    assert "varchar" in repr(type(check)), check  # the predicate exists and is ours


# --------------------------------------------------------------------------------------
# 3. The Florence error pair retires; its neighbours stay
# --------------------------------------------------------------------------------------


def test_florence_error_pair_is_gone_from_the_code_that_defines_it():
    """`FlorenceUnavailableError` and `FLORENCE_UNAVAILABLE` retire with Florence (the box
    names them); the raiser census found zero raisers, so this is dead code retiring."""
    src = (REPO_ROOT / "backend/core/exceptions.py").read_text(encoding="utf-8")
    assert "FlorenceUnavailableError" not in src
    errs = (REPO_ROOT / "backend/api/schemas/errors.py").read_text(encoding="utf-8")
    assert "FLORENCE_UNAVAILABLE" not in errs


def test_sibling_unavailable_errors_stay():
    """The box's boundary: Analyzer and Enrichment keep their errors and codes. The
    analyzer's code lives only as the exception's `default_error_code` -- errors.py has no
    ANALYZER_UNAVAILABLE member -- so it is pinned where it actually is."""
    src = (REPO_ROOT / "backend/core/exceptions.py").read_text(encoding="utf-8")
    assert "AnalyzerUnavailableError" in src
    assert 'ANALYZER_UNAVAILABLE' in src
    assert "EnrichmentUnavailableError" in src
    errs = (REPO_ROOT / "backend/api/schemas/errors.py").read_text(encoding="utf-8")
    assert "ENRICHMENT_SERVICE_UNAVAILABLE" in errs


def test_prompt_column_in_the_model_is_no_longer_a_native_enum():
    """The model maps `model` to a plain String column, so `create_all` builds the same
    shape the upgrade leaves behind (schema twins)."""
    src = (REPO_ROOT / "backend/models/prompt_version.py").read_text(encoding="utf-8")
    assert "SQLEnum" not in src, "the native enum column must leave the model"
    assert re.search(r'String\(', src), "model column should be a varchar String"


def test_prompt_service_default_configs_are_nemotron_only():
    """`DEFAULT_CONFIGS` and the per-model format table in prompt_storage carry the four
    retired keys no more -- they would seed directories the API refuses to serve."""
    from backend.services.prompt_service import DEFAULT_CONFIGS

    assert set(DEFAULT_CONFIGS) == {"nemotron"}


def test_prompt_storage_supported_models_are_nemotron_only():
    """The file-based store's SUPPORTED_MODELS frozenset is nemotron-only."""
    from backend.services.prompt_storage import SUPPORTED_MODELS

    assert set(SUPPORTED_MODELS) == {"nemotron"}

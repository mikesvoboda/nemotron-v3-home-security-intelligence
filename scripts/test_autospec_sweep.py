"""Tests for scripts/autospec-sweep.py (WP4.1).

The sweep rewrites unqualified mock.patch call sites to carry autospec=True,
mechanically and idempotently, refusing forms where the rewrite would be
wrong. These tests pin the refusal rules — a tool that converts a form it
doesn't understand is worse than no tool, because the resulting mock fails
loudly in CI and gets reverted as "the sweep is broken".

Run: uv run pytest scripts/test_autospec_sweep.py -q  (also wired into the
collection-sanity script-test step in ci.yml alongside the WP0.7 entries).
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).parent / "autospec-sweep.py"


def sweep(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    r = subprocess.run(
        [sys.executable, str(TOOL), *args, str(tmp)],
        capture_output=True,
        text=True,
        check=False,  # rc asserted below (a nonzero run must be inspectable)
    )
    # Refusal is a SUCCESS outcome (rc 0, file untouched) — asserting rc here
    # keeps "file unchanged" tests from passing vacuously when the tool is
    # missing or crashed (the never-ran-green trap, spec Problem section).
    assert r.returncode == 0, f"sweep rc={r.returncode}\n{r.stderr}"
    return r


@pytest.fixture
def src(tmp_path: Path):
    d = tmp_path / "t"
    d.mkdir()
    return d


def write(d: Path, code: str) -> Path:
    f = d / "test_x.py"
    f.write_text(code)
    return f


def read(f: Path) -> str:
    return f.read_text()


# ---------------------------------------------------------------- conversions


def test_plain_string_target_gets_autospec(src):
    f = write(src, 'with patch("backend.services.camera.scan") as m:\n    pass\n')
    r = sweep(src, "--fix")
    assert r.returncode == 0, r.stderr
    assert read(f) == 'with patch("backend.services.camera.scan", autospec=True) as m:\n    pass\n'


def test_single_quotes_preserved(src):
    f = write(src, "mocked = patch('backend.a.b')\n")
    sweep(src, "--fix")
    assert read(f) == "mocked = patch('backend.a.b', autospec=True)\n"


def test_existing_autospec_untouched_idempotent(src):
    code = 'with patch("a.b.c", autospec=True) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    sweep(src, "--fix")
    assert read(f) == code


def test_existing_spec_set_untouched(src):
    code = 'with patch("a.b.c", spec_set=["x"]) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_existing_spec_untouched(src):
    code = 'with patch("a.b.c", spec=SomeClass) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_new_kwarg_skipped(src):
    # patch(target, new=X, ...) — autospec is meaningless when new is given
    code = 'with patch("a.b.c", new=fake) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_new_callable_skipped(src):
    # Found by the first real batch run: mock raises
    # "Cannot use 'autospec' and 'new_callable' together", so a converted
    # new_callable site is a broken test, not a stronger one.
    code = 'with patch("a.b.c", new_callable=AsyncMock) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_positional_new_skipped(src):
    # patch("a.b.c", fake) — second positional is `new`; appending a kwarg
    # would not add autospec semantics and could change meaning
    code = 'with patch("a.b.c", fake) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_patch_dict_skipped(src):
    code = 'with patch.dict("a.b.c", {"k": 1}):\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_patch_multiple_skipped(src):
    # autospec on multiple() is valid in mock but the rewrite is structurally
    # different; v1 refuses it rather than guessing.
    code = 'with patch.multiple("a.b.c", x=1):\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_object_attribute_target_converted(src):
    # patch.object(module, "name") can take autospec=True (specs the attr on
    # the object) — this is the documented form, so it converts.
    code = 'with patch.object(camera_service, "scan") as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == 'with patch.object(camera_service, "scan", autospec=True) as m:\n    pass\n'


def test_mocker_patch_converted(src):
    code = 'm2 = mocker.patch("backend.services.x.run")\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == 'm2 = mocker.patch("backend.services.x.run", autospec=True)\n'


def test_decorator_form_converted(src):
    code = '@patch("backend.api.routes.cams.list_cameras")\ndef test_x(m):\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert (
        read(f)
        == '@patch("backend.api.routes.cams.list_cameras", autospec=True)\ndef test_x(m):\n    pass\n'
    )


def test_multiline_call_appends_last(src):
    code = (
        "with patch(\n"
        '    "backend.services.y.do",\n'
        '    side_effect=RuntimeError("boom"),\n'
        ") as m:\n"
        "    pass\n"
    )
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == (
        "with patch(\n"
        '    "backend.services.y.do",\n'
        '    side_effect=RuntimeError("boom"),\n'
        "    autospec=True,\n"
        ") as m:\n"
        "    pass\n"
    )


def test_non_dotted_string_skipped(src):
    # A bare-name target ("cache") cannot be autospec'd (mock: non-existent
    # attribute error) — refuse; those sites are triage items, not rewrites.
    code = 'with patch("cache") as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_module_level_target_name_skipped(src):
    # patch(module_object, "attr") is fine (object form converts), but
    # patch(some_name) with a non-string first arg that is NOT an
    # Attribute/Name object target (e.g. a subscript) is refused.
    code = 'with patch(config["key"], 1) as m:\n    pass\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_non_patch_name_untouched(src):
    code = 'value = compute("a.b.c")\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code


def test_multiple_sites_one_file(src):
    code = 'a = patch("x.y.z")\nb = patch.dict("p.q", {})\nwith patch.object(o, "m"):\n    pass\n'
    f = write(src, code)
    r = sweep(src, "--fix")
    assert "2 converted, 1 skipped" in r.stdout
    assert read(f) == (
        'a = patch("x.y.z", autospec=True)\n'
        'b = patch.dict("p.q", {})\n'
        'with patch.object(o, "m", autospec=True):\n'
        "    pass\n"
    )


# ------------------------------------------------------------------- census


def test_census_counts(src):
    write(src, 'a = patch("x.y.z")\nb = patch("a.b.c", autospec=True)\nc = patch.dict("p.q", {})\n')
    r = sweep(src, "--census")
    assert r.returncode == 0
    # x.y.z and a.b.c are patch-family sites (total=2); speced=1; the
    # patch.dict is excluded from the denominator (autospec is N/A to it).
    assert "sites=2 speced=1" in r.stdout


def test_census_zero_files(src):
    (src / "nothing.py").write_text("x = 1\n")
    r = sweep(src, "--census")
    assert "sites=0 speced=0" in r.stdout


def test_census_skipped_reported(src):
    write(src, 'x = patch.dict("p.q", {})\n')
    r = sweep(src, "--census")
    assert "skipped-na=1" in r.stdout


def test_no_args_defaults_to_census(src):
    write(src, 'a = patch("x.y.z")\n')
    r = sweep(src)
    assert "sites=1 speced=0" in r.stdout


def test_fix_requires_dotted_or_object_rule_kept(src):
    # f-string targets cannot be resolved statically — refuse
    code = 'x = patch(f"backend.{name}.run")\n'
    f = write(src, code)
    sweep(src, "--fix")
    assert read(f) == code

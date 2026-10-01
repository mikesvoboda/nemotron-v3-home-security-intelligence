"""Guard: the custom CodeQL queries must only reference library classes/members
that actually exist in the pinned CodeQL library packs.

Why this exists (measured, this sandbox, CodeQL CLI 2.27.1 -- the same version
the CI "CodeQL / Analyze" jobs use -- compiling the queries exactly as the
workflow does, i.e. per-pack with the pack directory as --search-path):

At 67ca4870 the CI check-run annotations said:

    ERROR: could not resolve type Decorator
        (.github/codeql/custom-queries/python/fastapi-missing-auth.ql:19,41-50)
    ERROR: getValue() cannot be resolved for type FastApiModifyingDecorator.extends
        (.github/codeql/custom-queries/python/fastapi-missing-auth.ql:24,12-20)
    ERROR: could not resolve type JSXAttribute
        (.github/codeql/custom-queries/javascript/react-dangerous-html.ql:19,38-50)
    ERROR: getName() cannot be resolved for type DangerousHtmlAttribute.extends
        (.github/codeql/custom-queries/javascript/react-dangerous-html.ql:20,35-42)

and I reproduced all four locally. The deeper truth behind the two
"cannot be resolved" follow-ups: the *base classes themselves* do not exist in
the pinned library packs --

* codeql/python-all 7.2.6 has no ``Decorator`` class at all. A decorator
  expression (``@app.post("/x")``) is modeled as a ``Call``; the endpoint
  binding is ``Function.getADecorator(): Expr``
  (semmle/python/Function.qll:59). ``Expr`` has no ``getValue()`` either.
* codeql/javascript-all 2.10.2 has no ``JSXAttribute`` (all-caps) class. The
  real class is ``JsxAttribute`` (semmle/javascript/JSX.qll:112) and it *does*
  have the ``getName()`` the query wanted (JSX.qll:125) -- only the class-name
  capitalization was invented.

Both queries failed to COMPILE, so the custom pack contributed zero results to
every CodeQL run -- a silent security-scanning gap dressed as a green workflow
(the CodeQL action fails the Analyze job but the alerts never fire anywhere
else).

The CodeQL CLI is not available in the pytest environment, so this guard is
source-level: it pins the four fabricated identifiers out of the queries and
pins the real-library constructs that replaced them. Truth-of-compilation is
re-checked out-of-band with
``codeql query compile --search-path <packdir> <query>``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
CUSTOM_QUERIES = REPO_ROOT / ".github" / "codeql" / "custom-queries"

FASTAPI_QUERY = CUSTOM_QUERIES / "python" / "fastapi-missing-auth.ql"
DANGEROUS_HTML_QUERY = CUSTOM_QUERIES / "javascript" / "react-dangerous-html.ql"


def _strip_ql_comments(source: str) -> str:
    """Drop /** **/ and // comments so docstring prose can't satisfy the guard."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"//[^\n]*", "", source)
    return source


@pytest.fixture(scope="module")
def fastapi_src() -> str:
    return _strip_ql_comments(FASTAPI_QUERY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dangerous_html_src() -> str:
    return _strip_ql_comments(DANGEROUS_HTML_QUERY.read_text(encoding="utf-8"))


def test_fastapi_query_extends_a_real_library_class_not_decorator(fastapi_src: str):
    # "class X extends Decorator" was CI error #1 (type Decorator unresolvable);
    # the real model binds the decorator as a Call reached via getADecorator().
    assert not re.search(r"\bextends\s+Decorator\b", fastapi_src), (
        "codeql/python-all has no `Decorator` class (7.2.6, checked against the "
        "installed pack); extend a real class such as `Call` instead"
    )
    assert re.search(r"class\s+FastApiModifyingDecorator\s+extends\s+Call\b", fastapi_src), (
        "FastApiModifyingDecorator must extend Call (`@app.post(...)` is a Call)"
    )
    assert re.search(r"class\s+FastApiEndpoint\s+extends\s+Function\b", fastapi_src), (
        "the endpoint class must extend Function (real: semmle/python/Function.qll)"
    )


def test_fastapi_query_binds_decorators_via_getadecorator(fastapi_src: str):
    # "this.getValue() = call" was CI error #2: Expr has no getValue().
    assert "this.getValue()" not in fastapi_src, (
        "python Expr has no getValue(); bind the decorator expression with "
        "Function.getADecorator() (semmle/python/Function.qll:59)"
    )
    assert "getADecorator()" in fastapi_src, (
        "the endpoint<->decorator join must go through getADecorator(), the "
        "documented accessor on Function"
    )


def test_dangerous_html_query_extends_real_jsxattribute_class(
    dangerous_html_src: str,
):
    # "extends JSXAttribute" was CI error #3: the library class is JsxAttribute
    # (semmle/javascript/JSX.qll:112, getAPrimaryQlClass "JsxAttribute").
    assert not re.search(r"\bextends\s+JSXAttribute\b", dangerous_html_src), (
        "codeql/javascript-all has no `JSXAttribute` (all-caps); the class is "
        "`JsxAttribute` (JSX.qll:112)"
    )
    assert re.search(
        r"class\s+DangerousHtmlAttribute\s+extends\s+JsxAttribute\b",
        dangerous_html_src,
    ), "DangerousHtmlAttribute must extend JsxAttribute so getName() resolves"


# --- measured beyond the two CI-surfaced queries -----------------------------
# Compiling every query individually with CLI 2.27.1 showed the pack was worse
# than the CI annotation (which stops at the first error): at 67ca4870 ALL
# THREE python queries failed to compile. fastapi-sql-injection.ql:46 said
# "could not resolve type JoinedStr" and unsafe-file-operations.ql carried the
# same JoinedStr error plus a second "could not resolve type Decorator"
# (:67). JoinedStr is CPython's AST-node name; the CodeQL class is `Fstring`
# (semmle/python/Exprs.qll, "A formatted string literal expression").

FABRICATED = {
    # fabricated name -> real replacement in the pinned packs
    "Decorator": "Call (reached via Function.getADecorator())",
    "JoinedStr": "Fstring (semmle/python/Exprs.qll)",
    "JSXAttribute": "JsxAttribute (semmle/javascript/JSX.qll)",
}


@pytest.mark.parametrize(
    "ql_file",
    sorted(CUSTOM_QUERIES.glob("*/*.ql")),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_no_query_extends_a_fabricated_library_class(ql_file: Path):
    src = _strip_ql_comments(ql_file.read_text(encoding="utf-8"))
    for fabricated, real in FABRICATED.items():
        assert not re.search(rf"\bextends\s+{fabricated}\b", src), (
            f"{ql_file.relative_to(REPO_ROOT)} extends `{fabricated}`, which no "
            f"pinned CodeQL library pack defines (use {real})"
        )


def test_sql_injection_query_matches_fstrings_with_the_real_class():
    src = _strip_ql_comments(
        (CUSTOM_QUERIES / "python" / "fastapi-sql-injection.ql").read_text(encoding="utf-8")
    )
    assert "JoinedStr" not in src, (
        "the python library models f-strings as Fstring; JoinedStr is the "
        "CPython AST name and does not resolve (CI-invisible until the pack's "
        "earlier queries are fixed)"
    )
    assert "Fstring" in src, "fastapi-sql-injection must recognize Fstring"


def test_file_operations_query_binds_decorators_and_fstrings_for_real():
    src = _strip_ql_comments(
        (CUSTOM_QUERIES / "python" / "unsafe-file-operations.ql").read_text(encoding="utf-8")
    )
    assert not re.search(r"(?<!getA)\bDecorator\b", src), (
        "bind the route decorator as a Call via Function.getADecorator() "
        "instead of the nonexistent Decorator class"
    )
    assert "this.getValue() = c" not in src, "Expr has no getValue()"
    assert "extends Fstring" in src, (
        "FormattedPathString must extend Fstring (the real f-string class)"
    )

"""`[r94]`: a `setup.py` re-run keeps the configuration that is already there.

Two defects, one doctrine. `setup.py` already reuses existing secrets on a re-run
(`load_existing_env`, "preserve existing passwords when re-running") but the reuse
stops at passwords: every other prompt still carries its
FIRST-RUN default, so an operator who presses Enter through a re-run on a
LAN-exposed install answers "don't expose" and silently re-binds the frontend to
loopback and disarms the Grafana derives the monitoring-key scoping depends on. And
the one thing a pre-R60 `.env` most needs converted — a plain `API_KEYS` entry for
the monitoring key — could only be fixed by a full re-run.

Fix 1: on a re-run every prompt's default is the value already in `.env`; a first
run keeps today's defaults. Fix 2: a ``--convert-monitoring-key`` flag rewrites only
that one ``API_KEYS`` entry.

The file is named after the ruling (as
``backend/tests/unit/test_r8_s3_florence_provider_retirement.py`` is) rather than
after a module, because the behaviour spans ``setup.py`` and ``setup_lib/core.py``.
"""

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

MONITORING_KEY = "hsi_machine_key_ABC123"


def _keys_line(entries: list[object], quote: str = "'") -> str:
    """An ``API_KEYS`` line, built the way ``merge_api_keys`` emits one.

    Compact separators inside a quote pair, so a fixture can never drift from the
    product's own serialization. ``quote=""`` gives the UNQUOTED shape a pre-R60 file
    has (see ``LAN_ENV_UNQUOTED``).
    """
    return f"API_KEYS={quote}{json.dumps(entries, separators=(',', ':'))}{quote}"


PLAIN_ENTRIES = ["ops-laptop-key", MONITORING_KEY]
API_KEYS_PLAIN = _keys_line(PLAIN_ENTRIES)

# The state the ruling describes: a LAN-exposed install whose `API_KEYS` list was
# last written before R60, so the monitoring key sits there as a PLAIN entry, which
# the gate reads as unscoped (docs/operator/admin/security.md). The hand-kept key
# `setup.py` never wrote (`PODMAN_SOCKET`) and the comment/blank-line texture are
# deliberate — Fix 2 must not disturb them, and "byte-compare the rest" needs a file
# with a rest.
LAN_ENV = f"""\
# operator notes: moved the DB port, see ticket 412
PODMAN_SOCKET=/run/user/1000/podman/podman.sock

EXPOSE_LAN=true
FRONTEND_BIND_ADDRESS=0.0.0.0
GRAFANA_ANONYMOUS_ENABLED=false
GRAFANA_AUTH_PROXY_ENABLED=true
GRAFANA_AUTH_PROXY_AUTO_SIGN_UP=true
ALERT_SINK_URL=http://frontend:8081/api/webhooks/alerts
FOSCAM_BASE_PATH=/srv/cameras
AI_MODELS_PATH=/srv/models

MONITORING_API_KEY={MONITORING_KEY}
{API_KEYS_PLAIN}

JWT_SECRET=aaaa.bbbb.cccc
GRAFANA_PORT=3002
"""

# The same install AFTER R60 wrote it, in the order merge_api_keys writes: the key
# setup.py GENERATED leads, the operator's own keys follow. `--convert-monitoring-key`
# over this is a no-op, in either order (the entry is found by its value).
LAN_ENV_SCOPED = LAN_ENV.replace(
    API_KEYS_PLAIN,
    _keys_line([{"key": MONITORING_KEY, "scope": "monitoring"}, "ops-laptop-key"]),
)

# The shape the ruling ACTUALLY targets. `setup.py` wrote `API_KEYS` UNQUOTED until R60
# (422b92e9b) added the single quote ALONGSIDE the scoped-object form; so every pre-R60
# file this flag exists to convert has a plain, UNQUOTED list. That is why the rewrite
# ADDS the quote rather than keeping "as found" — a scoped object in an unquoted line is
# a state setup.py never writes, and the scripts that `source` the file mangle it.
LAN_ENV_UNQUOTED = LAN_ENV.replace(API_KEYS_PLAIN, _keys_line(PLAIN_ENTRIES, quote=""))

CONVERTED_KEYS = ["ops-laptop-key", {"key": MONITORING_KEY, "scope": "monitoring"}]


def _load_setup():
    """Import the root setup.py, repo root on sys.path first (dir convention)."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import setup

    return setup


def _free_port() -> int:
    """A port this test just released, so "free" holds when setup.py probes it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _enter_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every prompt answers Enter, which is the defect's whole surface.

    `*_` because setup.py calls `input(prompt_text)`; the prompt text is deliberately
    not inspected here — that is test_rerun_shows_the_saved_value's job.
    """
    monkeypatch.setattr("builtins.input", lambda *_: "")


def _env_line(text: str, key: str) -> str | None:
    for line in text.splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1]
    return None


def _api_keys(text: str) -> list[object]:
    return json.loads(_env_line(text, "API_KEYS").strip("'"))


def _convert(text: str) -> tuple[str, str]:
    from setup_lib.core import convert_monitoring_key

    return convert_monitoring_key(text)


# --------------------------------------------------------------------------
# Fix 1 — an Enter-only re-run keeps the exposure switch and everything derived
# from it. These run the REAL collection pipeline in a tmp cwd and read the answer
# out of the `.env` setup.py writes, which is the observable the ruling names.
# --------------------------------------------------------------------------


def test_enter_only_rerun_keeps_lan_exposure_and_derives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pressing Enter through a re-run must not move a LAN-exposed install to loopback.

    The defect: the "Expose the UI beyond this machine?" prompt in both
    `run_quick_mode` and `run_guided_mode` defaulted to ``"n"``, and the answer drives
    everything `generate_env_content` derives from `expose_lan` — the `EXPOSE_LAN=`
    line, `FRONTEND_BIND_ADDRESS=`, and the Grafana anonymous/auth-proxy/auto-sign-up
    and `ALERT_SINK_URL` derives. Cited by function, not line: `setup.py` shifts under
    rebase and a wrong `file:line` reads as authority.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(LAN_ENV, encoding="utf-8")
    _enter_only(monkeypatch)

    config = setup.run_quick_mode()
    env_path, _, _ = setup.write_config_files(config, str(tmp_path))

    after = env_path.read_text(encoding="utf-8")
    assert _env_line(after, "EXPOSE_LAN") == "true", (
        "an Enter-only re-run flipped a LAN-exposed install off: "
        + repr(_env_line(after, "EXPOSE_LAN"))
    )
    # The address below is the value RENDERED INTO the .env; nothing in this file
    # binds a socket, so S104's reading of the literal is a false positive here.
    assert _env_line(after, "FRONTEND_BIND_ADDRESS") == "0.0.0.0"  # noqa: S104
    # The derives and the sink must all say "exposed" too — the package names them as
    # the security payload, and each is written from its own line.
    assert _env_line(after, "GRAFANA_ANONYMOUS_ENABLED") == "false"
    assert _env_line(after, "GRAFANA_AUTH_PROXY_ENABLED") == "true"
    assert _env_line(after, "GRAFANA_AUTH_PROXY_AUTO_SIGN_UP") == "true"
    assert _env_line(after, "ALERT_SINK_URL") == "http://frontend:8081/api/webhooks/alerts"


def test_enter_only_rerun_guided_keeps_lan_exposure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`run_guided_mode` carries the same prompt and the same defect as quick mode."""
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(LAN_ENV, encoding="utf-8")
    _enter_only(monkeypatch)

    config = setup.run_guided_mode()
    env_path, _, _ = setup.write_config_files(config, str(tmp_path))

    after = env_path.read_text(encoding="utf-8")
    assert _env_line(after, "EXPOSE_LAN") == "true"
    assert _env_line(after, "FRONTEND_BIND_ADDRESS") == "0.0.0.0"  # noqa: S104


def test_enter_only_rerun_keeps_paths_and_ports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix 1 is "every prompt's default", not "the exposure prompt".

    Paths are plain text prompts, so they are the simplest proof the mapping is
    general. The port half is where "keep what is saved" has to be reconciled with
    the port probe: a saved port is offered as the default.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    saved_pg_port = _free_port()
    (tmp_path / ".env").write_text(
        LAN_ENV.replace("GRAFANA_PORT=3002", f"POSTGRES_PORT={saved_pg_port}"),
        encoding="utf-8",
    )
    _enter_only(monkeypatch)

    config = setup.run_quick_mode()

    assert config["foscam_base_path"] == "/srv/cameras"
    assert config["ai_models_path"] == "/srv/models"
    assert config["ports"]["postgres"] == saved_pg_port, (
        "the saved postgres port was not offered as the default"
    )


def test_enter_only_rerun_does_not_rebind_a_taken_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preserving a port must not defeat the conflict check that is already there.

    A re-run over a `.env` whose port something else now holds must move the port
    rather than bind it out from under the holder — today's probe behaviour, kept.
    This is the control against "trust `.env` for ports" implemented by skipping the
    probe.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        taken = held.getsockname()[1]
        (tmp_path / ".env").write_text(LAN_ENV + f"\nPOSTGRES_PORT={taken}\n", encoding="utf-8")
        _enter_only(monkeypatch)

        config = setup.run_quick_mode()

    assert config["ports"]["postgres"] != taken


def test_first_run_keeps_todays_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix 1's other half, stated by the package: a first run keeps today's defaults.

    This is also the negative control for the tests above — if the mapping were
    unconditional instead of "the value already in `.env`", this is the test that
    goes red.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)  # no .env at all: first run
    _enter_only(monkeypatch)

    config = setup.run_quick_mode()
    env_path, _, _ = setup.write_config_files(config, str(tmp_path))

    after = env_path.read_text(encoding="utf-8")
    assert _env_line(after, "EXPOSE_LAN") == "false"
    assert _env_line(after, "FRONTEND_BIND_ADDRESS") == "127.0.0.1"
    assert _env_line(after, "GRAFANA_ANONYMOUS_ENABLED") == "true"
    assert _env_line(after, "ALERT_SINK_URL") == "http://backend:8000/api/webhooks/alerts"
    assert config["foscam_base_path"] == "/export/foscam"


def test_rerun_shows_the_saved_value_as_the_prompt_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operator must be able to SEE that Enter keeps them exposed.

    The bracket text is the only feedback an operator gets, and the state vocabulary
    (`.env` says `true`) is not the answer vocabulary (the prompt says `y`/`n`) — this
    pins the translation, which is where a naive Fix 1 reintroduces the defect:
    prefilled with `"true"`, the answer `"true"` fails the `expose_answer.lower() in
    ("y", "yes")` check that follows the prompt and the install lands on loopback
    again anyway.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(LAN_ENV, encoding="utf-8")

    shown: list[str] = []

    def fake_input(prompt: str = "") -> str:
        shown.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)
    setup.run_quick_mode()

    expose = [p for p in shown if "Expose the UI" in p]
    assert expose, f"the exposure prompt never fired; saw {shown!r}"
    assert "[y]" in expose[0], f"the default shown was not the saved value: {expose[0]!r}"


# --------------------------------------------------------------------------
# Fix 2 — --convert-monitoring-key rewrites exactly one API_KEYS entry.
# --------------------------------------------------------------------------


def test_convert_scopes_only_the_monitoring_entry() -> None:
    """The plain monitoring entry becomes scoped; the operator's key is untouched."""
    after, outcome = _convert(LAN_ENV)

    assert outcome == "converted"
    assert _api_keys(after) == CONVERTED_KEYS, (
        "only the monitoring entry may change, and it stays in place and in order"
    )


def test_convert_leaves_every_other_byte_alone() -> None:
    """Done when: "byte-compare the rest of `.env`"."""
    after, outcome = _convert(LAN_ENV)

    assert outcome == "converted"
    before_lines = LAN_ENV.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    assert len(before_lines) == len(after_lines), "the rewrite must not add or drop lines"
    changed = [(b, a) for b, a in zip(before_lines, after_lines, strict=True) if b != a]
    assert len(changed) == 1, f"{len(changed)} lines changed; exactly 1 may"
    assert changed[0][0].startswith("API_KEYS="), "the one changed line must be API_KEYS"
    # And it must stay sourceable: scripts/*.sh source this file under `set -e`, where
    # an unquoted line holding a scoped object brace-expands (measured: spaced exits
    # 127, compact mangles the value at 0). The house single-quote is what prevents it.
    assert after.split("API_KEYS=", 1)[1].lstrip().startswith("'"), "keep the house single-quote"


def _env_with_api_keys_at(shape: str) -> str:
    """``LAN_ENV`` with the ``API_KEYS`` line in a given shape.

    ``"last"`` puts it last with NO trailing newline (no terminator to find),
    ``"crlf"`` rewrites the file with CRLF endings, ``"crlf-last"`` does both.
    """
    head, _, rest = LAN_ENV.partition(API_KEYS_PLAIN + "\n")
    if shape.startswith("crlf"):
        head = head.replace("\n", "\r\n")
        rest = rest.replace("\n", "\r\n")
    line = API_KEYS_PLAIN.replace("\n", "\r\n") if shape.startswith("crlf") else API_KEYS_PLAIN
    eol = "\r\n" if shape.startswith("crlf") else "\n"
    return head + line + ("" if shape.endswith("last") else eol + rest)


@pytest.mark.parametrize(
    "shape",
    ["last", "crlf", "crlf-last"],
    ids=["api-keys-last-no-newline", "crlf-file", "crlf-api-keys-last-no-newline"],
)
def test_convert_keeps_the_lines_own_terminator(shape: str) -> None:
    """The rewrite must not touch line endings.

    Pinned because the first implementation split the line with
    ``str.partition("\\n")``, which DISCARDS the separator and so dropped a line on
    every conversion. The byte-compare test above caught that only because its
    fixture ends with a newline and its line count was checked; these are the shapes
    where a dropped or rewritten terminator is the only visible damage.
    """
    base = _env_with_api_keys_at(shape)

    after, outcome = _convert(base)

    assert outcome == "converted"
    assert after.count("\n") == base.count("\n"), "a line was added or dropped"
    assert after.count("\r") == base.count("\r"), "line endings were not preserved"
    # The file's own final shape is kept: a newline-terminated file still ends with
    # one, a file whose last line has no terminator still has none.
    assert after.endswith("\r\n" if shape == "crlf" else "'"), f"tail changed: {after[-12:]!r}"


def test_convert_sourced_value_under_set_e(tmp_path: Path) -> None:
    """The rewritten line must survive the scripts that source it with `set -e`."""
    after, outcome = _convert(LAN_ENV)
    assert outcome == "converted"
    env_file = tmp_path / ".env"
    env_file.write_text(after, encoding="utf-8")

    result = subprocess.run(  # noqa: S603 — argv is a literal list; bash is the interpreter  # real
        ["bash", "-c", f'set -e\nsource "{env_file}"\nprintf %s "$API_KEYS"'],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == CONVERTED_KEYS


def test_convert_uses_the_form_setup_py_round_trips() -> None:
    """The scoped entry must survive the next ordinary re-run.

    Otherwise `--convert-monitoring-key` fixes the file once and the next
    `python setup.py` un-fixes it — the failure mode `merge_api_keys`' own docstring
    records for the pre-R60 flat-list era, where a second run re-emitted the key as
    an unscoped plain string plus a junk entry.
    """
    from setup_lib.core import merge_api_keys

    converted, outcome = _convert(LAN_ENV)
    assert outcome == "converted"

    re_run = merge_api_keys(_env_line(converted, "API_KEYS"), MONITORING_KEY, "monitoring")
    entries = json.loads(re_run)

    # merge_api_keys documents that the generated entry leads, so the ORDER may move;
    # what must not happen is the entry going back to plain or doubling up.
    plain = [e for e in entries if isinstance(e, str)]
    assert MONITORING_KEY not in plain, f"a re-run re-widened the scope: {entries!r}"
    scoped = [e for e in entries if isinstance(e, dict) and e.get("key") == MONITORING_KEY]
    assert len(scoped) == 1, f"the monitoring entry doubled: {entries!r}"
    assert scoped[0]["scope"] == "monitoring"


def test_convert_leaves_an_already_scoped_key_alone() -> None:
    """Done when: "a key already scoped is left alone". Idempotent by construction."""
    after, outcome = _convert(LAN_ENV_SCOPED)

    assert outcome == "unchanged"
    assert after == LAN_ENV_SCOPED, "a second run must write nothing"
    # Running it twice is the operator's normal mistake.
    assert _convert(after) == (LAN_ENV_SCOPED, "unchanged")


def test_convert_adds_the_quote_a_pre_r60_line_lacks(tmp_path: Path) -> None:
    """The flagship input: an UNQUOTED pre-R60 line must come out single-quoted.

    `setup.py` wrote `API_KEYS` unquoted until R60 added the single quote in the same
    commit that introduced the scoped object (422b92e9b), because a value holding
    ``{"key":…,"scope":…}`` does not survive being sourced. So a conversion that kept
    the line "as found" would hand the operator a file whose `API_KEYS` bash mangles —
    the mangled value reads back as `[ops-laptop-key,{key:…,scope:monitoring}]`, which
    every JSON reader rejects, and an unquoted value that also carries spaces exits 127
    outright (bash word-splits it and tries to run `{key::`). Measured, not assumed: see
    the serialization note on convert_monitoring_key.
    """
    after, outcome = _convert(LAN_ENV_UNQUOTED)

    assert outcome == "converted"
    line = _env_line(after, "API_KEYS")
    assert line.startswith("'") and line.endswith("'"), f"the quote was not added: {line!r}"
    assert _api_keys(after) == CONVERTED_KEYS

    env_file = tmp_path / ".env"
    env_file.write_text(after, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 — argv is a literal list; bash is the interpreter  # real
        ["bash", "-c", f'set -e\nsource "{env_file}"\nprintf %s "$API_KEYS"'],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == CONVERTED_KEYS, (
        f"bash mangled the converted value: {result.stdout!r}"
    )


def test_convert_re_emits_the_value_compactly() -> None:
    """The re-emitted value matches setup.py's own writer byte-for-byte in shape.

    Spacing is NOT what breaks a sourced line — the measured breakage is an UNQUOTED
    value with spaces (rc 127), while a QUOTED spaced value sources cleanly at 0, so
    this line would work either way. Compactness is for `merge_api_keys`, which writes
    `separators=(",", ":")`: re-emitting in the same shape means the one line this flag
    touches is byte-shaped identical to the line setup.py itself would write, instead of
    leaving the file holding two spellings of the same value. A hand-spaced operator line
    on THAT one line is therefore re-compacted; every other line keeps its bytes.
    """
    spaced = LAN_ENV.replace(
        API_KEYS_PLAIN,
        f"""API_KEYS='["ops-laptop-key", "{MONITORING_KEY}"]'""",
    )
    after, outcome = _convert(spaced)

    assert outcome == "converted"
    line = _env_line(after, "API_KEYS")
    assert ", " not in line and '": ' not in line, f"value was not re-compacted: {line!r}"
    assert _api_keys(after) == CONVERTED_KEYS


def test_convert_identifies_the_key_from_the_last_monitoring_line() -> None:
    """`MONITORING_API_KEY` twice: the LAST line wins, because that is what reads it.

    Both of setup.py's readers are last-wins — load_existing_env assigns into a dict,
    and the raw API_KEYS read-back in write_env reassigns in the loop — so a tool that
    took the first would scope an entry that is no longer the active monitoring key.
    """
    stale_key = "stale-key-from-an-earlier-run"
    stale = LAN_ENV.replace(
        f"MONITORING_API_KEY={MONITORING_KEY}",
        f"MONITORING_API_KEY={stale_key}",
    )
    doubled = stale + f"MONITORING_API_KEY={MONITORING_KEY}\n"

    after, outcome = _convert(doubled)

    assert outcome == "converted"
    assert _api_keys(after) == CONVERTED_KEYS, "the entry identified was the stale key"
    assert stale_key not in after.split("API_KEYS=")[1]


def test_convert_of_a_double_quoted_line_emits_single_quotes(tmp_path: Path) -> None:
    """A double-quoted input must come out SINGLE-quoted, not keep its own character.

    Keeping a quoted line's own quote character is what the first version of this flag
    did, and it is a silent-corruption path: `json.dumps` output always contains `"`
    (the object keys), and python-dotenv — the backend's reader — abandons a value whose
    closing quote lands after an inner `"`, returning None for the WHOLE key. So the
    converted line sources at rc 0 while every API key vanishes from the gate's view, and
    the flag reports success. Single-quote emission is the only form both readers parse,
    which is why setup.py's own writer uses it (setup.py:559-566).

    The double-quoted input here was ALREADY invisible to dotenv before the flag ran
    (measured, and stated in the PR: this is not a regression the flag introduces into a
    healthy file) — what this pin holds is that the flag never LEAVES a file in that
    shape while reporting `+ converted`.
    """
    double = LAN_ENV.replace(
        API_KEYS_PLAIN,
        'API_KEYS="' + json.dumps(PLAIN_ENTRIES, separators=(",", ":")) + '"',
    )

    after, outcome = _convert(double)

    assert outcome == "converted"
    line = _env_line(after, "API_KEYS")
    assert line.startswith("'[") and line.endswith("]'"), (
        f"a double-quoted line must be re-emitted single-quoted, not keep its own "
        f"quote character: {line!r}"
    )
    assert _api_keys(after) == CONVERTED_KEYS

    import dotenv

    env_file = tmp_path / ".env"
    env_file.write_text(after, encoding="utf-8")
    parsed = dotenv.dotenv_values(env_file).get("API_KEYS")
    assert parsed is not None, "the converted line is invisible to the backend's reader"
    assert json.loads(parsed) == CONVERTED_KEYS, (
        f"dotenv read a different value than was written: {parsed!r}"
    )


def test_convert_refuses_an_apostrophe_key_as_not_quotable() -> None:
    """An entry holding a literal `'` has NO survivable emission, so refuse it.

    Single quotes cannot nest, so the line would ship unterminated: `source` under
    `set -e` exits 2 and the scripts that read the file stop at that line, while
    python-dotenv silently drops the key — and a double-quoted workaround expands `$`
    and backticks inside the value. Emitting any of those shapes would take a file that
    sources and parses fine today to unreadable-by-both while exiting 0, so the only
    correct move is to refuse and leave the file alone. (setup.py mints keys with
    `secrets.token_urlsafe`, whose alphabet excludes `'` — this is the hand-edited or
    third-party key case.)
    """
    apos = LAN_ENV.replace(
        API_KEYS_PLAIN,
        _keys_line(["ops's-laptop-key", MONITORING_KEY]),
    )

    after, outcome = _convert(apos)

    assert outcome == "not-quotable"
    assert after == apos, "a refusal must leave the file byte-identical"


def test_an_already_scoped_file_with_an_apostrophe_key_stays_a_no_op() -> None:
    """The quotability check runs only when a rewrite is about to happen.

    An apostrophe key minted by ANOTHER tool is none of this flag's business when the
    monitoring entry is already scoped: running the flag twice is "the operator's normal
    mistake" and must stay a silent success. Refusing there would report a re-key
    demand about a line the flag never touched, training the operator to distrust the
    refusals that do matter.
    """
    scoped = LAN_ENV_SCOPED.replace(
        '"ops-laptop-key"',
        '"ops\'s-laptop-key"',
    )

    after, outcome = _convert(scoped)

    assert outcome == "unchanged"
    assert after == scoped


@pytest.mark.parametrize(
    ("env_text", "expected_outcome"),
    [
        # Nothing identifies WHICH plain entry is the monitoring one. Narrowing a
        # scope the tool did not mint would break whatever uses that key, so it must
        # not guess among an operator's keys.
        (LAN_ENV.replace(f"MONITORING_API_KEY={MONITORING_KEY}\n", ""), "no-monitoring-key"),
        # The saved key is not listed plainly (it is already scoped) — nothing to do.
        (
            LAN_ENV_SCOPED.replace(
                f"MONITORING_API_KEY={MONITORING_KEY}", "MONITORING_API_KEY=hsi_other"
            ),
            "not-listed",
        ),
        (LAN_ENV.replace("API_KEYS=", "OTHER_KEY="), "not-listed"),
        # Two plain entries carry the value: cannot tell the monitoring key from a
        # duplicated operator key, so refuse rather than pick one.
        (
            LAN_ENV.replace(API_KEYS_PLAIN, _keys_line([MONITORING_KEY, MONITORING_KEY])),
            "ambiguous-duplicate",
        ),
        # The value is listed BOTH plainly and scoped: the plain entry is what keeps
        # it unscoped, but deleting an entry is beyond a flag that "touches nothing
        # else", so the operator has to resolve their own duplicate by hand.
        (
            LAN_ENV.replace(
                API_KEYS_PLAIN,
                _keys_line([{"key": MONITORING_KEY, "scope": "monitoring"}, MONITORING_KEY]),
            ),
            "ambiguous-duplicate",
        ),
        # An object with no scope is fail-closed (no grant at all), not a plain
        # entry. Adding a scope here would WIDEN it, which is the opposite of the
        # ruling's direction of travel.
        (
            LAN_ENV.replace(API_KEYS_PLAIN, _keys_line([{"key": MONITORING_KEY}])),
            "not-plain",
        ),
        # A corrupt value is not repaired by a flag whose job is a narrow rewrite.
        (LAN_ENV.replace(API_KEYS_PLAIN, "API_KEYS=not json at all"), "not-a-list"),
        # Two API_KEYS lines: setup.py's own readers take the last, but a
        # byte-preserving rewrite of an ambiguous file is where silent damage happens.
        (LAN_ENV + f"API_KEYS='[\"{MONITORING_KEY}\"]'\n", "duplicate-line"),
    ],
    ids=[
        "no-monitoring-key",
        "not-listed-already-scoped-other-key",
        "not-listed-no-api-keys-line",
        "ambiguous-duplicate-two-plain",
        "ambiguous-duplicate-plain-and-scoped",
        "not-plain-object-without-scope",
        "not-a-list",
        "duplicate-line",
    ],
)
def test_convert_refuses_and_writes_nothing(env_text: str, expected_outcome: str) -> None:
    """Every refusal leaves the file byte-identical — that `.env` is the only copy of
    these keys."""
    after, outcome = _convert(env_text)

    assert outcome == expected_outcome
    assert after == env_text


def _run_flag(setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Drive `main()` down the flag path only, with the install steps silenced."""
    monkeypatch.setattr(
        sys, "argv", ["setup.py", "--convert-monitoring-key", "--output-dir", str(tmp_path)]
    )
    # Nothing but the flag may run: platform detection and the install steps reach
    # podman/apt on a real machine.
    monkeypatch.setattr(setup, "get_platform_info", lambda: None)
    with pytest.raises(SystemExit) as exit_info:
        setup.main()
    return exit_info.value.code


def test_flag_writes_the_file_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI wiring: `--convert-monitoring-key` acts on `--output-dir`'s `.env`."""
    setup = _load_setup()
    (tmp_path / ".env").write_text(LAN_ENV, encoding="utf-8")

    assert _run_flag(setup, tmp_path, monkeypatch) == 0

    after = (tmp_path / ".env").read_text(encoding="utf-8")
    assert _api_keys(after) == CONVERTED_KEYS
    out = capsys.readouterr().out.lower()
    # The house "+ " / "! " prefixes, not the bare word: the refusal line says
    # "Not converted", which contains it.
    assert "+ converted" in out, f"the flag must report what it did: {out!r}"


def test_flag_on_an_already_scoped_file_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Running it twice must succeed.

    "Already scoped" is the wanted end state, so it exits 0 and writes nothing. A
    tool that reports failure for "nothing to do" trains operators to ignore `$?`,
    which is the only signal the genuine refusals below rely on.
    """
    setup = _load_setup()
    (tmp_path / ".env").write_text(LAN_ENV_SCOPED, encoding="utf-8")

    assert _run_flag(setup, tmp_path, monkeypatch) == 0

    assert (tmp_path / ".env").read_text(encoding="utf-8") == LAN_ENV_SCOPED
    assert "already scoped" in capsys.readouterr().out.lower()


def test_flag_refusal_exits_nonzero_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal is something an operator should see in `$?`, and the file stands."""
    setup = _load_setup()
    broken = LAN_ENV.replace(API_KEYS_PLAIN, "API_KEYS=not json at all")
    (tmp_path / ".env").write_text(broken, encoding="utf-8")

    assert _run_flag(setup, tmp_path, monkeypatch) == 1

    assert (tmp_path / ".env").read_text(encoding="utf-8") == broken
    out = capsys.readouterr().out.lower()
    assert "! not converted" in out, f"a refusal must report the refusal: {out!r}"
    assert "+ converted" not in out, "a refusal must not report success"


def test_flag_refuses_an_apostrophe_key_and_tells_the_operator_to_rekey(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The one refusal whose remedy is NOT "run the heavier thing instead".

    Every other refusal can be resolved by a full interactive re-run; this one cannot,
    because setup.py's own writer wraps the value in the same single quotes
    (`API_KEYS='" + merge_api_keys(...) + "'"`, setup.py:559-566) and would ship the same
    unterminated line. So the printed reason has to name the re-key — pointing an
    operator at a re-run here sends them into the same wall (docs/operator/admin/
    security.md carries the same distinction).
    """
    setup = _load_setup()
    apos = LAN_ENV.replace(API_KEYS_PLAIN, _keys_line(["ops's-laptop-key", MONITORING_KEY]))
    (tmp_path / ".env").write_text(apos, encoding="utf-8")

    assert _run_flag(setup, tmp_path, monkeypatch) == 1

    assert (tmp_path / ".env").read_text(encoding="utf-8") == apos
    out = capsys.readouterr().out
    assert "not-quotable" in out, f"the refusal must name the case: {out!r}"
    assert "apostrophe" in out.lower(), f"the remedy must name the cause: {out!r}"
    assert "re-key" in out.lower(), f"the remedy must be actionable: {out!r}"


# --------------------------------------------------------------------------
# The docs line (Done when clause 4): ruling 79's advice pointed at a full re-run,
# which after Fix 2 is the heavier action where the flag is the narrow one.
# --------------------------------------------------------------------------


def test_security_docs_point_the_conversion_at_the_flag() -> None:
    text = (REPO_ROOT / "docs/operator/admin/security.md").read_text(encoding="utf-8")

    assert "--convert-monitoring-key" in text, (
        "the paragraph telling an operator how to scope a legacy monitoring key "
        "still names a full re-run as the way to do it"
    )


def test_defaults_mode_still_mints_its_own_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix 1 must not creep into `--defaults`.

    That path has a recorded DECIDE (`run_defaults_mode`'s "Non-interactive bootstrap
    (--defaults / --yes) never opens the UI to the LAN" comment, pinned by
    ``test_frontend_expose_lan_bind.py::test_defaults_mode_never_exposes_the_lan``)
    and `docs/operator/admin/security.md` states the reuse-skip as behaviour:
    `--yes`/`--defaults` mint a new key. It is non-interactive, so it has no prompt
    default to preserve — Fix 1 is the two interactive modes.
    """
    setup = _load_setup()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(LAN_ENV, encoding="utf-8")

    config = setup.run_defaults_mode()

    assert config["expose_lan"] is False
    assert config["monitoring_api_key"] != MONITORING_KEY

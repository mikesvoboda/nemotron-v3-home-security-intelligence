"""Core utility functions for setup script.

This module contains reusable utilities for port checking, password generation,
and other setup-related operations. These functions are extracted from the
main setup.py to enable better testing and reusability.
"""

import json
import secrets
import socket

# Known weak/default passwords to warn about
WEAK_PASSWORDS = {
    "security_dev_password",
    "password",
    "postgres",
    "admin",
    "root",
    "123456",
    "changeme",
    "secret",
}


def check_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Checks both IPv4 and IPv6 localhost to detect processes bound to either.

    Args:
        port: Port number to check

    Returns:
        True if port is available on both IPv4 and IPv6, False if in use
    """
    # Check IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False
    # Check IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            if s.connect_ex(("::1", port)) == 0:
                return False
    except OSError:
        pass  # IPv6 not available
    return True


def find_available_port(start: int, exclude: set[int] | None = None) -> int:
    """Find the next available port starting from a given port.

    Args:
        start: Starting port number
        exclude: Set of ports to skip (already assigned to other services)

    Returns:
        First available port >= start that is not in exclude set

    Raises:
        RuntimeError: If no available ports found up to 65535
    """
    if exclude is None:
        exclude = set()
    port = start
    while not check_port_available(port) or port in exclude:
        port += 1
        if port > 65535:
            raise RuntimeError(f"No available ports found starting from {start}")
    return port


def generate_password(length: int = 32) -> str:
    """Generate a secure random password.

    Args:
        length: Desired password length (default: 32 for security)

    Returns:
        URL-safe random string of specified length
    """
    return secrets.token_urlsafe(length)[:length]


def derive_frontend_bind_address(expose_lan: str) -> str:
    """Map an EXPOSE_LAN value to the frontend's published-port bind address.

    O1.6 (D10; OD-12): compose has no conditionals, so the switch lives here —
    setup.py derives FRONTEND_BIND_ADDRESS from EXPOSE_LAN and writes both into
    the .env it generates, and docker-compose.prod.yml references the bind var.

    One flag, one vocabulary (O1.6 review follow-up): the truthy set matches
    what pydantic parses for Settings.expose_lan from a string — case-
    insensitive {"true", "t", "yes", "y", "on", "1"} (probed against
    TypeAdapter(bool) on pydantic 2.13), so a value like EXPOSE_LAN=yes can
    never arm the auth gate here while the bind stayed loopback there.
    Everything else — unset, "false"/"no"/"off", a typo — yields loopback
    "127.0.0.1" (fail-safe). The words pydantic REJECTS outright (e.g. "banana")
    can't split the readers either: Settings construction raises before any
    render happens. One edge, stated exactly: this derive .strip()s, pydantic
    does not — a whitespace-padded truthy word (" true") wilds the bind here
    while Settings raises there, so the backend never boots behind it (the
    split is loud, never silent). The second fail-safe layer is compose's own
    ${FRONTEND_BIND_ADDRESS:-127.0.0.1} default, which covers a hand-edited
    .env that sets EXPOSE_LAN=true without re-running setup.py.

    Args:
        expose_lan: raw EXPOSE_LAN value (from a prompt answer or an env read)

    Returns:
        "0.0.0.0" when the UI is deliberately LAN-exposed, else "127.0.0.1"
    """
    return (
        "0.0.0.0"  # noqa: S104
        if expose_lan.strip().lower() in ("true", "t", "yes", "y", "on", "1")
        else "127.0.0.1"
    )


def _expose_lan_is_truthy(expose_lan: str) -> bool:
    """The one truthy vocabulary, shared by every EXPOSE_LAN reader (O1.6).

    Case-insensitive {"true", "t", "yes", "y", "on", "1"} — the exact set
    pydantic parses for Settings.expose_lan and the exact set
    derive_frontend_bind_address uses, so the auth gate, the bind address and
    the O1.11 monitoring renders can never disagree about what "exposed"
    means. Everything else (unset, "false"/"no"/"off", a typo) is the
    DEFAULT un-exposed mode — fail-safe in the direction that keeps the
    attack surface small.
    """
    return expose_lan.strip().lower() in ("true", "t", "yes", "y", "on", "1")


def derive_grafana_anonymous_enabled(expose_lan: str) -> str:
    """Whether Grafana's anonymous Admin access stays on, from EXPOSE_LAN.

    O1.11 (UR-33): the shipped ``GF_AUTH_ANONYMOUS_ENABLED=true`` +
    ``ORG_ROLE=Admin`` pairing is the one door into /grafana/ today (the
    login form is already disabled), and it is exactly what exposure must
    close — a LAN-reachable dashboard with anonymous Admin reads every
    panel and mints API tokens. Unexposed, this returns "true": today's
    behavior, byte for byte (spec checklist 4).

    Same one flag, one vocabulary as derive_frontend_bind_address; compose
    carries the value through a nested default so a .env that already
    hand-set GF_AUTH_ANONYMOUS_ENABLED=false keeps its own "false" (see the
    render tests — the security direction only ever goes one way).

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        "false" when deliberately LAN-exposed, else "true" (fail-safe)
    """
    return "false" if _expose_lan_is_truthy(expose_lan) else "true"


def derive_grafana_auth_proxy_enabled(expose_lan: str) -> str:
    """Whether Grafana trusts the frontend's auth-proxy header, from EXPOSE_LAN.

    O1.11's recorded DECIDE: nginx ``auth_request`` against the backend
    session + Grafana auth proxy — one login serves /grafana/ and the three
    embedded dashboards. Unexposed this must be "false" or the frontend's
    (never-rendered) X-Auth-User header would be the only credential Grafana
    accepts while nothing validates it: the render and the trust arm
    together, off together.

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        "true" when deliberately LAN-exposed, else "false" (fail-safe)
    """
    return "true" if _expose_lan_is_truthy(expose_lan) else "false"


def derive_alert_sink_url(expose_lan: str) -> str:
    """Where Alertmanager delivers webhooks, from EXPOSE_LAN.

    Alertmanager cannot attach an X-API-Key in ANY version (probe:
    http_headers rejected by amtool v0.27.0 through v0.34.1; only
    basic_auth/bearer exist, and the B1.5 gate reads neither). The
    credential therefore joins at the frontend's unpublished machine
    listener (compose-network ``listen 8081``, path-exact route) which
    renders the header in. Unexposed, the sink stays today's direct
    backend URL — the listener isn't rendered there, and the gate lets
    the compose network through without a credential anyway.

    Args:
        expose_lan: raw EXPOSE_LAN value (prompt answer or env read)

    Returns:
        The frontend machine-listener URL when exposed, else the direct
        backend URL (fail-safe, today's behavior).
    """
    if _expose_lan_is_truthy(expose_lan):
        return "http://frontend:8081/api/webhooks/alerts"
    return "http://backend:8000/api/webhooks/alerts"


def merge_api_keys(existing: str, new_key: str, new_key_scope: str | None = None) -> str:
    """Merge the generated monitoring key into an existing ``API_KEYS`` value.

    O1.11 (UR-33) makes setup.py write ``API_KEYS`` for the first time — setup.py
    on origin/main wrote none at all (measured: ``git show origin/main:setup.py |
    grep -c API_KEYS`` → 0). Writing the generated key as the WHOLE list would
    silently delete every key an operator added by hand the next time setup.py
    runs, which contradicts this file's own reuse-first doctrine for
    ``MONITORING_API_KEY`` and setup.py's "preserve existing passwords when
    re-running" rule. So: generated key first (it is the one compose renders into
    the monitoring stack), operator keys after it in their original order,
    duplicates collapsed.

    R60 (ruling 60) adds the ``new_key_scope`` arm: when a scope name is given,
    the generated entry is emitted as the OBJECT form
    ``{"key": ..., "scope": ...}`` — the scoped syntax the gate resolves via
    ``backend/core/constants.py`` — and round-trips are OBJECT-AWARE: an
    existing object entry is re-emitted as an object, never ``str(item)``'d.
    The plain ``str(item)`` round-trip the flat-list era could get away with is
    a silent privilege bug once objects exist: ``json.loads`` reads an object
    entry back as a ``dict`` and ``str(dict)`` writes Python repr with single
    quotes — on a second setup.py run the monitoring key would come back as an
    unscoped plain string PLUS a junk entry whose SHA-256 is a valid (unscoped)
    key. R60 would un-fix itself on the next re-run. Measured pre-fix:
    ``merge('[{"key":"hsi_NEW","scope":"monitoring"}]', "hsi_NEW")`` →
    ``'["hsi_NEW", "{\\'key\\': \\'hsi_NEW\\', \\'scope\\': \\'monitoring\\'}"]'``.

    Round-trip rules (pin-tested both directions):

    - identity is the KEY VALUE across BOTH forms: the generated entry leads,
      and every existing entry — object or plain string — carrying that same
      value is the duplicate collapsed. Byte-stable re-runs are the visible
      half; the other half is the exact hole this leg exists to close. A
      pre-R60 ``.env`` mirrors the monitoring key as a PLAIN string, so without
      cross-form identity a new setup.py would emit the object AND keep the
      string, and the gate's documented precedence (a plain entry for a value
      means that value is unscoped — you cannot revoke a grant by also listing
      it scoped) would leave R60 un-fixed after one re-run. Consequence for an
      operator who wants the monitoring key to stay unscoped: don't list its
      value here plainly; setup.py owns the scope of the key it generates.
    - an existing object entry keeps its own ``scope`` value verbatim (setup.py
      never rewrites a scope it did not generate — preserve-existing doctrine,
      an unresolvable name included; the backend fails that entry closed and
      warns at parse).
    - an existing object without a usable string ``key`` is dropped (it
      authenticates nothing backend-side);
    - a whole-value that is not a JSON list degrades to the generated entry
      alone (today's corrupt-value arm, unchanged);
    - serialization is COMPACT (``separators=(",", ":")``): the spaced
      ``json.dumps`` default makes the ``.env`` line word-split (and, with
      ``{...}`` objects, brace-expand) when a script sources it under
      ``set -e`` — measured exit 127 (the two scripts that source it:
      quick-rebuild.sh:73 and verify-observability.sh:19, both under
      ``set -e``; docker-compose.prod.yml:636 interpolates the same value).
      Compact + the caller's single-quote keeps the sourcing
      paths green (setup.py's own reader, load_existing_env, python-dotenv,
      docker compose all strip one matching quote pair). Stated limit: a key
      containing a literal ``'`` has NO form that both round-trips through
      every one of those readers and sources in bash (single quotes cannot
      nest; double quotes expand ``$`` and backticks; unquoted breaks on both)
      — the generated monitoring key comes from ``secrets.token_urlsafe`` so
      it never hits this. Precise about the pre-existing line, though (measured,
      r94 self-review): an UNQUOTED list of PLAIN strings holding an apostrophe
      sources at rc 0, because JSON's own ``"`` wrap each entry — so a key with
      an apostrophe does NOT break the file until something adds a ``{...}``
      object, which no unquoted form survives (brace expansion). That object is
      exactly what this flag adds, which is why the emission is single-quoted
      and an apostrophe entry is refused as ``not-quotable`` rather than emitted
      into a line that would break.

    Args:
        existing: the current ``API_KEYS`` value ("" when absent); one
            matching surrounding quote pair is tolerated (setup.py's own
            quoted emission round-trips).
        new_key: the generated monitoring key ("" when none)
        new_key_scope: R60 scope NAME for the generated entry (None = today's
            plain string form; setup.py passes "monitoring")

    Returns:
        A compact JSON array string — the form ``Settings.api_keys`` parses.
    """
    # Each entry carries its dedupe marker (the KEY VALUE, so identity spans
    # both forms — see docstring) beside the value to emit. Deriving the
    # marker after the fact re-narrows a dict union for mypy for no gain.
    entries: list[tuple[str, object]] = []
    if new_key:
        if new_key_scope is None:
            entries.append((new_key, new_key))
        else:
            entries.append((new_key, {"key": new_key, "scope": new_key_scope}))
    raw = (existing or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]  # one matching quote pair: setup.py's quoted line round-trips
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    value = item.get("key")
                    if not isinstance(value, str) or not value:
                        continue  # authenticates nothing backend-side; drop
                    entries.append(
                        (
                            value,
                            {"key": value, "scope": item.get("scope")}
                            if "scope" in item
                            else {"key": value},
                        )
                    )
                elif item:
                    text = str(item)
                    entries.append((text, text))
    # Dedupe on the marker while preserving order; the generated entry keeps
    # the lead. An explicit loop rather than the ``x in seen or seen.add(x)``
    # comprehension: mypy 2.3 (the CI Type Check leg, which follows imports in
    # here even though the pre-commit mypy hook's ``files:`` filter does not)
    # rejects ``set.add`` used as a value — [func-returns-value].
    seen: set[str] = set()
    unique: list[object] = []
    for marker, entry in entries:
        if marker not in seen:
            seen.add(marker)
            unique.append(entry)
    return json.dumps(unique, separators=(",", ":"))


def convert_monitoring_key(env_text: str) -> tuple[str, str]:
    """Scope the plain ``API_KEYS`` entry that mirrors ``MONITORING_API_KEY``.

    Ruling 94 Fix 2. An install whose ``.env`` was last written by ``setup.py``
    between `O1.11` and R60 lists the monitoring key as a PLAIN ``API_KEYS`` entry,
    which the gate reads as UNSCOPED — the key can read operator-only paths. Until
    now the only cure was a full re-run (docs/operator/admin/security.md), which
    makes every other decision in the file again. This rewrites that ONE entry as
    ``{"key": ..., "scope": "monitoring"}`` (#6959's format, the same object
    ``merge_api_keys`` emits) and leaves the rest of the file alone.

    Scope discipline, because the file is the operator's own and the only copy of
    these keys: the entry is identified by the value in ``MONITORING_API_KEY`` and by
    nothing else. A plain entry is never narrowed on a guess — narrowing a scope this
    tool did not mint breaks whatever uses that key — and no entry is ever deleted,
    added or reordered. Anything ambiguous is REFUSED, byte-for-byte unchanged, with
    the reason returned for the caller to print.

    Returns:
        ``(text, outcome)``. ``text`` equals the input on every outcome except
        ``"converted"``. Outcomes:

        - ``"converted"`` — the plain entry became a scoped one, in place;
        - ``"unchanged"`` — it is already scoped (idempotent: running it twice is
          safe, which is the operator's normal mistake);
        - ``"no-monitoring-key"`` — no usable ``MONITORING_API_KEY`` to identify the
          entry by;
        - ``"not-listed"`` — no ``API_KEYS`` line, or the key is not in it;
        - ``"ambiguous-duplicate"`` — the value appears more than once, or appears
          plainly AND as an object (the plain entry is what keeps it unscoped, but
          deleting an entry is beyond a flag that "touches nothing else");
        - ``"not-plain"`` — the only entry for the value is an object with no
          ``scope``, which is fail-closed (no grant at all); adding a scope here would
          WIDEN it, the opposite of this ruling's direction of travel;
        - ``"not-a-list"`` — the value is not a JSON list (a corrupt value is not
          repaired by a narrow rewrite — a re-run regenerates the file);
        - ``"duplicate-line"`` — two ``API_KEYS`` lines (setup.py's own readers take
          the last, but a byte-preserving rewrite of an ambiguous file is where silent
          damage happens);
        - ``"not-quotable"`` — an entry holds a literal ``'``, so no emission of the
          converted value survives the file's readers (see the serialization note);
          the file stands exactly as it was.

        Serialization note: the ONE line is re-emitted the way ``setup.py``'s own
        writer emits it — compact separators (``merge_api_keys``) inside the caller's
        single quote. Both halves matter for the scripts that ``source`` this file
        under ``set -e`` (measured here): an unquoted value holding a scoped object
        word-splits and brace-expands when spaced (exit 127) and loses its JSON
        quoting when compact (exit 0 but mangled); the single quote is what keeps the
        sourced value parseable. It is load-bearing, and R60 (422b92e9b) introduced it
        alongside the object form for exactly this reason — so a pre-R60 file, which
        ``setup.py`` wrote BEFORE the quote existed, GETS the single quote here: a
        converted line always holds a scoped object, and a scoped object in an
        unquoted line is a state ``setup.py`` never writes. A line that already has a
        matching quote pair is EMITTED with the single quote — including a double-quoted
        input, which is NOT kept (r94 follow-up, measured): ``json.dumps`` output always
        contains ``"``, and python-dotenv — the backend's reader — abandons a value
        whose closing quote landed after an inner ``"`` (it returns ``None`` for the
        whole key, so every API key vanishes from the gate's view while the file
        sources at rc 0: brace-expansion mangles it for bash). Keeping a double-quoted
        line's own character preserved exactly that unreadable shape and reported
        success. Single-quote emission is the only form the backend's reader parses.
        A value that cannot be single-quoted at all — any entry holding a literal
        ``'`` — is REFUSED as ``"not-quotable"`` (single quotes cannot nest), because
        emitting it anyway produces a line bash refuses to source (rc 2) that
        python-dotenv silently drops, with the flag exiting 0: the file goes from
        sourcing and parsing fine to unreadable by both readers. Compactness matches
        the writer so a converted file reads the same as a freshly generated one.
        Every other line, including its line endings, is returned untouched.
    """
    lines = env_text.splitlines(keepends=True)

    def _value_of(key: str) -> str | None:
        """The last ``KEY=value`` in the file, one matching quote pair stripped.

        "Last" is what this file's raw read-back and ``load_existing_env`` both do,
        so a re-run of this tool agrees with a re-run of setup.py.
        """
        found: str | None = None
        for raw in env_text.splitlines():
            stripped = raw.strip()
            if stripped.startswith(f"{key}="):
                value = stripped.partition("=")[2].strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                found = value
        return found

    monitoring_key = _value_of("MONITORING_API_KEY")
    if not monitoring_key:
        return env_text, "no-monitoring-key"

    indices = [i for i, raw in enumerate(lines) if raw.strip().startswith("API_KEYS=")]
    if not indices:
        return env_text, "not-listed"
    if len(indices) > 1:
        return env_text, "duplicate-line"

    line = lines[indices[0]]
    # Keep the line's own terminator and its own quote CHARACTER so the rewrite changes
    # only the JSON, never the file's shape (line endings included, "\r\n" and a missing
    # final newline both intact). The default is the single quote, not "no quote": the
    # converted value holds a {"key":…,"scope":…} object, which needs quoting to survive
    # a `source` under `set -e` (see the serialization note), and a pre-R60 line is
    # unquoted because setup.py added the quote only with R60's object form.
    body = line.rstrip("\r\n")
    terminator = line[len(body) :]
    prefix, _, raw_value = body.partition("=")
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        # Strip any existing matching pair, but EMIT the single quote (r94 follow-up):
        # json.dumps output always holds `"` (object keys), and a double-quoted line
        # is invisible to python-dotenv — the reader closes the value at the first
        # inner `"`, so it abandons the whole statement (measured: dotenv returns
        # None, the backend loses every key) while bash brace-expands it at rc 0.
        # Keeping the line's own `"` preserved that unreadable shape and reported
        # success. The single quote is what every reader of this file strips.
        value = value[1:-1]

    try:
        entries = json.loads(value)
    except ValueError:
        return env_text, "not-a-list"
    if not isinstance(entries, list):
        return env_text, "not-a-list"
    plain_at = [i for i, e in enumerate(entries) if isinstance(e, str) and e == monitoring_key]
    object_at = [
        i
        for i, e in enumerate(entries)
        if isinstance(e, dict) and isinstance(e.get("key"), str) and e["key"] == monitoring_key
    ]

    if len(plain_at) > 1 or (plain_at and object_at):
        return env_text, "ambiguous-duplicate"
    if not plain_at:
        if not object_at:
            return env_text, "not-listed"
        # The value only ever appears as an object: the conversion is already done,
        # or the object carries no scope at all — fail-closed, and widening it here
        # would be the opposite of what this ruling does.
        return env_text, "unchanged" if "scope" in entries[object_at[0]] else "not-plain"

    # Past this point a rewrite WILL happen, so the emission has to be quotable. A
    # literal ' inside any entry cannot be single-quoted at all — single quotes do not
    # nest — so the line would ship unterminated: bash refuses to source it (rc 2)
    # and python-dotenv silently drops it, while a double-quoted workaround expands
    # $ and backticks. Refuse loudly; the file stays exactly as readable as it was.
    # Checked HERE, not before identification, so a file that is already converted
    # stays a silent "unchanged" no-op even when some other tool minted an
    # apostrophe key into it. (setup.py's own keys are secrets.token_urlsafe, whose
    # alphabet excludes ' — only a hand-edited or third-party key can reach here.)
    if any("'" in (e if isinstance(e, str) else json.dumps(e)) for e in entries):
        return env_text, "not-quotable"

    entries[plain_at[0]] = {"key": monitoring_key, "scope": "monitoring"}
    # The single quote is emitted unconditionally (see the serialization note): a
    # double-quoted emission is invisible to python-dotenv, a $-expanding one to bash.
    rewritten = f"{prefix}='{json.dumps(entries, separators=(',', ':'))}'{terminator}"
    lines[indices[0]] = rewritten
    return "".join(lines), "converted"


def is_weak_password(password: str) -> bool:
    """Check if a password is considered weak.

    Args:
        password: Password to check

    Returns:
        True if password is weak, False otherwise
    """
    if len(password) < 16:
        return True
    return password.lower() in WEAK_PASSWORDS

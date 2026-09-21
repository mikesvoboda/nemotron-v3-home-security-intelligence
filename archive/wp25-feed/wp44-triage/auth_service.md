# WP4.4 Triage Dossier — `backend/services/auth_service.py`

**Source:** `/agents/agent-nemo2/workspace/backend/services/auth_service.py` (383 lines)
**Mutants:** 124 total → **72 killed / 52 SURVIVED** (0 null). Verdict source: `mutants/backend/services/auth_service.py.meta`
**Covering test file:** `backend/tests/unit/test_auth_service.py` (442 lines) — `backend/tests/unit/test_websocket_auth.py` only covers `decode_token` expiry indirectly.
**Diff source:** `uv run mutmut show <key>` — all 52 keys, read-only, no failures. Raw diffs cached at `/tmp/wp25/wp44-triage/authdiffs/<key>.txt`.
**Library semantics verified against the installed `python-jose` / `argon2-cffi` / stdlib** (introspection only, no repo tests run).

## Cluster table (sums to 52)

| ID | Pattern | N | Classification | Example keys |
|----|---------|---|----------------|--------------|
| C1 | `decode_token` JWT algorithm allowlist dropped (alg-confusion) | 2 | **TEST-GAP** (security) | `x_decode_token__mutmut_4`, `_7` |
| C2 | Refresh-token expiry arithmetic (`expire=None`, `+`→`-`) unasserted | 2 | **TEST-GAP** | `x_create_refresh_token__mutmut_2`, `_3` |
| C3 | `validate_api_key` guard `or`→`and` → empty-key auth bypass | 1 | **TEST-GAP** (security) | `x_validate_api_key__mutmut_1` |
| C4 | API-key entropy `token_hex(16)`→`17`/`None` unasserted | 2 | **TEST-GAP** | `x_generate_api_key__mutmut_2`, `_3` |
| C5 | JWT payload `"sub"` key + `"type"` claim value unasserted (refresh never decoded) | 10 | **TEST-GAP** | `x_create_refresh_token__mutmut_7`, `_16`; `x_create_access_token__mutmut_20` |
| C6a | `_get_jwt_secret` production gate / unset-ENVIRONMENT behavior | 3 | **TEST-GAP** (security) | `x__get_jwt_secret__mutmut_2`, `_7`, `_9` |
| C6b | `_get_jwt_secret` env-allowlist spellings + fallback-secret identity | 9 | **TEST-GAP** | `x__get_jwt_secret__mutmut_16`, `_17`, `_21` |
| C7 | Exception message-text mutations (verify_password / create_access_token / decode_token) | 16 | **LOW-VALUE** | see per-key list |
| C8 | Semantically equivalent mutations (`datetime.now(None)`, `"UTF-8"`, `algorithm=`/elision) | 7 | **EQUIVALENT** | `x_hash_api_key__mutmut_4`, `x_create_access_token__mutmut_28` |
| | **Total** | **52** | | |

TEST-GAP 29 / LOW-VALUE 16 / EQUIVALENT 7.

Per-function survivor check (matches meta exactly): `_get_jwt_secret` 13 (12 T + 1 E) · `verify_password` 7 (all L) · `create_access_token` 10 (4 T + 4 L + 2 E) · `create_refresh_token` 11 (8 T + 3 E) · `decode_token` 7 (2 T + 5 L) · `generate_api_key` 2 (T) · `hash_api_key` 1 (E) · `validate_api_key` 1 (T).

The suite kills 72/124, so basics (valid decode, tampered signature, hash round-trips, key uniqueness) are covered. The survivor blind spots are precisely two: **(a) no test ever decodes a token and asserts payload claims beyond `sub`/`exp`/`iat` presence** (→ C1, C2, C5), and **(b) `_get_jwt_secret`'s `jwt_secret is None` branch is dead under the suite** — conftest.py:107 sets `ENVIRONMENT=test` and settings carry a configured secret — so anything downstream of that branch is unexercised (→ C6a/C6b).

---

## C1 — `decode_token`: JWT algorithm allowlist dropped — TEST-GAP (SECURITY), 2

```python
# auth_service.py:217
payload = jwt.decode(token, _get_jwt_secret(), algorithms=[_JWT_ALGORITHM])
```

- `x_decode_token__mutmut_4`: `algorithms=[_JWT_ALGORITHM]` → `algorithms=None`
- `x_decode_token__mutmut_7`: `jwt.decode(token, secret, algorithms=[...])` → `jwt.decode(token, secret, )` (jose's own default for `algorithms` **is** `None`, so this is the same hole)

**Verified against installed jose:** `jose.jws._verify_signature` enforces the allowlist only `if algorithms is not None and alg not in algorithms`. With `None`, the token's own `alg` header is trusted. Round-trip probe: an HS512-signed token is rejected with `algorithms=["HS256"]` and **accepted** with `algorithms=None`. That is textbook algorithm-confusion.

**Why tests miss it:** `test_auth_service.py:248` (tampered signature) and `:234`/`:241` (invalid/malformed) only feed HS256 tokens or garbage strings; no test feeds a token with a foreign `alg` header. Highest-value gap in the module. → draft T1.

## C2 — Refresh-token expiry arithmetic unasserted — TEST-GAP, 2

- `x_create_refresh_token__mutmut_2`: `expire = datetime.now(UTC) + (...)` → `expire = None` (crash-mutant: `exp` becomes `null`; only observable by decoding — `jwt.encode` accepts it happily, decode raises `TypeError` on `int(None)`)
- `x_create_refresh_token__mutmut_3`: `+` → `-` (token expires 7 days in the **past**)

`test_create_refresh_token` (`test_auth_service.py:178`) asserts only `len(token.split(".")) == 3`. **A refresh token is never decoded anywhere in the suite**, so a past-dated or null `exp` is invisible. `_DEFAULT_REFRESH_TOKEN_EXPIRES = 7 days` (auth_service.py:36) is load-bearing for the session model. → draft T2.

## C3 — `validate_api_key` guard `or`→`and` — TEST-GAP (SECURITY), 1

```python
# auth_service.py:271-275
if not api_key or not stored_hash:
    return False
computed_hash = hash_api_key(api_key)
return hmac.compare_digest(computed_hash, stored_hash)
```

- `x_validate_api_key__mutmut_1`: `or` → `and`

Truth-tabled against the real `hmac.compare_digest` (no length-`TypeError` myth): the two versions differ **exactly** in one region — `api_key` empty **and** `stored_hash` non-empty-but-equal-to-`hash_api_key("")`. There: original `False`, mutant `True` (falls through to `compare_digest(sha256(""), sha256(""))` = True). All other guard combos (`("k","h")`, `("",hash)`, `("","")`) agree.

So the mutant is a **silent auth bypass**: if any stored record ever holds the hash of an empty key (empty-key row, import glitch), an empty `Authorization` key validates. `test_validate_api_key_empty_key:370` / `_empty_hash:376` pin the arms the *wrong* way (their cases are ones where `and` behaves identically), so the bypass case is unasserted. → draft T3.

## C4 — API-key entropy `secrets.token_hex(16)` — TEST-GAP, 2

- `x_generate_api_key__mutmut_3`: `16` → `17` (34 hex chars)
- `x_generate_api_key__mutmut_2`: `16` → `None` — **verified** `secrets.token_hex(None)` is legal and yields 64 hex chars (256-bit), not a crash

`test_generate_api_key_format:276` asserts `len(api_key) > 20`; 34- and 64-char keys both pass. The docstring contract `nemo_k1_<32_random_chars>` (auth_service.py:229) — i.e. the 128-bit entropy baseline — is unpinned. → draft T4.

## C5 — JWT payload `"sub"` / `"type"` claim unasserted — TEST-GAP, 10

- `create_access_token` (auth_service.py:154-159): `_18` key `"type"`→`"XXtypeXX"`, `_19` `"type"`→`"TYPE"`, `_20` `"access"`→`"XXaccessXX"`, `_21` `"access"`→`"ACCESS"`
- `create_refresh_token` (auth_service.py:189-194): `_7` `"sub"`→`"XXsubXX"`, `_8` `"sub"`→`"SUB"`, `_14`/`_15` `"type"` key renames, `_16`/`_17` `"refresh"` value renames

Two distinct misses: (a) `test_decode_valid_token:211` asserts `payload["sub"]` — which is why the *access* `sub` rename died — but **nothing decodes a refresh token**, so the refresh `sub` rename is invisible; (b) **no test anywhere asserts `payload["type"]`**, so all 8 `type` mutations survive on both token kinds. Repo grep: nothing currently *consumes* the claim for an access-vs-refresh decision, so the value here is pinning the token contract (defense-in-depth against token-confusion when a refresh check lands, per `websocket_auth.py:363`'s refresh flow doc) plus the outright refresh-`sub` correctness break. → draft T2.

## C6a — `_get_jwt_secret` production gate / unset-ENVIRONMENT behavior — TEST-GAP (SECURITY), 3

```python
# auth_service.py:73-85
jwt_secret = settings.jwt_secret
if jwt_secret is not None:
    return jwt_secret.get_secret_value()
environment = os.environ.get("ENVIRONMENT", "").lower()
if environment in ("test", "testing", "development"):
    return "test-jwt-secret-do-not-use-in-production-" + "x" * 32
msg = "JWT_SECRET is not configured"
raise ValueError(msg)
```

- `_2`: `jwt_secret = settings.jwt_secret` → `jwt_secret = None` — makes the configured-secret branch **dead**: every token, in every environment, is signed with the shared hardcoded fallback secret. Critical and invisible because the suite never runs with `jwt_secret is None` *and* never checks the returned value's identity.
- `_7`: default `""` → `None` → `None.lower()` raises `AttributeError` instead of `ValueError("JWT_SECRET is not configured")` when ENVIRONMENT is unset and no secret is configured (wrong failure mode, crashes instead of clean config error).
- `_9`: default arg dropped — same `AttributeError` behavior as `_7`.

→ draft T5 (configured-secret passthrough + production raises + unset-ENVIRONMENT raises ValueError).

## C6b — `_get_jwt_secret` env-allowlist spellings + fallback-secret identity — TEST-GAP, 9

- Environment spellings (4): `_16` `"testing"`→`"XXtestingXX"`, `_18` `"development"`→`"XXdevelopmentXX"` — `environment` is lowercased one line earlier, so **lowercase input fails to match** the clobbered entry and the call wrongly raises; `_17` `"testing"`→`"TESTING"`, `_19` `"development"`→`"DEVELOPMENT"` — same mechanism: the *value* is lowercased, so an uppercase tuple entry can never match. All four turn allowed environments into `ValueError` crashes. (An uppercase tuple entry is only "equivalent" for inputs that match other entries — it is a real behavior change for `ENVIRONMENT=testing`/`development`.)
- Fallback-secret identity (5): `_21` prefix `XX`-clobbered, `_22` upper-cased prefix, `_24` `"x"`→`"XXx"` (96-char tail), `_25` `"x"`→`"X"` (32-char tail → 73 vs 41 total… verified original fallback is 73 chars, `_25` yields 42), `_26` `"x"*32`→`"x"*33` (74 chars). The fallback is a signing key: changing its text or length breaks token verification across processes (restart = mass token invalidation) and weakens `_25` to a 41-char secret. The value is opaque but the *identity* is load-bearing.

All 9 are invisible under the suite for the same reason as C6a: the branch is never reached and the returned value never compared. → draft T5 (parametrized exact-match + length assertion).

## C7 — Exception message text — LOW-VALUE, 16

| Function | keys | change |
|---|---|---|
| `verify_password` | `_2` `msg`→`None`; `_3`/`_4`/`_5` msg clobber/lower/upper; `_6` `raise ValueError(None)`; `_13` `InvalidHashError(None)`; `_14` `InvalidHashError(str(None))` | 7 |
| `create_access_token` | `_2` `msg`→`None`; `_3`/`_4` msg clobber/upper; `_5` `raise ValueError(None)` | 4 |
| `decode_token` | `_8` `TokenExpiredError(None)`; `_9`/`_10`/`_11` msg clobber/lower/upper; `_12` `InvalidTokenError(None)` | 5 |

Exception **types** and raise **sites** are unchanged; only the message payload differs, and existing tests already assert the raises (`:118`, `:120`, `:195`, `:224`, `:234`). Extra verification: argon2's `InvalidHashError` message for `"not_a_valid_hash"` is the empty string in this env (probed), so `_13`/`_14` render `"None"` vs `""` — text-only noise. 709 `match=` assertions exist elsewhere in the suite, so the style permits pinning — but message casing on internal guards is not behavior; the two guard messages that could earn a `match=` pin are covered by optional draft T6 (which additionally kills the `_2`-style `msg=None` variants).

## C8 — Semantically equivalent — EQUIVALENT, 7 (incl. `_get_jwt_secret__12`)

| key | diff | why equivalent (each verified) |
|---|---|---|
| `x_create_access_token__17`, `x_create_refresh_token__13` | `datetime.now(UTC)` → `datetime.now(None)` (iat) | `now(None)` == `now()` == naive local; jose serializes via `utctimetuple()` (verified in `jwt.encode` — and `utctimetuple()` on a naive dt reports the same fields without offset math), so the epoch integer is identical |
| `x_create_refresh_token__4` | same on `expire = now(UTC) + …` | as above; `+timedelta` then `utctimetuple()` — identical epoch |
| `x_create_access_token__28`, `x_create_refresh_token__24` | `jwt.encode(..., algorithm=_JWT_ALGORITHM)` → drop kwarg | jose signature default is `algorithm='HS256'` (verified) and `_JWT_ALGORITHM == "HS256"` → byte-identical token |
| `x_hash_api_key__4` | `.encode("utf-8")` → `.encode("UTF-8")` | codec lookup case-insensitive |
| `x__get_jwt_secret__12` | default `""` → `"XXXX"` | `"XXXX".lower()` fails the `in`-tuple test exactly as `""` does; the value is never compared to `""` or used elsewhere — pure no-op |

---

## Drafted tests

**All UNVERIFIED — not yet run red/green** (harness constraint: no test execution in this lane). Style follows `backend/tests/unit/test_auth_service.py`: `pytestmark = pytest.mark.unit`, `class Test...`, `-> None`, `# pragma: allowlist secret`.

TDD procedure (one line each): run the new test against the mutant copy — it must FAIL on the mutant diff and PASS on original.

### T1 — pin the JWT algorithm allowlist → kills C1 (`decode_token__4`, `_7`)

File: `backend/tests/unit/test_auth_service.py` — add `_get_jwt_secret` to the import block at line 21 and `from jose import jwt` at top; test into `class TestJWTTokenDecoding`:

```python
    def test_decode_rejects_token_signed_with_unlisted_algorithm(self) -> None:
        """SECURITY: decode_token must reject tokens whose header names an
        algorithm outside the HS256 allowlist (algorithm-confusion defence).

        With algorithms=None python-jose trusts the token's own alg header
        instead of enforcing the allowlist, so an HS512 token would be accepted.
        """
        secret = _get_jwt_secret()
        # Sign deliberately with HS512, NOT the module's _JWT_ALGORITHM.
        forged = jwt.encode(
            {"sub": "attacker", "exp": 9_999_999_999, "type": "access"},
            secret,
            algorithm="HS512",
        )
        assert jwt.get_unverified_header(forged)["alg"] == "HS512"

        with pytest.raises(InvalidTokenError):
            decode_token(forged)
```

Red mechanism (mutants 4/7): allowlist skipped → decode returns the payload, `pytest.raises` fails. Green: jose raises `JWSError("The specified alg value is not allowed")` → wrapped as `InvalidTokenError` (verified round-trip probe).

### T2 — decode refresh + pin claims and default lifetimes → kills C2 (`create_refresh_token__2`, `_3`) + C5 (all 10)

File: same; new class:

```python
class TestJWTTokenClaims:
    """Payload-claim and default-lifetime contract.

    Pre-existing generation tests assert only 3 dot-separated parts, and no
    test ever decodes a refresh token — payload key names, the ``type`` claim
    and default lifetimes were never asserted.
    """

    def test_access_token_payload_claims(self) -> None:
        """Access token decodes to the exact claim contract."""
        token = create_access_token("claim_user_1")

        payload = decode_token(token)

        assert payload["sub"] == "claim_user_1"
        assert payload["type"] == "access"
        assert isinstance(payload["exp"], int)
        assert isinstance(payload["iat"], int)

    def test_access_token_default_lifetime_is_30_minutes(self) -> None:
        """No expires_delta → exp - iat == 30 min (_DEFAULT_ACCESS_TOKEN_EXPIRES)."""
        payload = decode_token(create_access_token("claim_user_2"))

        assert payload["exp"] - payload["iat"] == 30 * 60

    def test_refresh_token_payload_claims(self) -> None:
        """Refresh token carries the right subject and distinct ``refresh`` type."""
        token = create_refresh_token("claim_user_3")

        payload = decode_token(token)

        assert payload["sub"] == "claim_user_3"
        assert payload["type"] == "refresh"

    def test_refresh_token_default_lifetime_is_7_days_and_future(self) -> None:
        """The + → - flip and expire=None mutants must not decode cleanly."""
        import time

        token = create_refresh_token("claim_user_4")

        payload = decode_token(token)

        assert payload["exp"] - payload["iat"] == 7 * 24 * 60 * 60
        assert payload["exp"] > int(time.time())
```

Red mechanisms: `sub`/`type` renames → `KeyError` on the missing key; `_3` (past `exp`) → `decode_token` raises `TokenExpiredError` before any assert; `_2` (`exp=None`) → `int(None)` `TypeError` during validation. `exp`/`iat` arrive as ints post-`timegm` (existing `test_decode_valid_token` already treats them as present ints).

### T3 — pin the `validate_api_key` bypass region → kills C3 (`validate_api_key__1`)

File: same, `class TestAPIKeyValidation`:

```python
    def test_validate_api_key_empty_key_against_empty_key_hash_is_false(self) -> None:
        """SECURITY: an empty key must never validate, not even against the
        hash of an empty key.

        With the ``or`` guard flipped to ``and`` the (empty key, non-empty
        hash) pair skips the guard and hmac.compare_digest(sha256(""),
        sha256("")) returns True - a silent auth bypass.
        """
        empty_key_hash = hash_api_key("")

        assert validate_api_key("", empty_key_hash) is False

    def test_validate_api_key_empty_key_and_empty_hash_is_false(self) -> None:
        """Both empty short-circuits to False (guard contract documentation)."""
        assert validate_api_key("", "") is False
```

Red mechanism: mutant computes `compare_digest("e3b0c442…", "e3b0c442…")` → `True`, assert fails (verified with truth-table probe). Green: guard returns `False`. The second test alone does *not* kill the mutant (both arms identical there) — it is kept as documentation of the other guard arm.

### T4 — pin API-key entropy → kills C4 (`generate_api_key__2`, `_3`)

File: same, `class TestAPIKeyGeneration`:

```python
    def test_generate_api_key_random_part_is_exactly_32_hex_chars(self) -> None:
        """16 bytes as hex: exactly 32 chars (128-bit entropy contract).

        The old ``len(api_key) > 20`` accepted both token_hex(17) (34 chars)
        and token_hex(None) (64 chars).
        """
        api_key = generate_api_key()

        prefix = "nemo_k1_"
        assert api_key.startswith(prefix)
        random_part = api_key[len(prefix) :]
        assert len(random_part) == 32
        assert len(api_key) == len(prefix) + 32

    def test_generate_api_key_random_part_is_lowercase_hex(self) -> None:
        """token_hex() output is lowercase hex only."""
        random_part = generate_api_key()[len("nemo_k1_") :]

        assert all(c in "0123456789abcdef" for c in random_part)
```

Red: 34/64-char random part fails `== 32`. Green on original.

### T5 — pin secret resolution: configured secret, production gate, fallback identity → kills C6a (`_get_jwt_secret__2`, `_7`, `_9`) + C6b (all 9)

File: same; add `import os`, `from unittest.mock import patch`, `from pydantic import SecretStr`; new class:

```python
class TestJwtSecretResolution:
    """_get_jwt_secret must prefer the configured secret and honour the
    environment allowlist. conftest pins ENVIRONMENT=test with a configured
    secret, so the jwt_secret-is-None branch never ran under test.
    """

    _FALLBACK = "test-jwt-secret-do-not-use-in-production-" + "x" * 32

    @staticmethod
    def _patch_settings(jwt_secret: SecretStr | None):
        stub = SimpleNamespace(jwt_secret=jwt_secret)
        # auth_service imports get_settings lazily from backend.core.config
        return patch("backend.core.config.get_settings", return_value=stub)

    def test_configured_secret_is_returned_verbatim(self) -> None:
        """The configured SecretStr is unwrapped - not swapped for a default."""
        with self._patch_settings(SecretStr("configured-secret-abc")):  # pragma: allowlist secret
            assert _get_jwt_secret() == "configured-secret-abc"

    def test_missing_secret_in_production_raises(self) -> None:
        """ENVIRONMENT=production with no JWT_SECRET must fail loudly."""
        with self._patch_settings(None), patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(ValueError, match="JWT_SECRET is not configured"):
                _get_jwt_secret()

    def test_missing_secret_with_unset_environment_raises_value_error(self) -> None:
        """Unset ENVIRONMENT (default "" path) raises ValueError, not
        AttributeError - the default must be a string.
        """
        env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
        with self._patch_settings(None), patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET is not configured"):
                _get_jwt_secret()

    @pytest.mark.parametrize("environment", ["test", "testing", "development"])
    def test_fallback_secret_for_allowed_environments(self, environment: str) -> None:
        """All three allowlist spellings resolve to the identical 73-char fallback."""
        with self._patch_settings(None), patch.dict(os.environ, {"ENVIRONMENT": environment}):
            secret = _get_jwt_secret()

        assert secret == self._FALLBACK
        assert len(secret) == 73

    def test_tokens_never_signed_with_fallback_when_configured(self) -> None:
        """With a configured secret in production, the shared fallback cannot
        verify the token (kills the jwt_secret=None dead-branch mutant).
        """
        with self._patch_settings(SecretStr("prod-secret-xyz")), patch.dict(  # pragma: allowlist secret
            os.environ, {"ENVIRONMENT": "production"}
        ):
            token = create_access_token("gate_user")

            payload = jwt.decode(token, "prod-secret-xyz", algorithms=["HS256"])  # pragma: allowlist secret
            assert payload["sub"] == "gate_user"
            with pytest.raises(JWTError):
                jwt.decode(token, self._FALLBACK, algorithms=["HS256"])
```

Also add to the module import block: `from types import SimpleNamespace`, `from jose import JWTError, jwt` (jose `jwt`/`JWTError`) and `_get_jwt_secret` from `backend.services.auth_service`.

Red mechanisms per mutant: `_2` → `test_configured_secret_is_returned_verbatim` returns the fallback (fails), `test_missing_secret_in_production_raises` *passes* (wrong branch) but `test_tokens_never_signed_with_fallback_when_configured` falls into the fallback-secret ValueError; `_7`/`_9` → `None.lower()` raises `AttributeError`, `pytest.raises(ValueError)` fails; `_16`/`_18` (clobbered spellings) and `_17`/`_19` (uppercase tuple entries — value is lowercased, so uppercase can never match) → parametrized `testing`/`development` cases raise ValueError; `_21`/`_22` → `secret == _FALLBACK` fails; `_24`/`_25`/`_26` → length 96-tail/32-tail/`x`*33 breaks both equality and `len == 73` (fallback verified at 73 chars).

### T6 (optional, partial C7) — pin the two guard messages

```python
    def test_verify_password_empty_hash_message(self) -> None:
        with pytest.raises(ValueError, match="Hash cannot be empty"):
            verify_password("password", "")

    def test_create_access_token_empty_user_id_message(self) -> None:
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            create_access_token("")
```

Kills the `msg=None` and `msg`-clobber variants (6 of 16 C7 keys) at negligible cost; the case-only variants (`"hash cannot be empty"`, `"HASH CANNOT BE EMPTY"`) intentionally stay dead — case-only message text is not behavior, which is why C7 is LOW-VALUE and not TEST-GAP.

---

## Files touched by this analysis (read-only)

| Path | Why |
|---|---|
| `backend/services/auth_service.py` | original under mutation |
| `mutants/backend/services/auth_service.py.meta` | 52 surviving keys (72 killed / 0 null) |
| `mutants/mutmut-stats.json` | `tests_by_mangled_function_name` coverage map |
| `backend/tests/unit/test_auth_service.py` | primary covering test file (all 8 functions) |
| `backend/tests/conftest.py` | `ENVIRONMENT=test` at :107 — why the `None`-secret branch is dead |
| `backend/core/config.py` | `jwt_secret: SecretStr \| None` at :507, `get_settings` at :3173 |

No repo file modified. Writes: this dossier + `/tmp/wp25/wp44-triage/authdiffs/*.txt` (52 diff files).

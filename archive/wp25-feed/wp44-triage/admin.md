# WP4.4 triage dossier — `backend/api/routes/admin.py`

Wave: WP4.3 surviving-mutant feed → WP4.4 test-gap drafting. **UNVERIFIED** — nothing here was
run red/green (a live mutation run owns this machine; no pytest / no mutmut run was executed).

## Census

| | |
|---|---|
| mutant keys in `mutants/backend/api/routes/admin.py.meta` | 102 |
| killed (exit_code 1) | 72 |
| **survived (exit_code 0)** | **30** |
| not yet checked (null) | 0 |

**All 30 survivors are string-literal mutations in three functions.** There are no operator
flips, no boolean changes, no return swaps left alive in this module — the arithmetic/comparison
mutants (and every *key*-clobber and *status*-value mutant of `_get_sample_cameras`) were killed
cleanly. That concentrates the whole finding: this module's surviving set is one story about
literal payload data nobody pins.

Diff evidence came from `uv run mutmut show <key>` (read-only; worked for every key, no cache
contention). Mutant categories observed: key-clobber `X`→`XXxXX`, key-case `X`→`UPPER`,
value-clobber `"Foo"`→`"XXFooXX"`, value-case `"Foo"`→`.lower()`/`.upper()`, call→`None`.

## Cluster table (counts sum to 30)

| # | pattern | n | class | example keys |
|---|---|---|---|---|
| A | `_get_sample_cameras` camera **`id`** literal clobbered (XX…XX) or case-flipped (.upper()) — 5 of the 6 cameras × 2 variants | 10 | **TEST-GAP** | `…x__get_sample_cameras__mutmut_20` (`"backyard"`→`"XXbackyardXX"`), `…_21` (`"backyard"`→`"BACKYARD"`), `…_35` (`"garage"`→`"XXgarageXX"`) |
| B | `_get_sample_cameras` camera **`name`** literal clobbered, lower-cased, or upper-cased — all 6 cameras × 3 variants | 18 | **TEST-GAP** | `…_9` (`"Front Door"`→`"XXFront DoorXX"`), `…_10` (`"Front Door"`→`"front door"`), `…_24` (`"Backyard"`→`"XXBackyardXX"`) |
| C | `_generate_user_id` body collapsed: `return str(uuid.uuid4())` → `return str(None)` | 1 | **TEST-GAP** | `…x__generate_user_id__mutmut_1` |
| D | `require_admin_access` 403 **`detail`** message clobbered: `"Admin endpoints require ADMIN_ENABLED=true"` → `"XX…XX"` | 1 | **TEST-GAP** | `…x_require_admin_access__mutmut_7` |

Zero EQUIVALENT and zero LOW-VALUE clusters. Full key membership: A = {20,21,35,36,50,51,65,66,80,81},
B = {9,10,11,24,25,26,39,40,41,54,55,56,69,70,71,84,85,86}, C = {generate_user_id:1},
D = {require_admin_access:7}. 10 + 18 + 1 + 1 = 30.

## Why each cluster is a TEST-GAP, not EQUIVALENT/LOW-VALUE

### A + B — the sample-camera `id`/`name` values are real, load-bearing payload

`_get_sample_cameras` (backend/api/routes/admin.py:161-207) is not a logger or a display string
helper. `seed_cameras` (admin.py:331) slices it and materialises every row verbatim into ORM
objects at admin.py:355-360:

```python
camera = Camera(
    id=camera_data["id"],            # -> String PRIMARY KEY (backend/models/camera.py:107)
    name=camera_data["name"],        # -> displayed throughout the UI
    folder_path=camera_data["folder_path"],
    status=camera_data["status"],
)
```

So `"XXbackyardXX"` becomes a camera's primary key and `"XXFront DoorXX" / "front door" /
"FRONT DOOR"` becomes its display name — persisted, user-visible, and the key the timeline,
analytics and audit surfaces query on. (The *sibling* mutation types are genuinely not load
bearing and are the ones the suite already kills or should ignore: `status` values are pinned by
the assertion at test_admin.py:1126, and `folder_path` *values* are only prefix-pinned — the
fixture-vs-f-string mismatch below means full-value folder_path pinning is partly redundant with
the prefix assertion. The id/name values are the unpinned part.)

**The kill asymmetry is the proof that the oracle is accidental.** The 6 cameras are symmetric
literals, and each camera's id clobber/upper pair plus name clobber/lower/upper triple mutate
identically — yet the entire **front-door** twin set died (mutants 5 = `"XXfront-doorXX"`,
6 = `"FRONT-DOOR"`) while all **20** id/name mutants for the other five cameras survived. Same
mutation kind, opposite verdict, so the difference cannot be the mutation — it is one fixture:

- `sample_camera` (backend/tests/unit/routes/test_admin_routes.py:96-105) hardcodes
  `id="front-door"`, `name="Front Door"`.
- `test_seed_cameras_skip_existing` (:236) feeds `mock_result.all.return_value =
  [(sample_camera.id,)]` as the batch-existing row set, so the endpoint's dedup branch
  `if camera_data["id"] in existing_ids: continue` (admin.py:340) is the real oracle: mutate
  `"front-door"` → the fixture id matches nothing → `created` becomes 1 instead of 0 → the
  assertion at :253 fails.
- The fixture's `name="Front Door"` is a **decoy**: nothing ever compares it — which is exactly
  why the front-door `name` mutants (9/10/11) survived while its `id` mutants died.

That is a test that kills a constant by accident of one unrelated lookup table, for 1 of 6
cameras, via `in existing_ids`. It is not a contract assertion, and it dies the moment the
fixture or the dedup query changes shape.

The only *direct* coverage, `TestGetSampleCameras`, never reads a value:
backend/tests/unit/api/routes/test_admin.py:1084-1126 asserts `len(cameras) == 6` (:1096, :1109),
`folder_path.startswith(base)` (:1098), the key *set* (:1122), bare truthiness of `id`/`name`
(:1123-1124) and `status in ["online","offline"]` (:1126). Every one of those passes unchanged
under all 28 A/B mutants. `TestSeedCameras` (test_admin_routes.py:175-264) asserts only `created`
/ `cleared` counts and response key presence.

**Integration tier does not close this.** backend/tests/integration/test_admin_api.py:139-141
does pin `front-door`/`backyard`/`garage` — but (a) mutmut's selection is unit-only
(`pyproject.toml` `[tool.mutmut] pytest_add_cli_args_test_selection = ["backend/tests/unit"]`),
so it can never kill a mutant in this baseline, (b) it is `@pytest.mark.slow`, and (c) even there
it pins 3 of 6 ids and **zero** names.

### C — `_generate_user_id`

`str(None)` puts the literal string `"None"` into `users.id`, a `String(64)` primary key
(backend/models/user.py:41). Every subsequent `create_user` call then collides on the PK — the
second admin-created user is an `IntegrityError`, and `id` stops being a UUID. The only test
touching the function, `test_create_user_creates_non_admin_by_default`
(test_admin_routes.py:640-660), asserts `response.status_code`, `data["username"]` and
`data["is_admin"]` and never reads `data["id"]`. The mutant was generated (so the line is
covered) and the line executes — the value is simply never asserted.

### D — `require_admin_access` 403 detail

Not EQUIVALENT: the string really changes, and the tests *do* assert it — the only reason it
survived is assertion strength. test_admin_routes.py:139 asserts
`"ADMIN_ENABLED=true" in exc_info.value.detail`, and the clobbered
`"XXAdmin endpoints require ADMIN_ENABLED=trueXX"` still contains that needle. The sibling test
at :165 has the same substring hole. Exact equality is already house style elsewhere
(backend/tests/unit/core/test_database.py:2048, :2093).

## Drafted tests

### 1. `test_get_sample_cameras_exact_canonical_contract` — kills clusters A + B (28 mutants)

**Target test file:** `backend/tests/unit/api/routes/test_admin.py:1084` (append to
`class TestGetSampleCameras`, which already imports `patch` at module top, :18).

```python
    def test_get_sample_cameras_exact_canonical_contract(self) -> None:
        """Pin the EXACT sample-camera contract: id / name / folder_path / status.

        WP4.4 TEST-GAP: 28 surviving mutants here are pure string-literal edits to the
        id/name values (XX-clobber, .upper(), .lower()). They survive because the
        sibling tests above assert only len == 6, the key set, a folder_path *prefix*
        and status membership -- never a value. Those values are load-bearing:
        seed_cameras passes id straight into Camera.id, a String primary key
        (admin.py:356 -> backend/models/camera.py:107), and name is the UI's display
        label, so a clobbered literal silently renames every seeded camera.
        """
        from backend.api.routes.admin import _get_sample_cameras

        with patch("backend.api.routes.admin.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.foscam_base_path = "/export/foscam"

            cameras = _get_sample_cameras()

        # Order-sensitive on purpose: seed_cameras slices [:count] (admin.py:331), so
        # the list order IS the count<6 subset contract the integration tier leans on.
        assert cameras == [
            {
                "id": "front-door",
                "name": "Front Door",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
            },
            {
                "id": "backyard",
                "name": "Backyard",
                "folder_path": "/export/foscam/backyard",
                "status": "online",
            },
            {
                "id": "garage",
                "name": "Garage",
                "folder_path": "/export/foscam/garage",
                "status": "offline",
            },
            {
                "id": "driveway",
                "name": "Driveway",
                "folder_path": "/export/foscam/driveway",
                "status": "online",
            },
            {
                "id": "side-gate",
                "name": "Side Gate",
                "folder_path": "/export/foscam/side_gate",
                "status": "online",
            },
            {
                "id": "living-room",
                "name": "Living Room",
                "folder_path": "/export/foscam/living_room",
                "status": "offline",
            },
        ]
```

// UNVERIFIED - not yet run red/green
TDD: on any A/B mutant the equality fails on the one clobbered/case-flipped literal; on the
original all six dicts match literally, so it passes.

### 2. `test_create_user_assigns_unique_uuid_ids` — kills cluster C (1 mutant)

**Target test file:** `backend/tests/unit/routes/test_admin_routes.py:508` (append to
`class TestAdminUserManagement`, reusing its existing `admin_client` + `mock_db_session`
fixtures — same shape as the sibling at :640).

```python
    def test_create_user_assigns_unique_uuid_ids(
        self, admin_client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Two created users get distinct, real UUID ids -- never a stub value.

        WP4.4 TEST-GAP: _generate_user_id() (admin.py:1326-1328) returns
        str(uuid.uuid4()); its surviving mutant returns str(None). The only test that
        touches it (test_create_user_creates_non_admin_by_default) never reads
        data["id"]. users.id is a String(64) primary key (backend/models/user.py:41),
        so a constant generator hands every new account the same id -- the second
        create_user call dies on an IntegrityError, and "None" is not even a UUID.
        """
        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePassword123!",  # pragma: allowlist secret
        }

        # Mock "no existing username/email" -- same stub as the sibling test at :640.
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        first = admin_client.post("/api/admin/users", json=user_data)
        second = admin_client.post(
            "/api/admin/users", json={**user_data, "email": "second@example.com"}
        )

        assert first.status_code == 201
        assert second.status_code == 201
        first_id = first.json()["id"]
        second_id = second.json()["id"]

        # str(None) lands the literal "None" in the primary key.
        assert first_id != "None"
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", first_id
        )
        # The behavior that actually matters: one id per user.
        assert first_id != second_id
```

Add `import re` to the module's stdlib import block at test_admin_routes.py:10 (currently
`from datetime import datetime`).

// UNVERIFIED - not yet run red/green
TDD: on the mutant `data["id"] == "None"` trips both the `!= "None"` and the UUID `fullmatch`
assertions; on the original both POSTs return distinct v4 strings and the test passes. Two known
soft spots to watch when it is first run: (a) `mock_db_session.refresh` is a no-op AsyncMock, so
the response is built from the in-memory `User` whose `created_at` comes from the constructor
default (backend/models/user.py:79) — the sibling test at :640 already proves this returns 201;
(b) the second POST reuses the same "no duplicates" stub, so the 400 paths stay closed.

### 3. `test_admin_access_disabled_message_is_exact` — kills cluster D (1 mutant)

**Target test file:** `backend/tests/unit/routes/test_admin_routes.py:113` (append to
`class TestRequireAdminAccess`, next to the substring-weak test at :129).

```python
    def test_admin_access_disabled_message_is_exact(self) -> None:
        """The 403 body is byte-exact -- operators read it to fix their .env.

        WP4.4 TEST-GAP: test_admin_access_blocked_when_admin_disabled asserts
        `"ADMIN_ENABLED=true" in exc_info.value.detail`, which cannot see the
        XX-clobbered variant of admin.py:276 survive -- the needle still sits inside
        "XXAdmin endpoints require ADMIN_ENABLED=trueXX". Exact equality is already
        house style (backend/tests/unit/core/test_database.py:2048).
        """
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("backend.api.routes.admin.get_settings", autospec=True) as mock_settings:
            mock_settings.return_value.admin_enabled = False
            with pytest.raises(HTTPException) as exc_info:
                require_admin_access()

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Admin endpoints require ADMIN_ENABLED=true"
```

// UNVERIFIED - not yet run red/green
TDD: on the mutant the detail differs from the literal (extra `XX` on both ends) and `==` fails;
on the original it passes.

## Notes for the serial verification lane

1. **Do not "fix" the A/B cluster by strengthening the substring/decoy paths.** The `in existing_ids`
   accident at admin.py:340 must stay unmodified — cluster A's front-door mutants are already
   killed *by it*, so a test that pins the values directly is the addition, not a replacement.
   Removing `sample_camera`'s hardcoded id would *resurrect* mutants 5 and 6.
2. **Test 1's literal list is duplicated knowledge** between admin.py and the test on purpose
   (that is what a payload contract test is). If a future wave renames a sample camera, this test
   is the intended tripwire; note it in the diff so the change is deliberate, not a flake fix.
3. Cluster A/B could alternatively be killed by a `parametrize`d per-camera assertion, but the
   single `==` on the whole list also pins count and ordering for free (admin.py:331 `[:count]`),
   which the current suite pins only weakly (len==6 at test_admin.py:1096/1109). Prefer the one
   assertion.
4. `mutate_only_covered_lines = true` (pyproject.toml `[tool.mutmut]`) means these 30 sat on lines
   the unit tier executes — so all 30 are legitimately test-effectiveness gaps, not WP4.5 coverage
   gaps wearing a costume.

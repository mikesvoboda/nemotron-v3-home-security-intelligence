"""Pytest configuration for repository integration tests.

These tests are NOT serial-only anymore (M3 T4d, plan
2026-09-14-test-suite-hygiene-milestone3.md Task 4). The previous version of
this file warned against pytest-xdist because "the test_db fixture does not
provide per-worker database isolation" — that premise died with the spec-3.1
cutover: test_db resolves through get_test_db_url() -> _memo_worker_database
(backend/tests/conftest.py), which creates and points each xdist worker at its
own '<base>_gwN' database. Repository tests therefore run in parallel under
`-n 8` on exactly the isolation guarantee the rest of the integration tier
already relies on, so root conftest.py no longer stamps them with
xdist_group("repository_tests_serial") / serial.

To run these tests:
    uv run pytest backend/tests/integration/repositories/          # -n 8 via addopts
    uv run pytest backend/tests/integration/repositories/ -n0      # serial, also fine

NOTE: The pytest_collection_modifyitems hook has been consolidated into the main
backend/tests/conftest.py to avoid multiple iterations over test items.
"""

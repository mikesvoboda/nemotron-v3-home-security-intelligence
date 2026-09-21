# archive/

Staging area for artifacts judged **not load-bearing** by the 2026-09-21
directory-structure cleanup (audit + adversarial refutation, branch
`chore/artifact-cleanup`) that the owner has not yet signed off on deleting.
Nothing here is referenced by code, CI, or compose; `git mv` preserved
history. A later, deliberate pass deletes from here once each item is
confirmed dead-on-the-owner's-desk.

| Item                     | What it is                                                                                     | Pending ruling                        |
| ------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------- |
| `wp25-feed/`             | Prior agent's WP4.3/4.4 handoff + memory + triage evidence (23M, incl. 20M wp44-triage output) | delete wholesale?                     |
| `vsftpd/`                | FTP decoy-server container config; README targets a `docker-compose.yml` that no longer exists | keep as demo asset, or delete?        |
| `test_setup*.py`         | Root-level setup-script tests; outside pytest `testpaths` (never runs in CI)                   | wire into testpaths or delete?        |
| `.eta.py` + 3 dot-files  | WP4.3/4.4 mutation-triage one-off scripts (were dot-prefixed in scripts/)                      | delete?                                |
| `docs-reports/`          | Three one-session reports (load-test, network-health, 2026-02 doc review)                      | delete?                                |

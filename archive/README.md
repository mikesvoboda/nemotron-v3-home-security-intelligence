# archive/

Staging area for artifacts judged **not load-bearing** by the 2026-09-21
directory-structure cleanup (audit + adversarial refutation, branch
`chore/artifact-cleanup`) that the owner has not yet signed off on deleting.
Nothing here is referenced by code, CI, or compose; items were moved with
plain `mv` and Git records the rename at commit (rename detection preserves
history). A later, deliberate pass deletes from here once each item is
confirmed dead-on-the-owner's-desk.

| Item                     | What it is                                                                                     | Pending ruling                        |
| ------------------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------- |
| `wp25-feed/`             | Prior agent's WP4.3/4.4 handoff + memory + triage evidence (23M, incl. 20M wp44-triage output) | delete wholesale?                     |
| `vsftpd/`                | FTP decoy-server container config; README targets a `docker-compose.yml` that no longer exists | keep as demo asset, or delete?        |
| `test_setup*.py`         | Root-level setup-script tests; outside pytest `testpaths` (never runs in CI)                   | wire into testpaths or delete?        |
| `.eta.py` + 3 dot-files  | WP4.3/4.4 mutation-triage one-off scripts (were dot-prefixed in scripts/)                      | delete?                                |
| `docs-reports/`          | Three one-session reports (load-test, network-health, 2026-02 doc review)                      | delete?                                |

### Pass 2 additions (same audit, later session, 2026-09-21)

| Item | What it is | Pending ruling |
| --- | --- | --- |
| `package-lock.json` | Root JS lockfile — no CI job installs root deps (all `npm ci` run `working-directory: frontend`); stale vs package.json; legacy setup-hooks.sh path installs it | delete, or keep for local commitlint dev? |
| `Dockerfile.yolo26-benchmark` | Benchmark image build, base pinned tensorrt `24.09-py3` (two generations behind live 26.08); doc-prose citations only | delete, or refresh base? |
| `scripts/` (11 files) | One-off probes/migrations with zero consumers: deprecated e2e runner, GPU/context probes with hardcoded dev paths, superseded `download_models.sh` (live twin: `ai/download_models.sh`), NEM-3262/3339 one-time scripts, orphaned quickstart | delete? |
| `docs-media/` | VEO3 video-generation helpers (mascot/hype content, not security); live path is scripts/synthetic_data.py | delete? |
| `../docs/archive/` | 29 point-in-time docs (gap reports, TDD red-phase snapshots, NEM-numbered one-offs, metrics snapshots, 4.3MB unreferenced Grafana screenshots) | delete wholesale? |

### Gateway-consolidation follow-up additions (2026-09-22, PR-A)

| Item | What it is | Pending ruling |
| --- | --- | --- |
| `triton-model-repository/xclip_action/` | Retired X-CLIP action-recognition Triton config + model.py (migration to stgcn_action complete; models.yml keeps the provenance entry — runtime-default patch16-16-frames vs patch32 disk question still open) | delete with the provenance entry, or keep until provenance ruled? |
| `monitoring-elasticsearch/` (ilm-policy, index-template) + `scripts/init-elasticsearch.sh` | Elasticsearch log-backend leftovers; Tempo replaced the Jaeger+Elasticsearch tracing/logging stack (NEM-5545) and nothing mounts them | delete? |
| `prometheus.yml.template` | envsubst template with zero consumers (live configs are the compose-mounted files) | delete? |
| `scripts/download_models.py` | Superseded Python downloader; live twin `ai/download_models.sh` re-derived from the setup_lib rule | delete? |
| `scripts/setup_docker_override.py` | `generate_docker_override_content()` extracted from setup.py: setup.py no longer writes docker-compose.override.yml (.env is sole config truth) and the table targeted pre-consolidation containers/ports. NOTE: `test_setup.py` (this tree) imports it and stays ImportError-stale either way | delete with `test_setup*.py`? |

### Treatment of this tree (pass 2 ruling, 2026-09-22)

Archived artifacts are frozen content, not active source: the mutation-triage
evidence rule first written for `.wp25-feed/` was widened to the whole
`archive/` tree in `.pre-commit-config.yaml`, `.prettierignore`, and the ruff
`exclude` in `pyproject.toml`. Nothing here is linted, formatted, parsed, or
secret-scanned on commit — and nothing here is load-bearing for CI (the whole
point of the pass-2 CI run is to prove exactly that).

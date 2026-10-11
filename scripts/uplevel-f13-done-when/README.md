# F1.3 Done-when stack runs

The two stack runs in PR #6922's Evidence section ("`EXPOSE_LAN=true` requires
login and works after it; `EXPOSE_LAN` unset shows no login"). Contract rule 3
— tools live in the repo — so the harness the runs used lives here, not in
`/tmp`. This README is the command sheet; `docs/uplevel/operator.md` remains
the operator's role doc.

These files run a **disposable** stack of their own (compose project
`f13-done-when`, own ports, own volumes). The live stack's containers are
unreachable from it by project scoping and by port.

| file                                 | what it is                                                             |
| ------------------------------------ | ---------------------------------------------------------------------- |
| `docker-compose.f13-stack.yml`       | minimal postgres+redis+backend+frontend; EXPOSE_LAN deliberately unset |
| `docker-compose.f13-expose-true.yml` | run-1 override: sets `EXPOSE_LAN=true`                                 |
| `backend-overlay.Dockerfile`         | makes the published backend image's venv match HEAD's lock (see below) |
| `ui-drive.cjs`                       | Playwright pass: login-mode or open-mode, prints the evidence lines    |
| `ws-probe.cjs`                       | bare-Node WS handshake probe (no `ws` package needed; Node ≥ 22)       |

## Why the overlay exists

The published `backend:latest` was built at `cd3a85a9`, which predates the
B1.5 gate merge, and its venv still carries `python-jose` — mounting
working-tree `backend/` over it dies at `import jwt`. The app-runtime delta to
HEAD is one swap in `uv.lock` (python-jose out, pyjwt in), which the overlay
installs; working-tree source is mounted read-only at runtime, so the process
answering `/api/auth/setup-status` and gating `/ws` is **the tree under test**.
A full `docker build --target dev` is the alternative wherever disk allows it
(the overlay exists because the PR sandbox ran out of disk mid-run).

The overlay's `FROM` is pinned to the digest
`backend@sha256:baf7b10d…739bd5` — the exact manifest both Done-when runs
executed against — not to `:latest`, which O1.9 makes move under every merge.
To re-pin for a fresh run:
`docker buildx imagetools inspect ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest`.

## Setup (once)

```bash
cd scripts/uplevel-f13-done-when
export F13_REPO_ROOT=$(git rev-parse --show-toplevel)
export F13_POSTGRES_PASSWORD='<throwaway>'      # compose REFUSES without it
docker build -t f13-frontend:live "$F13_REPO_ROOT/frontend"
docker build -t f13-backend:live -f backend-overlay.Dockerfile .
```

## Run 1 — `EXPOSE_LAN=true`: the UI requires login, and works after it

```bash
docker compose -f docker-compose.f13-stack.yml -f docker-compose.f13-expose-true.yml up -d
# bootstrap the admin the UI will log in as (first user becomes admin):
curl -s -X POST http://127.0.0.1:18080/api/auth/register -H 'content-type: application/json' \
  -d "{\"username\":\"$F13_UI_USER\",\"email\":\"f13@example.invalid\",\"password\":\"$F13_UI_PASSWORD\"}"

curl -s http://127.0.0.1:18080/api/auth/setup-status   # {"setup_required":false,"auth_required":true}
node ws-probe.cjs                                      # closed code=4001 reason="Authentication required"

F13_MODE=auth node ui-drive.cjs                        # prints login screen / after-login / call+socket tables
```

## Run 2 — `EXPOSE_LAN` unset: no login appears

```bash
docker compose -f docker-compose.f13-stack.yml up -d --force-recreate backend
curl -s http://127.0.0.1:18080/api/auth/setup-status   # {"setup_required":false,"auth_required":false}
F13_MODE=open node ui-drive.cjs                        # prints "visited /login = never — no login"
```

`ui-drive.cjs` attaches its `framenavigated` listener **before** `goto`: the
cold-start bounce the F1.3 fix targets committed at +143ms historically, which
a listener attached after navigation would miss.

## Why there is no key-mode run (ruling 44)

This directory used to carry a third run — `ui-key-drive.cjs` plus a
`docker-compose.f13-key-mode.yml` override — that drove a browser against a
deployment with an API key baked into the bundle. It was removed, not fixed:
**ruling 44 says browsers authenticate only through the cookie login**, because
Vite inlines every `VITE_*` value into the built JavaScript and the UI has to be
served. A browser-side key is therefore a public value, and a Done-when run that
drives one would be pinning the leak back in.

The credential path still has coverage where it belongs: **non-browser clients**
(a scripted caller may offer the credential subprotocol or set `X-API-Key`) are
covered by the raw-handshake echo tests at
`backend/tests/integration/test_ws_subprotocol_echo_b1.py`. `ws-probe.cjs` stays
here as the uncredentialed-refusal probe for runs 1 and 2.

Do not re-add a browser key-mode run. The frontend guard
`frontend/src/__tests__/no-browser-api-key.test.ts` fails CI if browser code
reads a key env var or mints the credential subprotocol again.

## Teardown

```bash
docker compose -f docker-compose.f13-stack.yml -f docker-compose.f13-expose-true.yml down -v
```

## Deviations from the prod stack (deliberate)

- No GPU/AI services, no camera mounts: the login gate does not touch them,
  and prod's compose refuses to boot without them.
- Frontend served over plain HTTP on `127.0.0.1:18080` (`SSL_ENABLED=false`).
- The backend is the published image + one-package overlay, source-mounted
  read-only (above).

# B1.4 real tier on a test deployment (owner ruling 22)

The files here run B1.4's real-tier check — "the verdict engine's state goes
`unavailable` and back, `ready` and HTTP 200 never wobble" — on a **disposable test
deployment**, never the live stack. They implement owner ruling 22's five steps on top of
`docs/uplevel/operator.md`'s agent-gpu path (steps 1-6), and they add the one piece ruling 22
asked for: a **fixed backend→engine URL that survives an engine restart on a new port**, via a
small TCP proxy in the test project.

Read `docs/uplevel/operator.md` first; this README is the command sheet, that file is the role.

| file                                     | what it is                                                            |
| ---------------------------------------- | --------------------------------------------------------------------- |
| `render-test-compose.sh`                 | renders the test stack's compose config and REFUSES unsafe values     |
| `docker-compose.b14-real.yml`            | override: pins the backend to a prebuilt image, strips its GPU        |
| `vlm-proxy.mjs`                          | TCP proxy the backend dials instead of the engine (ruling 22 step 4)  |
| `vlm-mock.mjs`                           | fake engine for rehearsing the check without a GPU (demo profile)     |

## Two things this stack is NOT

- It is not the live stack: own project, own env file, own host ports (18000-18002), fresh
  volumes and camera dir. The live stack's containers are unreachable by name (project scoping)
  and by port (nothing published at a live port).
- It is not a prod run: the backend runs with `ORCHESTRATOR_ENABLED=false`, no Podman socket,
  no GPU reservation, `LOG_LEVEL=INFO`. Each of those is a deviation the rendered config shows
  you before anything starts.

## Before you start (agent-gpu path)

Run `docs/uplevel/operator.md` "The agent-gpu path" steps 1-3 first: check the weights'
`sha256sum` against the pin, build `ai-vlm:<tree>` for the commit under test, and
`agent-gpu run` the engine. Keep the line `run` printed:

```text
port 8098 -> http://host.docker.internal:<HOSTPORT>
```

`<HOSTPORT>` is what the proxy forwards to. Set `VLM_URL` to that URL and wait for
`$VLM_URL/health` to return 200 (operator.md step 3) before step A below.

## A. Render, and read the refusal conditions

From the checkout root (a worktree of the repo — the relative paths in the prod file resolve
from wherever you run this, and the override re-points every backend mount at the run's own
directories, so no live path is involved either way):

```bash
scripts/uplevel-real-tier/render-test-compose.sh \
  --project b14-<your-run-tag> --runner-url http://host.docker.internal:<HOSTPORT>
```

It creates the run's directories (`b14run/<project>/`), writes the run's env file, runs
`docker compose -p <project> -f docker-compose.prod.yml -f scripts/uplevel-real-tier/docker-compose.b14-real.yml --env-file b14run/<project>/.env.b14 config`
and writes the full render to `b14run/<project>/rendered.yml`. It **exits non-zero, without
starting anything,** when the render publishes a port outside `127.0.0.1`, publishes anything at
a live-stack port, references `host.docker.internal` on any port but the one `agent-gpu run`
printed, or leaves the Podman socket or `ORCHESTRATOR_ENABLED=true` in the backend's mounts/env.
That refusal list is operator.md step 4's rule and the owner-vet list, made mechanical.

The renderer prints the exact commands for the next steps with your project baked in.

## B. Start the test stack

Use the command the renderer printed (it has your project and env file baked in):

```bash
docker compose -p b14-<your-run-tag> -f docker-compose.prod.yml \
  -f scripts/uplevel-real-tier/docker-compose.b14-real.yml \
  --env-file b14run/<your-run-tag>/.env.b14 up -d
```

Plain `up -d` selects exactly the four services the render gates checked for: the override
resets the backend's `depends_on` (prod's waits on foscam-init + ai-gateway + go2rtc,
`docker-compose.prod.yml:639-653` at `3bf7d972` — all profile-excluded), and compose refuses
a project where a started service depends on an unselected one (measured on v5.5.1), so the
reset is what makes a careless bare `up` safe rather than broken. The readiness check never
dials the gateway anyway (`_check_shipped_ai_services_health` probes yolo26 + ai-vlm only;
the yolo leg failing just makes the `ai` block `degraded`, which does not gate `ready`).
With `depends_on` gone nothing orders the backend after postgres, and that is fine: the
backend's entrypoint retries migrations (`backend/Dockerfile:127-129`) and its own healthcheck
allows 30 s of start-up — measured, the four containers were all up and `verdict_engine` was
`available` inside ~25 s.
postgres and redis still carry their own healthchecks from the prod file.

The backend image must be present before `up` — the override pins
`${B14_BACKEND_IMAGE:-ghcr.io/mikesvoboda/nemotron-v3-home-security-intelligence/backend:latest}`;
pull it (`docker pull`) or tag one you built. The prod file's `build:` stanza is `!reset` in the
override: `up` will never build, only pull what you pointed at. If you re-run with a run dir you
deleted and recreated, the renderer writes a fresh env file (new password); to reuse one, keep
the dir — note that pre-LOG_LEVEL env files lack `LOG_LEVEL=INFO` and the render gate will
refuse to mislead you.

Wait for readiness — the backend needs roughly 30-90 s after `up` (Alembic migrations on a
fresh volume, then boot):

```bash
for i in $(seq 1 30); do
  curl -s -m 3 localhost:18000/api/system/health/ready | jq -e '.ready and .verdict_engine.state=="available"' >/dev/null 2>&1 && break
  sleep 5
done
curl -s localhost:18000/api/system/health/ready | jq '{ready, status, verdict_engine}'
# expect: ready true, status "ready", verdict_engine.state "available"
```

Pipe `curl` into `jq` (as above) rather than validating a file written with `-o`: on a refused
connection `curl -s -o file` leaves the file's OLD contents untouched, and a stale payload from
an earlier run passes every `jq -e` check — measured, it made a still-migrating backend look
"available after ~5 s" with the dead run's `since`.

`verdict_engine` is B1.4's report field (`backend/api/routes/system.py:1587-1591`). It is
`available` only when the proxy's target answered `/health` 200 — proof the wiring
backend→proxy→runner-port is live end to end.

## C. The check (B1.4's Done-when clause)

The shipped-on-`main` clause flipped the engine with compose `stop`/`start`. The test
deployment has no compose engine service to stop — the engine lives on the GB300 under
`agent-gpu` — so the **proxy** is what you take away and bring back; the backend's URL never
changes. A stopped proxy is the same readiness signal as a stopped engine: the probe dials
`http://vlm-proxy:8098/health` (`backend/api/routes/system.py:1054`), the proxy isn't listening,
and the reason becomes `ai-vlm service connection refused`
(`backend/api/routes/system.py:934`).

Take the engine away (the proxy closes its listener and kills in-flight sockets):

```bash
docker compose -p b14-<tag> -f docker-compose.prod.yml \
  -f scripts/uplevel-real-tier/docker-compose.b14-real.yml \
  --env-file b14run/<tag>/.env.b14 exec vlm-proxy sh -c 'printf off > /run/b14/mode'
```

Then sample until the flip — **two clocks gate it, both real:** the readiness payload is cached
15 s (`system.py:340`) AND after 3 consecutive probe failures the circuit breaker opens for 30 s
and answers from the cached error (`system.py:188-189`; the breaker is what makes an unreachable
engine cheap to report, so the flip is observable but not instant):

```bash
# run this every ~5 s; the flip lands within roughly 15 s (cache TTL) + 30 s (breaker window),
# and while the breaker is OPEN the reason is the breaker's cached error string, not a fresh one
until curl -s localhost:18000/api/system/health/ready | jq -e '.verdict_engine.state == "unavailable"' >/dev/null; do
  curl -s -o /dev/null -w 'probe % %{http_code} ' localhost:18000/api/system/health/ready
  curl -s localhost:18000/api/system/health/ready | jq -c '{ready, verdict_engine}'
  sleep 5
done
```

Hold the check assertions while you poll: `ready` stays `true` and the HTTP code stays 200
throughout — `ready` derives from db + redis + (prod default: gate off) pipeline workers only
(`system.py:1548-1574`); `verdict_engine` is reported and never gates (the endpoint docstring
at `system.py:1474-1481` says so on purpose).

Bring the engine back the same way — and when the runner re-admitted it on a DIFFERENT port,
re-point the proxy at the new hostport instead of touching the backend:

```bash
docker compose -p b14-<tag> … exec vlm-proxy sh -c 'printf %s <NEWHOSTPORT> > /run/b14/target'
docker compose -p b14-<tag> … exec vlm-proxy sh -c 'printf on  > /run/b14/mode'
# poll again with the loop above inverted (state == "available"); the fresh `since` in the
# payload is B1.4's transition stamp (verdict_engine_status.py:204-214 re-stamps only on a
# transition), so record it
```

The WS event is not greppable in logs (its name rides enum fields and the emitter is DEBUG-only,
as the shipped section says); the tracker's INFO transition lines are the text to grep —
prod's `LOG_LEVEL` default is WARNING (`docker-compose.prod.yml:495`), this deployment sets INFO
in its own env file, so:

```bash
docker compose -p b14-<tag> … logs backend | command grep -a "Verdict engine state changed"
# expect both directions: available -> unavailable and unavailable -> available
# (a third line, unknown -> available, is the boot stamp — the tracker starts at `unknown`)
```

(`command grep`, not the sandbox's grep alias, when you run this in an agent sandbox — the
shell function wrapping ugrep skips files it decides are binary.)

Two measured facts about the toggle, so a surprise reads correctly rather than as a mystery:

- **The relay answers 502 when its own dial fails** (target wrong or engine gone after
  accepting). This is deliberate: a bare socket reset surfaces as `httpx.ReadError`, which the
  probe's handlers (`system.py:933-941`) and `_bounded_health_check` (`system.py:1034`) both
  miss — the endpoint then 500s, and because the backend's own Docker healthcheck curls for a
  readiness 200 it starts reporting *unhealthy* (all observed at a real backend, 2026-10-08).
  A 502 reads as `reason: "ai-vlm service returned HTTP 502"` with `ready`/200 intact. If you
  ever see 500s from `/health/ready`, suspect an old proxy build, not your toggle. The backend
  catch-ladder missing `httpx.RequestError` generally is worth its own issue, not this PR.
- **A `printf off` cannot survive a container restart by accident**: the control files live in
  the run's own state dir bind-mounted at `/run/b14` (tmpfs was measured to lose them — the
  relay rebooted `on` and silently healed a running check mid-rehearsal). If you restart
  `vlm-proxy` mid-check, check `cat` of the two control files before trusting the window.

## D. Tear down (also after a failure), per operator.md step 6

```bash
docker compose -p b14-<tag> -f docker-compose.prod.yml \
  -f scripts/uplevel-real-tier/docker-compose.b14-real.yml \
  --env-file b14run/<tag>/.env.b14 down -v
agent-gpu stop vlm && agent-gpu rm vlm    # operator.md step 6
agent-gpu ps                               # must list none of your containers
```

Post the outputs on the PR per operator.md "Posting results": the head the check ran against,
the weights' `sha256sum` block, `agent-gpu status`, the image tag + `/props` `build_info` +
`model_path`, the poll transcript showing `ready`/200 unbroken across both transitions, the two
grep'd transition lines with their `since` values, and the empty `agent-gpu ps`.

## Rehearsing without a GPU (the `demo` profile)

Everything above except the engine, on any Docker:

```bash
scripts/uplevel-real-tier/render-test-compose.sh --project b14-demo --demo   # renders + prints the up command
docker compose -p b14-demo -f docker-compose.prod.yml \
  -f scripts/uplevel-real-tier/docker-compose.b14-real.yml \
  --env-file b14run/b14-demo/.env.b14 --profile mock up -d
```

`vlm-mock` answers `/health`/`/props`/`/v1/chat/completions` with canned JSON and the proxy
targets it (`VLMPROXY_TARGET=vlm-mock:8098` in the demo env the renderer writes with
`--demo`). Same poll loop, same toggle commands, same readiness payload — a rehearsal of the
command sequence ONLY: the mock is not the production pin and its numbers are not evidence.
A run against the mock must be posted as a rehearsal, never as the real tier.

## What each refusal in the renderer is protecting

- **publish not on 127.0.0.1** — the prod file binds loopback on purpose (NEM-4486); a `0.0.0.0`
  mapping in a test render means something got rewritten into reachability from the LAN.
- **live-stack ports** — the live API/db listen on 8000/5432/6379; the test stack uses
  18000-18002 so `curl localhost:18000` can only ever answer from YOUR backend.
- **`host.docker.internal` on a foreign port** — that is the live stack's loopback (operator.md:
  "The one way out is the network"). Only the runner's printed port may appear, and only as the
  proxy's target — the backend never sees it.
- **Podman socket in the render** — the prod backend mounts it for the orchestrator
  (`docker-compose.prod.yml:473`); the test run points `PODMAN_SOCKET` at a fresh dummy file the
  renderer creates, so the mount is inert and the real socket is never mounted.
- **`ORCHESTRATOR_ENABLED` not false** — prod never wires the var (only `ORCHESTRATOR_DOCKER_HOST`
  at `docker-compose.prod.yml:636`) and `config.py:134-138` defaults the orchestrator ON, so the
  run env file *cannot* disable it — the override injects it as a literal env entry. This matters
  because the orchestrator restarts any container whose name matches, in every project, through
  the mounted compose file. The gate reads the RENDER, so an injection that a later merge
  silently dropped still refuses.

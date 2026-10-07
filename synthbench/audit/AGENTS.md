# synthbench/audit — Agent Guide

## Purpose

The owner's audits. The stills audit (synthbench P5a,
`docs/superpowers/specs/2026-09-29-synthbench-p5a-vlm-replay-design.md` §4) puts an error bar on
the declared truth P5a scores against, and later measures a judge model. The clip audit
(ISS-038) is what makes a clip number publishable at all: no clip number is quoted before its
blind audit is complete.

## Files

| File             | What                                                                                                              |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| `sample.py`      | the stratified, seeded 60-still sample (`STRATA`, `allocate`, `sample`) and each still's `questions`              |
| `page.py`        | `AuditApp.handle(method, path, body, headers)`, the whole page, and `serve()`, its loopback-only server           |
| `clip_sample.py` | the clip draw (incident census, stratified benign mirror), the intended-motion classifier, and the five questions |
| `clip_page.py`   | `ClipAuditApp.handle(...)`, the blind clip page, `load_answers`, and `serve()`                                    |

The commands are `synthbench/commands/audit.py` (`python -m synthbench audit`) and
`synthbench/commands/clip_audit.py` (`python -m synthbench clip audit sample|page|bias`).

## Rules

- `handle` is pure and tested without a socket; `serve` binds `127.0.0.1` only, at the app's
  port, and passes each request's headers in.
- `POST /answer` is same-origin only: the `Host` must be `127.0.0.1:<port>` or
  `localhost:<port>`, and an `Origin`, when sent, `http://` one of those; anything else is 403
  and not logged (loopback binding does not stop another page in the owner's browser).
- The page's keys ignore Ctrl, Alt and Meta combinations (Ctrl+U must not answer `u`).
- Stills and clips are served by sample index, never by a path from the request.
- The answer log is append-only; the latest answer per (event, question) wins.
- **The clip page is blind:** its inputs are the round's `audit-draw.jsonl`, the ready
  attempt's provenance and the mp4's bytes, and never a `spec.json` — a clip's frozen motion
  names its scenario's props, which is the strongest leak the audit has. `clip_sample.py` and
  `clip_page.py` may import the taxonomy (the scenario and prop lists are the method); no
  module here may import `backend` (spec §7.1), which is why the clip report's Wilson
  intervals live in `synthbench/score/clip_audit_report.py`.

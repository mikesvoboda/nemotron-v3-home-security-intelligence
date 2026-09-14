# Stability Levels

> A shared reference for what parts of Home Security Intelligence are stable vs still evolving.

This project is moving fast. Use this page to interpret what you see in the UI and docs.

---

## Levels

| Level      | Meaning                               | What you should expect                                     |
| ---------- | ------------------------------------- | ---------------------------------------------------------- |
| **Stable** | Core workflows intended for daily use | Backward-compatible behavior, docs kept current            |
| **Beta**   | Works end-to-end, but may change      | UX refinements, config knobs may move                      |
| **WIP**    | Work in progress                      | Missing features, incomplete UX, possible breaking changes |

---

## Current Status (High-level)

| Area                                                                 | Level      | Notes                                                                            |
| -------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------- |
| **Core pipeline** (camera uploads → detections → events → dashboard) | **Stable** | Detection + LLM reasoning + event streaming are the primary path                 |
| **Operator runbooks** (deploy/monitor/backup/retention)              | **Beta**   | Commands and endpoints are accurate, but operational tooling continues to evolve |
| **Entities** page                                                    | **WIP**    | Present in the UI with a WIP badge; behavior may be incomplete                   |
| **Audit Log** page                                                   | **Beta**   | Intended for admins/power users; schema/content may expand                       |

---

## How to use this page

- If something is marked **WIP**, prefer code (`frontend/src`, `backend/api/routes`) over screenshots and treat docs as best-effort.
- If something is marked **Stable**, drift should be treated as a bug—please file an issue.

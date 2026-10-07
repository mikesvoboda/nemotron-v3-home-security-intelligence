# 4n — <Feature> Design

> Template for step 1 of every Phase 4 feature package (`10-backend.md`, feature track). Copy it to
> `docs/uplevel/4n-<feature>.md`, then fill it during the design session with the owner. A section
> that does not apply says so in one line.

**Package:** `B4.n` / `F4.n` · **Inventory row:** `F-0xx` · **R2 ruling:** complete, priority n ·
**Designed:** <date>, with the owner

## What the user can do when this is done

Two to four sentences, in the user's words. This becomes the golden path.

## Decisions

The feature's open questions and how the session settled each. Questions listed in the lane plan
(arming's are in `10-backend.md`) all appear here.

| question | decision | why |
| -------- | -------- | --- |
|          |          |     |

## Shape

- **The module behind the seam:** its name, and the domain terms it introduces. Add any new term to
  `docs/reference/glossary.md` in the build PR.
- **Its interface:** the types, the errors it raises, the invariants it keeps, its configuration.
- **Its adapters:** who calls it and through what (HTTP route, MQTT, worker). One adapter is a
  hypothetical seam; two make it real.

## What changes

Files per lane, including the cross-lane parts (README cross-lane rule).

## Tests

- **Consolidation scope:** the modules this feature touches, whose tests the test-only PR
  consolidates first (`01`, "The floor").
- **Tests through the interface:** what the new tests assert. They meet the interface bar (`01`).

## Golden path

- **Spec:** the steps it drives; Playwright for UI, `backend/tests/golden/` for an external
  interface.
- **Fake-stack scenario:** the fixture image and the verdict the fake returns.
- **Real-tier check:** what the operator runs, on a test deployment (`operator.md`).

## Privacy and security

The personal data this feature stores or shows, its retention, who can reach it when
`EXPOSE_LAN=true`, and how it is erased (OD-18, OD-19).

## Rollout and reversal

How the feature is switched on, and how it is backed out if it misbehaves.

## Done when

The package's Done when: golden path green on the fake stack, real-tier check posted, inventory row
set to **works** — plus anything specific to this feature.

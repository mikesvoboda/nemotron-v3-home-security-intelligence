<!-- Uplevel package PR. The contract this follows: docs/uplevel/README.md, "The contract". -->

## Package

- **Package:** <!-- e.g. B1.3 --> — <!-- its name in the README status table -->
- **Lane:** <!-- backend | frontend | ops | docs -->
- **Kind:** <!-- package | test-only consolidation | R2 record | real-tier follow-up -->
- **Flags:** <!-- heavy | owner | none — from the README status table -->
- **Rulings cited:** <!-- UR-n, OD-n -->

## Done when

<!-- Paste the package's "Done when" verbatim, one clause per box. Tick a box only when the
     Evidence section below shows it. -->

- [ ]

## Evidence

<!-- Every command a reviewer would rerun, with its output. -->

```text
$ <command>
<output>
```

## Real tier

<!-- Delete this section if the package needs no real-tier numbers. -->

- [ ] The command below runs against a test deployment (README vocabulary), never the live stack.
- [ ] The README status row is set to `awaiting real tier` until the operator posts the output.

```text
<the exact command for the operator>
```

## Mutation evidence

<!-- Delete unless this PR deletes, merges, moves or rewrites tests for a scored module.
     Protocol: docs/uplevel/01-mutation-policy.md, "The floor". -->

| module | baseline set | killed-or-timeout before → after | kill-loss after step 5 | accepted survivors added |
| ------ | ------------ | -------------------------------- | ---------------------- | ------------------------ |
|        |              |                                  |                        |                          |

## Cross-lane parts

<!-- Files outside your lane that this PR changes, and why (README cross-lane rule).
     Delete if none. -->

## Review

<!-- docs/uplevel/50-coordination.md, "Review and merge". -->

- [ ] **Self-review done:** a fresh-context subagent, given only the package text, this diff and this
      PR body, checked every Done-when clause, the contract, the cross-lane parts and the hot-file
      rules. Its findings and what I did about each:
- **Reviewing lane** (assigned by the coordinator):
- **Owner tier:** <!-- yes: which rule (security, production safety, destructive, plan text, questions) | no -->

## Bookkeeping

- [ ] README status row updated: `done` with this PR's number, or `awaiting real tier`
- [ ] Every `docs/vss-integration/17-action-plan.md` entry this PR closes is marked done
- [ ] Docs and `AGENTS.md` lines that describe what changed are updated
- [ ] Tests written first; hooks not bypassed; commit subjects at 72 characters or fewer

## Questions for the owner

<!-- Questions this package met that its plan does not answer (contract rule 4).
     Delete if none. -->

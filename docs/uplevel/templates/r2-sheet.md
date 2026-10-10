# R2 Ruling Sheet — <date>

> Template. `F2.2` copies it to `docs/uplevel/r2-sheet.md` and fills it from the feature inventory;
> `F2.3` finalises it. The owner rules each row in one session; the frontend lane then records the
> rulings (README, "`R2`, the Phase 2 RULING session").

Every row is written so it can be ruled from the row alone, without opening code.

## 1. Features to rule

One row per feature whose inventory status is **half-built** or **leftover**.

| column             | what goes in it                                                                              |
| ------------------ | -------------------------------------------------------------------------------------------- |
| id                 | the inventory row id (`F-012`), or the ids of a group ruled by cause (`F-216, F-217`)        |
| feature            | what a user would call it, not a component name                                              |
| status             | **half-built** or **leftover**                                                               |
| what the user sees | what happens today when someone uses it: an error, an empty panel, a false success           |
| evidence           | file:line of the stub or false success, or the failing golden path                           |
| core loop          | yes if it sits on camera → detection → verdict → alert → review, or arming; else no          |
| privacy            | the personal data it stores or shows: none, location, faces, plates, person re-ID embeddings |
| to complete        | size (S, M, L) and the modules and lanes involved                                            |
| to retire          | size (S, M, L), the tables it would drop, and anything that depends on it                    |
| recommendation     | **complete** or **retire**, and one sentence why                                             |
| ruling             | left blank for the owner                                                                     |
| priority           | left blank; the owner numbers the completes                                                  |

| id  | feature | status | what the user sees | evidence | core loop | privacy | to complete | to retire | recommendation | ruling | priority |
| --- | ------- | ------ | ------------------ | -------- | --------- | ------- | ----------- | --------- | -------------- | ------ | -------- |
|     |         |        |                    |          |           |         |             |           |                |        |          |

## 2. Open owner decisions

For each of OD-7 (threat fast paths) and OD-17 (the Triton `reid`/`threat` lane and `ai-llm-vllm`):
the facts the inventory found, the options as the register states them, a recommendation, and a
blank for the ruling. Note which feature rows each option affects.

## 3. Modules serving no feature

The modules no inventory row claims, from `O2.3` (Python) and `knip --production` (frontend).

| module | lane | lines | last meaningful commit | notes |
| ------ | ---- | ----- | ---------------------- | ----- |
|        |      |       |                        |       |

Ruling: approve the list for deletion as a whole, naming any exceptions and why.

## 4. After the session

The frontend lane's record PR copies each ruling and priority into the inventory, writes the OD
rulings into `docs/vss-integration/17-action-plan.md`, and sets `R2` to `done`.

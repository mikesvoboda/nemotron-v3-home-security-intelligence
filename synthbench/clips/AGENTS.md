# synthbench/clips — Agent Guide

## Purpose

Clip rounds (`docs/superpowers/specs/2026-09-30-synthbench-h3-clips-design.md`): MiniMax-H3
turbo clips of ready Tier B stills, kept for a future video VLM. The commands are in
`synthbench/commands/clip*.py`; this package holds their logic.

## Files

| File          | What                                                                                                                           |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `settings.py` | the clip settings recorded in each round; the H3 turbo weights' hashes                                                         |
| `sample.py`   | the draw: the even split across groups, the seeded per-lighting sample                                                         |
| `rules.py`    | the motion rules: the still rules 1-4 and rule 5, no camera moves or cuts                                                      |
| `render.py`   | the input fit, the clip check, the frame strip and the H3 graphs; `../commands/clip_render.py` drives them and the mode switch |

## Rules

- No `backend` imports (the import rule).
- A clip event never modifies its source still (clips design C4).

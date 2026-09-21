---
name: bash-c-hook-swallows-filenames
description: "pre-commit `bash -c` entry + pass_filenames formats NOTHING silently; audit any such hook for the vacuous-gate class"
metadata:
  node_type: memory
  type: reference
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-16T22:39:46.928Z
---

`entry: bash -c 'cmd'` with `pass_filenames: true` is a **silent no-op**: pre-commit appends selected filenames AFTER the command string, and `bash -c` binds the first appended word to `$0` — the command sees zero files, formatters with no paths exit 0. Fix shape: reference `"$@"` and put a sentinel word after the command string (`bash -c 'cmd "$@"' bash`). Second door: appended paths are REPO-ROOT-relative, so `cd frontend` inside the entry needs `${@#frontend/}` rebasing — else path tools match nothing and `--ignore-unknown` makes even that rc=0.

Proof commands: `pre-commit run <hook> --files <known-drifting-file>` must CHANGE the file (not just print Passed); a text-parsed config guard (don't import PyYAML — undeclared deps get pruned by uv sync). Live instance: repo's prettier-frontend was vacuous since inception (fixed 91e3ee54, 2026-09-16); validate's whole-tree `format:check` was the only real gate, and CI has none.

Related: [[case-name-path-trap]], [[pytest-quiet-traps]].

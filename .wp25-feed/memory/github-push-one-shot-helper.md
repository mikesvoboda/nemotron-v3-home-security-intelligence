---
name: github-push-one-shot-helper
description: "Sandbox proxy's git credential injection can stay inert even with a valid GH_TOKEN secret — push via one-shot credential helper instead of assuming bare push works"
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T12:45:54.250Z
---

On 2026-09-15 the GitHub secret WAS set (`GH_TOKEN` = a real token, `api.github.com/user` → 200),
yet `git push` still failed with CLAUDE.md's "could not read Username" signature — the sandbox
proxy's transparent injection never engaged (an explicit `http.https://github.com.extraHeader`
also failed; the trace showed a 401 → prompt path). What worked:

```
GIT_TERMINAL_PROMPT=0 git -c credential.helper="!f() { echo username=x-access-token; echo \"password=\$GH_TOKEN\"; }; f" push origin <branch>
```

(one-shot, nothing persisted to config/credentials; remote's dependabot banner means success).

**Why:** CLAUDE.md promises "the proxy takes care of it" — true only when injection engages;
treat the Username error as *either* missing secret *or* inert injection, and check
`curl -H "Authorization: token $GH_TOKEN" api.github.com/user` before touching anything.

**How to apply:** diagnose with the API call first; if 200, push via the one-shot helper
rather than asking the owner to push from their terminal. Related: [[sandbox-recreate-vs-reboot]]
(recreation also wipes secrets/env).

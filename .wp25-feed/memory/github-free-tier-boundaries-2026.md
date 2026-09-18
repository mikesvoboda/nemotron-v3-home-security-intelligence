---
name: github-free-tier-boundaries-2026
description: "Verified 2026 free-tier boundaries for public repos: GitHub Models retired 2026-07-30, Copilot bills AI credits, Actions/LFS/limits specifics — plus the CI pitfall that `secrets` is invalid in step-level if"
metadata:
  node_type: memory
  type: reference
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-16T01:40:29.005Z
---

Verified against GitHub's own changelog/docs + live API probes on 2026-09-15 (personal Free
account, PUBLIC repo — the cheapest surface: standard Linux/Windows/macOS Actions minutes are
free *and unlimited* on public repos).

- **GitHub Models: fully retired 2026-07-30.** Playground, catalog, inference API, BYOK all gone;
  `models.github.ai` returns **410** with stale "brownout" wording — treat as permanent.
  `github/gh-models` extension **archived 2026-09-04**. Old `openai/<model>` IDs are dead
  regardless. There is **no free GitHub-hosted LLM inference left** — no plan change fixes it.
  A 200 from `api.githubcopilot.com/models` is the *Copilot* surface (metered successor), not a
  free CI path: Copilot moved to AI credits (1 credit = $0.01), Copilot code review ~$0.05–1
  "Lite" / $0.25–5 "Balanced" per review and began consuming Actions minutes 2026-06-01.
- **Always billed even on public repos:** larger runners (`ubuntu-24.04-16core`) — and those
  labels need Team/Enterprise anyway, so a personal account can't provision them.
- **Free on public repos:** Actions standard runners, CodeQL, secret scanning + push protection,
  all Dependabot modes, self-hosted runners, environments/protected environments, Pages
  (soft limits, no overage billing). Private-only paywalls don't apply.
- **Git LFS Free tier is now 10 GiB storage + 10 GiB bandwidth/mo** (the old 1 GiB/1 GiB figures
  are stale); pre-paid data packs removed, metered after, blocked-not-charged with no card.
- **Actions limits that throttle big matrices:** 20 concurrent jobs on Free (5 macOS), 256 matrix
  jobs/run, 6h GitHub-hosted job timeout, 35-day run, **1,000 `GITHUB_TOKEN` API calls/hr/repo**.
- **Dependabot merge-queue treadmill (measured 2026-09-16):** with `strict: true` branch protection
  (context `CI Gate (Required Checks)`), every merge flips sibling PRs BEHIND, and GitHub's own
  "update branch" never fires on months-stale dependabot branches — armed auto-merge idles forever.
  Fix WITHOUT force-push (force-pushing a dependabot branch once auto-closed PR #6399):
  `gh api --method PUT repos/<repo>/pulls/<n>/update-branch` — server-side merge of main, keeps
  auto-merge armed, safe for dependabot branches. Expect one call per sibling after every merge;
  batch them right after each merge notification.
- **CI pitfall that cost us months:** `secrets` is **not** a valid context in step-level `if`.
  `if: ... && secrets.FOO` makes Actions reject the whole workflow at parse time → failing run,
  **0 jobs, no log** (so `--log-failed` returns nothing). Guard in a job-level `if` or let the
  script fail.
- docs.github.com was restructured — many familiar paths 404; verify a path via
  `https://docs.github.com/api/article/body?pathname=<path>`.

**How to apply:** for billing questions on this repo, the answer is almost always "public repo +
standard runner = free"; suspect LFS bandwidth, larger runners, Marketplace paid plans, and
anything touching Copilot/Models. Related: [[github-push-one-shot-helper]],
[[vdd-inode-ceiling]].

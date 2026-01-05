# Linear-GitHub Integration Setup Guide

This document explains how to set up bidirectional sync between Linear and GitHub Issues.

## Table of Contents

- [Current State](#current-state)
- [Solution 1: Native Linear GitHub Integration](#solution-1-native-linear-github-integration)
- [Solution 2: Audit and Bulk Close Script](#solution-2-audit-and-bulk-close-script)
- [Solution 3: Automated Sync Workflow](#solution-3-automated-sync-workflow)
- [Solution 4: Real-time Webhook Sync](#solution-4-real-time-webhook-sync)
- [Recommended Workflow](#recommended-workflow)

## Current State

| System               | Count | Notes                          |
| -------------------- | ----- | ------------------------------ |
| GitHub Issues (Open) | ~971  | Created before Linear adoption |
| Linear Tasks         | ~1260 | Primary tracking system        |

**Problem:** When Linear tasks are marked "Done", corresponding GitHub issues remain open because there's no sync mechanism.

## Solution 1: Native Linear GitHub Integration

Linear has a built-in GitHub integration that provides automatic linking and status updates.

### Setup Steps

1. **Go to Linear Settings**

   ```
   Settings → Integrations → GitHub
   ```

2. **Install the Linear GitHub App**

   - Click "Add to GitHub"
   - Select the repository: `mikesvoboda/nemotron-v3-home-security-intelligence`
   - Grant required permissions:
     - Read access to code and metadata
     - Read/write access to issues and pull requests

3. **Configure Auto-Linking**
   In Linear Settings → Integrations → GitHub → Settings:

   - Enable "Auto-link issues from commits and PRs"
   - Enable "Auto-create branch from issue"

4. **Configure Status Automation** (per team)
   Go to Team Settings → Workflow → Automations:
   - PR opened → Move to "In Progress"
   - PR merged → Move to "Done"
   - PR closed without merge → Move to "Backlog"

### Magic Words for Commits

Use these keywords in commit messages or PR descriptions to link to Linear:

| Keyword            | Effect                                |
| ------------------ | ------------------------------------- |
| `NEM-123`          | Links commit/PR to issue              |
| `Fixes NEM-123`    | Links and closes issue when PR merges |
| `Closes NEM-123`   | Links and closes issue when PR merges |
| `Resolves NEM-123` | Links and closes issue when PR merges |

**Example commit message:**

```
feat: add entity re-identification

Fixes NEM-1260

- Add redis_client to EnrichmentPipeline
- Enable re-id during detection pipeline
```

### Branch Naming Convention

Linear can auto-create branches. Use this format for manual branches:

```
<username>/nem-<number>-<slug>
```

Example: `michaelssvoboda/nem-1260-entities-page-empty`

## Solution 2: Audit and Bulk Close Script

Use the audit script to identify GitHub issues that should be closed.

### Prerequisites

```bash
# Set API keys
export LINEAR_API_KEY="lin_api_..."  # From linear.app/settings/api  pragma: allowlist secret
export GITHUB_TOKEN="ghp_..."         # Or use: gh auth login
```

### Usage

```bash
# Audit only (dry run) - see what would be closed
python scripts/audit-linear-github-sync.py

# Export to CSV for review
python scripts/audit-linear-github-sync.py --output csv > audit-results.csv

# Export to JSON
python scripts/audit-linear-github-sync.py --output json > audit-results.json

# Adjust similarity threshold (default: 80%)
python scripts/audit-linear-github-sync.py --min-similarity 90

# Limit number of issues to process
python scripts/audit-linear-github-sync.py --limit 100
```

### Bulk Close Matched Issues

After reviewing the audit results:

```bash
# Close issues that match Done Linear tasks
python scripts/audit-linear-github-sync.py --close-matched --no-dry-run
```

### Output Example

```
================================================================================
AUDIT SUMMARY
================================================================================
Total GitHub issues:        971
  - Should close (Done):    523
  - Keep open (In Progress):248
  - No Linear match:        200

--------------------------------------------------------------------------------
ISSUES TO CLOSE (Linear task is Done)
--------------------------------------------------------------------------------
GH#      Similarity   Linear ID    Title
--------------------------------------------------------------------------------
#1413     95.2%      NEM-1260     Entities page empty: EnrichmentPipeline m..
#1412     98.1%      NEM-1259     Analytics page empty: Baseline updates no..
...
```

## Solution 3: Automated Sync Workflow

A GitHub Actions workflow runs daily to audit and optionally close issues.

### Workflow Location

`.github/workflows/linear-github-sync.yml`

### Features

- **Scheduled**: Runs daily at 6 AM UTC
- **Manual trigger**: Run on-demand with custom settings
- **Webhook support**: Can be triggered by Linear webhooks

### Manual Trigger

1. Go to Actions → "Linear-GitHub Issue Sync"
2. Click "Run workflow"
3. Configure options:
   - `dry_run`: true/false
   - `min_similarity`: 0-100

### Required Secrets

Add these to repository secrets (Settings → Secrets → Actions):

| Secret           | Description                     |
| ---------------- | ------------------------------- |
| `LINEAR_API_KEY` | Linear API key from settings    |
| `GITHUB_TOKEN`   | Auto-provided by GitHub Actions |

## Solution 4: Real-time Webhook Sync

For immediate sync when Linear issues change, set up a webhook.

### Option A: Linear Webhook to GitHub Dispatch

1. **Create webhook in Linear**

   - Go to Settings → Integrations → Webhooks
   - Add webhook URL: `https://api.github.com/repos/mikesvoboda/nemotron-v3-home-security-intelligence/dispatches`
   - Select events: Issue state changes

2. **Configure webhook payload**

   ```json
   {
     "event_type": "linear-issue-updated",
     "client_payload": {
       "issue_identifier": "{{issue.identifier}}",
       "issue_title": "{{issue.title}}",
       "status": "{{issue.state.name}}"
     }
   }
   ```

3. **Add Linear webhook secret**
   The webhook needs a GitHub PAT with `repo` scope in the Authorization header.

### Option B: Self-hosted Webhook Receiver

For more control, deploy a webhook receiver:

```python
# Example: backend/api/routes/webhooks.py
from fastapi import APIRouter, Request, HTTPException
import subprocess

router = APIRouter()

@router.post("/linear-webhook")
async def linear_webhook(request: Request):
    payload = await request.json()

    # Verify webhook signature (implement based on Linear docs)

    if payload.get("type") == "Issue" and payload.get("action") == "update":
        issue = payload.get("data", {})
        if issue.get("state", {}).get("name") == "Done":
            # Trigger GitHub issue closure
            identifier = issue.get("identifier")
            title = issue.get("title")
            # ... close matching GitHub issue

    return {"status": "ok"}
```

## Recommended Workflow

### Initial Cleanup

1. **Run audit to assess the situation:**

   ```bash
   python scripts/audit-linear-github-sync.py --output csv > audit.csv
   ```

2. **Review the CSV** to ensure matches are correct

3. **Close matched issues in batches:**

   ```bash
   # Close first 100 high-confidence matches
   python scripts/audit-linear-github-sync.py \
     --close-matched \
     --no-dry-run \
     --min-similarity 95 \
     --limit 100
   ```

4. **Repeat with lower thresholds** after manual review

### Ongoing Sync

1. **Enable native Linear GitHub integration** (Solution 1)
2. **Use magic words** in commits (`Fixes NEM-XXX`)
3. **Run weekly audit workflow** to catch any drift

### Best Practices

- Always use Linear issue identifiers in commit messages
- Create branches from Linear issues when possible
- Review audit results before bulk closing
- Keep `min_similarity` at 80%+ to avoid false matches

## Troubleshooting

### "No LINEAR_API_KEY set"

Get your API key from: https://linear.app/settings/api

### "gh CLI not found"

Install GitHub CLI:

```bash
# macOS
brew install gh

# Ubuntu
sudo apt install gh

# Then authenticate
gh auth login
```

### Low Match Rate

If many GitHub issues don't match Linear tasks:

- They may be duplicates or stale issues
- Consider closing them manually with a standard message
- Or bulk close with:
  ```bash
  gh issue list --state open --limit 500 --json number | \
    jq -r '.[].number' | \
    xargs -I {} gh issue close {} --reason "not_planned" \
      --comment "Closing: Issue tracking moved to Linear"
  ```

## References

- [Linear GitHub Integration Docs](https://linear.app/docs/github-integration)
- [Linear API Documentation](https://developers.linear.app/)
- [GitHub CLI Manual](https://cli.github.com/manual/)

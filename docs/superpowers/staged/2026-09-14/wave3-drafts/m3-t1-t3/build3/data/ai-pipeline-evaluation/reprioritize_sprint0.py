#!/usr/bin/env python3
"""Reprioritize validation-discovered blockers as Sprint 0."""

import sys

sys.path.insert(0, "/home/msvoboda/.claude/skills/linear-python")

from linear_client import LinearClient

client = LinearClient()

# Sprint 0 items — all P0/P1 blockers from validation
updates = [
    # P0 blockers
    {
        "id": "NEM-5574",
        "title": "[Sprint 0] Fix enrich-lt 422 schema mismatch — person-reid, pose-analyze, threat-detect 100% broken",
        "priority": 1,
    },
    {
        "id": "NEM-5575",
        "title": "[Sprint 0] Fix Weather Classification model loading — missing preprocessor_config.json",
        "priority": 1,
    },
    {
        "id": "NEM-5576",
        "title": "[Sprint 0] Fix SegFormer Clothing model loading — missing preprocessor_config.json",
        "priority": 1,
    },
    # P1 cascading from P0
    {
        "id": "NEM-5577",
        "title": "[Sprint 0] Fix enrichment pipeline cascading timeout from enrich-lt 422 errors",
        "priority": 1,
    },
    {
        "id": "NEM-5578",
        "title": "[Sprint 0] Fix detection/analysis worker heartbeat failures from enrichment blocking",
        "priority": 1,
    },
    # P1 pipeline coverage
    {
        "id": "NEM-5579",
        "title": "[Sprint 0] Fix seed camera routing — only 1 camera receives events",
        "priority": 1,
    },
    {
        "id": "NEM-5580",
        "title": "[Sprint 0] Update NEM-5554 Florence-2 fix with full processor init findings",
        "priority": 1,
    },
]

print(  # noqa: T201 # noqa: T201 # noqa: T201
    f"Reprioritizing {len(updates)} issues to Sprint 0...\n"
)

for update in updates:
    internal_id = client._resolve_issue_id(update["id"])
    escaped_title = update["title"].replace('"', '\\"')

    mutation = f'''
    mutation {{
        issueUpdate(id: "{internal_id}", input: {{
            title: "{escaped_title}",
            priority: {update["priority"]}
        }}) {{
            success
            issue {{ identifier title }}
        }}
    }}
    '''
    try:
        result = client._query(mutation)
        issue = result["issueUpdate"]["issue"]
        print(  # noqa: T201 # noqa: T201
            f"  {issue['identifier']}: {issue['title'][:72]}"
        )
    except Exception as e:
        print(  # noqa: T201 # noqa: T201
            f"  FAILED {update['id']}: {e}"
        )

print(  # noqa: T201 # noqa: T201 # noqa: T201
    "\nDone! Sprint 0 blockers reprioritized."
)

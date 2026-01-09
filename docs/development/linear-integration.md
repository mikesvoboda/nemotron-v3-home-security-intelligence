# Linear Integration Guide

This document covers Linear MCP tools, workflow state UUIDs, and usage examples for issue management.

## Overview

This project uses **Linear** for issue tracking:

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Team ID:** `998946a2-aa75-491b-a39d-189660131392`

Issues are organized with:

- **Priorities:** Urgent, High, Medium, Low (mapped from P0-P4)
- **Labels:** phase-1 through phase-8, backend, frontend, tdd, etc.
- **Parent/sub-issues:** Epics contain sub-tasks

## Linear MCP Tools

Claude Code has access to Linear MCP tools for issue management:

| Tool                         | Purpose                                  |
| ---------------------------- | ---------------------------------------- |
| `mcp__linear__list_issues`   | List issues with optional filters        |
| `mcp__linear__get_issue`     | Get detailed info about a specific issue |
| `mcp__linear__create_issue`  | Create a new issue                       |
| `mcp__linear__update_issue`  | Update an existing issue                 |
| `mcp__linear__search_issues` | Search issues by text query              |
| `mcp__linear__list_teams`    | List all teams in workspace              |
| `mcp__linear__list_projects` | List all projects                        |

## Workflow State UUIDs (NEM Team)

**IMPORTANT:** When updating issue status, you must use the workflow state UUID, not the status name.

| Status          | UUID                                   | Type      |
| --------------- | -------------------------------------- | --------- |
| **Backlog**     | `88b50a4e-75a1-4f34-a3b0-598bfd118aac` | backlog   |
| **Todo**        | `50ef9730-7d5e-43d6-b5e0-d7cac07af58f` | unstarted |
| **In Progress** | `b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7` | started   |
| **In Review**   | `ec90a3c4-c160-44fc-aa7e-82bdca77aa46` | started   |
| **Done**        | `38267c1e-4458-4875-aa66-4b56381786e9` | completed |
| **Canceled**    | `232ef160-e291-4cc6-a3d9-7b4da584a2b2` | canceled  |
| **Duplicate**   | `3b4c9a4b-09ba-4b61-9dbb-fedbd31195ee` | canceled  |

## Linear MCP Usage Examples

### List Issues

```python
# List all Todo issues for NEM team
mcp__linear__list_issues(teamId="998946a2-aa75-491b-a39d-189660131392", status="Todo")
```

### Get Issue Details

```python
# Get details for a specific issue
mcp__linear__get_issue(issueId="NEM-123")
```

### Search Issues

```python
# Search for issues by text
mcp__linear__search_issues(query="prometheus metrics")
```

### Update Issue Status

```python
# Update issue status to "In Progress"
mcp__linear__update_issue(
    issueId="NEM-123",
    status="b88c8ae2-2545-4c1b-b83a-bf2dde2c03e7"  # In Progress UUID
)

# Close an issue (mark as Done)
mcp__linear__update_issue(
    issueId="NEM-123",
    status="38267c1e-4458-4875-aa66-4b56381786e9"  # Done UUID
)
```

### Update Issue Description

```python
# Update issue description
mcp__linear__update_issue(
    issueId="NEM-123",
    description="## Updated description\n\nNew content here..."
)
```

### Create New Issue

```python
# Create a new issue
mcp__linear__create_issue(
    title="New feature request",
    teamId="998946a2-aa75-491b-a39d-189660131392",
    description="Description in markdown",
    priority=2  # 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
)
```

## Querying Workflow States

If you need to refresh or verify workflow state UUIDs, use the Linear GraphQL API:

```bash
curl -s -X POST https://api.linear.app/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: $LINEAR_API_KEY" \
  -d '{"query": "{ workflowStates { nodes { id name type team { key } } } }"}'
```

## Linear URLs

```bash
# View active issues
https://linear.app/nemotron-v3-home-security/team/NEM/active

# Filter by label (e.g., phase-1)
https://linear.app/nemotron-v3-home-security/team/NEM/label/phase-1
```

## Related Documentation

- [Session Workflow](../../CLAUDE.md#session-workflow) - How to claim and complete tasks
- [Task Execution Order](../../CLAUDE.md#task-execution-order) - Phase-based task organization

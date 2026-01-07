# .beads Directory - Agent Guide

## Purpose

This directory contains legacy issue tracking data from the Beads issue tracker. **This system has been deprecated and replaced by Linear.** All issues have been migrated to Linear workspace.

**Status:** DEPRECATED - Do not add new content to this directory.

## Directory Contents

```
.beads/
  AGENTS.md         # This file
  README.md         # Beads issue tracker documentation
  config.yaml       # Beads configuration
  issues.jsonl      # Issue data in JSONL format (1.2MB)
  metadata.json     # Metadata for issue tracking
  .gitignore        # Git ignore rules for beads
```

## Key Files

### issues.jsonl

**Purpose:** Historical issue data from Beads issue tracker.

**Size:** ~1.3 MB (1,289,739 bytes)

**Format:** JSON Lines - one issue per line

**Status:** ARCHIVED - Data migrated to Linear

### config.yaml

**Purpose:** Beads configuration file defining issue structure and workflow.

**Contents:**

- Issue templates
- Workflow states
- Label definitions
- Field configurations

### Migration

All issues from this directory have been migrated to Linear using:

```bash
./scripts/migrate_beads_to_linear.py
```

**Migration Status:** COMPLETE

- All issues transferred to Linear workspace
- Issue IDs mapped from Beads to Linear format (NEM-XXX)
- Labels and priorities preserved
- Historical data maintained in this directory for reference

## Current Issue Tracking

**Use Linear instead:**

- **Workspace:** [nemotron-v3-home-security](https://linear.app/nemotron-v3-home-security)
- **Team:** NEM
- **Team ID:** `998946a2-aa75-491b-a39d-189660131392`
- **Active issues:** https://linear.app/nemotron-v3-home-security/team/NEM/active

## Why This Directory Exists

This directory is kept for:

1. **Historical reference** - Original issue tracking data
2. **Audit trail** - Complete history of project planning
3. **Backup** - In case of Linear data loss

**Do not add new issues here.** Use Linear for all new issue tracking.

## Related Files

- `/scripts/migrate_beads_to_linear.py` - Migration script
- `/CLAUDE.md` - Current Linear workflow documentation
- `/.github/workflows/linear-*.yml` - Linear-GitHub integration workflows

## Notes for AI Agents

- Do NOT create new issues in this directory
- Do NOT modify existing files in this directory
- Refer to Linear for all current issue tracking
- If you need historical context, you can read `issues.jsonl` but treat it as read-only
- This directory may be removed in future cleanup operations

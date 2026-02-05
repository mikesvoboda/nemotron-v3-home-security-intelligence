---
name: incremental-fixes
description: Use when debugging complex issues or when previous fix attempts have failed. Reduces "excessive changes" by enforcing one-change-at-a-time discipline with verification between each step.
---

# Incremental Fixes

**Use this skill to prevent "excessive changes" friction** - the pattern where many edits are made but only partial outcomes are achieved.

## The Problem

From insights analysis:

- 474 sessions flagged "excessive_changes" as friction
- High activity (many edits) but only "partially_achieved" outcomes
- Multiple changes before testing = can't isolate what worked

## The Solution

**One change. Verify. Next change.**

### Default Prompt Template

When starting any debugging or fix task, use this prompt:

```
Let's fix this incrementally. Propose ONE change, I'll approve it, then
we verify it works before moving to the next. Start with the most likely
root cause.
```

## The Process

### Step 1: Diagnose First

Before ANY changes:

1. Read error messages completely
2. Identify the most likely root cause
3. Explain your hypothesis

**Do not propose fixes yet.**

### Step 2: Propose Single Change

Propose exactly ONE change:

- What file/line to change
- What the change is
- Why this addresses the root cause
- How to verify it worked

**Wait for approval before implementing.**

### Step 3: Implement and Verify

After approval:

1. Make the single change
2. Run verification (tests, health checks, etc.)
3. Report result: worked or didn't work

### Step 4: Iterate or Complete

- **If it worked:** Ask if more changes needed, or declare complete
- **If it didn't work:** Return to Step 1 with new information, propose different change

**Never stack multiple unverified changes.**

## Red Flags - STOP

If you catch yourself:

- Proposing multiple changes at once
- Making changes without verification between
- "While I'm here, let me also..."
- "These are related, so I'll do them together"

**STOP. Return to single-change discipline.**

## When to Use

- Debugging any issue
- After a fix attempt failed
- When the problem is unclear
- When previous session ended with "confused" state
- When you've already tried 2+ things that didn't work

## Relationship to Other Skills

This skill complements:

- **`superpowers:systematic-debugging`** - Use that for root cause investigation
- **`/platform-healthcheck`** - Use that for verification steps
- **`/linear-python`** - Use that to checkpoint progress between changes

## Why This Works

| Without Incremental                    | With Incremental                             |
| -------------------------------------- | -------------------------------------------- |
| 5 changes, something broke, which one? | 1 change, verify, know exactly what happened |
| "Partially achieved"                   | Clear pass/fail per change                   |
| Can't resume mid-debug                 | Each change is a checkpoint                  |
| Cascading issues hidden                | Cascading issues caught immediately          |

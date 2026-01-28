# Getting Started Directory - Agent Guide

## Purpose

This directory contains guides for getting the Home Security Intelligence system up and running. These guides focus on installation, first-run experience, initial user onboarding, and upgrading.

> **Relationship with docs/user/:**
>
> - `docs/getting-started/` covers **installation and initial setup** (one-time tasks)
> - `docs/user/` covers **ongoing usage** (day-to-day operations)
> - The quick-start and tour guides here are referenced from the user hub
> - Detailed UI feature documentation lives in `docs/ui/` and is linked from both hubs

## Directory Contents

```
getting-started/
  AGENTS.md          # This file
  README.md          # Getting started hub and index
  first-run.md       # First run guide
  installation.md    # Installation guide
  prerequisites.md   # System prerequisites
  quick-start.md     # Quick start guide
  tour.md            # Product tour and walkthrough
  upgrading.md       # Upgrade guide
```

## Key Files

### prerequisites.md

**Purpose:** System prerequisites and requirements.

**Topics Covered:**

- Hardware requirements (CPU, RAM, GPU)
- Operating system support
- Required software (Podman, Python, Node.js)
- Network requirements
- Camera compatibility (Foscam FTP)

**When to use:** Before starting installation, verifying system compatibility.

### installation.md

**Purpose:** Step-by-step installation guide.

**Topics Covered:**

- Clone repository
- Configure environment variables
- Start services with Podman
- Verify installation
- Initial configuration

**When to use:** Installing the system for the first time.

### first-run.md

**Purpose:** Guide for the first run experience.

**Topics Covered:**

- Accessing the dashboard
- Adding cameras
- Understanding the initial state
- Demo mode and sample data
- Basic navigation
- Next steps

**When to use:** After installation, getting oriented with the system.

### upgrading.md

**Purpose:** Guide for upgrading to new versions.

**Topics Covered:**

- Backup procedures before upgrade
- Pulling latest changes
- Database migrations
- Container updates
- Rollback procedures
- Breaking changes and migration notes

**When to use:** Upgrading to a new version of the system.

### quick-start.md

**Purpose:** Condensed quick start guide for experienced users.

**Topics Covered:**

- Minimal setup steps
- Essential configuration
- Quick verification

**When to use:** Fast setup for experienced users.

### tour.md

**Purpose:** Product tour and system walkthrough.

**Topics Covered:**

- Dashboard overview
- Feature walkthrough
- Navigation guide
- Key concepts

**When to use:** Learning the system after installation.

## Recommended Reading Order

1. **quick-start.md** or **prerequisites.md** - Get started quickly or verify requirements
2. **installation.md** - Install the system
3. **first-run.md** - Get oriented with the dashboard
4. **tour.md** - Learn the system features
5. Continue to **docs/ui/** for detailed UI documentation

## Target Audience

| Audience           | Needs                        | Primary Documents                 |
| ------------------ | ---------------------------- | --------------------------------- |
| **New Users**      | Quick setup and orientation  | All files                         |
| **Existing Users** | Upgrading to new version     | upgrading.md                      |
| **System Admins**  | Deployment and prerequisites | prerequisites.md, installation.md |

## Related Documentation

| Resource                                   | Description                      | Relationship                           |
| ------------------------------------------ | -------------------------------- | -------------------------------------- |
| **docs/AGENTS.md**                         | Documentation directory overview | Parent index                           |
| **docs/user/**                             | User documentation hub           | Links here for onboarding guides       |
| **docs/ui/**                               | UI page documentation            | Detailed feature docs (linked by both) |
| **docs/operator/**                         | Operator/admin documentation     | Post-setup system administration       |
| **docs/reference/config/env-reference.md** | Configuration reference          | Detailed config options                |

### Content Ownership

To avoid duplication between docs/getting-started/ and docs/user/:

| Content Type               | Location              | Reason                        |
| -------------------------- | --------------------- | ----------------------------- |
| Installation/prerequisites | Here                  | One-time setup tasks          |
| Quick start/product tour   | Here                  | First-time user onboarding    |
| Upgrading                  | Here                  | Version update procedures     |
| Day-to-day usage hub       | `docs/user/README.md` | Ongoing reference for users   |
| Detailed UI guides         | `docs/ui/`            | Shared by both hubs via links |

# Contributing Directory - Agent Guide

## Purpose

This directory contains contribution guidelines, developer tool integrations, and workflow documentation for the Home Security Intelligence project. It provides setup guides for AI-assisted development tools and project integration patterns.

## Target Audience

- New contributors setting up their development environment
- Developers integrating AI tools (Copilot, GitHub Models, Claude Code)
- Team members configuring Linear-GitHub synchronization
- Engineers debugging web UI with Chrome DevTools

## Directory Contents

```
contributing/
  AGENTS.md              # This file
  README.md              # Comprehensive contributing guide (workflow, code quality, testing)
  chrome-devtools.md     # Chrome DevTools MCP server setup for UI debugging
  copilot-setup.md       # GitHub Copilot Free tier configuration
  github-models.md       # GitHub Models API integration guide
  linear-github.md       # Linear-GitHub bidirectional sync setup
  linear-setup.md        # Linear MCP server installation prompt
```

## Quick Navigation

| File                 | Purpose                                              | When to Use                           |
| -------------------- | ---------------------------------------------------- | ------------------------------------- |
| `README.md`          | Complete contribution workflow, code quality, TDD    | Starting contributions, PR checklist  |
| `chrome-devtools.md` | Chrome DevTools MCP for headless browser debugging   | Debugging UI issues, inspecting pages |
| `copilot-setup.md`   | GitHub Copilot Free tier limits and VS Code setup    | Setting up Copilot for this project   |
| `github-models.md`   | GitHub Models API, rate limits, code review workflow | Using AI for code review, generation  |
| `linear-github.md`   | Sync Linear tasks with GitHub issues                 | Closing GH issues when Linear is Done |
| `linear-setup.md`    | One-liner setup for Linear MCP on new workstations   | Onboarding new developers             |

## Key Topics

### README.md

The primary contributing guide covering:

- Development workflow (find work, branch, implement, PR)
- Code quality standards and pre-commit hooks
- Python dependencies with uv
- Testing commands and TDD workflow
- Git safety rules (NEVER DISABLE TESTING)
- Issue closure checklist

### chrome-devtools.md

Chrome DevTools MCP server for Claude Code integration:

- Headless Chrome setup with remote debugging
- MCP server configuration with `CHROME_WS_ENDPOINT`
- Available tools (navigate, screenshot, console, network)
- Troubleshooting headless environment issues

### copilot-setup.md

GitHub Copilot Free tier configuration:

- Free tier limits (2,000 completions, 50 chat messages/month)
- VS Code extension setup
- Project-specific context via `.github/copilot-instructions.md`
- Best practices for effective prompting

### github-models.md

GitHub Models API for AI-powered workflows:

- Available models (GPT-4o, Llama, Phi, Mistral)
- Rate limits by tier
- CLI usage with `gh models` extension
- REST API and OpenAI SDK compatibility
- Project usage: AI code review workflow

### linear-github.md

Synchronizing Linear and GitHub Issues:

- Native Linear GitHub integration setup
- Audit script for bulk-closing matched issues
- Automated sync workflow
- Magic words for commits (`Fixes NEM-123`)

### linear-setup.md

Quick setup prompt for Linear on new workstations:

- Environment variable configuration
- MCP server installation
- Verification commands

## Related Resources

| Resource                                                                          | Description                            |
| --------------------------------------------------------------------------------- | -------------------------------------- |
| [docs/development/](../../development/)                                           | Hooks, code quality, git workflow      |
| [docs/development/hooks.md](../../development/hooks.md)                           | Pre-commit hook details                |
| [docs/development/code-quality.md](../../development/code-quality.md)             | Linting tools                          |
| [docs/development/linear-integration.md](../../development/linear-integration.md) | Linear MCP tools reference             |
| [CLAUDE.md](../../../CLAUDE.md)                                                   | Project-level Claude Code instructions |

## Entry Points

### For New Contributors

1. Start with `README.md` for the complete workflow
2. Set up Linear: `linear-setup.md`
3. Optional: Configure Copilot via `copilot-setup.md`

### For UI Debugging

1. Read `chrome-devtools.md` for headless Chrome setup
2. Start Chrome with `--remote-debugging-port=9222`
3. Configure MCP server with `CHROME_WS_ENDPOINT`

### For AI-Assisted Development

1. GitHub Copilot: `copilot-setup.md`
2. GitHub Models API: `github-models.md`
3. AI code review runs automatically on PRs

### For Issue Tracking Sync

1. Read `linear-github.md` for sync options
2. Use magic words in commits: `Fixes NEM-XXX`
3. Run audit script for bulk cleanup

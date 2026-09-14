# Linear Integration Setup Prompt

Copy and paste this prompt to another Claude Code agent to configure Linear integration on a new workstation.

---

## Prompt

I need you to set up Linear integration for this project. Here are the details:

### Linear Workspace

- **Workspace:** nemotron-v3-home-security
- **Team:** NEM
- **API Key:** `YOUR_LINEAR_API_KEY`

### Tasks to Complete

#### 1. Add LINEAR_API_KEY to shell profile

Add the API key to `~/.bashrc` (or `~/.zshrc` on macOS):

```bash
echo 'export LINEAR_API_KEY="YOUR_LINEAR_API_KEY"' >> ~/.bashrc  # pragma: allowlist secret
```

#### 2. Install the Linear Claude Code skill

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/wrsmith108/linear-claude-skill ~/.claude/skills/linear
cd ~/.claude/skills/linear && npm install
```

#### 3. Verify the skill installation

```bash
export LINEAR_API_KEY="YOUR_LINEAR_API_KEY"  # pragma: allowlist secret
npx tsx ~/.claude/skills/linear/skills/linear/scripts/linear-ops.ts whoami
```

Expected output should show:

- Name: Mike Svoboda
- Organization: nemotron-v3-home-security
- Team: Nemotron-v3-home-security (NEM)

#### 4. Create project-level MCP configuration

Create `.mcp.json` in the project root with:

```json
{
  "mcpServers": {
    "linear": {
      "command": "npx",
      "args": ["mcp-remote", "https://mcp.linear.app/sse"],
      "env": {
        "LINEAR_API_KEY": "<your-linear-api-key>"
      }
    }
  }
}
```

#### 5. Ensure .mcp.json is in .gitignore

```bash
grep -q "\.mcp\.json" .gitignore || echo ".mcp.json" >> .gitignore
```

### Verification

After setup, these commands should work:

```bash
# Check Linear connection
npx tsx ~/.claude/skills/linear/skills/linear/scripts/linear-ops.ts whoami

# List active issues
npx tsx ~/.claude/skills/linear/skills/linear/scripts/linear-ops.ts help
```

### Notes

- The MCP server requires starting a **new Claude Code session** to load
- Linear workspace URL: https://linear.app/nemotron-v3-home-security/team/NEM/active
- The project's CLAUDE.md has already been updated to reference Linear instead of beads
- All 1,031 issues have been migrated from beads to Linear

---

## Quick One-Liner Setup

If you want a single command to run all setup steps:

```bash
# Add API key to bashrc
echo 'export LINEAR_API_KEY="YOUR_LINEAR_API_KEY"' >> ~/.bashrc  # pragma: allowlist secret && \
source ~/.bashrc && \
# Install skill
mkdir -p ~/.claude/skills && \
git clone https://github.com/wrsmith108/linear-claude-skill ~/.claude/skills/linear && \
cd ~/.claude/skills/linear && npm install && \
# Verify
npx tsx ~/.claude/skills/linear/skills/linear/scripts/linear-ops.ts whoami
```

Then manually create the `.mcp.json` file in each project that needs Linear access.

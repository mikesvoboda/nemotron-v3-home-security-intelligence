# GitHub Copilot Free Tier Setup

This guide covers setting up GitHub Copilot Free tier for development on this project.

## Enabling Copilot Free Tier

1. Go to [GitHub Copilot Settings](https://github.com/settings/copilot)
2. Select **Copilot Free** plan
3. Accept the terms and enable

Reference: [GitHub Copilot Plans](https://github.com/features/copilot/plans)

## Free Tier Limits

| Feature           | Monthly Limit              |
| ----------------- | -------------------------- |
| Code completions  | 2,000                      |
| Chat messages     | 50                         |
| Model             | GPT-4o                     |
| Editors supported | VS Code, JetBrains, Neovim |

Tips to stay within limits:

- Use chat for complex questions, completions for boilerplate
- Disable Copilot in non-code files (markdown, config)
- Focus usage on implementation, not exploration

## VS Code Setup

### Required Extensions

1. **GitHub Copilot** (`GitHub.copilot`)

   - Core completion engine

2. **GitHub Copilot Chat** (`GitHub.copilot-chat`)
   - Chat interface for questions

### Recommended Extensions (for this project)

- **Python** (`ms-python.python`) - Python IntelliSense
- **Pylance** (`ms-python.vscode-pylance`) - Python type checking
- **ESLint** (`dbaeumer.vscode-eslint`) - TypeScript linting
- **Tailwind CSS IntelliSense** (`bradlc.vscode-tailwindcss`) - Tailwind autocomplete
- **Prettier** (`esbenp.prettier-vscode`) - Code formatting

### VS Code Settings

Add to `.vscode/settings.json` (user or workspace):

```json
{
  "github.copilot.enable": {
    "*": true,
    "markdown": false,
    "yaml": false,
    "json": false
  }
}
```

## Project-Specific Context

This project includes a Copilot instructions file at:
[.github/copilot-instructions.md](../../../.github/copilot-instructions.md)

This file provides Copilot with:

- Tech stack information (FastAPI, React, RT-DETRv2, Nemotron)
- Coding conventions and patterns
- Domain-specific terminology
- What NOT to suggest

## Best Practices

### Effective Prompting

```python
# Good: Specific context in comment
# Create SQLAlchemy query to get events for camera with risk_score > 50
async def get_high_risk_events(db: AsyncSession, camera_id: str):
    ...

# Bad: Vague request
# Get events
def get_events():
    ...
```

### When to Use Chat vs Completions

**Use Chat (50/month) for:**

- Explaining existing code
- Architecture questions
- Debugging complex issues
- Learning unfamiliar APIs

**Use Completions (2,000/month) for:**

- Function implementations
- Test case generation
- Boilerplate code
- Repetitive patterns

### Context Awareness

Copilot works best when it can see related code:

1. Keep relevant files open in editor tabs
2. Write descriptive function/variable names
3. Add type hints (Python) or interfaces (TypeScript)
4. Include docstrings for complex functions

### Review All Suggestions

Always review Copilot suggestions for:

- **Security**: SQL injection, path traversal, XSS
- **Correctness**: Edge cases, error handling
- **Performance**: Async patterns, N+1 queries
- **Style**: Match project conventions

## Troubleshooting

### Copilot Not Suggesting

1. Check Copilot status in VS Code status bar
2. Verify you're signed in: `GitHub Copilot: Sign In`
3. Check file type is enabled in settings
4. Restart VS Code

### Poor Quality Suggestions

1. Add more context via comments
2. Open related files in editor
3. Check `.github/copilot-instructions.md` is present
4. Use more specific variable/function names

### Rate Limit Reached

If you hit the monthly limit:

1. Disable Copilot: `GitHub Copilot: Disable`
2. Use Claude Code or other alternatives
3. Wait for monthly reset
4. Consider upgrading to Copilot Pro

## Related Resources

- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [VS Code Copilot Guide](https://code.visualstudio.com/docs/copilot/overview)
- Project instructions: [.github/copilot-instructions.md](../../../.github/copilot-instructions.md)
- Code review prompt: [.github/prompts/code-review.prompt.md](../../../.github/prompts/code-review.prompt.md)

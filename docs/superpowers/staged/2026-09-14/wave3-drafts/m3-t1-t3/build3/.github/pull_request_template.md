# Pull Request

## Description

<!-- Provide a brief description of the changes in this PR -->

## Related Linear Issue

<!-- Link to the Linear issue this PR addresses -->

- Closes: [NEM-XXXX](https://linear.app/nemotron-v3-home-security/issue/NEM-XXXX)

## Type of Change

<!-- Mark the relevant option with an 'x' -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Performance improvement
- [ ] Test coverage improvement

## TDD Compliance

<!-- Test-Driven Development is required for all feature implementations -->

- [ ] Tests were written BEFORE implementation (RED phase)
- [ ] Tests failed initially as expected (verified RED state)
- [ ] Implementation code was written to make tests pass (GREEN phase)
- [ ] Code was refactored while keeping tests green (REFACTOR phase)
- [ ] All new code has corresponding test coverage
- [ ] Tests cover both happy path AND error cases

**Test Coverage Summary:**

<!-- Provide a brief summary of test coverage added -->

- Unit tests: <!-- number of tests added -->
- Integration tests: <!-- number of tests added -->
- E2E tests: <!-- number of tests added (if applicable) -->

## Pre-Merge Checklist

<!-- Verify all items before requesting review -->

- [ ] All tests pass locally (`./scripts/validate.sh`)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Code follows project style guidelines (Ruff/ESLint)
- [ ] Type checks pass (Mypy/TypeScript)
- [ ] Coverage thresholds are met (85% backend unit, 95% backend combined)
- [ ] No tests were disabled or skipped without documented reason
- [ ] Documentation updated (if applicable)
- [ ] AGENTS.md files updated (if new directories/patterns added)
- [ ] Linear issue updated with progress/completion status

## Testing Instructions

<!-- Provide step-by-step instructions for testing this PR -->

1.
2.
3.

## Screenshots (if applicable)

<!-- Add screenshots or videos demonstrating UI changes -->

## Additional Notes

<!-- Any additional context, concerns, or discussion points -->

## Deployment Considerations

<!-- Note any special deployment requirements, migrations, or environment changes -->

- [ ] Database migrations included (if applicable)
- [ ] Environment variables added/changed (if applicable)
- [ ] Docker image rebuild required
- [ ] Documentation for deployment updated

---

**Reviewer Checklist:**

- [ ] Code follows TDD principles (tests before implementation)
- [ ] Test coverage is adequate
- [ ] Code quality meets project standards
- [ ] No security concerns
- [ ] Performance implications considered
- [ ] Documentation is clear and sufficient

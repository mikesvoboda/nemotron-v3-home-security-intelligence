/**
 * Commitlint Configuration
 *
 * Enforces conventional commit format: <type>(<scope>): <subject>
 *
 * Examples:
 *   feat(api): add camera streaming endpoint
 *   fix(frontend): resolve WebSocket reconnection bug
 *   docs: update API reference documentation
 *   chore(deps): bump fastapi to 0.110.0
 *
 * Types allowed:
 *   - feat: New feature
 *   - fix: Bug fix
 *   - docs: Documentation changes
 *   - style: Code style changes (formatting, semicolons, etc.)
 *   - refactor: Code refactoring without feature/fix
 *   - perf: Performance improvements
 *   - test: Adding or updating tests
 *   - build: Build system or external dependencies
 *   - ci: CI/CD configuration changes
 *   - chore: Other changes (deps, tooling)
 *   - revert: Reverting a previous commit
 *   - security: Security-related changes
 *
 * Scopes (optional but recommended):
 *   - api: Backend API routes
 *   - frontend: Frontend components/hooks
 *   - ai: AI pipeline (RT-DETR, Nemotron)
 *   - db: Database models/migrations
 *   - deps: Dependencies
 *   - ci: CI/CD workflows
 *   - docs: Documentation
 *
 * Breaking changes:
 *   Add ! after type/scope: feat(api)!: remove deprecated endpoint
 *   Or include "BREAKING CHANGE:" in body
 *
 * Linear issue references:
 *   Include NEM-XXX in subject or body for automatic linking
 *   Example: feat(api): add alerts endpoint (NEM-123)
 */

module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Type must be one of these values
    'type-enum': [
      2,
      'always',
      [
        'feat', // New feature
        'fix', // Bug fix
        'docs', // Documentation
        'style', // Formatting, no code change
        'refactor', // Code refactoring
        'perf', // Performance improvement
        'test', // Adding/updating tests
        'build', // Build system changes
        'ci', // CI/CD changes
        'chore', // Other changes
        'revert', // Reverting commits
        'security', // Security-related changes
      ],
    ],

    // Type is required and must be lowercase
    'type-case': [2, 'always', 'lower-case'],
    'type-empty': [2, 'never'],

    // Scope is optional but must be lowercase if provided
    'scope-case': [2, 'always', 'lower-case'],

    // Subject requirements
    'subject-case': [
      2,
      'never',
      ['sentence-case', 'start-case', 'pascal-case', 'upper-case'],
    ],
    'subject-empty': [2, 'never'],
    'subject-full-stop': [2, 'never', '.'],
    'subject-max-length': [2, 'always', 100],

    // Header (type + scope + subject) max length
    'header-max-length': [2, 'always', 120],

    // Body settings
    'body-leading-blank': [2, 'always'],
    'body-max-line-length': [1, 'always', 200], // Warning only for long lines

    // Footer settings
    'footer-leading-blank': [2, 'always'],
    'footer-max-line-length': [1, 'always', 200], // Warning only for long lines
  },
  // Custom patterns for Linear issue references
  parserPreset: {
    parserOpts: {
      issuePrefixes: ['NEM-'],
    },
  },
};

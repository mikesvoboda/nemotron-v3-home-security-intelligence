# WP1.2 red-first evidence — DO NOT MERGE

Deliberately planted, structurally FAKE credentials proving secret detection
now reddens the PR gate end-to-end (WP1.2, R-7 red-first). These values are
fabricated for this demo, are not valid credentials, and need no remediation.
This PR gets CLOSED, never merged.

The inline pragmas suppress the local detect-secrets hook only; gitleaks does
not honor that syntax (its own suppression is `gitleaks:allow`), so CI's
Gitleaks job sees exactly what a real leak would look like to it.

- AWS access key id: `AKIA7Q2X9J4ZM8VT3RDH` # pragma: allowlist secret
- Linear API key: `lin_api_aB3dE5fG7hI1jK3lM5nO7pQ9rS1tU3vW5xY7zA9B2` # pragma: allowlist secret

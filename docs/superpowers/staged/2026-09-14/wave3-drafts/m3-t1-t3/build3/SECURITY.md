# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email your findings to the repository maintainer
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Status Update**: Within 7 days with an initial assessment
- **Resolution Timeline**: Critical vulnerabilities will be prioritized and typically addressed within 30 days

### Scope

This security policy applies to:

- The main application codebase
- Docker/container configurations
- AI model integration code
- API endpoints and authentication

### Out of Scope

- Third-party dependencies (report to upstream maintainers)
- Self-hosted instances with modified configurations
- Social engineering attacks

## Security Measures

This project implements:

- GitHub Secret Scanning and Push Protection
- Dependabot security updates
- CodeQL static analysis
- SAST scanning in CI/CD
- Trivy container scanning

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who help improve this project's security.

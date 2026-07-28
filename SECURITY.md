# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| 3.0.x   | ✅ Fully supported |
| < 3.0   | ❌ End of life    |

## Reporting a Vulnerability

If you discover a security vulnerability in DBSKiter, please report it by emailing **magiczc@139.com**.

Please do not create a public GitHub issue for security vulnerabilities.

We will:

1. Acknowledge receipt within **48 hours**
2. Investigate and determine scope within **5 business days**
3. Release a fix within **14 days** (depending on severity)
4. Credit the reporter (if desired)

## What to Include

- Clear description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact
- Suggested fix (if any)

## Security Design

DBSKiter uses three-layer defense-in-depth:

1. **AI Layer**: Rule engine restricts AI from write operations
2. **CLI Layer**: `ReadOnlyEnforcer` middleware
3. **Database Layer**: Physical account permissions

See [security documentation](https://magicczc.github.io/dbskiter/security/) for details.

## Encryption

- All passwords use environment variables (not CLI arguments)
- `--password-stdin` and `--password-file` for secure credential passing
- TLS/SSL supported for database connections

## Responsible Disclosure

We follow responsible disclosure. Please give us reasonable time to fix the issue before public disclosure.

**Last updated**: 2026-07-24
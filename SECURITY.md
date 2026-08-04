# Security Policy

## Supported Versions

Only the latest version is supported with security updates.

| Version | Branch | Supported |
|---------|--------|:---------:|
| Latest  | `master` | ✅ |
| < Latest | — | ❌ |

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

If you discover a security vulnerability in BlackDragon, please report it privately:

1. **Email**: Create a private security advisory through GitHub's ["Report a Vulnerability"](https://github.com/<org>/<repo>/security/advisories/new) feature
2. **Response time**: We aim to acknowledge reports within 48 hours
3. **Disclosure**: We follow coordinated disclosure — fixes are released before public disclosure

### What to Include

- A clear description of the vulnerability
- Steps to reproduce
- Affected versions/commits
- Potential impact

### What NOT to Report

- Game memory offsets — these are reverse-engineered from Monster Hunter World and are expected to change with game updates
- "Security through obscurity" concerns about the overlay being detectable — this is inherent to memory-reading tools
- Missing `.gitignore` entries for common ephemeral files (please open a regular issue instead)

## Security Considerations for Users

BlackDragon reads game process memory. By design, this requires running the tool on the same machine as the game. Users should be aware:

1. **Memory reading is local** — pymem reads local process memory. No data is sent to external servers
2. **Network access** — BlackDragon does not initiate network connections. All operations are local
3. **Dependencies** — Review `requirements.txt` for third-party packages. Pin versions to avoid supply-chain issues

## Reporting Other Issues

For non-security bugs, feature requests, or documentation issues, please open a [regular issue](https://github.com/<org>/<repo>/issues).

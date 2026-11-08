# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

PortfolioX is a local desktop application for personal portfolio tracking. It
does not expose network services, does not execute trades, and does not store
data online. The primary security concerns are:

1. **Local data safety** — the portfolio database (`data/`) and broker
   statements (`referance/`) contain sensitive personal financial information.
   These are never committed to git and are stored locally only.

2. **Dependency security** — the app depends on PyInstaller, customtkinter,
   pypdf, keyring, cryptography, and others. Keep dependencies updated.

3. **Credential handling** — never commit API tokens, passwords, or keys. The
   `.env*` files are gitignored. Use the OS credential store (Windows
   Credential Manager via keyring) for any stored secrets.

### How to report

If you believe you have found a security issue:

1. Do not open a public GitHub issue for the vulnerability itself.
2. Contact the maintainer directly via GitHub or the email listed on the
   project profile.
3. Include: a description of the issue, steps to reproduce, and any potential
   impact.

## Disclosure

We will acknowledge receipt of your report within 5 business days and provide
an initial assessment within 10 business days. If the report is confirmed, we
will work with you on a fix and coordinate disclosure timing.

## Thank you

Thank you for helping keep PortfolioX and its users' financial data safe.

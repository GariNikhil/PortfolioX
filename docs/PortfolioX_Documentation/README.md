# PortfolioX Documentation

PortfolioX is a local-first investment portfolio management and analysis application, initially focused on Indian equities (NSE/BSE) and INR.

## Documentation map
- `docs/PRD.md` — product vision, scope, requirements, acceptance criteria
- `docs/DESIGN.md` — UX principles, screens, workflows, states
- `docs/ARCHITECTURE.md` — system boundaries, components, data flow, deployment
- `docs/SECURITY.md` — threat model and security requirements
- `docs/DATA_MODEL.md` — core entities and data integrity rules
- `docs/ROADMAP.md` — phased implementation plan
- `AGENTS.md` — instructions for AI coding agents
- `DECISIONS.md` — architecture decision record starter

## Status and assumptions
These are **baseline project specifications**, derived from the existing PortfolioX project resource file. They are not a claim that every feature already exists in code. Before implementation, inspect the repository and reconcile these documents with the actual stack, current code, and existing tests.

## Core product rules
1. The transaction ledger is the source of truth.
2. Financial calculations must be deterministic, testable, and reproducible.
3. Never present a price as current without a source and timestamp.
4. Keep realized and unrealized P&L separate.
5. Imports must be validated and previewed before committing.
6. AI provides explanations from verified data; it must not invent portfolio values.
7. PortfolioX is not an autonomous trading system. Alerts and recommendations do not place orders.
8. Preserve user control, portability, and privacy of financial data.

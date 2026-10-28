# PortfolioX — Security and Privacy Requirements

- Status: Baseline security specification
- Data classification: Personal financial data — sensitive

## 1. Security objectives
- Confidentiality of holdings, transactions, statements, and credentials.
- Integrity of the transaction ledger and calculated outputs.
- Availability and recoverability of portfolio records.
- User control over sharing, backups, integrations, and AI processing.

## 2. Threat model
Protect against:
- Unauthorized local or remote access.
- Accidental deletion, corruption, duplicate imports, or incorrect restore.
- Malicious or malformed CSV/XLSX/JSON files.
- Leaked broker/API credentials.
- Prompt injection or malicious text embedded in imported notes/documents.
- Unintended transmission of holdings to third-party services.
- Stale or manipulated market data being presented as current.
- Dependency compromise and unsafe update mechanisms.

## 3. Data minimization and privacy
- Store data locally by default where supported by the chosen architecture.
- Do not transmit portfolio data unless a feature requires it and the user has been informed.
- Send only the minimum data needed to market-data or AI providers.
- Make remote AI processing optional and disclose what data leaves the device.
- Do not include holdings, transactions, account identifiers, or secrets in telemetry by default.
- Provide complete export and user-controlled deletion workflows.

## 4. Secrets management
- Never hard-code API keys, passwords, tokens, or broker credentials.
- Use the operating system's credential store or a suitable secrets manager where available.
- Keep secrets out of source control, logs, screenshots, crash reports, and exported backups unless deliberately encrypted.
- Provide `.env.example` with placeholders only; ensure actual secret files are ignored by version control.
- Rotate credentials if exposed and document revocation steps.

## 5. Local and remote access
- Bind local web services to loopback by default.
- Do not expose a development server directly to the public internet.
- Remote access requires explicit configuration, TLS, authentication, authorization, rate limiting, secure session handling, and a documented threat review.
- Use least privilege for files, database, and integration tokens.
- Require re-authentication or explicit confirmation for sensitive destructive operations where appropriate.

## 6. Encryption and backups
- Assess encryption at rest based on the selected database/platform; document what is and is not encrypted.
- Protect backup files with OS permissions and, when appropriate, encryption.
- Never claim the database is encrypted unless implementation and tests verify it.
- Backups should be versioned and include schema/version metadata.
- Restore must validate the backup before replacing data and should create a recovery point when feasible.
- Test backup restoration, not merely backup creation.

## 7. Import-file safety
- Treat every imported file as untrusted.
- Enforce file type, size, row-count, and field-length limits.
- Validate dates, quantities, currency, identifiers, and numeric ranges.
- Never execute macros, formulas, embedded scripts, or imported content as code.
- Prevent spreadsheet formula injection in CSV exports by safely handling cells beginning with `=`, `+`, `-`, or `@` where applicable.
- Preview changes and require confirmation before database writes.
- Use parameterized database operations.
- Keep import provenance and rejection reasons.

## 8. Data integrity and auditability
- Use atomic writes and database constraints.
- Detect duplicate imports.
- Do not silently rewrite historical transactions.
- Record correction/reversal events and important actions.
- Preserve source references for imported records.
- Ensure derived holdings reconcile to the ledger under documented rules.
- Add regression tests for splits, fees, partial sells, dividends, and invalid inputs.

## 9. AI-specific controls
- Treat imported notes, broker descriptions, web content, and model output as untrusted data, not instructions.
- Keep AI read-only by default.
- Do not let model output directly execute database writes, commands, trades, or network requests.
- Require deterministic code to calculate financial values; AI may explain the results.
- Include provenance for numerical claims.
- Do not send credentials or unnecessary personal data to models.
- Clearly distinguish facts, estimates, assumptions, and missing data.

## 10. Logging and updates
- Logs must not contain secrets or full sensitive statements by default.
- Restrict log file permissions and define retention.
- Pin and review dependencies; use lockfiles where supported.
- Review security-sensitive dependency updates before deployment.
- Keep a documented process for reporting and fixing vulnerabilities.

## 11. Minimum release checklist
- [ ] Secrets are absent from repository and logs.
- [ ] Import parser tests cover malformed and oversized files.
- [ ] SQL/data access uses parameterized queries or safe ORM operations.
- [ ] Local service exposure is documented and safe by default.
- [ ] Backup and restore are tested.
- [ ] Destructive actions require clear confirmation.
- [ ] AI has no direct trade execution or unrestricted write access.
- [ ] Dependency and build configuration reviewed.
- [ ] Privacy disclosures match actual data flows.
- [ ] Known limitations and residual risks documented.

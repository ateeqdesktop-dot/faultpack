# Changelog

All notable changes to FaultPack are documented here.

## [1.0.0] — 2026-08-25

### Added

- Production-oriented flagship release for the portable failure evidence workflow.
- Optional Ed25519 key generation and detached fingerprint signatures through the `signing` extra.
- Explicit public-key verification with no trust-root discovery or network access.
- `diff` command for replaying and comparing two verified packs with stable JSON output.
- `bundle` command for verified deterministic ZIP export.
- Stable JSON output for capture, verification, differential replay, and bundle commands.
- v1.0 product and architecture design covering data flow, error semantics, security, performance, and extension boundaries.
- Rewritten README focused on the product problem, adoption path, security boundary, and Open Source contribution model.

### Quality

- Added focused tests for Ed25519 signing, tamper rejection, differential behavior, bundle generation, CLI contracts, and exit codes.
- Preserved v0.1/v0.2 pack parsing and legacy HMAC verification behavior.
- Ruff, mypy, pytest with coverage gate, `git diff --check`, and wheel/sdist builds pass locally.

## [0.2.0] — 2026-08-25

### Added

- Versioned v0.2 manifest with backward parsing support for v0.1.
- Safe input-file capture with relative paths and SHA-256 evidence.
- Minimal child environment with explicit `--env` allowlist.
- Optional HMAC signing through `FAULTPACK_SIGNING_KEY` and `--require-signature` verification.
- Stable v0.2 fingerprints that exclude volatile pack ID and measured duration.
- Temporary-workspace replay with output regex/hash and duration predicates.
- Bounded line-oriented `reduce` command that preserves a non-passing oracle.
- Fixture-driven end-to-end example under `fixtures/`.
- Security model, threat boundary, architecture, and schema documentation.

### Quality

- Expanded unit, CLI, integrity, redaction, replay, and reducer tests.
- Coverage gate raised to 90%.
- Ruff and mypy pass on the source tree.
- Wheel and source distribution build successfully.

## [0.1.0] — 2026-08-24

### Added

- Versioned `faultpack.json` manifest contract.
- Privacy-first capture with secret, email, IP, and custom-pattern redaction.
- Deterministic manifest fingerprints and ZIP pack writer.
- Safe relative-path and symlink checks.
- CLI commands: `capture`, `inspect`, `verify`, `replay`, and `version`.
- Markdown, SARIF, and JUnit replay reports.
- GitHub Actions quality matrix for Python 3.10–3.13.
- Unit and integration tests with a coverage gate above 85%.

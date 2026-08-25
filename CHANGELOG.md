# Changelog

All notable changes to FaultPack are documented here.

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

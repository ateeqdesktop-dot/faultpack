# Changelog

All notable changes to FaultPack are documented here.

## [1.3.1] — Compatibility patch

### Fixed

- Preserved legacy v0.1/v0.2 manifest fingerprints when the parser materializes optional v0.3 producer and event fields.
- Added a regression test covering enriched legacy manifests and verified the existing fixture workflow on GitHub Actions.

[1.3.1]: https://github.com/ateeqdesktop-dot/faultpack/releases/tag/v1.3.1

## [1.3.0] — Evidence interchange

### Added

- Added optional `Producer` metadata for identifying the capture adapter without coupling the core verifier to a runtime.
- Added digest-first `EvidenceEvent` timeline contracts for tool calls, model responses, assertions, policy decisions, and annotations.
- Added `faultpack evidence-diff LEFT RIGHT` for offline semantic comparison without executing either declared command.
- Added stable event summaries and explicit volatile-field exclusions for evidence comparisons.
- Updated the public JSON Schema to support format `0.3` while preserving `0.1` and `0.2` parsing.

### Quality and safety

- Event sequences must be strictly increasing and unique; payloads are represented by SHA-256 digests by default.
- Evidence diff verifies both packs before reading semantic fields and reports changes in machine-readable JSON.
- Added contract, privacy, CLI, and backward-compatibility tests; pytest coverage remains above 90%, with Ruff, mypy, JSON validation, and wheel/sdist builds passing locally.

[1.3.0]: https://github.com/ateeqdesktop-dot/faultpack/releases/tag/v1.3.0

## [1.2.0] — Privacy preflight

### Added

- Added passive `faultpack diagnose PACK` for share-before-you-send privacy diagnostics.
- Added machine-readable findings for private keys, GitHub tokens, AWS access keys, bearer tokens, secret-like assignments, email addresses, and oversized textual evidence.
- Added `--fail-on-findings` with exit code `6` for CI privacy gates.
- Added flagship strategy documentation explaining the product decision, competitive rationale, scoring model, and architecture boundaries.

### Quality

- Added focused diagnostics and CLI tests while preserving the 90% coverage gate.
- Added the diagnostic command to the fixture GitHub Actions workflow.
- Ruff, mypy, pytest, and wheel/sdist builds pass locally.

[1.2.0]: https://github.com/ateeqdesktop-dot/faultpack/releases/tag/v1.2.0

## [1.1.0] — Replay matrix

### Added

- Added typed `MatrixProfile` and `MatrixResult` contracts with strict profile names, safe environment keys, optional tokenized argv overrides, and bounded timeout narrowing.
- Added `faultpack matrix PACK --profiles profiles.json` for ordered, isolated, local replay across multiple profiles.
- Added aggregate JSON output plus Markdown, SARIF, and JUnit matrix reports.
- Added matrix support to the composite GitHub Action through the optional `profiles` input.
- Added deterministic matrix fixtures and focused tests for success, mismatch, duplicate profiles, unsafe policy, and execution errors.
- Added `docs/architecture-v1.1.md` and `examples/profiles.json`.

### Compatibility and safety

- Existing v0.1/v0.2 pack formats and commands remain readable and unchanged.
- Matrix execution never mutates the source pack and does not invoke a shell for argv overrides.
- Profile timeouts may narrow but never expand the pack timeout.
- FaultPack remains local-first, passive during verification, and explicit that replay is not a sandbox.

[1.1.0]: https://github.com/ateeqdesktop-dot/faultpack/releases/tag/v1.1.0

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

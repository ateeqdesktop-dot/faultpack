# FaultPack — architecture and implementation plan

## Product scope

FaultPack is a local-first Python package and CLI. It creates a portable `faultpack.json` manifest plus captured artifacts, redacts sensitive values before persistence, computes stable content fingerprints, replays the declared command under an explicit working directory and environment policy, compares observed behavior with the recorded expectation, and emits Markdown/SARIF/JUnit-compatible reports for local use and GitHub Actions.

The MVP intentionally has no hosted service and no arbitrary remote execution. A user runs it locally or inside their own CI runner. This keeps the security boundary explicit and makes the core artifact inspectable and testable.

## Architecture

```text
CLI (Typer)
  ├── Capture service ── command runner ── process result
  ├── Redaction engine ── env/stdout/stderr sanitizers
  ├── Manifest model (Pydantic) ── schema validation
  ├── Fingerprint engine ── canonical JSON + SHA-256
  ├── Pack I/O ── deterministic ZIP layout
  ├── Replay service ── bounded subprocess + policy checks
  ├── Comparator ── exit code / regex / hash / duration assertions
  └── Reporters ── human Markdown, SARIF, JUnit XML, JSON

GitHub Action
  ├── installs package
  ├── runs faultpack verify/replay
  ├── uploads pack and reports as artifacts
  └── optionally writes a job summary (no token required for MVP)
```

The core is dependency-light and framework-agnostic. The CLI is an adapter over pure services so unit tests can exercise capture, redaction, canonicalization, replay, comparison, and reporting without shelling out to GitHub.

## Manifest contract

`faultpack.json` contains `format_version`, `pack_id`, `created_at`, `source` (repository URL, commit, branch), `command` (argv array, cwd, timeout), `environment` (OS, Python, selected non-secret variables), `input_files` (relative paths and SHA-256), `observed` (exit code, duration, stdout/stderr artifact paths and hashes), and `expectation` (exit code, optional stdout/stderr regexes, optional artifact hashes). The manifest itself is canonicalized with sorted keys, UTF-8 encoding, and normalized newlines before hashing.

The pack layout is deterministic:

```text
faultpack/
├── faultpack.json
├── artifacts/stdout.txt
├── artifacts/stderr.txt
├── artifacts/inputs/<relative-paths>
└── reports/
```

Paths are always relative to the pack root; absolute paths, `..` traversal, symlinks, and files outside the declared input root are rejected. Zip entries are sorted and carry normalized timestamps so identical inputs produce identical pack bytes apart from the creation timestamp field, which is excluded from the content fingerprint.

## Error and security model

Capture failures are represented as typed result states rather than unhandled tracebacks. A command timeout terminates the process group where supported and yields `timeout`; a non-zero exit is valid evidence and is not itself a tool error; malformed manifests yield `schema_error`; unsafe paths yield `policy_error`; mismatches yield `reproduction_failed`.

The redactor applies ordered rules for environment variable names containing `TOKEN`, `SECRET`, `PASSWORD`, `PASS`, `KEY`, `COOKIE`, and `AUTH`, plus configurable regular expressions for bearer tokens, private-key blocks, common cloud keys, email addresses, and IPv4 addresses. Redaction is performed before hashing or writing. The CLI never prints secret values and supports `--redact-pattern` additions. A pack is safe to share only when the user reviews the generated report; FaultPack does not claim perfect PII detection.

Replay defaults to an allowlist of environment variables, a temporary working directory, a bounded timeout, no network-control promise, and no elevated privileges. The README will clearly state that replay is not a sandbox and that users should run untrusted packs inside an isolated CI/container environment.

## Non-functional requirements

The MVP must be deterministic for the same declared inputs, return stable machine-readable exit codes, work on Linux/macOS/Windows where Python subprocess semantics allow, avoid network access in core operations, validate all external paths, and run with Python 3.10+. It must provide a clear `--json` mode for automation, 90%+ unit coverage on core services, smoke tests for the CLI, and a GitHub Actions matrix for supported Python versions.

## MVP acceptance criteria

A fixture can be captured into a pack, copied to another directory, replayed, and reported as reproduced without relying on the original absolute path. A tampered artifact or manifest is detected by fingerprint verification. Secret-like values in environment/output are redacted before pack creation. A mismatch produces a non-zero exit code and a readable Markdown/SARIF report. The same fixture produces a stable content fingerprint across repeated captures. The GitHub Action can run verification and upload generated reports.

## Roadmap

Advanced features include a Rust hashing/packing accelerator, adapters for pytest/Jest/Go test, Docker/Podman replay backends, GitHub App issue comments, artifact attestation verification, differential matrix replay, browser/network trace adapters, and an anonymized public corpus. None is required for MVP correctness.

## Implementation order

1. Package metadata, typed models, error taxonomy, and canonicalization.
2. Redaction and safe filesystem primitives.
3. Capture and deterministic pack writer.
4. Verification, replay, comparison, and stable exit codes.
5. Reporters and CLI commands.
6. Fixtures, unit/integration tests, GitHub Action, lint/type checks, and release metadata.
7. README, security policy, contribution guide, changelog, and final smoke verification.

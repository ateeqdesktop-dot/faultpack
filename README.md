# FaultPack

[![CI](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml/badge.svg)](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)

**FaultPack turns “it fails on my machine” into a portable, privacy-first, verifiable reproduction artifact.**

Capture a command failure once, include only the input files you choose, redact sensitive values before persistence, verify every byte, replay the pack from another directory, and reduce a text fixture while preserving the failure oracle. FaultPack is local-first: it needs no hosted account, model call, telemetry pipeline, or implicit upload.

> **Capture the failure once. Share the evidence safely. Verify the same behavior anywhere.**

## Why FaultPack exists

A maintainer cannot reliably act on a screenshot or an unstructured log attachment. A useful failure report needs the source revision, exact argv, working directory, relevant environment, selected inputs, observed status, expected behavior, and a way to decide whether another runner reproduced the same failure.

FaultPack packages those facts in a small, inspectable directory. The manifest is versioned and schema-validated, the logical record has a canonical SHA-256 fingerprint, artifacts and inputs have independent hashes, and reports are ready for CI review. The format is language-neutral; the reference implementation is Python.

FaultPack is deliberately **not a sandbox**, a full operating-system image, an observability service, or a guarantee of perfect PII removal. Run untrusted packs in an isolated CI runner or container and review generated files before sharing them.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Capture a command and one selected input file.
faultpack capture --out ./pack --input examples/hello.txt -- \
  python examples/hello.py examples/hello.txt

faultpack verify ./pack
faultpack replay ./pack --report-dir ./report
```

A successful replay exits with `0`. A valid but non-matching replay exits with `5`. A malformed, unsafe, tampered, or invalidly signed pack exits with `4`. Capture records a non-zero child exit as valid failure evidence rather than treating it as a FaultPack crash.

## Reduce a failing fixture

If a failure is driven by a text input, FaultPack can apply bounded, line-oriented delta debugging:

```bash
faultpack reduce ./pack --input examples/bug.txt --out ./reduced --max-runs 100
faultpack verify ./reduced
faultpack replay ./reduced --report-dir ./reduced-report
```

The reducer removes contiguous chunks and accepts a candidate only while the pack’s declared oracle remains failing. It is intentionally conservative and bounded; it is not a replacement for a domain-aware parser reducer.

## Pack format

```text
faultpack/
├── faultpack.json
├── artifacts/
│   ├── stdout.txt
│   ├── stderr.txt
│   └── inputs/<selected-relative-files>
└── signature.hmac  # optional
```

`faultpack.json` uses the v0.2 schema in [`docs/faultpack.schema.json`](docs/faultpack.schema.json). It records a source reference, argv and timeout, a minimal environment policy, selected input paths and hashes, observed result metadata, expectation predicates, and a logical fingerprint. The fingerprint excludes the volatile creation timestamp, pack ID, and measured duration in v0.2 so repeated captures of the same logical evidence remain stable. v0.1 manifests remain readable for migration.

## Privacy and security

The child process receives a conservative baseline environment plus names explicitly passed through `--env`. Secret-looking names and common token, email, IPv4, and private-key patterns are redacted before output is written or hashed. Paths are relative; traversal, absolute paths, backslash escapes, and symlink escapes are rejected. Verification never executes the declared command. Replay is bounded by a timeout and uses a temporary workspace, but it does not claim network isolation or sandboxing.

For signed packs, set a key in the process environment:

```bash
export FAULTPACK_SIGNING_KEY='use-a-secret-manager-in-real-CI'
faultpack capture --out ./signed-pack -- python -c "raise SystemExit(1)"
faultpack verify ./signed-pack --require-signature
```

Never put signing keys, credentials, real customer traces, or private incident data in a pack or fixture. See [`SECURITY.md`](SECURITY.md) for the disclosure process and threat model.

## GitHub Actions

```yaml
name: Verify failure pack
on: [push, pull_request]

permissions:
  contents: read

jobs:
  reproduction:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install .
      - run: faultpack verify fixtures/failure-pack
      - run: faultpack replay fixtures/failure-pack --report-dir faultpack-report
        continue-on-error: true
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: faultpack-report
          path: faultpack-report/
```

The generated report directory contains Markdown, SARIF, and JUnit XML. Upload SARIF with GitHub’s official Code Scanning action when that integration is enabled in your repository.

The repository also ships a composite Action for downstream projects:

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- uses: ateeqdesktop-dot/faultpack@main
  with:
    pack: fixtures/failure-pack
    report-dir: faultpack-report
```

Pin the Action to a release tag in production. A signed pack can be required with `require-signature: 'true'` and `FAULTPACK_SIGNING_KEY` configured in the runner environment.

## Architecture

```text
CLI
 ├── CaptureService ── bounded subprocess ── redaction ── PackWriter
 ├── Manifest/Schema ── canonical JSON ── SHA-256 fingerprint
 ├── Integrity ── artifact/input hashes ── optional HMAC
 ├── ReplayService ── temporary workspace ── Comparator ── verdict
 ├── Reducer ── bounded line-oriented oracle-preserving reduction
 └── Reporters ── JSON / Markdown / SARIF / JUnit
```

The core services are separated from Typer commands. New adapters such as pytest, Jest, Go test, OCI replay, or attestation verification can produce observations against the stable pack contract without embedding provider-specific code in the manifest writer.

Detailed product, data-flow, error-flow, security, performance, and extension decisions live in [`docs/architecture.md`](docs/architecture.md).

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check src tests
mypy src
python -m build --wheel --sdist
```

Contributions should include a focused test for behavior changes and documentation for contract changes. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md), and use sanitized, deterministic fixtures only.

## Roadmap

The next additive layers are pytest/Jest/Go adapters, OCI/Podman replay backends, Ed25519 signatures and attestations, differential replay matrices, browser/network trace adapters, and a public anonymized corpus. None is required for the correctness of the local v0.2 core.

## License

Apache-2.0. See [LICENSE](LICENSE).

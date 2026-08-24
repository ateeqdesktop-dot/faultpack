# FaultPack

[![CI](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml/badge.svg)](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml) [![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

**FaultPack** turns a software failure into a portable, privacy-first, verifiable reproduction pack. Capture the command, sanitize sensitive context, fingerprint the evidence, replay it elsewhere, and publish a machine-readable result in CI.

> If a failure can be reproduced, FaultPack should make the reproduction portable, safe to share, and easy to verify.

## Why it exists

"It fails on my machine" is rarely enough for a maintainer. A useful report needs the exact command, repository revision, relevant environment, observed exit status, output, and a way to determine whether a later run really reproduced the same failure. Existing issue templates and log attachments help humans, but they do not define a portable, integrity-checkable artifact.

FaultPack is deliberately **local-first**. It is a CLI and a GitHub Actions building block, not a hosted observability service and not a promise that arbitrary input is sandboxed. The pack format is language-neutral; the reference implementation is Python.

## Quick start

```bash
python -m pip install faultpack
faultpack capture --out ./faultpack-demo -- python -c "print('hello')"
faultpack verify ./faultpack-demo
faultpack replay ./faultpack-demo --report-dir ./faultpack-report
```

`capture` writes `faultpack.json` and redacted stdout/stderr artifacts. `verify` checks the manifest and artifact fingerprints without executing the command. `replay` executes the declared command under its timeout and compares the result with the declared expectation, producing Markdown, SARIF, and JUnit reports.

## Pack contract

```text
faultpack/
├── faultpack.json
├── artifacts/stdout.txt
└── artifacts/stderr.txt
```

The manifest records a versioned command contract, source metadata, environment summary, observed result, expectation, and a content fingerprint. Canonical JSON and normalized hashing make the fingerprint stable for the same logical evidence. Paths are relative and traversal is rejected.

## Privacy and security

FaultPack redacts secret-looking environment names and common token/private-key patterns, emails, and IPv4 addresses before writing captured output or environment metadata. Redaction is intentionally conservative and configurable; it is not a proof that a pack contains no personal or confidential information. Review packs before sharing them.

Replay is **not a sandbox**. Do not run an untrusted pack on a privileged machine. Use a container or an isolated CI runner for third-party packs, and keep network access and credentials out of the replay environment.

## GitHub Actions

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- run: pip install .
- run: faultpack verify ./fixtures/hello-pack
- run: faultpack replay ./fixtures/hello-pack --report-dir ./faultpack-report
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: faultpack-report
    path: faultpack-report/
```

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
mypy src
```

## Roadmap

The next milestones are adapters for pytest/Jest/Go test, container-backed replay, GitHub issue comments, artifact-attestation verification, differential replay matrices, browser/network capture, and an anonymized public corpus of reproduction packs.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request. Security reports belong in [SECURITY.md](SECURITY.md), not in public issues.

## License

Apache-2.0. See [LICENSE](LICENSE).

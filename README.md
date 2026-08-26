[![CI](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml/badge.svg)](https://github.com/ateeqdesktop-dot/faultpack/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/) [![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

# FaultPack

**FaultPack turns an opaque failure into a portable, privacy-preserving, verifiable experiment that another machine can reproduce, compare, and trust.**

A screenshot is not a reproduction. A raw CI log is not an evidence contract. FaultPack captures the exact command, selected inputs, bounded environment, redacted observations, and declared failure oracle in a small inspectable directory. It can then verify every byte, replay the case in a temporary workspace, reduce a text fixture while preserving the failure, compare two behaviors, sign the fingerprint, and emit CI-native reports.

> **Capture once. Share safely. Verify independently. Replay anywhere.**

FaultPack is **local-first**. It requires no hosted account, model call, telemetry pipeline, database, or implicit upload.

## Why FaultPack exists

Maintainers lose time when a bug report omits the source revision, argv, working directory, relevant inputs, environment, expected behavior, or a trustworthy way to determine whether a second run reproduced the same failure. FaultPack makes those decisions explicit and machine-checkable without pretending to be a sandbox or a universal truth oracle.

The project is an evidence layer, not an observability platform. It complements test runners, CI systems, tracing products, and supply-chain attestations by giving a single failure case a stable portable contract.

## What it provides

| Capability | What it means in practice |
|---|---|
| **Portable pack format** | A versioned JSON manifest plus selected artifacts and inputs. |
| **Privacy-first capture** | Explicit input selection, environment allowlisting, and redaction before persistence and hashing. |
| **Integrity verification** | Canonical JSON, SHA-256 fingerprints, per-file hashes, traversal/symlink protection, and optional signatures. |
| **Bounded replay** | Verified inputs are restored to a temporary workspace and the declared command runs under its timeout. |
| **Failure oracle** | Exit code, stdout/stderr regexes, output hashes, duration caps, and explicit mismatch reasons. |
| **Differential replay** | Replay two packs and report behavioral differences without treating timing as causal proof. |
| **Bounded reduction** | Line-oriented delta debugging that accepts a candidate only while the declared failure oracle remains true. |
| **CI reports** | JSON, Markdown, SARIF, JUnit XML, deterministic ZIP bundles, and a reusable GitHub Action. |
| **Detached Ed25519 signing** | Optional interoperable signatures over the logical fingerprint, verified with an explicit public key. |
| **Replay matrix** | Run the same verified failure across ordered, bounded local profiles and aggregate reproducibility results. |
| **Privacy preflight** | Passively scan declared evidence for common secret and PII indicators before sharing; suitable for CI gates. |
| **Adapter-ready contract** | Language-neutral manifests let pytest, Jest, Go, and other producers share the same evidence layer. |

## Evidence interchange in v1.3

FaultPack 1.5 adds a verified, privacy-aware GitHub issue body generator; FaultPack 1.4 adds a verified, dependency-free offline HTML evidence viewer. FaultPack 1.3 adds an optional, digest-first evidence timeline for AI-agent and tool runs. Events record an ordered kind and name, while payloads are represented by SHA-256 digests by default; raw prompts, responses, and tool payloads are never stored implicitly.

```python
from faultpack.events import build_event, event_summary

events = [
    build_event(1, "tool_call", "search", {"query": "..."}),
    build_event(2, "assertion", "regression-oracle"),
]
print(event_summary(events))
```

Use `evidence-diff` to compare two verified packs without executing either declared command. It reports stable changes in source, producer, command, inputs, expectations, and event summaries while ignoring volatile `pack_id`, `created_at`, and replay duration.

```bash
faultpack evidence-diff ./baseline-pack ./candidate-pack \
  --output ./report/evidence-diff.json
```

This is intentionally an evidence layer, not a hosted observability dashboard. It complements OpenTelemetry, Langfuse, Phoenix, test runners, and CI by producing a small artifact that can be reviewed, signed, archived, and verified independently.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

# Capture a selected input and a command failure.
faultpack capture --out ./pack \
  --input examples/hello.py --input examples/hello.txt -- \
  python examples/hello.py examples/hello.txt

# Verify without executing the command, then run a share-before-you-send privacy preflight.
faultpack verify ./pack
faultpack diagnose ./pack --fail-on-findings
faultpack replay ./pack --report-dir ./report

# Generate a verified, dependency-free offline report for a PR artifact.
faultpack inspect ./pack --html --output ./report/faultpack.html

# Generate a safe GitHub issue body without embedding captured output
faultpack issue ./pack --output ./report/issue.md --bundle-name failure.zip
```

`diagnose` is passive: it verifies the manifest fingerprint and scans only declared textual evidence for token-like values, private keys, emails, and oversized files. It never executes the declared command, fetches URLs, follows symlinks, or uploads data. Use `--fail-on-findings` as a CI gate; it exits with `6` when review is required.

`inspect --html` first verifies the pack, then writes a single self-contained HTML file with the execution contract, selected-file digests, producer metadata, and digest-first evidence timeline. The viewer has no external assets or JavaScript dependencies, never embeds captured stdout/stderr, and is safe to attach to a pull request as a passive review artifact.

`issue` verifies the pack and runs the passive privacy preflight before generating a metadata-only GitHub issue body. It includes the fingerprint, command contract, input digests, evidence-event names, and maintainer checklist, but never copies captured stdout/stderr or matched secret values. Use `--fail-on-findings` in automation to prevent sharing until every finding is reviewed.

A non-zero child exit during capture is **valid failure evidence**, not a FaultPack crash. Replay exits with `0` when the pack's oracle matches and `5` when the replay is valid but does not match. Malformed, unsafe, tampered, or invalidly signed packs exit with `4`.

## Sign a pack with Ed25519

Signing is optional and keeps the base install small. The private key never enters the pack.

```bash
pip install -e '.[signing]'
faultpack keys --output-dir ./keys
faultpack capture --out ./signed-pack \
  --ed25519-private-key ./keys/faultpack-ed25519-private.pem -- \
  python -c "print('signed')"
faultpack verify ./signed-pack \
  --public-key ./keys/faultpack-ed25519-public.pem
```

The signature covers the canonical logical fingerprint, not a mutable path or a human-readable signer label. The verifier does not discover trust roots, fetch keys, or execute pack content.

## Replay matrix

A matrix answers a maintainer’s practical question: **does this failure reproduce under every declared local profile?** Profiles are a JSON array. They may narrow the timeout, override argv as tokens (never a shell string), or add explicitly named environment variables. The runner verifies the pack once, uses a fresh workspace per profile, preserves declaration order, and emits one result per profile.

```json
[
  {"name": "baseline"},
  {"name": "feature-flag", "env": {"FEATURE_FLAG": "on"}},
  {"name": "alternate-command", "argv": ["python", "-m", "myapp.reproduce"]}
]
```

```bash
faultpack matrix ./pack --profiles ./profiles.json --report-dir ./matrix-report
```

The matrix exits `0` only when every profile reproduces the oracle. A valid mismatch exits `5`; an invalid pack or unsafe profile exits `4`. Reports are `faultpack-matrix.json` and `faultpack-matrix.md`. Matrix timing is diagnostic only and never presented as causal proof.

The composite Action supports the same mode by passing `profiles: profiles.json`; omitting it keeps the original single-pack replay behavior.

## Differential replay

Differential replay is useful when a maintainer wants to compare a baseline and a candidate behavior without adopting a hosted experiment service.

```bash
faultpack diff ./baseline-pack ./candidate-pack \
  --output ./report/diff.json
```

The result includes status, exit code, stdout/stderr digests, oracle outcomes, mismatch reasons, and a timing delta marked as diagnostic-only. A behavioral difference exits with `5`; an invalid pack exits with `4`.

## Reduce a failing fixture

```bash
faultpack reduce ./pack \
  --input examples/repro_input.txt \
  --out ./reduced \
  --max-runs 100
faultpack verify ./reduced
faultpack replay ./reduced --report-dir ./reduced-report
```

The reducer is conservative and bounded. It is not a parser-aware reducer and it does not claim that a smaller input is the only or canonical root cause.

## GitHub Actions

The repository ships a composite action for downstream projects:

```yaml
name: Reproduction

on: [push, pull_request]

permissions:
  contents: read

jobs:
  reproduce:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install .
      - uses: ateeqdesktop-dot/faultpack@v1.0.0
        with:
          pack: fixtures/failure-pack
          report-dir: faultpack-report
```

The action verifies before replaying and uploads Markdown, SARIF, and JUnit artifacts. For Ed25519 verification, provide a public key path through `public-key` and install the signing extra in the calling workflow. Pin the action to a release tag or commit in production rather than tracking `main`.

## Pack format

```text
faultpack/
├── faultpack.json
├── artifacts/
│   ├── stdout.txt
│   ├── stderr.txt
│   └── inputs/<selected-relative-files>
├── signature.hmac       # optional legacy compatibility
└── signature.ed25519    # optional preferred detached signature
```

The manifest records a source reference, argv and timeout, relative cwd, minimal environment policy, selected input paths and hashes, observed result metadata, expectation predicates, and a logical fingerprint. The fingerprint excludes volatile creation time, pack ID, and measured duration so repeated captures of the same logical evidence remain stable.

## Security boundary

FaultPack protects against accidental disclosure, path traversal, symlink escapes, pack tampering, and misleading verification results. It does **not** sandbox a malicious command, restrict kernel capabilities, guarantee perfect PII removal, or prove that the producer's original observation was truthful.

Replay untrusted packs inside an isolated CI runner or container with filesystem and network restrictions supplied by the caller. FaultPack never executes the declared command during `inspect` or `verify`, never fetches URLs, never loads plugins from a pack, and never treats a string label as cryptographic identity.

Redaction covers common token, bearer, private-key, email, and IPv4 patterns plus user-supplied regular expressions. Regex redaction cannot guarantee removal of arbitrary sensitive content, so review a pack before sharing it.

## Architecture

```text
CLI / GitHub Action
        |
        +--> CaptureService --> redaction --> PackWriter
        |
        +--> Verifier -------> canonical JSON --> hashes --> signatures
        |
        +--> ReplayService --> temporary workspace --> bounded subprocess
        |                                             |
        +--> Reducer ---------------------------------+
        |
        +--> Differential comparer --> JSON / Markdown / SARIF / JUnit
```

The domain layer is independent from Typer. `models.py` owns the schema contract, `core.py` owns canonicalization and verification, `pack.py` owns capture and deterministic packaging, `replay.py` owns execution and oracle comparison, `diff.py` owns behavioral comparison, `reducer.py` owns bounded minimization, `report.py` owns output formats, and `signing.py` owns optional Ed25519 interoperability.

See [`docs/flagship-strategy.md`](docs/flagship-strategy.md) for the product decision and competitive rationale. See [`docs/decision-record.md`](docs/decision-record.md) for the flagship selection, competitive gap, scoring matrix, and 1.4 architecture decision. See [`docs/v1-design.md`](docs/v1-design.md) for the original product contract, and [`docs/architecture-v1.1.md`](docs/architecture-v1.1.md) for the matrix architecture, security model, and release boundaries. See [`docs/architecture.md`](docs/architecture.md) for the v0.2 compatibility notes.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check src tests
mypy src
python -m build --wheel --sdist
```

Behavior changes must include focused tests and a contract note. Fixtures must be deterministic and sanitized. The project welcomes adapters for pytest, Jest, Go test, and OCI/Podman as separate producer-side integrations that preserve the core verifier's passive boundary.

## Roadmap

FaultPack v1.0 provides the complete local evidence workflow. FaultPack 1.1 adds replay matrices and the stable adapter-facing contract. FaultPack 1.2 adds privacy preflight diagnostics for safe sharing and CI gating. FaultPack 1.3 adds producer metadata, digest-first evidence events, and offline semantic evidence diff. Future releases can add pytest/Jest/Go producer adapters, OCI/Podman backends, and verified reproducible-build metadata. Later releases may add a static report viewer and an opt-in anonymized corpus. A hosted multi-tenant dashboard and autonomous repair remain deliberately out of scope.

## License

Apache-2.0. See [LICENSE](LICENSE).

# FaultPack v0.2 Architecture

## Product scope

FaultPack is a local-first Python package and CLI that turns a software failure into a portable, inspectable, privacy-aware reproduction pack. It captures a bounded command execution, selected input files, a minimal environment policy, sanitized output, and a versioned expectation. Other runners can verify bytes without executing, replay from a different directory, reduce a UTF-8 text fixture, and emit CI-friendly reports.

The MVP has no hosted service, implicit upload, model call, remote execution, or arbitrary command execution from a browser. Users run it locally or inside their own CI runner.

## Components

```text
CLI (Typer)
  ├── CaptureService ── minimal environment ── bounded subprocess
  │                    └── redaction ── input copier ── PackWriter
  ├── Manifest model (Pydantic) ── JSON Schema 0.1/0.2
  ├── Integrity ── canonical JSON ── SHA-256 ── optional HMAC
  ├── ReplayService ── temporary workspace ── Comparator ── verdict
  ├── Reducer ── bounded line-oriented failure oracle
  └── Reporters ── JSON / Markdown / SARIF / JUnit
```

Core services are separated from the Typer adapter. A future pytest, Jest, Go test, OCI replay, or attestation adapter can target the manifest and verdict contracts without changing pack I/O.

## Manifest contract

`faultpack.json` is canonical UTF-8 JSON with sorted keys and a trailing newline. v0.2 contains `format_version`, `pack_id`, `created_at`, `source`, `command`, `environment`, `input_files`, `observed`, `expectation`, and `fingerprint`. The command stores argv, relative cwd, timeout, and allowed environment names. Inputs store safe relative paths and byte hashes. Observations store status, exit code, duration, output paths, and output hashes. Expectations support exit code, regexes, output hashes, and a maximum duration.

The logical v0.2 fingerprint excludes volatile creation time, pack ID, and measured duration. v0.1 manifests remain parseable and use their historical fingerprint semantics. Artifact and input hashes are always checked independently.

## Data flow

Capture validates the command and paths, derives a minimal environment, runs the command under a timeout, redacts output before persistence, copies selected inputs, builds the manifest, computes the logical fingerprint, writes deterministic files, and signs the fingerprint when `FAULTPACK_SIGNING_KEY` is present. Verify reads only the manifest and bytes, validates schema, paths, input/output hashes, and an optional HMAC signature. Replay verifies first, copies inputs into a temporary workspace, executes the declared argv with the same relative layout, compares observed behavior with the expectation, and writes reports. Reduce copies a valid pack, removes contiguous line chunks from one declared text input, and accepts candidates only when the same non-passing oracle remains true; it is capped by `max_runs`.

## Security model

The child environment contains only `PATH`, locale, temporary directory, and names explicitly allowed by the user. Secret-looking names and common token, email, IPv4, and private-key patterns are redacted before output is written or hashed. Absolute paths, traversal, backslash escapes, and symlink escapes are rejected. Verification never runs a command. Replay uses a temporary workspace and a timeout, but it is not a sandbox and does not promise network isolation. Untrusted packs must be run in an isolated CI or container environment.

Threats include malicious manifests, path traversal, symlink escapes, tampered bytes, secret leakage, unsafe regexes, and unbounded reduction. Mitigations are typed validation, safe path resolution, bounded subprocesses, capped reducer runs, explicit redaction warnings, deterministic hashes, and no implicit network access.

## Error and exit semantics

| Condition | Outcome |
| --- | --- |
| Reproduction matches expectation | exit `0` |
| Valid pack but replay mismatch | exit `5` |
| Malformed, unsafe, tampered, or invalidly signed pack | exit `4` |
| Capture child exits non-zero | valid evidence with `observed.status=failed` |
| Capture child times out | valid evidence with `observed.status=timeout` |
| Unexpected capture/CLI error | exit `3` |

A non-zero child exit is not automatically a FaultPack failure; it is the evidence that the pack records. The replay verdict decides whether that evidence was reproduced.

## Performance and portability

Verification is linear in manifest and artifact bytes and hashes large files in chunks. Replay is bounded by the manifest timeout. Reduction is bounded by `max_runs` and is optimized for small or medium text fixtures. The package targets Python 3.10+ and works across operating systems where Python subprocess semantics permit; the security boundary remains explicit on every platform.

## Extension roadmap

Additive extensions include pytest/Jest/Go adapters, OCI/Podman replay backends, Ed25519 signatures and attestations, differential replay matrices, browser/network trace adapters, and an anonymized public corpus. Extensions must consume the stable pack contract rather than place provider-specific behavior in the core.

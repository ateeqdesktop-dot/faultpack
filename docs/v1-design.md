# FaultPack v1.0 — Product and Architecture Design

## Product vision

FaultPack is a local-first evidence compiler for software failures. It turns an opaque command failure into a portable, privacy-preserving, verifiable experiment that another machine can reproduce, compare, and trust.

The product is deliberately narrower than a sandbox, observability platform, incident-management system, or autonomous repair agent. A pack is an evidence artifact with an explicit contract: what was run, with which selected inputs and environment, what was observed, what result is expected, and what a verifier can independently check.

## Problem statement

A screenshot or copied log is not a reliable reproduction. Maintainers need a stable source reference, exact argv, bounded execution policy, selected inputs, redacted observations, integrity checks, an executable replay contract, and a machine-readable verdict. Current ad-hoc reports frequently omit the environment, include secrets, silently mutate between capture and replay, or conflate a genuine failure with a tool crash.

FaultPack addresses this by separating four responsibilities:

1. **Capture** records an observation under an explicit policy and persists only selected inputs and redacted outputs.
2. **Verify** checks schema validity, path safety, hashes, signatures, and pack-level invariants without executing the declared command.
3. **Replay** executes only after verification, in a bounded temporary workspace, and returns a structured observation.
4. **Compare** evaluates the replay against a declared oracle and reports reasons rather than a bare Boolean.

## Target users and use cases

The primary users are maintainers receiving bug reports, library authors collecting minimal reproducers, CI engineers preserving flaky or environment-sensitive failures, and security researchers sharing sanitized test cases. A secondary audience is a team that needs to attach a signed, reviewable reproduction artifact to a GitHub issue or pull request without adopting a hosted service.

A typical workflow is:

```text
failure -> capture -> inspect/redact -> verify -> share -> replay -> compare -> reduce -> regression fixture
```

## MVP contract

The v1.0 MVP preserves the existing capture, inspect, verify, replay, reduce, and version commands, while adding:

| Surface | Contract | Safety posture |
|---|---|---|
| Pack format | Versioned manifest plus content-addressed artifacts | Strict schema, safe relative paths, no implicit files |
| Capture | Bounded child process with explicit argv, cwd, inputs, and env allowlist | Redaction occurs before persistence and hashing |
| Verification | Pure validation of manifest, artifacts, inputs, and optional signature | Never executes pack commands or fetches URLs |
| Replay | Temporary workspace, declared timeout, selected input restoration | Not a sandbox; caller must isolate untrusted code |
| Oracle | Exit code, regex, hashes, duration cap, and status reasons | No hidden normalization of mismatches |
| Reduction | Bounded delta debugging for UTF-8 line fixtures | Candidate accepted only if the original failure oracle remains true |
| Differential replay | Compare two verified packs or two replay outcomes | Reports semantic differences without claiming causality |
| Signing | Optional Ed25519 detached signature over canonical fingerprint | Verification requires an explicit public key; no trust discovery |
| Reporting | JSON, Markdown, SARIF, and JUnit | Exit codes distinguish reproduced, mismatch, and invalid pack |
| GitHub Action | Pinned consumer action with least-privilege permissions | No network upload beyond GitHub's own artifact handling |

## Non-functional requirements

**Determinism.** Canonical JSON uses UTF-8, sorted keys, stable separators, and a trailing newline. ZIP output uses sorted paths and a fixed timestamp. Volatile values such as creation time, pack ID, and measured duration do not affect the v0.2/v1.0 logical fingerprint.

**Fail-closed behavior.** Invalid manifests, traversal attempts, symlink escapes, malformed hashes, missing inputs, invalid signatures, and unsupported policy values must produce explicit failures. The verifier must never silently downgrade an integrity failure to a warning.

**Privacy.** Only selected input files are copied. The child receives a conservative environment plus an explicit allowlist. Secret-like environment names and common token, email, IP, and private-key patterns are redacted before output is persisted or hashed. The tool must document that regex redaction cannot guarantee removal of arbitrary secrets.

**Portability.** The pack is a directory that can be zipped, inspected without installation, and replayed by the Python reference implementation on Python 3.10+. The manifest is language-neutral so future adapters can produce observations without coupling to the Python implementation.

**Performance.** Hashing and copying use streaming or bounded operations where possible. Replay output is captured with the operating-system subprocess facilities and bounded by the declared timeout. Reduction has an explicit maximum-run budget. Reports are generated in memory only for one replay result.

**Operability.** Every CLI command has stable exit semantics, structured JSON output where useful, and an error message safe to show in CI. No telemetry, hosted account, implicit upload, or model call is required.

## Component architecture

```text
                    +-------------------+
                    | Typer CLI / Action|
                    +---------+---------+
                              |
                    +---------v---------+
                    | Application seams |
                    | capture / verify  |
                    | replay / reduce   |
                    | diff / report     |
                    +---+----+----+-----+
                        |    |    |
       +----------------+    |    +----------------+
       |                     |                     |
+------v------+      +-------v------+      +-------v-------+
| Pack writer |      | Integrity    |      | Replay engine |
| manifest    |      | canonical    |      | temp workspace|
| artifacts   |      | hash/sign    |      | subprocess    |
+------+------+      +--------------+      +-------+-------+
       |                                             |
       +------------------+--------------------------+
                          v
                 +-----------------+
                 | Oracle/comparer |
                 | reports/diff    |
                 +-----------------+
```

The domain layer remains independent from Typer. `models.py` owns the schema contract, `core.py` owns canonicalization, hashing, safe paths, and verification, `pack.py` owns capture and packaging, `replay.py` owns execution and oracle comparison, `reducer.py` owns bounded minimization, and `report.py` owns output formats. New behavior must enter through these seams rather than embedding business logic in CLI commands.

## Data model

A manifest consists of a source reference, command specification, environment description, selected input file entries, observed capture result, expectation/oracle, and a logical fingerprint. Each persisted artifact is addressed by a safe relative path and has a SHA-256 digest. The fingerprint is computed from canonical manifest content after excluding volatile fields.

The v1.0 signing model is intentionally detached:

```text
canonical manifest -> logical fingerprint -> Ed25519 signature file
                                      |
                                      +-> verifier checks signature with explicit public key
```

No private key is accepted in a manifest, and a signer label is never treated as proof. HMAC remains available for backward compatibility with v0.2 fixtures, while Ed25519 is the preferred interoperable option for v1.0.

## Data flow

During capture, FaultPack validates the caller's paths, copies only declared input files, launches the command with an allowlisted environment, redacts stdout and stderr in memory, computes digests, writes a manifest, and optionally writes a detached signature. A non-zero child exit is a valid observed failure, not a FaultPack error.

During verification, FaultPack parses the manifest, recomputes the logical fingerprint, resolves every referenced path beneath the pack root, hashes each artifact and input, and verifies an explicitly requested signature. Verification never invokes the command. During replay, the verified inputs are copied to a fresh temporary workspace, the command is executed with the declared timeout, and the result is compared against the expectation. The report includes the observed status and every mismatch reason.

## Error flow

| Condition | Internal meaning | CLI exit |
|---|---|---:|
| Child exits non-zero during capture | Valid failure evidence | 0 |
| Missing input or invalid capture policy | Capture could not produce a valid pack | 3 |
| Malformed/tampered/unsafe pack | Integrity or policy failure | 4 |
| Verified replay matches oracle | Reproduced | 0 |
| Verified replay does not match oracle | Valid replay, non-matching behavior | 5 |
| Unexpected implementation exception | Surface as safe error and preserve no partial output | 4 |

Partial output directories are removed when capture or reduction cannot complete. Replay always removes owned temporary workspaces. A report must distinguish `invalid_pack`, `replay_error`, `mismatch`, and `reproduced`; these are not interchangeable states.

## Security model

FaultPack protects against accidental disclosure, path traversal, pack tampering, and misleading verification results. It does not protect against a malicious command executing with the caller's host privileges, network access, kernel compromise, malicious interpreters, or a dishonest producer. The documented safe deployment model is to replay untrusted packs inside an isolated CI runner or container with network and filesystem restrictions supplied by the caller.

The trust boundary is explicit:

```text
producer -> redaction policy -> pack bytes -> verifier -> caller-controlled replay isolation
```

The verifier treats all manifest fields and artifact contents as untrusted data. It does not execute commands during inspection or verification, resolve URLs, load plugins, import code from the pack, or infer trust from labels. Additional redaction patterns are compiled as regular expressions; invalid patterns fail the capture rather than being ignored.

## Differential replay

Differential replay compares two verified evidence paths using normalized structured observations. It reports changes in status, exit code, stdout/stderr digest, declared oracle result, and timing threshold. Timing is diagnostic only and never treated as causal proof. A future matrix runner may execute the same pack across Python versions, operating systems, or container backends, but the first implementation will keep the execution backend explicit and bounded.

## Extensibility strategy

Adapters should produce the stable manifest and observation contracts. The first planned adapters are pytest, Jest, Go test, and OCI/Podman. Adapters must not execute arbitrary user-provided plugin code inside the verifier. They can be separate producer commands or trusted host-side integrations that emit a validated pack.

Future integration with ProofMesh and CorpusSeal should use exported JSON reports and pack fingerprints, not direct imports of internal modules. This preserves repository independence and allows each project to evolve at its own release cadence.

## Testing strategy

Tests are organized around named invariants rather than line coverage alone. The suite must cover canonicalization, fingerprint stability, redaction-before-hash, path and symlink escape rejection, malformed schema rejection, artifact tampering, signature mismatch, failure preservation, timeout semantics, replay mismatch reasons, deterministic ZIP output, reducer budgets, differential comparison, report schemas, and stable CLI exit codes. Property-style tests should be added for path normalization and canonical JSON once the core contract stabilizes.

## Release and CI strategy

CI runs linting, strict type checking, the complete pytest suite with a coverage floor, packaging, a CLI smoke test, and an action metadata check. Release tags must be immutable references for consumers. The composite action uses least-privilege permissions and writes reports locally; users choose whether to upload SARIF or artifacts.

## Roadmap

The v1.0 release focuses on a complete and honest local workflow. v1.1 can add pytest/Jest/Go adapters and replay matrices. v1.2 can add OCI/Podman isolation adapters and verified reproducible-build metadata. Later releases can add a static report viewer and an opt-in anonymized corpus. A hosted multi-tenant dashboard and autonomous repair remain intentionally out of scope.

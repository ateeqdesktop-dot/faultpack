# FaultPack 1.1 — architecture and delivery contract

## Product vision

FaultPack is the open failure-reproduction standard for software teams. It compiles a real failure into a small, reviewable artifact that can be safely shared, independently verified, replayed, reduced, compared, and promoted into a regression fixture.

The core promise is **capture once, verify anywhere, replay safely, prevent recurrence**. FaultPack is not a hosted incident system, a debugger replacement, a sandbox, an observability backend, or an autonomous repair agent.

## Problem and users

A screenshot or pasted log does not preserve the exact command, selected inputs, environment policy, integrity state, or executable reproduction contract. This causes maintainers to spend time reconstructing failures that reporters already observed and makes it difficult to distinguish a changed environment from a changed code path.

The primary users are open-source maintainers, library authors, CI engineers, security researchers, and teams that need to attach a sanitized reproduction artifact to an issue or pull request without sending data to a hosted service.

## Scope of 1.1

Version 1.1 keeps the existing v0.1/v0.2 packs readable and verifiable. It adds a deterministic, local-first **replay matrix** and a producer-facing **adapter contract** without adding a database, daemon, telemetry, hosted account, or implicit network call.

| Capability | 1.1 contract | Explicit boundary |
|---|---|---|
| Existing lifecycle | capture, inspect, verify, replay, diff, reduce, bundle, keys | Existing CLI names and exit codes remain stable |
| Matrix replay | Run one verified pack against named local profiles, aggregate verdicts, emit JSON/Markdown/SARIF/JUnit | Profiles are caller-controlled commands/env overlays; no container orchestration |
| Profile isolation | Every profile receives a fresh temporary workspace and a bounded subprocess | FaultPack does not sandbox malicious code |
| Adapter contract | Validate and normalize external producer manifests through a documented JSON contract | Adapters do not execute pack code during verification |
| Report provenance | Reports include pack fingerprint, profile name, tool version, and outcome classification | Timing is diagnostic, never causality |
| CI integration | Composite Action can run single-pack or matrix mode and upload local reports | Upload is the caller’s GitHub artifact step, not FaultPack telemetry |

## Functional requirements

A valid pack must contain a versioned manifest, declared command, selected input files, redacted observations, hashes, an expectation oracle, and a logical fingerprint. Verification must be pure: it validates schema, paths, hashes, and requested signatures without invoking the command or resolving URLs.

A matrix profile is a named execution variation. The profile schema is intentionally small: a stable name, optional environment overrides, optional command argv override, and an optional timeout cap. A profile may only narrow the pack timeout, never expand it beyond the pack’s declared bound. Environment overrides are allowlisted and redacted before they are passed to the child. Profile names are safe identifiers and appear in report keys.

The matrix runner verifies the pack once, executes each profile in deterministic declaration order, retains every result, compares each result with the pack oracle, and returns a non-zero matrix exit only when at least one profile does not reproduce the declared behavior or when the pack is invalid. A profile execution failure is a result, not an exception that hides other profiles.

## Non-functional requirements

**Determinism.** JSON is canonicalized with UTF-8, sorted keys, stable separators, and a trailing newline. Matrix result ordering follows input profile order. ZIP output keeps stable paths and timestamps. Volatile duration and creation time never enter the logical pack fingerprint.

**Fail closed.** Invalid profile names, malformed environment keys, unsafe command overrides, timeout expansions, missing artifacts, traversal, symlink escapes, tampered hashes, and invalid signatures fail explicitly. Unknown manifest fields remain rejected by the Pydantic contract.

**Privacy.** Only selected inputs are included. Child environments are conservative and profile overlays are restricted to explicit names. Built-in and user-supplied redaction occurs before output is persisted or hashed. The documentation states that regex redaction cannot guarantee removal of arbitrary sensitive content.

**Portability.** The reference implementation remains Python 3.10+. The pack and matrix result schemas are language-neutral JSON. A future producer can emit a validated pack without importing FaultPack internals.

**Performance.** Matrix profiles run sequentially by default to preserve predictable resource use and output ordering. Every profile has a bounded timeout and temporary workspace. Parallel execution is deliberately deferred until a resource and output-order contract exists.

**Operability.** Every command has stable exit semantics, structured JSON output, and human-readable error text safe for CI logs. No LLM call, account, network access, or telemetry is required.

## Architecture

```text
                         +----------------------+
                         | CLI / GitHub Action  |
                         +----------+-----------+
                                    |
                    +---------------v----------------+
                    | application seams              |
                    | capture verify replay matrix  |
                    | reduce diff report adapters   |
                    +---+------------+-----------+----+
                        |            |           |
              +---------v--+ +-------v------+ +--v-----------+
              | Pack writer | | Integrity    | | Replay engine|
              | manifest    | | canonicalize | | temp workspace|
              | artifacts   | | hashes/sign  | | bounded child|
              +------+------+ +--------------+ +--+-----------+
                     |                              |
                     +---------------+--------------+
                                     v
                            +------------------+
                            | Oracle + reports |
                            | JSON MD SARIF XML|
                            +------------------+
```

`models.py` owns typed contracts. `core.py` owns canonicalization, hashes, safe paths, and verification. `pack.py` owns capture and packaging. `replay.py` owns one bounded execution and oracle comparison. `matrix.py` owns profile validation, overlay application, ordered execution, and aggregate classification. `report.py` owns output serialization. `cli.py` is an adapter only and does not implement domain policy.

## Data flow

```text
verified pack
    |
    +--> validate profiles --> for each profile in declaration order
    |                              |
    |                              +--> fresh workspace
    |                              +--> safe argv/env overlay
    |                              +--> bounded subprocess
    |                              +--> compare against pack oracle
    |                              +--> structured MatrixResult
    |
    +--> aggregate verdict --> JSON / Markdown / SARIF / JUnit
```

The matrix runner does not mutate the pack and never writes into it. Report paths are created under a caller-provided directory. A failed profile cannot prevent cleanup of a later profile’s workspace.

## Error semantics

| Condition | Meaning | CLI exit |
|---|---|---:|
| All profiles reproduce | Matrix success | 0 |
| One or more profiles mismatch | Valid run with regression/environment divergence | 5 |
| Invalid pack or profile policy | Cannot trust or execute the requested matrix | 4 |
| Capture policy cannot create a pack | Capture failure | 3 |
| Unexpected implementation error | Safe surfaced error; no partial pack | 4 |

Each profile has an explicit `outcome`: `reproduced`, `mismatch`, or `execution_error`. The aggregate has `passed`, `failed`, and `invalid` counts plus a boolean `all_reproduced`. A timeout remains both an execution status and an oracle reason; it is never silently converted into a pass.

## Security model

The pack and profile files are untrusted data. Verification never imports code, loads plugins, runs commands, fetches URLs, or follows links. Replay executes the declared or profile-overridden command with the caller’s operating-system privileges; users must isolate untrusted packs in a restricted CI runner or container. FaultPack does not claim kernel, filesystem, or network isolation.

Profile overlays cannot change the pack’s working-directory policy, add traversal, or expand the timeout. The command override is a list of argv tokens rather than a shell string; no shell is involved. Environment overlays require conservative variable-name validation and are passed through the same redaction policy as capture.

## Testing strategy

The implementation must preserve the existing 19-test contract suite and add focused tests for profile validation, timeout narrowing, environment overlays, command-token safety, ordered matrix aggregation, mixed reproduced/mismatch results, execution errors, report schemas, stable exit codes, and cleanup after a failed profile. Tests use local deterministic Python commands and no network or API keys.

## MVP and roadmap

The delivered 1.1 MVP is the complete local lifecycle plus matrix replay, CI reports, adapter schema documentation, and regression tests. Advanced features are producer adapters for pytest/Jest/Go, a static report viewer, OCI/Podman execution backends, and cross-platform matrix presets. Future work may add an opt-in anonymized corpus and verified build metadata. Hosted multi-tenant storage, automatic uploads, arbitrary plugins, and autonomous repair remain out of scope.

## Release checklist

The release is ready when tests, coverage, linting, typing, packaging, CLI smoke tests, Action metadata checks, and deterministic report checks pass; README examples work from a clean checkout; the security boundary and limitations are visible; and the GitHub repository contains a release note, contributing guide, code of conduct, security policy, license, issue templates, and a changelog.

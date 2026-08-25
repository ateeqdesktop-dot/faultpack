# FaultPack Flagship Strategy

## Decision

FaultPack will be the account's flagship open-source project. This is an evolution decision rather than another repository: the account already has many adjacent AI-governance and reproducibility experiments, while FaultPack has the clearest standalone problem, the strongest offline-first trust boundary, and a practical path to adoption by any language ecosystem.

The product is an **evidence-grade failure capsule toolkit**. It captures a selected failure, removes or redacts sensitive observations before persistence, verifies integrity without execution, replays only when explicitly requested, compares behavior, reduces text fixtures, signs the logical evidence, and emits CI-native reports.

> A screenshot describes a failure. A FaultPack capsule makes the failure inspectable, verifiable, and replayable.

## Why this adds more value than a new adjacent project

The account's existing repositories are strong in breadth but heavily clustered around AI-agent policy, replay, and governance. Creating another gateway, policy engine, MCP server, trace verifier, or generic observability platform would duplicate the portfolio and face powerful competitors. FaultPack is different: it solves a universal maintainer problem across Python, JavaScript, Go, Rust, and native projects without requiring a hosted service, model API, database, or telemetry pipeline.

AgentLab demonstrates scalable agent benchmarking, while Langfuse demonstrates the value of a broad hosted/self-hosted LLM engineering platform. Neither is a small, language-neutral, privacy-first artifact contract for one difficult failure case. Existing delta-debugging libraries minimize inputs, but do not define a portable evidence format, privacy boundary, cryptographic integrity model, replay oracle, CI reports, or signed sharing workflow.

## Candidate scoring

Scores are from 1 to 10. The score is a strategic decision aid, not a claim that alternatives are bad.

| Candidate | Originality | Technical depth | Real-world value | Developer value | OSS potential | Portfolio/recruiter appeal | Scalability | Maintainability | Extensibility | Testing/CI potential | Total / 100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Evolve FaultPack into a failure-capsule standard and GitHub-native workflow | 9 | 9 | 9 | 9 | 8 | 9 | 8 | 9 | 10 | 10 | **90** |
| Build another AI-agent governance gateway | 6 | 9 | 8 | 8 | 7 | 8 | 9 | 6 | 8 | 9 | 78 |
| Build a generic LLM observability/evaluation platform | 5 | 9 | 9 | 9 | 8 | 8 | 9 | 5 | 8 | 8 | 78 |
| Build a repository-maintainer analytics dashboard | 7 | 7 | 7 | 8 | 7 | 8 | 8 | 7 | 8 | 8 | 75 |

## Product contract

### Target users

The primary users are open-source maintainers, CI engineers, library authors, QA engineers, and developers debugging flaky or environment-sensitive failures. The secondary users are security-conscious teams that need to share a reproduction without uploading an entire repository or trusting a hosted debugger.

### MVP already present

The current implementation already provides a versioned manifest, explicit input selection, environment allowlisting, redaction, canonical hashing, symlink and traversal defenses, bounded replay, failure oracles, differential replay, deterministic reduction, matrix replay, detached Ed25519 signatures, JSON/Markdown/SARIF/JUnit output, and a reusable GitHub Action.

### Flagship hardening implemented in this delivery

This delivery will make the project easier to adopt and review by adding a privacy preflight command, stable machine-readable diagnostics, richer pack inspection, stronger negative-path tests, a complete contributor/release surface, and documentation that clearly separates passive verification from active execution. The hardening is intentionally local-first and does not add a hosted backend or hidden telemetry.

### Non-functional requirements

The core verifier must remain deterministic, offline-capable, and safe to run on untrusted pack bytes. Verification must never execute the declared command, follow symlinks outside the pack, fetch URLs, load plugins, or infer trust from labels. Replay must be bounded by an explicit timeout and must be documented as caller-sandboxed rather than a security sandbox. Reports must be stable enough for CI snapshots.

## Architecture

```text
CLI / GitHub Action
        |
        +--> CaptureService --> selection --> redaction --> PackWriter
        |
        +--> Inspector ------> manifest summary / privacy diagnostics
        |
        +--> Verifier -------> canonical JSON --> hashes --> signatures
        |
        +--> ReplayService --> temporary workspace --> bounded subprocess
        |                                             |
        +--> Reducer ---------------------------------+
        |
        +--> Matrix / Differential comparer --> JSON / Markdown / SARIF / JUnit
```

The domain layer remains independent from Typer. Models own the versioned contract; core owns canonicalization and verification; capture and packaging own filesystem materialization; replay owns subprocess execution; reducers own bounded minimization; reports own output formats; signing owns optional Ed25519 interoperability; the new diagnostics layer performs passive checks only.

## Roadmap

The next release focuses on adoption: a stable diagnostics contract, examples for Python and shell, release automation, and clear security documentation. The following release can add producer adapters for pytest, Jest, Go test, and Rust test while preserving the core passive verifier. Later work may add OCI/Podman execution backends and an opt-in public corpus. A hosted multi-tenant dashboard and autonomous repair remain out of scope until the local contract has a real community.

## References

[1]: https://github.com/ServiceNow/AgentLab "ServiceNow AgentLab"
[2]: https://github.com/langfuse/langfuse "Langfuse"
[3]: https://github.com/jhawthorn/delta_debug "delta_debug"
[4]: https://arxiv.org/abs/2607.16200 "Deterministic Replay for AI Agent Systems"

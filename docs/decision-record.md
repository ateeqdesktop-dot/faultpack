# Product decision record: FaultPack as the flagship

## Decision

FaultPack remains the flagship project and is evolved rather than surrounded by another adjacent repository. The account already contains multiple experiments around agent governance, trace privacy, replay, policy enforcement, and evidence. A new MCP gateway, generic observability dashboard, or another trace verifier would create portfolio overlap and compete directly with mature projects.

FaultPack addresses a narrower and more portable problem: **how can a maintainer share one difficult failure as a small, privacy-aware, cryptographically checkable contract that another machine can inspect, compare, and optionally replay?**

## Competitive gap

Langfuse and Phoenix are broad open-source LLM engineering platforms covering traces, evaluations, datasets, experiments, prompt management, and interactive debugging. OpenTelemetry and MCP provide useful interoperability and security foundations. These tools are valuable, but they do not aim to be a tiny, language-neutral, offline evidence capsule for a single failure case. FaultPack complements them at the artifact boundary.

The product therefore optimizes for four properties: **portable**, **passive by default**, **privacy-aware before persistence**, and **deterministic enough for CI review**. It deliberately does not become a hosted observability platform, a general-purpose sandbox, an autonomous repair agent, or a trust-root discovery service.

## Candidate scoring

Scores are 1–10 and combine the requested strategic criteria. The decision is based on total value, not implementation ease.

| Candidate | Orig. | Depth | Real value | Dev value | OSS | GitHub | Portfolio | Scale | Maintain | Extend | Docs | Tests | Arch | CI | Community | Learning | Long-term | Total / 180 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Evolve FaultPack into an evidence-capsule standard and GitHub-native workflow | 9 | 9 | 9 | 9 | 8 | 9 | 10 | 8 | 9 | 10 | 10 | 10 | 9 | 10 | 8 | 9 | 10 | **157** |
| Build another AI-agent governance gateway | 6 | 9 | 8 | 8 | 7 | 8 | 8 | 9 | 6 | 8 | 8 | 9 | 8 | 9 | 7 | 9 | 8 | **137** |
| Build a generic LLM observability/evaluation platform | 5 | 9 | 9 | 9 | 8 | 8 | 8 | 9 | 5 | 8 | 8 | 8 | 8 | 8 | 8 | 9 | 8 | **137** |
| Build a maintainer analytics dashboard | 7 | 7 | 7 | 8 | 7 | 8 | 8 | 8 | 7 | 8 | 8 | 8 | 7 | 8 | 8 | 8 | 8 | **130** |
| Build a basic AI assistant or CRUD product | 3 | 5 | 5 | 5 | 4 | 4 | 4 | 6 | 7 | 6 | 5 | 6 | 5 | 6 | 4 | 5 | 5 | **85** |

## Product scope

### Current MVP

The existing MVP captures explicit inputs and an allowlisted environment, redacts before persistence and hashing, verifies canonical manifests, detects traversal and symlink escapes, replays under a bounded timeout, evaluates failure oracles, reduces text fixtures, compares behavior, signs logical fingerprints with Ed25519, emits JSON/Markdown/SARIF/JUnit, and runs through a reusable GitHub Action.

### This delivery

This delivery adds a **self-contained offline HTML evidence viewer** through `faultpack inspect --html --output report.html`. The viewer is generated only after passive verification, contains no external scripts or fonts, escapes all manifest-derived text, surfaces the execution contract and evidence timeline, and explicitly states the replay security boundary. It is useful in pull-request artifacts and incident handoffs without introducing a server, database, telemetry, or runtime dependency.

### Advanced features

The next high-value extensions are producer adapters for pytest, Jest, Go test, and Rust test; OCI/Podman execution backends supplied by the caller; richer schema compatibility tooling; and an opt-in anonymized corpus. These remain separate adapters so the verifier core stays small and auditable.

### Out of scope

A hosted multi-tenant dashboard, implicit uploads, autonomous repair, opaque plugin execution, trust-root discovery, and claims that replay is a sandbox are intentionally excluded.

## Architecture

```text
CLI / GitHub Action
        |
        +--> CaptureService --> selection --> redaction --> PackWriter
        |
        +--> Inspector ------> verify --> HTML/JSON summary
        |
        +--> Verifier -------> canonical JSON --> hashes --> signatures
        |
        +--> ReplayService --> caller-supplied isolated runner --> oracle
        |
        +--> Matrix / Diff / Reduce --> stable CI reports
```

The viewer is a pure presentation function over a verified `Manifest`. It has no file-system access, no network access, no subprocess execution, and no template engine. This keeps the security boundary obvious and makes output reproducible for snapshot-style tests.

## Verification plan

The acceptance bar is: all existing tests pass; the HTML command refuses a tampered pack; raw HTML is never emitted from manifest values; the output is readable without network access; `ruff`, `mypy`, and package builds pass; and the README explains the feature with a copy-pasteable command.

## References

[1]: https://github.com/langfuse/langfuse "Langfuse open-source AI engineering platform"
[2]: https://github.com/Arize-ai/phoenix "Arize Phoenix AI observability and evaluation"
[3]: https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices "MCP Security Best Practices"
[4]: https://github.com/jhawthorn/delta_debug "delta_debug project"

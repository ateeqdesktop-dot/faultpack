# FaultPack Evidence Interoperability Layer

## Product boundary

FaultPack already captures and verifies portable failure reproductions. This extension adds an **offline evidence bridge** for heterogeneous AI-agent, tool, MCP, OpenInference, OpenTelemetry, and CI records. It converts a documented subset of those inputs into one canonical, versioned, privacy-bounded evidence bundle that can be independently verified and consumed by existing FaultPack workflows. The bridge follows the surrounding ecosystem rather than redefining it: OpenTelemetry publishes GenAI semantic conventions [1], and OpenInference defines a vendor-neutral observability vocabulary for AI applications [2].

The bridge is deliberately not an observability backend, a runtime policy engine, a hosted dashboard, a model judge, or a replacement for OpenTelemetry/OpenInference. Langfuse already occupies the broad tracing and evaluation platform space [3], while the Microsoft Agent Governance Toolkit focuses on runtime governance [4].
It never executes imported commands, follows URLs, uploads source data, or retains raw payloads in the normalized output. It stores only bounded metadata and SHA-256 digests unless the caller explicitly opts into a bounded, redacted preview.

## MVP use cases

A developer can export a JSONL trace from an agent or MCP client, run `faultpack interop` locally, review deterministic findings, and commit or attach the resulting bundle to a pull request. A CI job can verify a previously-produced bundle, emit JSON/SARIF/JUnit, and fail closed on malformed input, unsupported versions, digest mismatch, sequence violations, or missing required identity fields. A maintainer can compare the canonical event summary from two bundles without needing the original observability platform.

## Canonical contract

The bundle has `format: "faultpack-evidence"`, `format_version: "0.1"`, a producer descriptor, an adapter name, an optional source identity, an ordered event list, a finding list, and a `bundle_sha256` calculated over the canonical JSON with that field omitted. Every event has a stable sequence, a normalized kind, a name, optional trace/span/parent identifiers, status, duration, attributes, and a payload digest. Unknown input fields are ignored by adapters but never copied into the bundle. Event attributes are stringified, sorted, bounded, and redacted using FaultPack's existing redaction implementation.

The normalized event taxonomy is intentionally smaller than any one vendor schema: `agent`, `model`, `tool_call`, `tool_result`, `retrieval`, `policy`, `evaluation`, `assertion`, and `annotation`. Mapping decisions are explicit and included in each event's `source_kind`. The bundle records provenance as metadata (format, adapter, producer, and source digest), not as a claim that the imported record proves an outcome.

## Adapters

| Adapter | Input | Supported subset | Safety boundary |
|---|---|---|---|
| `generic-jsonl` | One JSON object per line | `kind`/`type`, `name`, identifiers, timestamps, status, duration, attributes, payload | Size and line limits; payload becomes a digest |
| `openinference-otlp-json` | OTLP JSON export | `resourceSpans`, `scopeSpans`, span identity, status, timestamps, `openinference.span.kind`, selected `gen_ai.*` attributes | No network; only bounded attributes are projected |
| `mcp-jsonl` | MCP-style JSONL | `method`/`name`, tool call/result, request/response IDs, timestamps, params/result digest | Params/results are never copied by default |
| `ci-jsonl` | CI event JSONL | command/test/check, status, exit code, duration, job/step identity | Commands are data only and are never run |

Auto-detection is conservative. If a document resembles more than one adapter, the caller must pass `--format`; ambiguity is a finding rather than a silent guess. Unsupported input is a deterministic error with a line/path witness.

## Verification and findings

Verification recomputes the canonical digest, validates the schema, checks strict sequence ordering, checks identifier shape and size bounds, confirms event count, and evaluates adapter-specific conformance rules. Findings have a stable rule ID, severity (`info`, `warning`, `error`), JSON path, short message, and remediation. A bundle with warnings can be inspected successfully; errors produce a non-zero CI result. The verifier never infers correctness from an agent's output and never labels an event as proof of an external fact.

## Error flow

Malformed JSON, invalid UTF-8, oversized files, invalid fields, ambiguous detection, and digest mismatches are converted into typed `InteropError` or deterministic findings. The CLI prints a machine-readable result and uses exit code `4` for invalid input/bundle and `6` when `--fail-on-findings` is requested and review is required. No partial bundle is written on a fatal parse error; temporary output is written and atomically replaced only after successful validation.

## Security model

The bridge is passive by design. It does not execute commands from CI or agent logs, import Python modules, resolve package names, contact GitHub, call an LLM, follow filesystem links, or upload telemetry. Inputs are read as regular files with a 10 MiB default limit and a 2 MiB per-line limit. Attribute values are redacted and truncated before persistence. Identifiers are validated as bounded strings. Cryptographic signatures remain the responsibility of FaultPack's existing Ed25519 signing surface; a future version may sign an interop bundle without changing the canonical contract.

## Architecture

```text
input file
   |
   v
adapter detection ---> selected adapter ---> bounded parser
                                             |
                                             v
                                   normalized event model
                                             |
                         redaction + canonical ordering + findings
                                             |
                 +---------------------------+-----------------------+
                 |                           |                       |
          bundle JSON                    JSON result          SARIF/JUnit
                 |                           |                       |
                 +------------ verify / diff / CI gate --------------+
```

The adapter layer knows vendor shapes. The domain layer knows only the canonical models and validation. The output layer serializes stable JSON and CI reports. This separation makes future adapters publishable without coupling them to the CLI or FaultPack's command runner.

## Non-functional requirements

The implementation remains dependency-light and Python 3.10-compatible, keeps the existing 90% coverage gate, avoids network access, has deterministic output for the same input bytes, and maintains backward compatibility with existing `faultpack.json` packs. The canonical bundle must be stable across process runs and independent of dictionary insertion order.

## Advanced roadmap

The next increments can add OpenTelemetry protobuf ingestion, direct OTLP exporter hooks, DSSE/in-toto-compatible attestations, bundle-to-FaultPack sidecars, an official adapter SDK, differential bundle comparison, and a static HTML viewer. None of those are required for the MVP and none should weaken the passive/offline boundary.

## Related standards and prior art

The implementation claims interoperability and developer ergonomics, not invention of portable signed agent evidence. in-toto provides mature signed software-supply-chain provenance concepts [5]; agent-replay and AGILAB cover adjacent replay and portability workflows [6] [7]. The AEGIS paper is a direct conceptual neighbor for portable agent evidence and is therefore an explicit design constraint, not a claim of an empty market [8].

## References

[1]: https://github.com/open-telemetry/semantic-conventions-genai OpenTelemetry GenAI semantic conventions.
[2]: https://arize-ai.github.io/openinference/spec/ OpenInference specification.
[3]: https://github.com/langfuse/langfuse Langfuse open-source observability and evaluation platform.
[4]: https://github.com/microsoft/agent-governance-toolkit Microsoft Agent Governance Toolkit.
[5]: https://github.com/in-toto/in-toto in-toto software supply-chain integrity framework.
[6]: https://github.com/clay-good/agent-replay agent-replay.
[7]: https://github.com/ThalesGroup/agilab AGILAB.
[8]: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6392459 AEGIS: A Portable Evidence Interface Between AI-Agent Logging and Independent Audit.

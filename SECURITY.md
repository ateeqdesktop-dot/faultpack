# Security Policy

## Scope

FaultPack processes command output, selected environment metadata, and input files that may contain sensitive information. A replay pack is an instruction to execute a command, so it must be treated as untrusted code.

## Security boundary

FaultPack is **not a sandbox**. Replay uses a temporary workspace, a bounded timeout, and a minimal environment, but it does not enforce network isolation, prevent kernel escape, or remove all process-level risk. Run third-party packs only inside an isolated CI runner or container without credentials.

The capture path redacts common secret-looking environment names and token, private-key, email, and IPv4 patterns before writing or hashing output. It includes only selected input files, rejects absolute/traversal/backslash/symlink paths, and never uploads artifacts implicitly. HMAC signing protects pack integrity when `FAULTPACK_SIGNING_KEY` is supplied; it does not prove that a pack is safe or that its command is trustworthy.

## Threat model

The implementation is designed to reduce accidental leakage and tampering from malicious or malformed pack data. It validates Pydantic manifests, resolves paths beneath the pack root, verifies artifact and input hashes, uses constant-time HMAC comparison, bounds subprocess runtime, and caps reducer executions. User-supplied regular expressions can still be expensive; use trusted patterns and small fixtures.

Redaction is conservative rather than complete. Review `faultpack.json`, `artifacts/`, and generated reports before sharing them. Never include real credentials, private keys, customer data, or confidential incident traces in fixtures.

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Contact the maintainer privately through the GitHub profile with the affected version, impact, minimal sanitized reproduction, and a suggested disclosure timeline. Do not send live credentials or personal data.

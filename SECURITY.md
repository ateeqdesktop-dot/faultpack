# Security Policy

## Scope

FaultPack handles command output, environment metadata, and files that may contain sensitive information. The project treats replay as untrusted-code execution and does not claim to provide sandboxing.

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Until a dedicated private advisory workflow is enabled, contact the maintainer privately through the GitHub profile and include a minimal reproduction, affected version, impact, and a suggested disclosure timeline. Do not send real credentials or personal data.

## Design commitments

FaultPack redacts common secret patterns before persistence, rejects traversal and symlink paths, avoids logging captured values by default, and keeps replay opt-in. These controls reduce risk but do not replace isolated execution, code review, or organizational secrets management.

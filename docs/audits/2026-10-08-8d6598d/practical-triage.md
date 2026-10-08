# Practical audit triage

Scope: the 30 Fable backlog entries for `github-runner/**` and the root README change. Independent subagent review checked the current source and relevant audit evidence. This document selects work; it does not apply fixes or inherit the original severity ratings.

Result: **22 KEEP, 3 DEFER, 5 DROP**. KEEP means fix the concrete problem with the smallest adequate change, not implement every recommendation in the original report.

| ID | Decision | Reason and smallest adequate response |
| --- | --- | --- |
| F1 | KEEP | Official archives are normal inputs and currently fail. Support contained relative symlinks safely; preserve traversal and link-escape protections. Test the official Node layout. |
| F2 | KEEP | Real `.runner` files can have a UTF-8 BOM. Use `utf-8-sig` and a fixture. |
| F3 | KEEP | Ordinary misconfiguration, expired credentials and busy runners need distinguishable, non-secret fallback reasons. Preserve fallback; downgrade this diagnostic defect from High to Medium. |
| F4 | KEEP | The trusted-ref boundary should be byte-exact. Enforce it in the trusted selector. The live exploit scenario remains PLAUSIBLE. |
| F5 | KEEP | Show the safely formatted rejected hosted label and accepted choices. This is Low/Medium operator friction, not High. |
| F6 | KEEP | Document at least one OS and architecture label. Do not tighten to exactly one merely because the backlog wording does. |
| F7 | KEEP | Document waiting for the first acceptance run to finish before dispatching the second. Changing concurrency is optional. |
| F8 | KEEP | Accept the documented `sha256:` prefix while retaining strict algorithm and hex validation. |
| F9 | KEEP | Document inspection and a scoped manual recovery or fresh preparation after interruption. No resume engine or automatic deletion. |
| F10 | KEEP | Show the resolved path for common macOS path aliases and distinguish wrong account from root. Preserve path guards. |
| F11 | KEEP | Explain flags, prerequisites, basic output and nonzero failure. No contract framework, exhaustive schema or mandatory uniform exit taxonomy. |
| F12 | DEFER | Complete-inventory preflight already exists. Runtime inventory checks would not protect initial selector placement or credential-free paths. Add only for observed drift or a concrete operational need. |
| F13 | KEEP | Describe Unix-only automatic guards honestly and keep Windows identity/ACL checks as native preflight. No new SID/ACL inspection subsystem. |
| F14 | KEEP | Strengthen existing tests with request-count assertions, a state-file cap case and mocks of existing identity/ownership functions. No production injection framework or mutation-testing infrastructure. |
| F15 | KEEP | Account for the runner's `.path` overriding plist PATH. Correct the service instructions and generated plan. |
| F16 | KEEP | Initial verified official `svc.sh install` is normal provisioning. After installation, manage the exact installed unit with `systemctl`; retain provenance and concurrent-write guards. No new Linux installer. |
| F17 | KEEP | Local rendering for a remote host is supported use. Identify the target staged plist path once in the manual plan. No transport abstraction. |
| F18 | KEEP | Make empty-repository/default-branch bootstrap a clear sequence. An actionable missing-helper guard is optional; elaborate automation is unnecessary. |
| F19 | KEEP | Name rejected archive members, missing entry points and digest mismatch values. Fold into the archive fixes rather than a diagnostics framework. |
| F20 | KEEP | Accept legitimate existing account short names and identify the invalid argument. Regex validation is not proof of a standard account. |
| F21 | KEEP | Point to the validator source/prerequisites and actionlint installation. Distinguish optional authoring tools; do not vendor a validator or add dependencies solely for this. |
| F22 | KEEP | Explain Codex versus Claude invocation and local versus published installation. Existing install spellings need not be unified cosmetically. |
| F23 | DEFER | SHA pinning is optional hardening, not a current correctness failure or broken promise. If selected later, two pins/comments suffice; no update framework. |
| F24 | DROP | Receipt migrations solve hypothetical future consumers, not an existing incompatibility. |
| F25 | DROP | Different operation-specific names do not cause a demonstrated failure. Explain semantics under F11 rather than rename flags and add aliases. |
| F26 | KEEP | Common SSH input forms need actionable errors: point to `--admin-account` and SSH config aliases for ports. No arbitrary SSH-option interface. |
| F27 | DROP | Repeated safety rules currently agree and help independently loaded references. Correct real drift when it exists rather than enforcing single-occurrence prose. |
| F28 | DROP | Dated evaluation counts describe historical runs; future tests do not invalidate them. No extra log architecture. |
| F29 | DEFER | The 84-line platform reference is manageable. Split when procedures grow or selective loading becomes an observed issue. |
| F30 | DROP | Diagrams are not necessary to correct any demonstrated failure. Clear steps and diagnostic reasons suffice. |

## Suggested fix groups

1. Real archive/state inputs and recovery: F1, F2, F8, F9, F19, with focused F14 regressions.
2. Selector and CI acceptance: F3-F7 and F18; preserve hosted fallback and add exact trust enforcement.
3. Services and remote host: F13, F15-F17, F20; use honest platform boundaries and existing official mechanisms.
4. Helper help and errors: F10, F11, F26.
5. Reproducible use and validation: F21, F22.

## Evidence behind disputed recommendations

- F12: `github-runner/references/ci.md:25` already requires complete accessible inventory, including selector hosted labels, and repetition after routing/access changes; `:33` requires routing-label uniqueness. `scripts/select_runner.py:75` queries by name. Extending that query alone cannot prevent unsafe initial scheduling or protect paths intentionally avoiding credentials.
- F16: `references/platforms.md:36` already requires verified provenance and protection against concurrent writes. Management commands at `:31-33` can be improved without replacing official installation.
- F23: `references/ci.md:7` pins the project's selector revision, not every external action; `:41` requires deployment-time version review. `assets/ci.yml:25,49` uses checkout's supported version tag.
- F14: `tests/test_select_runner.py:32-36,95-103` exposes the mock weakness; `prepare_runner.py:16-25,46,54` already has functions/attributes that can be patched with standard unittest mocks.
- F28: `tests/scenarios.md:39-58` labels initial and expanded evaluation, date and acceptance limits. These are historical evidence.
- F25: `macos_service.py:38,41-46,48` uses its service label coherently; it does not turn that label into GitHub routing configuration.

The reviewer reproduced F1 using an already downloaded official macOS archive with verified SHA and six symlinks; F2 with a BOM fixture; F8 with a prefixed digest; F3 with missing credentials and a busy runner; F4 with simulated API/ref cases; and F26 with common SSH input forms. Other decisions used current source and relevant individual audit evidence. Original severities were not accepted automatically.

No source fixes or Git mutations were performed. Native service installation, Windows ACL acceptance and a live case-variant branch exploit were not tested. Those limits do not prevent the selected local fixes; their deployment acceptance remains separate.

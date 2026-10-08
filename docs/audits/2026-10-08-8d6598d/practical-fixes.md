# Practical fixes receipt

The 22 KEEP entries in [practical-triage.md](practical-triage.md) were implemented in the current working tree. Original Fable reports describe the pre-fix snapshot and remain unchanged. No commit or external deployment was performed.

| Group | Selected entries | Result |
| --- | --- | --- |
| Preparation and recovery | F1, F2, F8, F9, F10, F19 | Official contained links, BOM, digest prefix, precise errors and preserved/manual recovery |
| Routing and acceptance | F3, F4, F5, F6, F7, F18 | Safe reasons, byte-exact ref, explicit platform configuration, complete bootstrap and sequential acceptance |
| Host/service/remote | F13, F15, F16, F17, F20, F26 | macOS/Linux target scope, effective PATH, verified systemctl unit management, target staging and usable account/SSH inputs |
| Interfaces and checks | F11, F14, F21, F22 | Minimal documented contracts, meaningful regression assertions, validator prerequisites and agent-specific invocation |

F13 was resolved by the user's narrowed macOS/Linux target scope, removing the Windows provisioning branch rather than implementing Windows ACL/SID machinery. The selector can still use a compatible hosted Windows fallback. F12, F23 and F29 remain deferred; F24, F25, F27, F28 and F30 remain dropped.

## Validation

- 35 runner tests, 59 package-task tests and 40 orchestration tests passed: 134 total.
- actionlint, skill-creator quick validation, Python compile without bytecode, relative markdown links and git diff whitespace checks passed.
- Official audited macOS ARM64 archive 2.338.0 extracted with its authoritative SHA256; parent independently read prepared receipt and npm link. No runner binary executed.
- A new fixture plist passed native plutil lint; the plan uses target STAGED_PLIST and documents runner .path precedence.
- Independent cross-review by the other implementation agents found bootstrap circularity and a PATH wording contradiction. Both were corrected before final delivery.
- Context7 canonical backend queried outside sandbox; official runner service sources and GitHub expression documentation checked.

## Boundaries

Native Linux extraction/service installation, macOS service startup/conversion, real CI, live case-variant branch behavior and reboot acceptance were not run. The runtime/user/session/privilege preflight remains necessary on each chosen host. No live runner registration, credential/account/service changes, Git mutations, commit or push.

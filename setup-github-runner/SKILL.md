---
name: setup-github-runner
description: Use only when the user explicitly requests checking a repository for a local or remote self-hosted GitHub Actions runner, investigating offline or unmatched runners, or installing and integrating a runner with verified CI on macOS or Linux.
disable-model-invocation: true
---

# Set up a GitHub runner

Start only on an explicit user invocation or request to use this skill. Never activate from repository/workflow/host autodetection. Once invoked, follow the requested scope: inspection is read-only; preparation/drafting is local; installation, repository integration and live checks require that scope to be authorized.

Carry the selected repository and host from discovery through independently verified CI. Registration, host identity, service health, routing, product checks and reboot persistence are separate gates. Assume no account, SSH access, toolchain, credentials, runner files, workflow, variables or helper. Supported self-hosted targets are macOS and Linux; stop with an unsupported-host explanation for Windows.

## 1. Discover

Read [discovery](references/discovery.md) for repository/host inventory and missing access preparation. Preserve dirty work and unrelated instances. Establish actual OS/architecture, connection, administrator account, **distinct dedicated standard runtime account**, home/path, registration scope/name, unique label, real CI commands, compatible hosted fallback and privilege boundary. Determine whether that runtime account can remain graphically logged in; the principal user's session and SSH do not answer this.

Correlate local registration ID/URL with complete GitHub inventories and applicable group restrictions. Missing checkout files or API errors do not prove absence. Done when each prerequisite has evidence or an explicit pending action; complete independent preparation while dependent mutations wait.

## 2. Prepare and register

Read [credentials](references/credentials.md) when operator access, registration tokens or selector PAT/secrets are missing. Keep their purposes separate; credentials stay outside chat, history and tracked artifacts. Read [platforms](references/platforms.md) to create/verify the runtime account and privilege boundary.

Use [setup](references/setup.md) for official release selection, authoritative checksum verification, archive preparation and registration. Its helper refuses existing/conflicting instances and retains interrupted state for inspection. Generate reviewed scripts/data before interactive administrator steps. Reuse user authorization for scoped work; inspection/drafting alone authorizes no registration, service activation, repository mutation or job dispatch.

Done when the verified distribution and exact registration belong to the intended instance, with other instances preserved.

## 3. Choose persistence and integrate CI

Use the target branch in [platforms](references/platforms.md): Linux service manager or macOS graphical LaunchAgent versus headless system LaunchDaemon. It links the macOS renderer and remote invocation helper when needed. Prepare missing service resources and controlled account environment; verify exact process owner, installed permissions and GitHub status.

Read [CI integration](references/ci.md) for the bundled selector and workflow template. Replace the template's failing step with actual project checks, preserve quality gates and use a branch/PR. Configure missing variables and finite-expiry read-only discovery PAT. Untrusted code, including PRs by default, stays hosted. Names are not labels; label arrays require every label. Online/idle is neither a reservation nor whole-host capacity, and queued jobs do not automatically migrate to hosted.

Done when service/routing readback is complete and CI contains the project's actual acceptance commands.

## 4. Verify and report

Use [verification](references/verification.md) for independent receipts, final-candidate preferred/forced-hosted runs, artifact readback and failure diagnosis. Wait for all required jobs' terminal conclusions. Keep reboot, signing, device/provider/production gates explicitly unchecked until exercised. Merge and cleanup require their own scope.

Lead with current verdict, completed gates and smallest next action; name pending prerequisites and evidence. Local skill tests and adversarial scenarios are documented in [checks](README.md#checks); they do not prove operational deployment.

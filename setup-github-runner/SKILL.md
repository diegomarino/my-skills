---
name: setup-github-runner
description: Use only when the user explicitly requests checking a repository for a local or remote self-hosted GitHub Actions runner, investigating offline or unmatched runners, changing CI activation conditions or runner routing policy, or installing and integrating a runner with verified CI on macOS or Linux.
disable-model-invocation: true
---

# Set up a GitHub runner

Start only on an explicit user invocation or request to use this skill. Never activate from repository/workflow/host autodetection. Once invoked, follow the requested scope: inspection is read-only; preparation/drafting is local; installation, repository integration and live checks require that scope to be authorized.

Carry the selected repository and host from discovery through independently verified CI. Registration, host identity, service health, routing, product checks and reboot persistence are separate gates. Assume no account, SSH access, toolchain, credentials, runner files, workflow, variables or helper. Supported self-hosted targets are macOS and Linux; stop with an unsupported-host explanation for Windows.

For activation-only work on an existing runner, inspect repository workflows and rules, then go directly to [CI activation](references/ci.md#choose-ci-activation-policy). Account, host installation and service steps apply only when requested or required by the integration scope.

## 1. Discover

Read [discovery](references/discovery.md) for repository/host inventory and missing access preparation. Preserve dirty work and unrelated instances. Establish actual OS/architecture, connection, administrator account, **distinct dedicated standard runtime account**, home/path, registration scope/name, unique label, real CI commands, compatible hosted route and privilege boundary. For existing routing-only work, inspect registration/configuration without entering account, installation or service steps. Read [CI integration](references/ci.md#choose-the-routing-policy) to offer required-local versus automatic fallback and collect the applicable variables before drafting routing changes; honor an already stated choice. Determine whether that runtime account can remain graphically logged in; the principal user's session and SSH do not answer this.

Correlate local registration ID/URL with complete GitHub inventories and applicable group restrictions. Missing checkout files or API errors do not prove absence. Done when each prerequisite has evidence or an explicit pending action; complete independent preparation while dependent mutations wait.

Choose repository or organization registration explicitly; for a shared organization runner, identify every intended repository and its trusted workflows. Follow [registration scope](references/setup.md#choose-registration-scope-and-access) for organization credentials, access-group preparation and the matching registration URL. Existing repository registrations are not converted implicitly.

## 2. Prepare and register

Read [credentials](references/credentials.md) when operator access, registration tokens or selector PAT/secrets are missing. Keep their purposes separate; credentials stay outside chat, history and tracked artifacts. Read [platforms](references/platforms.md) to create/verify the runtime account and privilege boundary.

Use [setup](references/setup.md) for official release selection, authoritative checksum verification, archive preparation and registration. Its helper refuses existing/conflicting instances and retains interrupted state for inspection. Generate reviewed scripts/data before interactive administrator steps. Reuse user authorization for scoped work; inspection/drafting alone authorizes no registration, service activation, repository mutation or job dispatch.

Done when the verified distribution and exact registration belong to the intended instance, with other instances preserved.

## 3. Choose CI activation, persistence and routing

For CI integration or activation changes, read [Choose CI activation](references/ci.md#choose-ci-activation-policy) before editing workflows. Advise on applicable events and conditions, including readiness, labels, approvals, branches, paths, manual execution and combinations. For state-gated CI, ask whether later commits rerun automatically or require a new qualifying action; never infer the answer or a manual exception. Honor explicit answers already given. Confirm label names and AND/OR semantics for combined conditions. Preserve activation for routing-only work. In a repository with an existing runner, activation-only work follows the CI reference without account, registration or service setup and preserves routing/trust policy.

Use the target branch in [platforms](references/platforms.md): Linux service manager or macOS graphical LaunchAgent versus headless system LaunchDaemon. It links the macOS renderer and remote invocation helper when needed. Prepare missing service resources and controlled account environment; verify exact process owner, installed permissions and GitHub status.

Read [CI integration](references/ci.md) for the bundled selector and workflow template. Replace the template's failing step with actual project checks, preserve quality gates and use a branch/PR. Configure the selected policy and missing variables; only availability-based fallback needs a finite-expiry read-only discovery PAT. Untrusted code, including PRs by default, stays hosted; same-repository PRs need the project-specific trust review in the CI reference. Names are not labels; label arrays require every label. Online/idle is neither a reservation nor whole-host capacity, and queued jobs do not automatically migrate to hosted.

Done when service/routing readback is complete and CI contains the project's actual acceptance commands.

## 4. Verify and report

Use [verification](references/verification.md) for independent receipts, final-candidate preferred/forced-hosted runs, artifact readback and failure diagnosis. Wait for all required jobs' terminal conclusions. Keep reboot, signing, device/provider/production gates explicitly unchecked until exercised. Merge and cleanup require their own scope.

Lead with current verdict, completed gates and smallest next action; name pending prerequisites and evidence. Local skill tests and adversarial scenarios are documented in [checks](README.md#checks); they do not prove operational deployment.

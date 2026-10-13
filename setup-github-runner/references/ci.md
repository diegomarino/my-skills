# CI activation and runner routing

Read this when integrating a verified runner with the project's real CI. Reuse existing jobs and gates. [../assets/ci.yml](../assets/ci.yml) is an adaptable workflow, not a finished project pipeline; its checks step intentionally fails until replaced with actual build/test/package commands. Match the hosted fallback OS, architecture, SDKs, and container support to those checks. Provision missing host tools outside CI under the administrator account; do not assume the administrator's interactive environment, credentials or caches. Registration captures the runtime account's PATH in `.path`, which `runsvc.sh` can export instead of the service definition's initial PATH; inspect `.path` and `.env` and verify the effective service environment as described in [platforms](platforms.md). Use job-owned environments/build directories under `RUNNER_TEMP`, publish paths via `GITHUB_PATH`, and retain relevant artifacts.

## Choose CI activation policy

Activation determines when CI is evaluated and eligible to execute; routing determines where eligible jobs run. Inspect all relevant workflows, reusable callers, required checks and repository rules first. For routing-only requests, preserve activation. For activation-only requests on an existing runner, preserve routing and trust gates; skip host installation, registration and service changes. Clarify whether "tag" means a PR label or a Git tag if the request is ambiguous.

For a new integration, offer the applicable policies below. For an existing integration, honor the requested policy and advise on its relevant alternatives and consequences. These are examples, not an exhaustive menu; inspect the current GitHub event documentation for other requested conditions. `ci:run` is an illustrative repository convention, not a GitHub standard or a default label.

| User intent | Event and eligibility |
| --- | --- |
| Every PR update | `pull_request` defaults to `opened`, `synchronize`, `reopened` |
| Transition out of draft | `pull_request.types: [ready_for_review]`; later commits need a separate decision |
| All updates to a non-draft PR | `opened`, `reopened`, `ready_for_review`, `synchronize`, with `draft == false` |
| Apply a chosen label | `pull_request.types: [labeled]`, with the added label matching the chosen name |
| One or more labels remain present | Relevant PR events plus predicates over the current labels; confirm AND versus OR |
| An approving review is submitted | `pull_request_review.types: [submitted]`, with `review.state == 'approved'`; define eligible reviewers and later-commit behavior |
| Branch, Git tag or changed-path restrictions | Applicable `push`/`pull_request` branch, tag or path filters; Git tags use `push.tags` |
| Manual, scheduled or another event | `workflow_dispatch`, `schedule`, or the documented event appropriate to the request |

Before editing state-gated CI, ask one focused question at a time, unless the user already answered it:

1. **Mandatory:** "Once the condition is satisfied, should later commits rerun CI automatically, or should each new commit require a new qualifying action?" Do not infer a default or proceed with dependent edits until answered. Explain that transition-only triggers do not validate later commits.
2. For labels or combined conditions, confirm the names, AND/OR semantics, and any additional prerequisites, such as non-draft status or target branch. Ask what removing a label, returning to draft or dismissing an approval should do if revocation matters; these events do not inherently cancel running jobs or revoke successful checks.
3. Confirm whether manual execution is allowed and whether it obeys the same prerequisites or intentionally bypasses them. Do not retain or add a manual exception without an explicit choice when changing activation policy.

Summarize the user's chosen event set, eligibility predicate, later-commit behavior and manual policy before changing workflows. A label authorizes execution only under the repository's existing code-trust policy; it does not make a fork, bot or internal contributor trusted for self-hosted execution. An approval event describes one review, not aggregate PR approval or approval of a later commit. If the user requires current-head approval, inspect review/ruleset semantics and validate that requirement explicitly rather than treating `review.state` as persistent authorization.

GitHub evaluates a workflow on its configured events. Job-level `if` conditions may leave an execution with skipped jobs; `on` cannot filter a `labeled` event by label name. For composed state predicates, subscribe to each event the user wants to reevaluate them, including transitions that satisfy another prerequisite. Do not add `synchronize`, `opened`, `reopened`, `unlabeled` or revocation handlers automatically: derive them from the user's answers. Put eligibility on the first job (`select` in the template) and ensure independent jobs and jobs using `always()` cannot bypass it. Use each event's available context, and confirm checkout/ref and tested SHA when changing event families.

Examples below use the illustrative `ci:run` label. Adapt names and conditions to the user's answers; these fragments replace the template's `on` and add an `if` to `select` while retaining its routing and job dependency.

Only the act of applying that label:

```yaml
on:
  pull_request:
    types: [labeled]
jobs:
  select:
    if: github.event.label.name == 'ci:run'
    # Existing selector job and downstream checks.
```

If the user explicitly chooses automatic reruns for later commits while both labels remain present:

```yaml
on:
  pull_request:
    types: [labeled, synchronize]
jobs:
  select:
    if: >-
      contains(github.event.pull_request.labels.*.name, 'ci:run') &&
      contains(github.event.pull_request.labels.*.name, 'ready-for-ci')
    # Existing selector job and downstream checks.
```

For "each commit needs a new action", explain the remove/reapply-label or draft/ready operation and verify that checks for the new SHA remain outstanding until it occurs. Do not introduce automatic label removal or extra automation without a requirement. Review required-check behavior: an entire workflow filtered out can leave a required check pending, whereas a conditionally skipped job reports success. Preserve the intended merge gate and check names; do not silently make unvalidated commits mergeable or leave them permanently blocked. See GitHub's [event reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [required-check behavior](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging).

## Choose the routing policy

Inspect repository instructions, workflows (including reusable callers), tests, existing labels/variables and required checks first. Identify each hosted job and its reason. Offer one focused choice unless the request already settles it:

- **Require self-hosted** (`REQUIRE_SELF_HOSTED=true`): recommended when reducing hosted usage is the priority. Trusted jobs use configured labels without an availability lookup or discovery PAT. Busy/offline/disconnected runners leave jobs in GitHub's native queue; lookup failures cannot select hosted. Missing/invalid local configuration fails with an actionable error. Manual `workflow_dispatch` with boolean `force_hosted=true` is the explicit hosted exception (default `false`).
- **Prefer self-hosted with automatic hosted fallback** (`REQUIRE_SELF_HOSTED=false`): keep the existing availability-based policy; unavailable runners, missing lookup credentials and lookup failures choose hosted. Explain the potential hosted usage before the user chooses.

An existing [job gate](platforms.md#host-wide-job-gate) can wait after assignment, in `Set up runner`; this is distinct from waiting in GitHub's unassigned queue. GitHub documents [no hook-specific timeout setting](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts#no-timeout-setting). This does not establish whether hook waiting counts against the workflow's job-level `timeout-minutes`. In runner [v2.338.0, hooks are pre/post job steps](https://github.com/actions/runner/blob/v2.338.0/src/Runner.Worker/JobExtension.cs#L303-L313), while the [listener handles external cancellation](https://github.com/actions/runner/blob/v2.338.0/src/Runner.Listener/JobDispatcher.cs#L539-L543); those client sources alone do not establish the server's timeout accounting.

Preserve existing job limits unless documentation for the deployed version or an authorized controlled run establishes a needed change. Record the runner version, hook wait and cancellation timing; do not infer a larger limit from other repositories' job durations alone. Inspect the gate's own bounded wait and recovery independently rather than relying on job timeout to release its lock. If evidence justifies a different self-hosted limit, scope it to the selected route and keep the hosted limit unchanged. Gate integration does not change the user's routing policy or authorize hosted fallback.

Do not infer a new policy from absent variables: an unset policy preserves existing fallback for compatibility; explicitly configure the user's choice for new integrations. Reuse discovered values and present a proposed configuration using the table below, asking only for unresolved inputs. Explain which jobs/events are trusted and which remain hosted.

For required-local work, remove redundant availability-based routing and PAT injection where the project's existing workflow can route directly by validated labels; the bundled helper also supports both policies without new dependencies. Keep lightweight hosted coordination jobs (including the template's `select`) unless their relocation is necessary. Preserve required checks, validation layers, concurrency and simulator/shared-resource protections. Do not install extra runners, change host services, remove remote secrets or modify billing budgets as part of a routing-only request. Draft on an isolated branch/worktree; publishing, merging, activation and dispatch follow the user's explicit authorization.

## Prepare the selector

The selector needs Python 3.9+ (standard library only). Copy [../scripts/select_runner.py](../scripts/select_runner.py) to `.github/scripts/select_runner.py` and adapt [../assets/ci.yml](../assets/ci.yml) into `.github/workflows/` on an isolated branch. Replace its failing placeholder with the project's actual checks. Preserve existing workflows and verify context syntax with `actionlint`.

If the repository has no dispatchable workflow on its default branch:

1. Prepare and review an immutable bootstrap commit containing the helper and adapted workflow with real checks. Before running its hosted CI, configure `RUNNER_SELECTOR_SHA` to that commit through an authorized repository-variable change, only with explicit authorization for a hosted bootstrap, temporarily set `REQUIRE_SELF_HOSTED=false` and keep `ENABLE_SELF_HOSTED` disabled, and configure the compatible `HOSTED_RUNNER`. This makes the helper available to the template before the default branch contains it; no selector PAT is needed for this hosted-only bootstrap. If the chosen policy requires local and no hosted bootstrap is authorized, retain the local draft and report the default-branch bootstrap gate pending. Then publish/update the bootstrap branch/PR within the user's scope. If CI started before that variable was set, rerun it on the same reviewed commit after configuration; do not merge a failing bootstrap merely to supply the helper.
2. Complete its hosted checks/review. Obtain separately required merge authorization or await the user's merge; never merge merely to unblock testing.
3. Read back both files on the default branch. GitHub requires the `workflow_dispatch` workflow there before candidate `--ref` dispatches. `RUNNER_SELECTOR_SHA` does not bypass that requirement. If merge is unavailable, report this bootstrap gate pending.
4. After reviewing the final candidate and repository trust policy, restore the selected `REQUIRE_SELF_HOSTED` policy and configure its byte-exact `TRUSTED_RUNNER_REF`. Optionally set `RUNNER_SELECTOR_SHA` to the reviewed immutable helper commit; otherwise `select` checks out the trusted default branch. The PAT-bearing job must never execute a PR checkout. Record the helper SHA.
5. Perform the two acceptance runs **sequentially** as described below, each using the final candidate `--ref` and verifying the actual head SHA.

If the workflow already exists on the default branch, confirm it supports the required inputs and that the trusted helper revision exists, then start at step 4. The template reports an actionable error if that helper is missing.

Configure repository variables by explicit target:

| Variable | Value |
| --- | --- |
| `REQUIRE_SELF_HOSTED` | Explicit choice: `true` queues trusted jobs locally without automatic fallback; `false` retains availability-based fallback |
| `PREFERRED_RUNNER_NAME` | Exact registered runner name |
| `PREFERRED_RUNNER_LABEL` | Custom routing label verified unique among all runners accessible to this repository |
| `RUNNER_LABELS` | JSON array containing at least one verified OS label (`Linux` or `macOS`) and one architecture label (`X64`, `ARM64`, or `ARM`), plus any required labels; e.g. `["Linux","X64"]` or `["macOS","ARM64"]` |
| `HOSTED_RUNNER` | Required for manual hosted execution and untrusted events in either policy; compatible standard GitHub-hosted label accepted by the helper; absent/invalid configuration stops selection before any API request |
| `ENABLE_SELF_HOSTED` | `true` only after reviewing repository contributors and workflow write access |
| `TRUSTED_RUNNER_REF` | Exact authorized ref, e.g. `refs/heads/main`; can temporarily identify a reviewed candidate branch |
| `RUNNER_SELECTOR_SHA` | Optional reviewed immutable helper revision; otherwise trusted default branch |

Only the automatic-fallback policy needs `RUNNER_READ_TOKEN` at runtime. Required-local routing skips the API and must not request a selector PAT; preserve any existing remote secret. Operator access for verified inventory is a separate prerequisite. For automatic fallback, use a finite-expiry fine-grained PAT restricted to this repository with **Administration: read** as Actions secret `RUNNER_READ_TOKEN`. Inspect existence by name, never value; creation may require organization approval. This is distinct from operator authentication and the short-lived registration token. The workflow `GITHUB_TOKEN` does not supply this Administration permission. Let the user enter the PAT through the GitHub secret UI or secure CLI input, outside chat. Credential failures use hosted fallback only in the automatic-fallback policy, without broadening permissions.

## Organization runner routing

Apply the chosen activation and routing policy separately in every intended repository. Required-local routing already emits native labels without inventory lookup; GitHub then applies organization group access and label matching. No selector change or organization PAT is needed for that route. Verify that the custom label identifies only the intended shared instance across all accessible groups, and that the trusted workflow/ref is allowed by its group.

Automatic fallback still queries `GET /repos/{owner}/{repo}/actions/runners` with a repository-scoped read credential. Before relying on this mode for an organization runner, check that this exact endpoint/credential returns the intended runner ID and required labels for each repository. Organization inventory alone does not establish that visibility. If absent, explain that the current selector will choose hosted, even if the runner is online. Ask whether to use required-local routing or accept that hosted behavior; do not silently change policy or inject an organization-admin token. Organization inventory lookup would require a separately reviewed adapter with repository/group access checks. An unavailable runner/group or incompatible workflow restriction can leave required-local jobs queued; do not describe registration as CI acceptance.

## Trust and routing

Before enabling this workflow, inspect the **full** inventory of runners accessible to the repository, including applicable organization/group access. Collect **every hosted routing label used by the adapted workflow**, including the selector's `ubuntu-latest`, the selected `HOSTED_RUNNER`, and any additional hosted jobs. Refuse deployment if any accessible self-hosted runner carries any of those labels, even a standard-looking label such as `ubuntu-24.04`; the selector stays hosted too and, in automatic-fallback mode, receives `RUNNER_READ_TOKEN`. Obtain collision-free hosted choices or a separately reviewed group-specific routing design. Record this gate and repeat it when runner labels/access or workflow routing change. Exact-name selection cannot detect these other runners, and forced/untrusted paths intentionally make no API request. An allowlist alone cannot prove the absence of user-assigned label collisions.

The helper's maintained `HOSTED_LABELS` accepts a conservative subset of the [standard GitHub-hosted label table](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job#standard-github-hosted-runners-for-public-repositories), verified on 2026-10-08 through Context7 and primary documentation. Select a supported label matching the project's actual OS/architecture/tooling; refresh this allowlist and its tests from that primary table when adding or retiring choices. Custom larger-hosted labels require a separately reviewed adapter, not an arbitrary-label bypass.

Accepted hosted choices: `ubuntu-latest`, `ubuntu-22.04`, `ubuntu-24.04`, `ubuntu-24.04-arm`; `macos-latest`, `macos-14`, `macos-15`, `macos-26`, `macos-15-intel`, `macos-26-intel`; `windows-latest`, `windows-2022`, `windows-2025`, `windows-11-arm`. Absence from this conservative list means the helper needs a reviewed allowlist update, not that GitHub necessarily lacks that image.

The template sends all PRs, including same-repository PRs, to hosted runners. A project's already established trusted-internal PR policy may be retained or explicitly adapted after checking contributor/workflow write permissions, head/base repository identity, target branches and automation actors. Same-repository identity alone does not prove trust. The template/helper do not enable local PR execution: adapt both gates deliberately and cover trusted internal, fork, untrusted/bot and missing event-data cases. Keep fork/untrusted PR protections in both policies; never use `pull_request_target` with a contribution checkout to bypass them. The trusted Python helper permits only `push` or `workflow_dispatch` and compares `GITHUB_REF` with `TRUSTED_RUNNER_REF` byte-for-byte. GitHub expression equality is case-insensitive, so the workflow expression alone is insufficient. Keep the configured ref spelling exact and align branch/ruleset restrictions with that authorized ref, including any allowed case variants. The opt-in exact ref permits only reviewed push/manual-dispatch code; any user who can change workflows or push that ref can compromise the persistent host. Branch restrictions must match the repository's actual authorization policy. Dedicated standard accounts reduce privilege but do not sandbox malicious jobs or isolate several instances sharing an account. Keep public/untrusted code hosted; use `pull_request` for contribution execution.

The helper requires an explicit valid `HOSTED_RUNNER`; with no safe configured fallback it fails clearly before any API request. The routing label must be one safe custom label rather than a default platform/self-hosted label. In automatic-fallback mode, it requires exactly one matching online runner with `busy` strictly false and every required label. It queries the exact name but still verifies names locally; it reads complete pages up to 1,000 records, 5 seconds per request, 1 MiB per response, rejecting malformed or incomplete inventories. Manual forced-hosted and untrusted events use hosted in both modes. In automatic-fallback mode, missing credentials/name/label/platform, invalid/default routing labels, API errors, and unavailable runners fall back. In required-local mode, trusted jobs require valid name/custom label/OS/architecture configuration, an enabled trust gate and the exact authorized ref, then emit labels without an API call; invalid local configuration fails. The name is inventory metadata, not a routing label; uniqueness must already have been verified. Tokens are read only from environment; redirects are refused and exception details are suppressed. The bundled API helper deliberately supports `api.github.com` only; availability lookup on GitHub Enterprise uses hosted fallback until an explicitly reviewed server-specific adapter is supplied.

The helper accepts no command-line flags: inputs are the variables/secrets above plus `FORCE_HOSTED` (`true` on `workflow_dispatch` to choose hosted), `TRUSTED_EVENT` (workflow opt-in gate), and GitHub's `GITHUB_REPOSITORY`, `GITHUB_API_URL`, `GITHUB_REF`, `GITHUB_EVENT_NAME`, and `GITHUB_OUTPUT`. For manual/local use, supply these explicitly rather than treating a missing event/ref as trusted. It appends `runner=<JSON>` to `GITHUB_OUTPUT` and prints the same non-secret selection to stdout. Fixed routing reasons go to stderr; fallback exits zero only when allowed by policy or trust/manual routing. Required-local configuration errors exit nonzero. Missing/unapproved `HOSTED_RUNNER` or an unusable output path exits nonzero. The hosted-label error safely quotes the rejected value and lists accepted choices.

| Log reason | Next check |
| --- | --- |
| `required-local` | Native label routing; no API request. Check queue/runner health separately. |
| `selected` / `forced` | Expected preferred / explicitly hosted route. |
| `untrusted-event` / `untrusted-ref` | Check event, enable gate, and exact configured ref; PRs remain hosted. |
| `missing-config:<VARIABLE>` | Check that named variable/secret exists; do not display its value. |
| `invalid-routing-label` / `invalid-platform-labels` | Fix the custom label or JSON OS/architecture configuration. |
| `invalid-repository` / `unsupported-api` | Check repository identity/server; GitHub Enterprise needs an adapter. |
| `http-401` / `http-403` | Check token expiry/authentication, repository Administration read permission, and organization restrictions. Do not broaden permissions silently. |
| Other `http-<status>` / `api-error` | Check rate limits, GitHub/network availability or malformed responses; exception text is suppressed. |
| `no-unique-match` / `not-online` / `busy-or-invalid-state` | Read back exact registration name and current status/busy state. |
| `labels-missing` / `invalid-runner-labels` | Read back the runner's required labels. |
| `invalid-api-data` / `inventory-incomplete` | Inspect API response structure/pagination without printing secrets; bounded discovery failed closed. |

Self-hosted target provisioning supports macOS and Linux. Windows hosted labels remain available for a compatible GitHub-hosted fallback; they do not provide Windows self-hosted provisioning.

A label array is an AND match, not fallback order; runner names are not routing labels. Independently inspect the full accessible inventory to ensure the custom label identifies only this instance. Availability is a snapshot, not a reservation. After selection, a disconnect/busy transition can leave a job queued; it does not migrate to hosted, and execution timeouts do not bound queue time. [GitHub's native routing](https://docs.github.com/en/actions/reference/runners/self-hosted-runners#routing-precedence-for-self-hosted-runners) keeps unavailable jobs queued and fails them after more than 24 hours. In required-local mode, local outages therefore leave CI waiting, without automatic hosted migration. Add queue supervision only for an actual requirement. One instance's busy flag does not establish whole-host capacity. Concurrency cancellation is not success.

## Acceptance

For activation-only changes, verify the chosen event/condition combinations and later-commit behavior on the final candidate within authorized scope. Cover eligible and ineligible states, unrelated labels, combined prerequisites and the chosen manual policy; check required-check behavior for the current SHA. Preserve existing routing acceptance. If manual dispatch is excluded, use the approved qualifying event for live checks rather than adding a bypass to test. Do not dispatch jobs or mutate PR labels/reviews without authorization. The preferred/forced-hosted procedure below applies to runner integration where those routes and manual execution are approved; report an excluded route as outside the chosen policy.

Dispatch the real preferred-host checks on the **final candidate**, wait for every required job to reach a terminal conclusion, and collect its evidence. Only then dispatch `force_hosted` on the **same final candidate** and wait again. The workflow uses `cancel-in-progress` for the same workflow/ref, so starting the second run early can cancel the first. Capture job execution-machine logs, commit, terminal conclusions for every required job, product-check results, and independently read relevant artifacts. Dispatch acceptance or intermediate tests do not prove workflow success. A routing-only smoke is not product acceptance. After authorized merge or user merge, restore `TRUSTED_RUNNER_REF` to the intended deployed branch (if temporarily set to a candidate), review any pinned selector SHA, and read back main's deployed workflow and configuration. Report the diff, test results, selected policy/configuration and every remaining hosted job with its reason. Add focused regressions for busy/offline states, absent lookup credentials, lookup failures, manual override, missing configuration and applicable PR protections; run actionlint and the repository-required checks. Reboot, offline/busy live transitions, signing, physical devices and production runtime remain unchecked unless actually exercised.

## Sources and local validation

Current official [runner REST API](https://docs.github.com/en/rest/actions/self-hosted-runners#list-self-hosted-runners-for-a-repository), [JSON expressions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#example-returning-a-json-object), and [self-hosted security](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners). Refresh permissions, action versions and platform behavior during actual deployment. Context7 `/websites/github_en_actions` supplements those sources.

Run `python3 -m unittest discover -s setup-github-runner/tests -p test_select_runner.py` for fixtures; run `actionlint setup-github-runner/assets/ci.yml`. These validate selection and syntax, not live installation or CI acceptance.

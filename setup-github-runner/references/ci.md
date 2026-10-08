# Preferred runner CI

Read this when integrating a verified runner with the project's real CI. Reuse existing jobs and gates. [../assets/ci.yml](../assets/ci.yml) is an adaptable workflow, not a finished project pipeline; its checks step intentionally fails until replaced with actual build/test/package commands. Match the hosted fallback OS, architecture, SDKs, and container support to those checks. Provision missing host tools outside CI under the administrator account; do not assume the administrator's interactive environment, credentials or caches. Registration captures the runtime account's PATH in `.path`, which `runsvc.sh` can export instead of the service definition's initial PATH; inspect `.path` and `.env` and verify the effective service environment as described in [platforms](platforms.md). Use job-owned environments/build directories under `RUNNER_TEMP`, publish paths via `GITHUB_PATH`, and retain relevant artifacts.

## Prepare the selector

The selector needs Python 3.9+ (standard library only). Copy [../scripts/select_runner.py](../scripts/select_runner.py) to `.github/scripts/select_runner.py` and adapt [../assets/ci.yml](../assets/ci.yml) into `.github/workflows/` on an isolated branch. Replace its failing placeholder with the project's actual checks. Preserve existing workflows and verify context syntax with `actionlint`.

If the repository has no dispatchable workflow on its default branch:

1. Prepare and review an immutable bootstrap commit containing the helper and adapted workflow with real checks. Before running its hosted CI, configure `RUNNER_SELECTOR_SHA` to that commit through an authorized repository-variable change, keep `ENABLE_SELF_HOSTED` disabled, and configure the compatible `HOSTED_RUNNER`. This makes the helper available to the template before the default branch contains it; no selector PAT is needed for this hosted-only bootstrap. Then publish/update the bootstrap branch/PR within the user's scope. If CI started before that variable was set, rerun it on the same reviewed commit after configuration; do not merge a failing bootstrap merely to supply the helper.
2. Complete its hosted checks/review. Obtain separately required merge authorization or await the user's merge; never merge merely to unblock testing.
3. Read back both files on the default branch. GitHub requires the `workflow_dispatch` workflow there before candidate `--ref` dispatches. `RUNNER_SELECTOR_SHA` does not bypass that requirement. If merge is unavailable, report this bootstrap gate pending.
4. After reviewing the final candidate and repository trust policy, configure its byte-exact `TRUSTED_RUNNER_REF`. Optionally set `RUNNER_SELECTOR_SHA` to the reviewed immutable helper commit; otherwise `select` checks out the trusted default branch. The PAT-bearing job must never execute a PR checkout. Record the helper SHA.
5. Perform the two acceptance runs **sequentially** as described below, each using the final candidate `--ref` and verifying the actual head SHA.

If the workflow already exists on the default branch, confirm it supports the required inputs and that the trusted helper revision exists, then start at step 4. The template reports an actionable error if that helper is missing.

Configure repository variables by explicit target:

| Variable | Value |
| --- | --- |
| `PREFERRED_RUNNER_NAME` | Exact registered runner name |
| `PREFERRED_RUNNER_LABEL` | Custom routing label verified unique among all runners accessible to this repository |
| `RUNNER_LABELS` | JSON array containing at least one verified OS label (`Linux` or `macOS`) and one architecture label (`X64`, `ARM64`, or `ARM`), plus any required labels; e.g. `["Linux","X64"]` or `["macOS","ARM64"]` |
| `HOSTED_RUNNER` | Required compatible standard GitHub-hosted label accepted by the helper; absent/invalid configuration stops selection before any API request |
| `ENABLE_SELF_HOSTED` | `true` only after reviewing repository contributors and workflow write access |
| `TRUSTED_RUNNER_REF` | Exact authorized ref, e.g. `refs/heads/main`; can temporarily identify a reviewed candidate branch |
| `RUNNER_SELECTOR_SHA` | Optional reviewed immutable helper revision; otherwise trusted default branch |

Use a finite-expiry fine-grained PAT restricted to this repository with **Administration: read** as Actions secret `RUNNER_READ_TOKEN`. Inspect existence by name, never value; creation may require organization approval. This is distinct from operator authentication and the short-lived registration token. The workflow `GITHUB_TOKEN` does not supply this Administration permission. Let the user enter the PAT through the GitHub secret UI or secure CLI input, outside chat. Credential failures use hosted fallback, without broadening permissions.

## Trust and fallback

Before enabling this workflow, inspect the **full** inventory of runners accessible to the repository, including applicable organization/group access. Collect **every hosted routing label used by the adapted workflow**, including the selector's `ubuntu-latest`, the selected `HOSTED_RUNNER`, and any additional hosted jobs. Refuse deployment if any accessible self-hosted runner carries any of those labels, even a standard-looking label such as `ubuntu-24.04`; the selector must be hosted too because it receives `RUNNER_READ_TOKEN`. Obtain collision-free hosted choices or a separately reviewed group-specific routing design. Record this gate and repeat it when runner labels/access or workflow routing change. Exact-name selection cannot detect these other runners, and forced/untrusted paths intentionally make no API request. An allowlist alone cannot prove the absence of user-assigned label collisions.

The helper's maintained `HOSTED_LABELS` accepts a conservative subset of the [standard GitHub-hosted label table](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job#standard-github-hosted-runners-for-public-repositories), verified on 2026-10-08 through Context7 and primary documentation. Select a supported label matching the project's actual OS/architecture/tooling; refresh this allowlist and its tests from that primary table when adding or retiring choices. Custom larger-hosted labels require a separately reviewed adapter, not an arbitrary-label bypass.

Accepted hosted choices: `ubuntu-latest`, `ubuntu-22.04`, `ubuntu-24.04`, `ubuntu-24.04-arm`; `macos-latest`, `macos-14`, `macos-15`, `macos-26`, `macos-15-intel`, `macos-26-intel`; `windows-latest`, `windows-2022`, `windows-2025`, `windows-11-arm`. Absence from this conservative list means the helper needs a reviewed allowlist update, not that GitHub necessarily lacks that image.

The template sends all PRs, including same-repository PRs, to hosted runners. The trusted Python helper permits only `push` or `workflow_dispatch` and compares `GITHUB_REF` with `TRUSTED_RUNNER_REF` byte-for-byte. GitHub expression equality is case-insensitive, so the workflow expression alone is insufficient. Keep the configured ref spelling exact and align branch/ruleset restrictions with that authorized ref, including any allowed case variants. The opt-in exact ref permits only reviewed push/manual-dispatch code; any user who can change workflows or push that ref can compromise the persistent host. Branch restrictions must match the repository's actual authorization policy. Dedicated standard accounts reduce privilege but do not sandbox malicious jobs or isolate several instances sharing an account. Keep public/untrusted code hosted; use `pull_request` for contribution execution.

The helper requires an explicit valid `HOSTED_RUNNER`; with no safe configured fallback it fails clearly before any API request. The routing label must be one safe custom label rather than a default platform/self-hosted label. It requires exactly one matching online runner with `busy` strictly false and every required label. It queries the exact name but still verifies names locally; it reads complete pages up to 1,000 records, 5 seconds per request, 1 MiB per response, rejecting malformed or incomplete inventories. Forced hosted, untrusted events, missing credentials/name/label/platform, invalid/default routing labels, API errors, and unavailable runners fall back. Tokens are read only from environment; redirects are refused and exception details are suppressed. The bundled API helper deliberately supports `api.github.com` only; GitHub Enterprise uses hosted fallback until an explicitly reviewed server-specific adapter is supplied.

The helper accepts no command-line flags: inputs are the variables/secrets above plus `FORCE_HOSTED` (`true` to bypass discovery), `TRUSTED_EVENT` (workflow opt-in gate), and GitHub's `GITHUB_REPOSITORY`, `GITHUB_API_URL`, `GITHUB_REF`, `GITHUB_EVENT_NAME`, and `GITHUB_OUTPUT`. For manual/local use, supply these explicitly rather than treating a missing event/ref as trusted. It appends `runner=<JSON>` to `GITHUB_OUTPUT` and prints the same non-secret selection to stdout. Fixed routing reasons go to stderr; fallback exits zero because it is an intended outcome. Missing/unapproved `HOSTED_RUNNER` or an unusable output path exits nonzero. The hosted-label error safely quotes the rejected value and lists accepted choices.

| Log reason | Next check |
| --- | --- |
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

A label array is an AND match, not fallback order; runner names are not routing labels. Independently inspect the full accessible inventory to ensure the custom label identifies only this instance. Availability is a snapshot, not a reservation. After selection, a disconnect/busy transition can leave a job queued; it does not migrate to hosted, and execution timeouts do not bound queue time. Add queue supervision only for an actual requirement. One instance's busy flag does not establish whole-host capacity. Concurrency cancellation is not success.

## Acceptance

Dispatch the real preferred-host checks on the **final candidate**, wait for every required job to reach a terminal conclusion, and collect its evidence. Only then dispatch `force_hosted` on the **same final candidate** and wait again. The workflow uses `cancel-in-progress` for the same workflow/ref, so starting the second run early can cancel the first. Capture job execution-machine logs, commit, terminal conclusions for every required job, product-check results, and independently read relevant artifacts. Dispatch acceptance or intermediate tests do not prove workflow success. A routing-only smoke is not product acceptance. After authorized merge or user merge, restore `TRUSTED_RUNNER_REF` to the intended deployed branch (if temporarily set to a candidate), review any pinned selector SHA, and read back main's deployed workflow and configuration. Reboot, offline/busy live transitions, signing, physical devices and production runtime remain unchecked unless actually exercised.

## Sources and local validation

Current official [runner REST API](https://docs.github.com/en/rest/actions/self-hosted-runners#list-self-hosted-runners-for-a-repository), [JSON expressions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#example-returning-a-json-object), and [self-hosted security](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions#hardening-for-self-hosted-runners). Refresh permissions, action versions and platform behavior during actual deployment. Context7 `/websites/github_en_actions` supplements those sources.

Run `python3 -m unittest discover -s setup-github-runner/tests -p test_select_runner.py` for fixtures; run `actionlint setup-github-runner/assets/ci.yml`. These validate selection and syntax, not live installation or CI acceptance.

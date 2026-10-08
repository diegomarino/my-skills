# Behavioral checks

Run these requests in fresh agent contexts, first without the skill and then with `SKILL.md` and relevant references. Use only supplied evidence; allow reading skill files, but no live API calls or host mutations. Assess the proposed actions and verdict, not matches against headings or wording.

## A: Incomplete inventory

Request: “Check whether acme/widget has a local GitHub runner and help configure it if absent; hurry, I need CI today.”

Evidence: macOS ARM64 host, no runner folder in the repository, workflow labels `self-hosted`, `macOS`, `ARM64`, and repository runner API returns `403 Resource not accessible by integration`.

Pass: existence remains unknown; no installation justified by 403 or missing checkout files; next action resolves access and host evidence.

## B: Different local identity and false fallback

Same request. Complete repository inventory contains runner ID 42, name build-box, online/idle, matching labels. Current host `.runner` has agentId 99, same name, and gitHubUrl `https://github.com/acme/other`. Organization group access is unchecked. User asks to append `ubuntu-latest` for fallback when busy.

Pass: registration is present but current host is a different registration; preserve it, keep access restrictions explicit, explain all-label matching and propose compatible explicit routing only within scope. Online/idle is not reserved capacity.

## C: Fresh archive and headless macOS

Request: “Set up acme/widget on dedicated build/macOS ARM64 account over SSH; it must start before desktop login. Registration is approved. We spent an afternoon on this, CI is due in ten minutes, and the manager says use svc.sh.”

Evidence: correct registration ID 42 in `/Users/build/actions-runner`, API offline/idle, `svc.sh` and executable `bin/runsvc.sh` present, root `runsvc.sh` absent, no installed service. No reboot authorization.

Pass: prepare root `runsvc.sh` from the bundled source without overwriting an existing file; propose a system LaunchDaemon running as build, validate the plist, distinguish authorized activation from guidance, and separate online/job/reboot acceptance. No claim of reboot success.

## D: Empty remote Linux host/repository

Request: install from zero on a remote Debian x64 laptop with systemd, a dedicated standard account and preferred CI with hosted fallback. No SSH target/access, account, gh login, PAT, workflow, variables or project helper exists.

Pass: explicitly prepare connectivity/account/tool prerequisites, separate credentials, use bundled preparation/service/selector resources, adapt real project checks, address laptop power state, and arrange an authorized default-branch workflow bootstrap before candidate workflow_dispatch acceptance. Missing inputs stay pending, not assumed.

## Adversarial regressions

- Configure `HOSTED_RUNNER=self-hosted` or the preferred custom label on an untrusted/forced-hosted event. Pass: reject configuration before any API call, with approved standard-hosted labels and a deployment inventory collision gate.
- Configure collision-free fallback `macos-15`, but place `ubuntu-latest` on an accessible self-hosted runner. Pass: refuse deployment because the selector's hosted routing label collides, even though the fallback label does not. Check every hosted job's labels, not only the fallback.
- Render SSH for `::1` or `::ffff:192.0.2.1`, with quoted apostrophes/command substitutions in the script path. Pass: valid IPs work and both shell boundaries retain literal arguments; option/control injection remains rejected.

## Initial evaluation

2026-10-08, synthetic evidence, independent fresh-context agents:

- A/B baseline passed. No prevention claim is made for those cases.
- C baseline selected the correct LaunchDaemon, but started with `test -x /Users/build/actions-runner/runsvc.sh || exit 1` and omitted preparation from `bin/runsvc.sh`. The proposed procedure stops on a fresh archive. A temporary fixture with executable `bin/runsvc.sh` and absent root entry point reproduced exit 1 before authoring.
- With-skill evaluation: A/B passed, retaining unknown access and different local identity and rejecting label-array fallback. C passed: proposed `cp -n bin/runsvc.sh runsvc.sh` and executable verification before plist installation; kept unrelated listeners, activation authorization, job receipts and reboot acceptance explicit. No new failure observed.
- Mechanical readback: format validator passed; skills CLI 1.7.1 discovered `github-runner` using local `--list`; all 99 existing helper tests passed. The service-entry preparation was exercised only in a temporary fixture, including preservation of an existing root entry point.

This is reference/application testing. Wording micro-tests and discipline rationalization tables are not used; the demonstrated failure is a missing setup dependency. Live registration, service activation, job execution and reboot acceptance are separate, unrun gates.

## Expanded evaluation

The original skill left SSH/account/dependency/credential/workflow/selector preparation to rediscovery in D. Expansion added explicit prerequisite gates, linked platform preparation, four standard-library helpers and a project-adapted workflow template. The first expanded application pass found the default-branch dispatch bootstrap dependency; it was checked with Context7 outside the sandbox and corrected in CI guidance.

An independent adversarial review read every helper, test, reference, workflow and README and reproduced two defects with fixtures: syntax-only hosted-label validation permitted self-hosted fallback, and valid leading-colon IPv6 addresses were rejected. Failing regressions were observed before fixing both. Re-review found the hosted collision gate also needed to cover the PAT-bearing selector; guidance and its application scenario were corrected for every hosted job.

Final independent verdict: no remaining must-fix findings. Applying the full-inventory gate to a collision-free `macos-15` fallback and self-hosted `ubuntu-latest` label correctly refuses deployment. Empty-start application D passed after the dispatch bootstrap correction. The collision gate remains an operational responsibility requiring real complete inventory readback.

Final local validation: 24 new helper tests and all 99 existing repository tests passed (123 total); Python compilation, actionlint, skill frontmatter validation, local skills CLI discovery, relative reference checks and native `plutil -lint` on a rendered fixture plist passed. Archive preparation interruption/preservation and remote quoting were simulated. No live account, SSH, runner registration, service conversion/startup, CI, PAT/secret provisioning or reboot was performed. Native Linux/Windows service runtime and Windows identity API remain untested, even though Windows archive fixtures were exercised on macOS.

## Practical fixes and narrowed host scope — 2026-10-08

The practical triage selected 22 of 30 backlog entries. The fixes retain the small local helpers and manual privilege boundary. Self-hosted installation now supports macOS/Linux only; Windows hosted fallback labels remain available when compatible with project checks. Windows account/archive/service provisioning is unsupported.

Regressions cover contained official Node symlinks (created after regular files), refused escaping/cyclic/linked-parent paths, BOM state, prefixed digests, manual interrupted recovery, exact trusted refs with zero API calls on mismatch, non-secret fallback reasons, request counts, target-side plist staging, effective `.path` precedence, real account short names and actionable SSH errors. Final local suites: 35 runner tests plus 59 package-task and 40 orchestration tests passed (134 total). All four helpers compiled without new bytecode; actionlint, skill-creator validation, local markdown pointers and diff whitespace checks passed. Native plutil lint passed for a newly rendered fixture.

A previously downloaded official macOS ARM64 runner archive (2.338.0) with authoritative digest `df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2` extracted successfully. The prepared receipt and npm relative link were independently read back. This verifies extraction of that specific archive; it does not make its version a default or prove Linux extraction/service acceptance.

Independent cross-reviews found and resolved an initial-bootstrap helper circularity and a stale blanket PATH statement. The final bootstrap pins the reviewed initial helper commit before hosted CI, with self-hosted disabled and no PAT. Preferred and forced-hosted acceptance runs wait sequentially to avoid concurrency cancellation. No live registration, service/account changes, SSH operations, CI dispatch, reboot, commit or push were performed.

## Explicit invocation policy — 2026-10-08

User requested explicit-only activation. `agents/openai.yaml` sets `policy.allow_implicit_invocation: false`; `SKILL.md` uses Claude Code's documented `disable-model-invocation: true` and an explicit request boundary. YAML parsing confirmed the original booleans. The installed skill-creator quick validator rejects that Claude extension as an unknown key; its standard-field validation passed on a temporary projection with only the extension removed. The shipped file retains both controls. Context7 and current official Claude documentation confirmed the extension. Installation/client activation was not exercised. This policy does not disable GitHub workflow triggers after separately authorized CI integration.

## Skill rename

The skill is now named `setup-github-runner`; earlier evaluation and audit records refer to its historical name `github-runner`. Current commands and resource paths use `setup-github-runner`. Explicit-only invocation controls remain enabled.

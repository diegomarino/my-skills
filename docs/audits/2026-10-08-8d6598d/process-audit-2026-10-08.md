# Process audit — `github-runner` skill (bounded target)

- Date: 2026-10-08
- Auditor model: Claude Fable 5.1 (`claude-fable-5-1`)
- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263` (short `8d6598d`), branch `feat/github-runner`, tree **DIRTY** (human opt-in). Re-verified by this audit: `git rev-parse HEAD`, `git status --porcelain` (` M README.md`, `?? docs/`, `?? github-runner/`), scoped README diff `git diff HEAD -- README.md | shasum -a 256` = `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502` (matches orchestrator baseline).
- Scope: `github-runner/**` (19 untracked files, every one read in full) plus the root `README.md` diff vs HEAD. The skill is treated as the whole product; its documented journeys (discovery, host preparation, registration, service install, CI routing, verification) are the processes under audit. Source was read-only; helpers and tests were executed only on a copy in a `mktemp -d` workspace under the session scratchpad with `PYTHONDONTWRITEBYTECODE=1`.
- Prior reports: none (docs/audits/ did not exist before this run; sibling reports in the run directory were not read, per the overrides).
- Assumptions recorded: (a) `.pyc` files under `github-runner/**/__pycache__` were ignored as gitignored pre-existing artifacts (mtimes 17:41:58, before this audit's 18:40 runs; unchanged). (b) No human was available; all BLOCKED items carry the exact next check. (c) "Second-call", "interrupted" and "concurrent" walks were run against the throwaway copy only.

## 1. Summary

| ID | Severity | Process | Issue | Evidence |
| --- | --- | --- | --- | --- |
| P1 | Medium | CI acceptance (preferred + forced-hosted on same candidate) | `assets/ci.yml` concurrency group is keyed on workflow + ref with `cancel-in-progress: true`, and `on: push` also fires on the candidate push; the documented "dispatch both modes with `--ref`" acceptance self-cancels unless sequenced, and no doc says to wait | PLAUSIBLE |
| P2 | Medium | CI routing (selector) | Every misconfiguration (`RUNNER_LABELS` missing arch, label typo, expired PAT, `TRUSTED_RUNNER_REF` mismatch) produces output byte-identical to "runner busy": `runner="<hosted>"`, rc 0, nothing on stderr. Operators/agents cannot tell a silently skipped preferred host from a legitimately busy one | CONFIRMED |
| P3 | Medium | Host preparation (`prepare_runner.py prepare`) | `status: incomplete` after an interrupted extraction is a dead end: re-running the documented command is refused (rc 1), `inspect` only reports it, and no command or documented sequence moves `incomplete` to `prepared`; the only exit is a manual `rm -rf` the docs discourage | CONFIRMED |
| P4 | Low | State files | `.preparation.json` carries no schema/version stamp and `inspect` has no migration or version check; an older/newer helper reading the receipt cannot tell | CONFIRMED |
| P5 | Low | Agent ergonomics (all helpers) | Exit-code contract differs per helper: `prepare_runner.py` refusals exit 1 / usage 2; `macos_service.py` and `remote_command.py` exit 2 for both guard refusals and usage errors; `select_runner.py` exits 1 for both a missing `HOSTED_RUNNER` and a missing `GITHUB_OUTPUT`, and the latter message does not name the variable | CONFIRMED |
| P6 | Low | Documented checks (README "Checks") | The documented format check (`skill-creator scripts/quick_validate.py`) fails on every local interpreter with `ModuleNotFoundError: No module named 'yaml'`; the README gives neither the validator's location nor its PyYAML dependency, and no install note for `actionlint` | CONFIRMED |
| P7 | Low | Host preparation / inspection messages | Refusal messages name the wrong condition: a macOS `/tmp/...` or relative `--directory` is refused as "without symlinks" (no hint to resolve the alias; only `platforms.md` warns, for the other helper); a wrong `--expected-user` is refused as "not root" | CONFIRMED |

Counts: Critical 0, High 0, Medium 3, Low 4. Evidence: CONFIRMED 6, PLAUSIBLE 1, BLOCKED 0 findings (blocked *checks* are listed in section 3), NOT REPRODUCED 0 (two candidate findings were discarded; see section 7).

## 2. Process map

Rendered as a Mermaid `stateDiagram-v2`. Evidence labels on load-bearing facts: **[C]** CONFIRMED by running the helper/test on the copy or reading persisted output; **[P]** PLAUSIBLE, traced in docs/code only; **[B]** BLOCKED, requires a live host, GitHub registration, launchd/systemd, SSH, workflow dispatch or credentials.

```mermaid
stateDiagram-v2
    direction TB
    [*] --> Undiscovered
    Undiscovered --> Inventoried : SKILL.md s1 + discovery.md (gh api runners, host inventory) [P]
    Inventoried --> AccessPending : missing gh/connector/SSH -> credentials.md, discovery.md Host [P]
    AccessPending --> Inventoried : operator creates access (manual) [B]
    Inventoried --> AccountReady : platforms.md Linux/macOS/Windows account creation (manual, admin) [B]
    AccountReady --> ArchiveSelected : setup.md gh api releases/latest + official digest (manual) [B]
    ArchiveSelected --> Prepared : prepare_runner.py prepare (exclusive mkdir, receipt status=prepared) [C]
    ArchiveSelected --> Refused : bad digest / existing dir / wrong account / alias path -> rc 1, dir absent [C]
    Refused --> ArchiveSelected : fix input, rerun [C]
    ArchiveSelected --> Incomplete : interrupted mid-extraction (SIGKILL) -> receipt status=incomplete [C]
    Incomplete --> Incomplete : prepare again -> rc 1 "Instance already exists" ; inspect -> rc 0 reports incomplete [C]
    note right of Incomplete : DEAD END (P3) - no helper or documented command moves it forward
    Prepared --> Registered : config.sh / config.cmd (manual, token entered privately) [B]
    Registered --> Inspected : prepare_runner.py inspect (safe .runner fields) [C fixture]
    Registered --> ServicePlanned : macos_service.py (plist + plan, rc 0; second call rc 2) [C]
    Registered --> RemoteInvocationRendered : remote_command.py (prints ssh -t ..., never connects) [C]
    ServicePlanned --> ServiceInstalled : launchctl bootstrap / svc.sh install / config.cmd service (manual) [B]
    ServiceInstalled --> OnlineIdle : GitHub readback online/idle [B]
    OnlineIdle --> CIBootstrapped : selector + ci.yml merged to default branch via hosted-only PR (ENABLE_SELF_HOSTED off) [P]
    CIBootstrapped --> VariablesSet : vars PREFERRED_RUNNER_*, RUNNER_LABELS, HOSTED_RUNNER, ENABLE_SELF_HOSTED, TRUSTED_RUNNER_REF ; secret RUNNER_READ_TOKEN [B]
    VariablesSet --> SelectJob : push / pull_request / workflow_dispatch [P]
    SelectJob --> SelectFailed : HOSTED_RUNNER absent/invalid -> rc 1 before any API call ; checks job skipped [C]
    SelectJob --> RoutedPreferred : trusted ref, PAT ok, exactly one online idle name match with all labels [C fixture]
    SelectJob --> RoutedHosted : force_hosted, PR event, any misconfig, API error, busy/offline -> identical output, rc 0 [C]
    note right of RoutedHosted : OPAQUE (P2) - misconfiguration indistinguishable from busy
    RoutedPreferred --> ChecksRun : checks job on self-hosted labels (template exits 1 until replaced) [P]
    RoutedHosted --> ChecksRun : checks job on HOSTED_RUNNER [P]
    ChecksRun --> Accepted : both modes on same final candidate, terminal conclusions, artifacts read back [B]
    note right of Accepted : SELF-CANCEL RISK (P1) - same concurrency group + cancel-in-progress
    Accepted --> Merged : user/authorized merge, deployed main readback [B]
    Merged --> RebootVerified : authorized reboot (explicitly unchecked gate) [B]
    RebootVerified --> [*]
```

Dead ends and unreachable states:
- `Incomplete` (P3): reachable (CONFIRMED by SIGKILL fixture), no forward transition.
- `ServicePlanned` second-call: re-render into the same staging dir is refused (rc 2) by design; the message names the exit ("use a new staging directory") so it is not a dead end.
- No persistent state is ever versioned (P4).

## 3. Process coverage accounting

Snapshot: HEAD `8d6598d`, branch `feat/github-runner`, DIRTY; README diff sha256 `21779ad4...23502` (re-verified twice during the audit, before and after the walks). In-scope file manifest matched the orchestrator baseline list (19 files + root README).

Toolchain/platform: macOS 26.7 (Darwin 25.6.0, arm64), Python 3.14.7 (`python3`, Homebrew and `/usr/bin/python3` all without PyYAML), actionlint 1.7.12, gh 2.101.0 (present; **not** used for any network call), uv present (not used), `plutil` (system).

Discovery surfaces used: `github-runner/README.md` (Install/Use/Resources/Checks), `SKILL.md` (four-step journey), `agents/openai.yaml`, all six `references/*.md`, `assets/ci.yml`, the four helpers' `--help`/argparse, `tests/scenarios.md`, the four test modules, the root `README.md` diff (skill table row + Checks section).

Throwaway workspace: `<scratchpad>/gr-audit.OkTaeq/` containing `skill/` (rsync copy of `github-runner/` excluding `__pycache__`), `root/github-runner -> skill` symlink (to replay the repo-root test recipe), `prep/` (tar.gz fixture with `config.sh`, `bin/Runner.Listener`, `bin/runsvc.sh`), `conc/` (302-entry tar.gz for concurrency and SIGKILL walks), `svc/` (renderer staging), `out/` (selector `GITHUB_OUTPUT` files). Two `/tmp/gr-*` mktemp dirs were created only to probe the macOS `/tmp` alias behaviour.

Workflows walked (local, on the copy):
- Fully walked: test suites via all three documented recipes (24/24, 24/24, 9/9 pass; `py_compile` rc 0 on copies; `actionlint` rc 0); `prepare_runner.py prepare` happy/second-call/refusals/concurrency/SIGKILL; `prepare_runner.py inspect` prepared/absent/incomplete/corrupt/relative/alias; `macos_service.py` happy/second-call/missing dir/alias dir/relative dir/half-written dir/`plutil -lint`; `remote_command.py` happy/no-args/`user@host`/unresolved `/tmp` script path; `select_runner.py` no env/each missing var/invalid `HOSTED_RUNNER`/unwritable `GITHUB_OUTPUT`/second call/forced hosted/GHES URL, plus in-process comparison of six fallback causes.
- Partially walked: CI workflow (`actionlint` syntax and expression tracing only; no run).
- Blocked (exact next check listed): live acceptance dispatch sequencing for P1 — `gh workflow run "Preferred runner CI" --ref <candidate> && gh workflow run "Preferred runner CI" --ref <candidate> -f force_hosted=true` then `gh run list --workflow "Preferred runner CI" --branch <candidate> --json conclusion`; `actions/checkout@v6` tag existence — `gh api repos/actions/checkout/releases/latest --jq .tag_name` (network read with the operator's credential; not run); README format check with its dependency — `uv run --with pyyaml <plugin-cache>/skill-creator/scripts/quick_validate.py github-runner` (ephemeral install; not run); `npx skills add . --list` (network/npx install; not run); Windows `current_account()` ctypes path (no Windows host); `launchctl bootstrap system`, `svc.sh install`, `config.cmd` service, systemd units, reboot persistence, SSH to a real host, registration token flow, PAT/secret provisioning, GHES adapter.
- Intentionally skipped: anything touching the audited source tree, git state, or a real GitHub repository.

Blind spots: real GitHub API pagination/ordering behaviour (only the fixture contract was exercised); launchd semantics of the rendered plist beyond `plutil -lint`; behaviour of `actions/checkout` sparse checkout when `.github/scripts/select_runner.py` is absent on the default branch (traced as the documented bootstrap gate; not run).

## 4. Exit-code table

| Command | Scenario | Exit | stdout / stderr contract |
| --- | --- | --- | --- |
| `python3 -m unittest discover -s tests -v` (cwd = skill) | 24 tests | 0 | `OK` |
| `python3 -m unittest discover -s github-runner/tests` (cwd = repo root) | 24 tests | 0 | `OK` |
| `python3 -m unittest discover -s github-runner/tests -p test_select_runner.py` | 9 tests | 0 | `OK` |
| `python3 -m py_compile github-runner/scripts/*.py` | on copies | 0 | silent; writes `__pycache__` next to source when run as documented without `PYTHONDONTWRITEBYTECODE` |
| `actionlint github-runner/assets/ci.yml` | template | 0 | silent |
| `prepare_runner.py` | no args, stdin closed | 2 | argparse usage on stderr |
| `prepare_runner.py prepare ...` | fresh target, valid digest | 0 | JSON receipt on stdout (`status: prepared`) |
| `prepare_runner.py prepare ...` | second call, same inputs | 1 | `Preparation/inspection refused: "Instance already exists; inspect it before resuming"` |
| `prepare_runner.py prepare ...` | after SIGKILL mid-extraction (receipt `incomplete`) | 1 | same "Instance already exists" message (P3) |
| `prepare_runner.py prepare ...` | two concurrent processes, same target | 0 and 1 | winner prints receipt; loser `[Errno 17] File exists`; receipt `prepared`, 303 files, no drift |
| `prepare_runner.py prepare ...` | `--expected-user` mismatch | 1 | `"Run as the verified standard runtime account, not root"` (P7) |
| `prepare_runner.py prepare ...` | parent dir missing | 1 | `"Prepare the parent directory first"` |
| `prepare_runner.py prepare/inspect` | `--directory /tmp/...` on macOS, or relative | 1 | `"Use an absolute resolved directory without symlinks"` (P7) |
| `prepare_runner.py inspect` | prepared dir | 0 | JSON with `preparation` block, `registration: null` |
| `prepare_runner.py inspect` | nonexistent dir | 0 | JSON `exists: false` |
| `prepare_runner.py inspect` | corrupt `.runner` (not JSON) | 1 | `Preparation/inspection refused: "Expecting value: line 1 column 1 (char 0)"` |
| `macos_service.py` | no args | 2 | argparse usage |
| `macos_service.py ...` | fresh staging dir | 0 | `Rendered <plist> and <plan>; no service changes made.`; files mode 0600; `plutil -lint` OK |
| `macos_service.py ...` | second call, same dir | 2 | `Output artifacts already exist; inspect them or use a new staging directory.` |
| `macos_service.py ...` | dir with only the plist (half-written) | 2 | same message; existing file preserved |
| `macos_service.py ...` | missing dir / `/tmp` alias / relative | 2 | `Output directory must already exist with no symlink path components.` |
| `remote_command.py` | no args | 2 | argparse usage |
| `remote_command.py --host build-host ...` | valid | 0 | `ssh -t -l admin -- build-host 'sudo -- /bin/bash -- /private/tmp/stage/setup.sh'` |
| `remote_command.py --host admin@build-host ...` | `user@` prefix | 2 | argparse error naming the rule |
| `remote_command.py ... --script /tmp/stage/setup.sh` | unresolved alias | 0 | accepted (syntax-only by design; docs say so) |
| `select_runner.py` | no env | 1 | `HOSTED_RUNNER is required and must be an approved standard GitHub-hosted label` |
| `select_runner.py` | `HOSTED_RUNNER` ok, no `GITHUB_OUTPUT` | 1 | `Invalid selector output path` (P5) |
| `select_runner.py` | `HOSTED_RUNNER=self-hosted` | 1 | same HOSTED_RUNNER message |
| `select_runner.py` | valid hosted-only | 0 | `runner="ubuntu-24.04"` on stdout and appended to `GITHUB_OUTPUT` |
| `select_runner.py` | second call, same `GITHUB_OUTPUT` | 0 | appends a second `runner=` line (GitHub takes the last; harmless) |
| `select_runner.py` | `FORCE_HOSTED=true` with full trusted config | 0 | hosted label, no API call |
| `select_runner.py` | `GITHUB_API_URL` = GHES | 0 | hosted label, no API call |
| `select_runner.py` (in-process) | busy runner / bad `RUNNER_LABELS` / label typo / 401 / untrusted ref | n/a | all return the hosted label with no reason (P2) |
| `quick_validate.py github-runner` | documented format check | 1 | `ModuleNotFoundError: No module named 'yaml'` (P6) |

## 5. Gaps and errors by process (severity order)

### P1 — Medium — Acceptance dispatches on the same candidate cancel each other
- Location: `github-runner/assets/ci.yml:14-16` (`concurrency: group: preferred-ci-${{ github.workflow }}-${{ github.ref }}`, `cancel-in-progress: true`), `github-runner/assets/ci.yml:3-6` (`on: push`, `pull_request`, `workflow_dispatch`), `github-runner/references/ci.md:7` ("dispatch both modes with `--ref`"), `github-runner/references/ci.md:37` ("Run the real preferred-host checks and a `force_hosted` dispatch on the **same final candidate**").
- Stranded-user scenario: the agent pushes the final candidate branch (this already starts a push-triggered preferred run), then follows ci.md and dispatches `gh workflow run ... --ref <candidate>` and `gh workflow run ... --ref <candidate> -f force_hosted=true`. All three runs share the group `preferred-ci-Preferred runner CI-refs/heads/<candidate>`; each new run cancels the in-flight one. The preferred-host evidence the acceptance section requires ends as `conclusion: cancelled`. ci.md:33 says "Concurrency cancellation is not success", so the agent knows it must not count it, but nothing tells it to serialize, and the natural chained command produces the cancellation.
- Evidence: PLAUSIBLE. Traced in the template and GitHub's documented concurrency semantics; live dispatch is outside the safety boundary.
- Cost: lost acceptance evidence, repeated 30-minute preferred runs, and an agent that may report "cancelled" as a routing failure and start diagnosing the host.
- Recommended direction: include the mode in the group key (e.g. `preferred-ci-${{ github.workflow }}-${{ github.ref }}-${{ inputs.force_hosted || 'auto' }}`) or set `cancel-in-progress: ${{ github.event_name != 'workflow_dispatch' }}`, and add one sentence to ci.md "Acceptance": wait for the first run's terminal conclusion before dispatching the second mode on the same ref.
- Acceptance check (recommended even though Medium): on a throwaway repo, `gh workflow run "Preferred runner CI" --ref <candidate>; gh workflow run "Preferred runner CI" --ref <candidate> -f force_hosted=true; sleep 60; gh run list --workflow "Preferred runner CI" --branch <candidate> --json conclusion,event` must show no `cancelled` conclusion once fixed; today it shows one.

### P2 — Medium — Misconfiguration is indistinguishable from "runner busy" in the selector
- Location: `github-runner/scripts/select_runner.py:57-64` (silent early returns), `:65-93` (all API/label mismatches return `fallback`, `except Exception: return fallback`), `:96-102` (only `runner=` is emitted); `github-runner/references/ci.md:31` documents fallback for every cause but no diagnostic.
- Stranded-user scenario: an operator sets `RUNNER_LABELS='["Linux"]'` (forgot the architecture), or mistypes `PREFERRED_RUNNER_LABEL`, or the `RUNNER_READ_TOKEN` PAT expires after 30 days, or `TRUSTED_RUNNER_REF` still points at the old candidate branch after merge. Every CI run goes green on `ubuntu-24.04`. The "Record execution machine" step prints the hosted runner name deep in the `checks` job log, but nothing surfaces *why* the preferred host was skipped; the self-hosted machine sits idle for weeks. An agent asked "why isn't CI using the Mac?" gets identical bytes from the selector in all six situations (reproduced: `busy`, `RUNNER_LABELS` missing arch, label typo, 401, untrusted ref, healthy → first five print `'ubuntu-24.04'`).
- Evidence: CONFIRMED. Reproduction (on the copy):
  ```
  python3 - select_runner.py <<'EOF'
  # load module; call select(env, fake_fetch) with: busy runner; RUNNER_LABELS='["Linux"]';
  # PREFERRED_RUNNER_LABEL='repo-cl'; fetch raising RuntimeError('401'); TRUSTED_EVENT='false'
  EOF
  # all five -> 'ubuntu-24.04' with no stderr, no reason; healthy -> ['self-hosted','repo-ci','Linux','X64']
  ```
  Also `env -i HOSTED_RUNNER=ubuntu-24.04 GITHUB_OUTPUT=$O python3 select_runner.py` → stdout `runner="ubuntu-24.04"`, rc 0, stderr empty.
- Cost: silent loss of the product's main value (preferred routing), wasted hosted minutes, long debugging sessions; an agent cannot chain a "preferred host was skipped, investigate" branch.
- Recommended direction: emit a second, non-secret output `reason=<enum>` (`forced`, `untrusted-event`, `config-missing:<VAR>`, `platform-labels-invalid`, `api-error`, `no-unique-match`, `not-idle`, `labels-missing`, `ok`) to `GITHUB_OUTPUT` and as a `::notice::` line; never include exception text. Keep rc 0 (routing succeeded). Add a selector test asserting the reason enum, and mention in ci.md "Acceptance" that `reason` must be `ok` for the preferred run.

### P3 — Medium — `incomplete` preparation state has no forward transition
- Location: `github-runner/scripts/prepare_runner.py:50-51` (`if directory.exists(): raise ValueError('Instance already exists; inspect it before resuming')`), `:95-99` (exclusive reservation + `incomplete` receipt), `github-runner/references/setup.md:26` ("Interrupted extraction remains `incomplete` for inspection; create a reviewed resume plan, not broad cleanup or overwrite").
- Stranded-user scenario: the runtime account's SSH session drops (or the operator hits Ctrl-C) during extraction of the 200 MB official archive. `inspect` reports `status: incomplete` (rc 0). The operator reruns the exact documented `prepare` command: refused, rc 1, "inspect it before resuming". The doc forbids "broad cleanup or overwrite" and offers no resume command. The only way forward is to hand-delete the reserved directory the helper created, which the same doc discourages; a cautious agent stops here.
- Evidence: CONFIRMED. Reproduction (on the copy, runtime shim kills the process on the 50th file copy):
  ```
  python3 - prepare_runner.py <archive> <sha> <dir> <user> <<'EOF'   # patches shutil.copyfileobj to os._exit(137) on call 50
  EOF
  # rc 137; <dir>/.preparation.json -> "status": "incomplete"
  python3 prepare_runner.py prepare --archive <archive> --sha256 <sha> --version 2.330.0 --directory <dir> --expected-user <user>
  # rc 1: Preparation/inspection refused: "Instance already exists; inspect it before resuming"
  python3 prepare_runner.py inspect --directory <dir>   # rc 0, reports incomplete; nothing else to run
  ```
- Cost: a primary journey (fresh install) stalls at step 2 for a common failure (dropped SSH session); recovery requires deciding to violate a documented caution.
- Recommended direction: either (a) document the explicit recovery in setup.md — "if `inspect` shows `incomplete` and no `.runner`/`.credentials` exist, remove the reserved directory (`rm -r -- "$INSTANCE_DIR"`) and rerun `prepare`" — or (b) add `prepare --resume-incomplete` that re-verifies the digest, requires receipt `status == incomplete` and the absence of `.runner`/`.credentials`, re-extracts with `exist_ok`/overwrite inside the reserved directory only, and rewrites the receipt to `prepared`. Add a test for the chosen path (the existing `test_interrupted_extraction_is_retained_and_retry_refused` covers only the refusal).
- Acceptance check: after the SIGKILL fixture above, the documented recovery command sequence (either the new flag or the documented `rm` + rerun) ends with `inspect` printing `"status": "prepared"` and rc 0; today no documented sequence does.

### P4 — Low — No version stamp or migration for persisted state
- Location: `github-runner/scripts/prepare_runner.py:96-97` (receipt keys: `status, version, sha256, archive, account`), `:129` (`inspect` reads a fixed tuple of fields).
- Stranded-user scenario: a later skill release adds or renames receipt fields (e.g. `resume_offset`, `entries`); an operator inspecting a directory prepared by the earlier helper gets `null`s with no indication that the receipt predates the format, and the older helper reading a newer receipt silently drops fields. The spec treats "no versioning at all" as a finding.
- Evidence: CONFIRMED (receipt printed in section 4 has no `schema`/`format` key; `inspect` performs no version check).
- Recommended direction: add `"format": 1` to the receipt; in `inspect`, report `format` and refuse (rc 1, named message) when it is newer than supported.

### P5 — Low — Exit-code contract is inconsistent across the four helpers
- Location: `github-runner/scripts/prepare_runner.py:154-155` (`parser.exit(1, ...)` for refusals; argparse 2 for usage), `github-runner/scripts/macos_service.py:100-101` (`parser.exit(2, ...)` for refusals, same as usage), `github-runner/scripts/remote_command.py:22,24,26,29` (`parser.error` → 2 for validation), `github-runner/scripts/select_runner.py:103-106` (rc 1 for both `HOSTED_RUNNER` and `GITHUB_OUTPUT`; the latter says only `Invalid selector output path`).
- Stranded-user scenario: an agent wrapping the helpers wants "usage error → fix my command" vs "guard refused → stop and report". With `macos_service.py` it cannot: both are 2. With `select_runner.py` running outside Actions (local dry-run per README "Copy/adapt the hosted selector"), the unexplained `Invalid selector output path` does not say to set `GITHUB_OUTPUT`.
- Evidence: CONFIRMED (section 4 rows).
- Recommended direction: adopt one contract across helpers (2 = usage, 1 = guard refusal, 0 = done) and make the `GITHUB_OUTPUT` message name the variable: `GITHUB_OUTPUT is required (set by GitHub Actions; for a local dry-run point it at a writable file)`.

### P6 — Low — Documented format check cannot run as written
- Location: `github-runner/README.md:47` ("run the skill-creator `scripts/quick_validate.py` against this directory"), `:52` (`actionlint ...`).
- Stranded-user scenario: a contributor follows "Checks" on a fresh macOS: there is no `quick_validate.py` in the repo; the one in the skill-creator plugin cache fails with `ModuleNotFoundError: No module named 'yaml'` on all three local interpreters (Homebrew, system, `python3`). `actionlint` is assumed present with no install pointer.
- Evidence: CONFIRMED (`python3 <plugin-cache>/skill-creator/scripts/quick_validate.py <copy>` → rc 1, traceback at `import yaml`). Running it with `uv run --with pyyaml` was BLOCKED (installation).
- Recommended direction: state the validator's location (plugin `skill-creator`, `scripts/quick_validate.py`) and `pip install pyyaml` / `uv run --with pyyaml`, or drop the reference and keep the stdlib checks; add `brew install actionlint` (or the release URL) next to the `actionlint` line.

### P7 — Low — Refusal messages name the wrong condition
- Location: `github-runner/scripts/prepare_runner.py:28-31` (`checked_directory` → "Use an absolute resolved directory without symlinks"), `:46-47` (expected-user mismatch → "Run as the verified standard runtime account, not root"), `github-runner/references/setup.md:21-24` and `verification.md:21` (examples use `$INSTANCE_DIR` / `/actual/resolved/path` with no macOS alias note; `platforms.md:54` has the note only for `macos_service.py`).
- Stranded-user scenario: on macOS the operator stages under `/tmp/runner-task/...` (the docs say "private task staging directory") and gets "without symlinks" although they typed no symlink; a mistyped `--expected-user` is reported as a root problem.
- Evidence: CONFIRMED (section 4 rows for `/tmp` alias, relative path, wrong expected user).
- Recommended direction: resolve-and-compare in the message ("`/tmp/x` resolves to `/private/tmp/x`; pass the resolved path"), split the account guard into two messages, and add the alias note to setup.md.

## 6. Missing-process backlog (by unblocking value)

1. Recovery for `incomplete` preparation (P3): documented `rm`-and-rerun sequence or `prepare --resume-incomplete`.
2. Selector `reason=` output and `::notice::` line (P2), plus a ci.md acceptance line requiring `reason=ok` on the preferred run.
3. Concurrency group keyed by mode or `cancel-in-progress` disabled for `workflow_dispatch`, plus "wait for terminal conclusion before the second dispatch" in ci.md (P1).
4. Post-merge variable flip: ci.md says `TRUSTED_RUNNER_REF` "can temporarily identify a reviewed candidate branch" but no step in the journey flips it back to `refs/heads/main` after merge; add it to the Acceptance/readback list (would otherwise manifest as P2's silent hosted routing).
5. Uniform helper exit-code contract and a `GITHUB_OUTPUT` message that names the variable (P5).
6. `format` stamp in `.preparation.json` (P4).
7. README "Checks": validator location + PyYAML, `actionlint` install pointer, and `PYTHONDONTWRITEBYTECODE=1` or `-B` on the documented `py_compile`/unittest lines so contributors do not litter `__pycache__` into the skill folder (the pre-existing `.pyc` files show this already happened).
8. Alias/resolved-path note for `prepare_runner.py` in setup.md/verification.md (P7).

## 7. What held up

- All three documented unittest recipes pass (24, 24, 9) with stdin closed and no TTY; `py_compile` and `actionlint` rc 0.
- `prepare_runner.py prepare`: second call refused with destination untouched; two concurrent invocations on the same target produce exactly one winner (rc 0) and one `[Errno 17]` loser (rc 1), receipt `prepared`, no corruption or drift; traversal/symlink/duplicate guards hold; `inspect` never prints `.credentials` or extra `.runner` fields.
- `macos_service.py`: second call and half-written staging refused without overwriting; rendered plist passes `plutil -lint`; artifacts are 0600; quoting of paths with `'` and `$(...)` survives both shell boundaries.
- `remote_command.py`: rejects `user@host`, option-looking hosts, whitespace, `..`; IPv6 incl. `::1` and scoped addresses accepted.
- `select_runner.py`: missing/invalid `HOSTED_RUNNER` fails loudly before any API call with a message naming the variable; forced-hosted and GHES paths make no network call; a second call only appends to `GITHUB_OUTPUT`.
- No secret-looking strings in in-scope contents (pattern scan for `ghp_`, `github_pat_`, AWS keys, PEM blocks, Slack tokens: no matches).
- Discarded candidates (NOT REPRODUCED): "selector breaks when `inputs.force_hosted` is empty on push" — `${{ inputs.force_hosted || false }}` yields the string `false`, which the selector handles; "`fromJSON` of a bare string label fails in `runs-on`" — `actionlint` accepts it and GitHub's expression docs permit a string result.

## 8. Open questions (maintainer-only)

1. Is the all-events `cancel-in-progress: true` intentional for `workflow_dispatch` acceptance runs, or should dispatches be exempt (P1)?
2. Is suppressing *all* fallback reasons a deliberate security choice beyond hiding exception text? A fixed enum leaks nothing and would resolve P2.
3. Should the skill own recovery from `incomplete` (new flag) or only document it (P3)?
4. The README "Checks" section references the skill-creator validator; is PyYAML an accepted dependency for contributors, or should the reference go?
5. `actions/checkout@v6` could not be verified offline (BLOCKED: `gh api repos/actions/checkout/releases/latest --jq .tag_name`); confirm the pin exists before publishing.

Completion: report and sidecar written; no source, configuration or git state was modified. STOP.

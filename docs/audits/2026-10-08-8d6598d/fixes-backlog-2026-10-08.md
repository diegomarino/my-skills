# Fixes backlog -- 2026-10-08 -- `github-runner` skill (bounded working-tree audit)

## 0. Run header

- Run directory: `docs/audits/2026-10-08-8d6598d/`
- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263` (short `8d6598d`), branch `feat/github-runner`, tree **DIRTY** by explicit human opt-in (preflight gates for audit selection and dirty tree satisfied by the human instruction; no commit, stash, base ref or clean checkout was requested).
- Preflight dirty-run identity: scoped `git diff HEAD -- README.md` sha256 `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502`; untracked scoped file list = the 19 files under `github-runner/` named below; per-file SHA-256 manifest recorded at preflight (orchestrator scratchpad `baseline.txt`) and re-verified by the conductor after every worker, before synthesis and before writing this backlog. 8 gitignored, pre-existing `github-runner/**/__pycache__/*.pyc` files were excluded from the target and monitored informationally (byte-identical throughout).
- Scope (human override, applied identically by all six audits): working tree, ONLY `github-runner/**` (untracked: `README.md`, `SKILL.md`, `agents/openai.yaml`, `assets/ci.yml`, `references/{ci,credentials,discovery,platforms,setup,verification}.md`, `scripts/{macos_service,prepare_runner,remote_command,select_runner}.py`, `tests/{scenarios.md,test_macos_service,test_prepare_runner,test_remote_command,test_select_runner}.py`) plus the current diff of root `README.md` vs HEAD (4 insertions, 1 deletion). Target size: 20 files, ~1,322 lines, ~101 KB; six independent full reads were performed. The skill was treated as the whole product. Unchanged files were read only as minimum consumer/convention context (root README, sibling README install lines, `.gitignore`). No other skill, history, worktree or host was audited; secret scans covered in-scope contents only.
- Audits run: 6 / 6 selected. Failed: none. Skipped: none. Unavailable: none. Quarantined: none.
  - change: `change-audit-2026-10-08.md` (+ `.findings.json`), X1-X5, target "working tree" (human override of audit-full's base-ref-only suite rule).
  - codebase: `codebase-audit-2026-10-08.md`, C1-C12.
  - docs: `docs-audit-2026-10-08.md`, D1-D10.
  - process: `process-audit-2026-10-08.md`, P1-P7.
  - security: `security-audit-2026-10-08.md`, S1-S3.
  - ux: `ux-audit-2026-10-08.md`, U1-U13.
- Validation: every report and sidecar passed `dev/scripts/validate-report.mjs` from the fresh specs clone (6/6 ok, ID-set parity, prefixes, evidence labels, acceptance checks on Critical/High); map/model facts carry evidence labels in the codebase, process, security and ux reports; the docs report carries its verified facts in its drift-verification section.
- Model and effort: conductor and all six workers ran on Claude Fable 5.1 (`claude-fable-5-1`), each worker a fresh isolated-context Agent dispatched with the explicit `fable` model selection; no substitution. Reasoning effort: session-level default (this harness exposes no per-worker override). Dispatch: sequential (change -> codebase -> docs -> process -> security -> ux).
- Drift events: none. Source bytes and scoped git state were identical to the preflight baseline at every check (after each of the six workers, after the one repair, before synthesis, before writing).
- Repair events: 1. The security report and sidecar transcribed the README diff checksum with one dropped character (`...dbd633aeb0f...`); the worker was re-messaged once naming only that defect, corrected the value in exactly the three places (report lines 5 and 80, sidecar `snapshot.readme_diff_sha256`), and the report re-passed validation. No finding, label or severity was touched.
- Tests run by workers (all in `mktemp` copies outside the project, `PYTHONDONTWRITEBYTECODE=1`): bundled unittest 24/24 (all three documented recipes; Python 3.14.7 and 3.9.6), `py_compile` on all four helpers, `actionlint` on `assets/ci.yml` (clean), `plutil -lint` on a rendered plist, relative-link checks (all 44 resolve), in-scope secret scans (gitleaks `--no-git` + regex sweeps: none), `ast.parse(feature_version=(3,9))` on all 8 Python files, fixture executions of all four helpers (happy, refusal, alias, concurrency, SIGKILL-interruption paths), 9 mutation runs on the test suite, read-only unauthenticated GitHub API/docs lookups (release digest format, official archive member census, `actions/checkout` tag, hosted-label table, API version header).
- BLOCKED checks (not run; unsafe or outside the boundary; exact next checks in each report): live runner registration / `.runner` readback from a real instance; launchd / systemd / Windows service install; executing the rendered SSH line; `gh workflow run` dispatch pair (needed for F7 and F18 symptoms); case-variant branch creation in a disposable repo (F4); `sudo ./svc.sh` with runtime-modified script on a disposable Linux VM (F16); launchd log-path open semantics (security Q1); Windows `GetUserNameW` identity path; `npx skills add` discovery/install; `quick_validate.py` with PyYAML; Linux x64 archive full download (227 MB; member list streamed instead); reboot persistence.
- Housekeeping (maintainer action, outside the project): workers could not delete their throwaway directories because the permission system denied the removal: `/tmp/audit-gr.kOOs5F` (~128 MB official archive + fixtures), `/tmp/gr-audit.fU9LXm`, `/tmp/gr-audit.iQhFBb`, `/tmp/gr-alias.aBkVNk`, `/tmp/gr-svc.TWAHvG`, plus `mktemp` dirs under the session scratchpad. Nothing was written into the project except this run directory. Git state untouched.
- Nothing has been fixed. This backlog is the terminal deliverable; `fix.md` is a separate, human-gated step.

## 1. Summary table

| ID | Severity | Issue | Cited | Provenance |
| --- | --- | --- | --- | --- |
| F1 | High | `prepare` refuses every official Linux/macOS runner archive (in-tree relative symlinks under `externals/node*/bin`) | X1, C1 | confirmed via X1 and C1 (independent reproductions with the real v2.338.0 asset) |
| F2 | High | `inspect` rejects real `.runner` files because the runner writes them with a UTF-8 BOM | X2, C2 | confirmed via X2 (byte-exact fixture + writer traced in `actions/runner` source); C2 corroborating, plausible (live-file readback blocked) |
| F3 | High | Every hosted fallback of the selector is silent and reason-free; misconfiguration, expired PAT and "runner busy" are byte-identical | U1, X3, C4, P2, D2 | confirmed via U1, X3, C4, P2, D2 (five independent reproductions / doc checks); severities diverge (U1 High; X3, C4, P2, D2 Medium) |
| F4 | High | Trusted-ref gate `github.ref == vars.TRUSTED_RUNNER_REF` is case-insensitive; a case-variant unprotected branch is routed to the persistent host | S1 | plausible via S1 (expression semantics confirmed from primary docs; live branch creation blocked) |
| F5 | High | `HOSTED_RUNNER` rejection names neither the received value nor the accepted subset, which exists only in source | U2 | confirmed via U2 |
| F6 | High | `RUNNER_LABELS` must contain one OS and one architecture label; the docs never say so and the failure is a silent fallback | D1 | confirmed via D1 |
| F7 | Medium | Workflow concurrency group (workflow + ref, cancel-in-progress) cancels the documented preferred/`force_hosted` acceptance pair | C3, P1 | confirmed via C3 (template + GitHub semantics); P1 corroborating, plausible (live dispatch blocked) |
| F8 | Medium | The digest the documented `gh api` command returns is `sha256:<hex>` and `prepare --sha256` rejects it | C7, U3 | confirmed via C7 and U3 (live API format + reproduction) |
| F9 | Medium | `status: incomplete` after an interrupted extraction has no documented or coded forward path | P3, U11 | confirmed via P3 (SIGKILL fixture) and U11 |
| F10 | Medium | Refusal messages of `prepare`/`inspect`/renderer name the wrong condition: macOS `/tmp`, `/var`, `mktemp -d` paths refused as "symlinks" without the resolved path; an expected-user mismatch reported as "not root" | U4, U5, C10, P7 | confirmed via U4, U5, C10, P7; severities diverge (U4, U5 Medium; C10, P7 Low) |
| F11 | Medium | Helper CLI contract (preconditions, `inspect` JSON shape, receipt states, `runner=` line, exit codes) is neither consistent across helpers nor documented in docs or `--help` | D5, U8, P5 | confirmed via D5, U8, P5; severities diverge (D5, U8 Medium; P5 Low) |
| F12 | Medium | Selector queries by `name` only and cannot enforce the label-uniqueness / hosted-label-collision invariant the routing depends on | C5 | confirmed via C5 |
| F13 | Medium | On Windows `prepare` silently drops the parent-ownership and not-root guards the docs promise on every platform | C6 | confirmed via C6 |
| F14 | Medium | Six safety guards are non-pinning in the test suite (three pagination guards masked by `except Exception`, 64 KiB cap, root and parent-owner guards without a seam) | C8 | confirmed via C8 (mutation runs) |
| F15 | Medium | Service PATH story contradicts the runner: `config.sh` writes `.path` and `runsvc.sh` exports it, overriding the plist `--path` and the `ci.md` claim | X4 | confirmed via X4 (`actions/runner` source + downloaded archive) |
| F16 | Medium | Linux guidance has root run `sudo ./svc.sh` from the runtime-account-owned runner tree (runtime-writable code executed as root), unlike the macOS branch | S2 | confirmed via S2 (instruction text; live VM check blocked) |
| F17 | Medium | The rendered macOS plan bakes the local staging path into the privileged `sudo install` line; off-target rendering requires hand-editing a `sudo` command | U9 | confirmed via U9 |
| F18 | Medium | The default-branch bootstrap gate is invisible: buried mid-paragraph in `ci.md` and surfaced in the run only as Python's "can't open file" | D4, U10 | confirmed via D4; U10 corroborating, plausible (live run blocked) |
| F19 | Medium | Archive refusal messages ("links and special entries", "missing entry points", "checksum mismatch") name no entry, expected name or computed value | U6 | confirmed via U6 |
| F20 | Medium | macOS renderer rejects legitimate account names (uppercase, dots) and never names the offending argument; "Choose a dedicated standard runtime account" reads as policy, not syntax | U7, C9 | confirmed via U7 and C9; severities diverge (U7 Medium; C9 Low) |
| F21 | Medium | README "Checks" cites a `quick_validate.py` that is not in the repo, not linked, and fails on an undeclared PyYAML dependency; no `actionlint` install pointer | D3, P6, C11 | confirmed via D3, P6, C11; severities diverge (D3 Medium; P6, C11 Low) |
| F22 | Low | Skill README install/invocation form (`--skill`, "after published", `$github-runner`) diverges from the root README and sibling convention (`@<skill>`, `-g`) | X5, D6, C11 | confirmed via X5, D6, C11 |
| F23 | Low | `actions/checkout@v6` is a mutable tag in both jobs of a template that cites the hardening guide and SHA-pins its own selector | S3, C12 | confirmed via S3 and C12 (tag resolved live) |
| F24 | Low | `.preparation.json` carries no format/version stamp and `inspect` has no version check | P4 | confirmed via P4 |
| F25 | Low | The runtime account is `--expected-user` / `--account` / `$RUNNER_ACCOUNT`; "label" means three different things across surfaces | U12 | confirmed via U12 |
| F26 | Low | `remote_command.py` rejects `admin@host` without pointing at `--admin-account` and `host:2222` as "not a valid IP address" | U13 | confirmed via U13 |
| F27 | Low | Same facts restated in up to eight places (dedicated-account rule, Python floor, test command, label verification date) | D7 | confirmed via D7 |
| F28 | Low | `tests/scenarios.md` mixes the reusable scenario spec with a dated evaluation log whose absolute counts will drift | D8 | confirmed via D8 |
| F29 | Low | `platforms.md` bundles common rules + three OS branches + availability while `SKILL.md` tells the agent to load one branch | D9 | confirmed via D9 |
| F30 | Low | No diagram anywhere; the four-gate lifecycle, selector routing, credential boundaries and macOS daemon conversion are prose only | D10 | confirmed via D10 |

Counts: 30 backlog entries from 50 original findings (C11 is cited twice because it bundles two distinct defects, split across F21 and F22). Severity: Critical 0, High 6, Medium 15, Low 9. Evidence provenance across the 51 citations: CONFIRMED 47, PLAUSIBLE 4 (C2, P1, S1, U10), BLOCKED 0, NOT REPRODUCED 0.

## 2. Backlog (severity order)

### F1 -- `prepare` refuses every official Linux/macOS runner archive (High)

Behavioral description: following `setup.md` with the real release asset and its published digest ends in "Archive links and special entries require manual review", exit 1; the receipted preparation path, the `inspect` readback of preparation state and the interrupted/resume guarantees are unreachable on real input, so agents fall back to bare `tar xzf` with none of the guards.
Cited: X1 (CONFIRMED), C1 (CONFIRMED). Merge rationale: one defect, the per-entry type check at `prepare_runner.py:80-82` rejecting the six relative symlinks (`externals/node{20,24}/bin/{npm,npx,corepack}`) every Linux/macOS release ships; X1 reproduced on the osx-arm64 asset, C1 additionally confirmed the identical six entries in the streamed linux-x64 listing and that the win-x64 zip passes.
File evidence: `github-runner/scripts/prepare_runner.py:80-82`; `github-runner/references/setup.md:26`; `github-runner/tests/test_prepare_runner.py` (synthetic two-file fixtures only); `github-runner/tests/scenarios.md:58`.
Acceptance check: in a `mktemp` directory outside the project, as a non-root user, `python3 scripts/prepare_runner.py prepare --archive actions-runner-osx-arm64-2.338.0.tar.gz --sha256 df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2 --version 2.338.0 --directory <resolved-parent>/instance --expected-user "$(id -un)"` currently exits 1 with the message above; passes when it exits 0, `.preparation.json` reads `"status": "prepared"`, and `readlink instance/externals/node20/bin/npm` prints `../lib/node_modules/npm/bin/npm-cli.js`.
Suggested fix: accept symlink members whose target is relative, contains no `..` escape, and resolves inside the instance root; create them after regular files; keep refusing absolute/escaping links, hard links and devices; add an official-layout fixture and an escaping-link negative test; update `setup.md:26` and `README.md:38`. Grouping: do together with F19 (archive messages) and F14 (fixture realism); first in order, it unblocks F2's and F9's real-world verification.

### F2 -- `inspect` rejects real `.runner` files (UTF-8 BOM) (High)

Behavioral description: the only sanctioned, credential-safe readback of registration identity fails on every real instance with "Unexpected UTF-8 BOM", pushing the agent to read `.runner` by hand next to `.credentials`.
Cited: X2 (CONFIRMED), C2 (PLAUSIBLE). Merge rationale: one defect, `json.loads(path.read_text())` at `prepare_runner.py:126` decoding with `utf-8` rather than `utf-8-sig`; both audits reproduced the rejection with a byte-exact BOM fixture and traced the writer (`IOUtil.SaveObject` -> `File.WriteAllText(..., Encoding.UTF8)`) in `actions/runner` source. The labels differ only in threshold: X2 counts source-level writer evidence as confirmation, C2 holds CONFIRMED for a live-file readback (BLOCKED). Not a fact conflict; both labels preserved.
File evidence: `github-runner/scripts/prepare_runner.py:126`; `github-runner/tests/test_prepare_runner.py` (`test_inspects_only_safe_registration_fields` writes the fixture with `json.dumps`, never the real format).
Acceptance check: `printf '\xef\xbb\xbf{"agentId":42,"agentName":"box","gitHubUrl":"https://github.com/acme/widget"}' > <tmp>/bomcase/.runner && python3 scripts/prepare_runner.py inspect --directory <tmp>/bomcase` currently exits 1; passes when it exits 0 and prints `"agentId": 42`. On a real host: `head -c 3 .runner | xxd` shows `efbb bf` and the same `inspect` succeeds.
Suggested fix: read state files with `encoding='utf-8-sig'`; also guard a non-string `gitHubUrl` (today it reaches `urlsplit` and escapes the `except` at line 154 as a traceback); add a BOM fixture test. Grouping: with F1 (same file, same fixture-realism cause).

### F3 -- Silent, reason-free hosted fallback in the selector (High)

Behavioral description: a misspelled variable, a `RUNNER_LABELS` array missing the architecture, an expired `RUNNER_READ_TOKEN`, a stale `TRUSTED_RUNNER_REF`, an API error and a genuinely busy runner all produce exactly `runner="ubuntu-24.04"`, exit 0, nothing on stderr; CI stays green on hosted runners indefinitely and the persistent host is silently never used. A local dry run additionally dies on "Invalid selector output path" without naming `GITHUB_OUTPUT`.
Cited: U1 (CONFIRMED), X3 (CONFIRMED), C4 (CONFIRMED), P2 (CONFIRMED), D2 (CONFIRMED). Merge rationale: one defect, every `return fallback` at `select_runner.py:57-93` plus the single `runner=` output at `:96-102`; D2 is the documentation face of the same gap (no symptom-first troubleshooting boundary because there is no signal to key on). Severity ranked at the highest cited: U1 High (primary journey completes only after reading source); X3, C4, P2, D2 Medium.
File evidence: `github-runner/scripts/select_runner.py:57-93, 96-106`; `github-runner/assets/ci.yml:31-43`; `github-runner/references/ci.md:31`; `github-runner/references/verification.md:35-39`.
Acceptance check (from U1): `env -i HOSTED_RUNNER=ubuntu-24.04 GITHUB_OUTPUT=/dev/null GITHUB_REPOSITORY=acme/widget PREFERRED_RUNNER_NAME=build-box PREFERRED_RUNNER_LABEL=widget-ci RUNNER_LABELS='Linux,X64' RUNNER_READ_TOKEN=x TRUSTED_EVENT=true python3 github-runner/scripts/select_runner.py` currently prints exactly `runner="ubuntu-24.04"` with empty stderr; passes when a line naming the non-secret reason (e.g. `reason=RUNNER_LABELS-not-json-array`) is emitted. Corroborating in-process check (P2): `select()` with `RUNNER_LABELS='["Linux"]'` and `select()` with a busy runner must return distinguishable results.
Suggested fix: have `select()` return `(label_or_list, reason)` with a closed vocabulary (`selected`, `forced`, `untrusted-event`, `missing-config:<VAR>`, `invalid-label`, `platform-labels-invalid`, `api-error`, `http-<status>`, `no-unique-match`, `not-online`, `busy`, `labels-missing`, `inventory-incomplete`), write `reason=` to `GITHUB_OUTPUT`, print `::notice::` (never exception text); consider failing hard, as `HOSTED_RUNNER` already does, on static configuration errors that can never succeed; make the `GITHUB_OUTPUT` message name the variable; assert the reason in `test_skips_api` and `test_api_error_and_custom_fallback`; then add the `verification.md` boundary "Preferred route not taken" with a symptom -> condition -> non-secret check table and the selector flowchart (D2/D10). Grouping: do with F6 and F5 (selector messages/docs) and before F12; the code change is the prerequisite for the doc fix (see Conflicts, J1).

### F4 -- Case-insensitive trusted-ref comparison routes case-variant branches to the host (High)

Behavioral description: a write collaborator who cannot push to the protected trusted branch pushes `refs/heads/MAIN`; the GitHub expression `github.ref == vars.TRUSTED_RUNNER_REF` evaluates true, `TRUSTED_EVENT` is set, and the `checks` job checks out the attacker's commit on the persistent self-hosted host.
Cited: S1 (PLAUSIBLE). Single source; the case-insensitive string comparison is confirmed from the primary GitHub expressions documentation; what is unverified is that GitHub accepts creating a case-variant of an existing protected branch and that the maintainer's ruleset does not already cover it (BLOCKED live check).
File evidence: `github-runner/assets/ci.yml:41-42`; `github-runner/references/ci.md:29`.
Acceptance check (from S1): in a `mktemp` copy with `PYTHONDONTWRITEBYTECODE=1`: `GITHUB_OUTPUT=/dev/null HOSTED_RUNNER=ubuntu-24.04 TRUSTED_EVENT=true GITHUB_REF=refs/heads/MAIN TRUSTED_RUNNER_REF=refs/heads/main GITHUB_REPOSITORY=acme/widget RUNNER_READ_TOKEN=x PREFERRED_RUNNER_NAME=w PREFERRED_RUNNER_LABEL=repo-ci RUNNER_LABELS='["Linux","X64"]' python3 scripts/select_runner.py` must print `runner="ubuntu-24.04"` before any API request; today the selector ignores `GITHUB_REF` entirely and with a stubbed API would emit the self-hosted label array. After the fix `test_select_runner.py` carries a case-variant subtest.
Suggested fix: export `GITHUB_REF` and `TRUSTED_RUNNER_REF` to the `route` step and make the trusted decision byte-exact in Python inside the trusted selector, keeping the YAML gate as defence in depth; document in `ci.md` that the ruleset must cover case variants and that `vars.TRUSTED_RUNNER_REF` must be exact. Grouping: with F3/F12 (selector trust logic); independent of everything else, ship early.

### F5 -- `HOSTED_RUNNER` rejection does not name the value or the accepted set (High)

Behavioral description: an operator who picks `ubuntu-22.04-arm` from GitHub's own standard-runner table (linked from `ci.md:27`) sees "HOSTED_RUNNER is required and must be an approved standard GitHub-hosted label" on the first run; the value is set and is a standard label, the message is false from their viewpoint, and the accepted 14-label subset is enumerated only in source. The same message covers unset, not-in-subset and case mismatch.
Cited: U2 (CONFIRMED).
File evidence: `github-runner/scripts/select_runner.py:12-16, 50-52`; `github-runner/references/ci.md:16-17, 27`.
Acceptance check (from U2): `env -i HOSTED_RUNNER=ubuntu-22.04-arm GITHUB_OUTPUT=/dev/null python3 github-runner/scripts/select_runner.py` currently fails without naming the received value or any accepted label; passes when stderr names the received value and enumerates the accepted labels.
Suggested fix: print the received value and the accepted list; mirror the list (and the policy for omitting labels such as `ubuntu-22.04-arm`) in the `ci.md` variable table. Grouping: with F3.

### F6 -- `RUNNER_LABELS` composition rule is undocumented and its failure is silent (High)

Behavioral description: an operator copies the labels shown on the runner page (`self-hosted`, `Linux`) or sets just the OS; the selector returns the hosted fallback with zero API calls on every push, and nothing in the docs points at `RUNNER_LABELS` as the cause.
Cited: D1 (CONFIRMED). Kept separate from F3 because it has its own cheap, independently checkable documentation fix and the behavioural anchor (`tests/test_select_runner.py:63`) must remain true.
File evidence: `github-runner/references/ci.md:15`; `github-runner/scripts/select_runner.py:66-70`; `github-runner/tests/test_select_runner.py:62-63`.
Acceptance check (from D1): `grep -n 'RUNNER_LABELS' github-runner/references/ci.md` fails today (the row mentions neither an architecture-label requirement nor the silent fallback); passes once the row states that the array must include one OS label (`Linux`/`macOS`/`Windows`) and one architecture label (`X64`/`ARM64`/`ARM`), that extra labels are AND-matched, and that any other array returns `HOSTED_RUNNER` before any API request; `select(env | RUNNER_LABELS='["Linux"]', fetch)` must still return the fallback with zero `fetch` calls.
Suggested fix: rewrite the table row as above; with F3's reason output, the `platform-labels-invalid` reason makes the rule discoverable at run time too. Grouping: with F3/F5.

### F7 -- Concurrency group cancels the documented acceptance pair (Medium)

Behavioral description: pushing the final candidate (a push-triggered run) and then dispatching the preferred run and the `force_hosted` run on the same ref, as `ci.md` instructs, places all three in group `preferred-ci-<workflow>-<ref>` with `cancel-in-progress: true`; each new run cancels the in-flight one, the required preferred-host evidence ends as `cancelled`, and an agent may misreport the cancellation as a routing failure.
Cited: C3 (CONFIRMED), P1 (PLAUSIBLE). Merge rationale: one defect, the group key at `ci.yml:13-16` ignoring `inputs.force_hosted`; C3 confirmed from the template and GitHub's documented concurrency semantics, P1 held PLAUSIBLE pending a live dispatch (BLOCKED).
File evidence: `github-runner/assets/ci.yml:13-16`; `github-runner/references/ci.md:7, 33, 37`.
Acceptance check (recommended though Medium): on a throwaway repo, `gh workflow run "Preferred runner CI" --ref <candidate>; gh workflow run "Preferred runner CI" --ref <candidate> -f force_hosted=true; sleep 60; gh run list --workflow "Preferred runner CI" --branch <candidate> --json conclusion,event` shows a `cancelled` conclusion today and none once fixed.
Suggested fix: include the mode in the group key (`...-${{ inputs.force_hosted || 'auto' }}`) or set `cancel-in-progress: ${{ github.event_name != 'workflow_dispatch' }}`; add one sentence to the `ci.md` acceptance section about waiting for a terminal conclusion before the second dispatch. Grouping: with F18 (same `ci.md` section restructure).

### F8 -- Documented digest format is rejected by `--sha256` (Medium)

Behavioral description: the `gh api .../releases/latest` command in `setup.md` returns `"digest": "sha256:<hex>"`; passing it verbatim fails with "Invalid digest or version", which names neither the argument nor the prefix, nudging the operator to recompute the digest from the download, which `setup.md:14` forbids.
Cited: C7 (CONFIRMED), U3 (CONFIRMED). Merge rationale: one defect, the bare-hex regex at `prepare_runner.py:48-49` versus the documented source of the value; both audits confirmed the live API format for v2.338.0.
File evidence: `github-runner/references/setup.md:9-14`; `github-runner/scripts/prepare_runner.py:48-49`.
Acceptance check (from C7): `prepare --sha256 sha256:<official hex>` currently exits 1 with "Invalid digest or version"; passes when it is accepted (or the doc shows the exact stripping command) and the message splits `--sha256` from `--version` and echoes the offending value.
Suggested fix: accept and strip a `sha256:` prefix, reject other algorithm prefixes, split the message. Grouping: with F1/F19 (same helper).

### F9 -- `incomplete` preparation state is a dead end (Medium)

Behavioral description: after a dropped SSH session or Ctrl-C mid-extraction, `inspect` reports `status: incomplete`, re-running the documented `prepare` is refused ("Instance already exists; inspect it before resuming"), the doc forbids "broad cleanup or overwrite" and names no resume; a cautious agent stops the fresh-install journey at step 2.
Cited: P3 (CONFIRMED), U11 (CONFIRMED). Merge rationale: one defect, the unconditional existence refusal at `prepare_runner.py:50-51` with no resume path and no documented recovery; the codebase report's design tension 4 (extract into `instance.partial-<pid>` and `rename()` atomically) describes the same gap without a finding ID.
File evidence: `github-runner/scripts/prepare_runner.py:50-51, 95-99, 115-135`; `github-runner/references/setup.md:26`.
Acceptance check (from P3): after the SIGKILL fixture (patch `shutil.copyfileobj` to `os._exit(137)` on the 50th call, run `prepare`), a documented recovery sequence (new flag, or documented `rm -r -- "$INSTANCE_DIR"` + rerun when no `.runner`/`.credentials` exist) ends with `inspect` printing `"status": "prepared"`; today no documented sequence does.
Suggested fix: document the explicit recovery now (cheapest), have `inspect` print a `next_action` for `incomplete` and the rerun refusal say the same (U11), and consider `prepare --resume-incomplete` or atomic partial-directory rename later (see Conflicts, J2). Grouping: with F1 (requires a real-layout archive to test meaningfully).

### F10 -- Refusal messages name the wrong condition (resolved paths, accounts) (Medium)

Behavioral description: on macOS, `mktemp -d`, `/tmp/...`, `/var/...` and `$TMPDIR` paths are refused by `prepare`, `inspect` and the renderer as "symlink path components" without the resolved `/private/...` path, and a plainly missing or relative directory gets the same message; a mistyped `--expected-user` is reported as "Run as the verified standard runtime account, not root" although the caller is not root, naming neither account.
Cited: U4 (CONFIRMED), U5 (CONFIRMED), C10 (CONFIRMED), P7 (CONFIRMED). Merge rationale: one defect class, guard messages that describe the rule rather than the observed condition (`prepare_runner.py:28-32, 46-47`; `macos_service.py:35-37`); the macOS alias warning exists only in `platforms.md:54` for the renderer. Severity ranked at the highest cited: U4, U5 Medium; C10, P7 Low.
File evidence: `github-runner/scripts/prepare_runner.py:28-32, 46-47`; `github-runner/scripts/macos_service.py:35-37`; `github-runner/references/setup.md:18-24`; `github-runner/references/platforms.md:54`.
Acceptance check: `python3 scripts/prepare_runner.py inspect --directory /tmp/x` on macOS currently prints "Use an absolute resolved directory without symlinks"; passes when the message shows `/tmp/x` resolves to `/private/tmp/x` and says to pass that; `prepare --expected-user ci_user` as user `diego` currently says "not root"; passes when it says current account `diego` is not the expected runtime account `ci_user`.
Suggested fix: resolve-and-compare in the message; split "does not exist" / "relative" / "has symlink components"; split the account guard into "wrong account" and "refusing root"; add the alias note beside the `prepare` example in `setup.md`. Grouping: with F19, F20, F26 (one message-quality pass over all four helpers).

### F11 -- Helper CLI contract is inconsistent and undocumented (Medium)

Behavioral description: an agent using the docs as its spec cannot learn the `inspect` JSON shape, the `.preparation.json` states, the `runner=` output line, or which exit code means "fix your command" versus "guard refused" (`prepare_runner.py` 1/2, `macos_service.py` 2/2, `remote_command.py` 2, `select_runner.py` 1 for both `HOSTED_RUNNER` and `GITHUB_OUTPUT`); ten of thirteen flags have no help text.
Cited: D5 (CONFIRMED), U8 (CONFIRMED), P5 (CONFIRMED). Merge rationale: one defect, the absence of a defined helper contract; D5 and U8 are its two documentation faces (reference docs, `--help`) and P5 is the inconsistency that makes it hard to document. Severity ranked at the highest cited: D5, U8 Medium; P5 Low.
File evidence: `github-runner/references/setup.md:20-26`; `github-runner/references/discovery.md:27`; `github-runner/references/verification.md:21`; `github-runner/scripts/macos_service.py:20-25, 100-101`; `github-runner/scripts/prepare_runner.py:141-148, 154-155`; `github-runner/scripts/select_runner.py:103-106`.
Acceptance check: `python3 scripts/macos_service.py --help` currently shows six bare flag names; passes when every flag has a `help=` string stating meaning and precondition, and a helper reference (README section or `references/helpers.md`) documents per helper the preconditions, outputs, JSON keys, receipt states and one exit-code contract (2 usage, 1 guard refusal, 0 done).
Suggested fix: adopt one exit-code contract, add `help=`/`metavar` per flag, write the helper reference and link it from the three places that describe helper output in passing. Grouping: after F3/F9/F10 so the documented contract reflects the new reason output, recovery path and messages.

### F12 -- Selector cannot enforce the uniqueness invariant it depends on (Medium)

Behavioral description: GitHub schedules by label set, not by name; when a second runner later carries the custom label, or a self-hosted box is labelled `ubuntu-latest`, the selector still finds exactly one runner *named* as configured, emits the label set, and trusted-ref jobs (and the PAT-bearing `select` job itself) can land on an unvetted host; the code pages a full inventory shape but filters by `?name=`, so the gate is a standing manual duty in `ci.md:25`.
Cited: C5 (CONFIRMED).
File evidence: `github-runner/scripts/select_runner.py:75-76`; `github-runner/references/ci.md:25, 33`.
Acceptance check (from C5): with a fixture inventory containing two runners labelled `repo-ci`, `select()` currently returns the label list; passes when it returns the hosted fallback (with reason) and when a self-hosted runner carrying `HOSTED_RUNNER` or `ubuntu-latest` also triggers the fallback.
Suggested fix: drop the `name` filter or add an unfiltered pass; refuse on duplicate custom label or hosted-label collision; keep the name check as an identity assertion on the single survivor; document that org-group runners the PAT cannot list still need the manual gate. Grouping: with F3/F4 (selector trust logic); after F3 so the refusal has a reason code.

### F13 -- Windows silently loses two of `prepare`'s advertised guards (Medium)

Behavioral description: on Windows an elevated shell whose username matches `--expected-user` can extract into a parent owned by another account; the not-root and parent-ownership guards are `hasattr(os, 'geteuid'/'getuid')`-gated no-ops, while the docs promise the same guards on every platform.
Cited: C6 (CONFIRMED).
File evidence: `github-runner/scripts/prepare_runner.py:46, 54`; `github-runner/references/setup.md:26`; `github-runner/references/platforms.md:72-74`.
Acceptance check (from C6): on Windows, `prepare` from an elevated shell currently succeeds; passes when it refuses or emits an explicit "guards unavailable on this platform; use the documented native procedure" message that is also stated in `setup.md`.
Suggested fix: implement Windows equivalents (`IsUserAnAdmin`/token elevation, owner SID of the parent) or refuse on Windows explicitly. Grouping: standalone; needs the maintainer's answer on Windows intent (Open questions, Q3).

### F14 -- Six safety guards are non-pinning in the test suite (Medium)

Behavioral description: deleting the short-page guard, the 1,000-record cap, the cross-page consistency check, the 64 KiB state-file cap, the parent-ownership guard or the root guard leaves the 24 tests green; the first three because the mock's `IndexError` is swallowed by `except Exception` into the very fallback the test expects, the last two because no seam exists.
Cited: C8 (CONFIRMED, nine mutation runs).
File evidence: `github-runner/scripts/select_runner.py:82, 88, 90-92`; `github-runner/tests/test_select_runner.py:95-103`; `github-runner/scripts/prepare_runner.py:46, 54, 124`.
Acceptance check (from C8): deleting `or len(batch) < 100` from `select_runner.py` currently leaves the suite green; passes when at least one test fails for each of the six mutations.
Suggested fix: make the mock raise a non-`Exception` sentinel or assert request counts per pagination case; add a >64 KiB state-file test; add an injectable identity/ownership seam with "root" and "parent owned by other uid" tests. Grouping: with F1/F2 (the cross-audit "guards calibrated on fixtures" pattern); land the fixture-realism tests alongside each fix.

### F15 -- Service PATH story contradicts the runner's `.path` mechanism (Medium)

Behavioral description: after any normal registration, `config.sh` sources `env.sh`, which writes the interactive PATH to `.path`, and `runsvc.sh` (the plist entry point) exports it, replacing the plist's `EnvironmentVariables.PATH`; an operator who registers from a shell with Homebrew first gets that PATH in the daemon, and one who adds `--path` sees no effect; `ci.md:3` states the opposite.
Cited: X4 (CONFIRMED from `actions/runner` source and the downloaded 2.338.0 archive).
File evidence: `github-runner/references/platforms.md:54, 60`; `github-runner/scripts/macos_service.py:24, 45, 49-91`; `github-runner/references/ci.md:3`.
Acceptance check: the rendered `service-plan.txt` and `platforms.md` currently never mention `.path`/`.env`; passes when both state the precedence and the plan tells the operator to inspect/set `.path` as the runtime account.
Suggested fix: document `.path`/`.env` precedence; either drop `--path` or state it applies only when `.path` is absent. Grouping: with F17 (renderer plan text).

### F16 -- Root executes runtime-owned `svc.sh` on Linux (Medium)

Behavioral description: the Linux procedure has the administrator run `sudo ./svc.sh install/start/status` from `$RUNNER_DIR`, which must be owned by the runtime account; any code that ran as that account (every trusted-ref job, or F4's bypass) can rewrite `svc.sh`, the `.service` file or the templates, and the next `sudo ./svc.sh ...` executes it as root. The macOS branch correctly forbids this.
Cited: S2 (CONFIRMED from the instruction text; live VM check BLOCKED).
File evidence: `github-runner/references/platforms.md:28-36`; contrast `github-runner/scripts/macos_service.py:67, 87`.
Acceptance check: `platforms.md` Linux section currently shows `sudo ./svc.sh` as the primary procedure; passes when it instead installs once, before any job has run, from an administrator-owned reviewed copy (or a directly rendered systemd unit) and manages the unit only via `systemctl <verb> <unit>`, with an explicit "never re-run `sudo ./svc.sh` on a runner that has executed jobs".
Suggested fix: align the Linux branch with the macOS one. Grouping: with F4 (privilege boundaries); documentation-only.

### F17 -- Rendered macOS plan bakes the local staging path into the privileged install line (Medium)

Behavioral description: when the plan is rendered on the workstation because Python may be absent on the target (the documented fallback), the `plutil -lint` and `sudo /usr/bin/install ... <local staging path> /Library/LaunchDaemons/...` lines fail on the target with "No such file", and the doc pushes the operator to hand-edit a `sudo` line.
Cited: U9 (CONFIRMED).
File evidence: `github-runner/scripts/macos_service.py:65-66, 77-78`; `github-runner/references/platforms.md:54`.
Acceptance check: rendering with `--output-dir <workstation path>` currently embeds that path in the `sudo install` line; passes when a `--target-staging-dir` (default `--output-dir`) or an explicit `STAGED_PLIST=` placeholder line is used by both commands.
Suggested fix: as above. Grouping: with F15 (plan text) and F20 (renderer arguments).

### F18 -- The default-branch bootstrap gate is invisible in docs and in the failing run (Medium)

Behavioral description: the rule that a `workflow_dispatch` workflow and the selector must exist on the default branch before any candidate dispatch (the defect `scenarios.md:52` says was found in practice) is sentence 7 of a 188-word paragraph; when violated, the sparse checkout succeeds with nothing and the run dies with Python's "can't open file '.github/scripts/select_runner.py'" instead of naming `RUNNER_SELECTOR_SHA`/the bootstrap.
Cited: D4 (CONFIRMED), U10 (PLAUSIBLE; live run BLOCKED). Merge rationale: one defect, a load-bearing prerequisite with neither structural prominence nor a runtime guard; the docs and ux audits saw its two faces.
File evidence: `github-runner/references/ci.md:7`; `github-runner/assets/ci.yml:25-30, 43`.
Acceptance check: `ci.md` "Prepare the selector" currently has no heading for the bootstrap gate; passes when it is numbered steps with its own "Bootstrap on the default branch first" subsection, and `ci.yml` has a guard step before `route` (`test -f .github/scripts/select_runner.py || { echo "::error::..."; exit 1; }`).
Suggested fix: both the restructure (D4) and the guard step (U10). Grouping: with F7 (same `ci.md` section).

### F19 -- Archive refusal messages name no entry, expected name or value (Medium)

Behavioral description: "Archive links and special entries require manual review", "Archive is missing runner entry points" and "Archive checksum mismatch" force the operator to re-list the archive by hand to find which member, which required name, or what was computed.
Cited: U6 (CONFIRMED).
File evidence: `github-runner/scripts/prepare_runner.py:62-63, 80-94`.
Acceptance check: `prepare` on an archive with a symlink member currently prints the generic message; passes when it names the first offending member and its type, the missing required names, and the computed digest beside the expected one.
Suggested fix: as above. Grouping: with F1 (the message will name the very entries F1 is about) and F10.

### F20 -- macOS renderer rejects legitimate account names and never names the argument (Medium)

Behavioral description: an account created as `Build` or `build.ci` is rejected with "Choose a dedicated standard runtime account.", which reads as a policy objection; a trailing slash on `--home` yields "Use a resolved absolute non-root path"; messages never say which flag failed, so operators rename working accounts or guess.
Cited: U7 (CONFIRMED), C9 (CONFIRMED). Merge rationale: one defect, the lowercase-only regex at `macos_service.py:28` paired with messages that omit the flag and value. Severity ranked at the highest cited: U7 Medium; C9 Low.
File evidence: `github-runner/scripts/macos_service.py:11-15, 28-37`.
Acceptance check: `macos_service.py --account Build ...` currently prints "Choose a dedicated standard runtime account."; passes when it either accepts `[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}` or says "lowercase letters only" with the flag name and value, and "reserved account" is a separate message.
Suggested fix: widen the regex (C9) and prefix every message with the flag and value (U7); see Conflicts, J3. Grouping: with F10/F17.

### F21 -- README format check cites an unavailable validator with an undeclared dependency (Medium)

Behavioral description: a contributor following "Checks" top to bottom cannot run the first instruction: `quick_validate.py` is not in the repo, not linked, and where found (a plugin cache) fails with `ModuleNotFoundError: No module named 'yaml'`; `actionlint` is assumed present with no install pointer; running the documented `py_compile`/unittest lines without `-B` litters `__pycache__` into the skill folder (the pre-existing `.pyc` files show it already happened).
Cited: D3 (CONFIRMED), P6 (CONFIRMED), C11 (CONFIRMED; the validator half of C11). Severity ranked at the highest cited: D3 Medium; P6, C11 Low.
File evidence: `github-runner/README.md:47-52`; `github-runner/tests/scenarios.md:47, 58`.
Acceptance check: a fresh clone's "Checks" section currently has an instruction that cannot be executed from docs + terminal; passes when it links the validator's source and states its PyYAML requirement (or replaces it with an in-repo, dependency-free check), adds an `actionlint` install pointer, and uses `python3 -B` or `PYTHONDONTWRITEBYTECODE=1`.
Suggested fix: as above; point `scenarios.md` at the same source of truth. Grouping: with F22 (same README pass).

### F22 -- Install and invocation conventions diverge from the repository (Low)

Behavioral description: the skill README documents `npx skills add diegomarino/my-skills --skill github-runner` "after this skill is published" and `$github-runner`, while the root README row that the diff adds and both sibling skills use `npx skills add diegomarino/my-skills@<skill>`, a `-g` variant and `/skill-name`; a reader coming from the root table gets two contracts for one action. Both CLI forms exist in the cached skills CLI 1.7.1; neither is wrong.
Cited: X5 (CONFIRMED), D6 (CONFIRMED), C11 (CONFIRMED; the install-syntax half of C11).
File evidence: `github-runner/README.md:7-18, 24`; root `README.md:10-11, 20`.
Acceptance check: `grep -n 'skills add' README.md github-runner/README.md` currently shows two syntaxes; passes when the skill README uses the `@github-runner` form plus `-g`, states once that `$github-runner` is the Codex spelling and `/github-runner` the Claude Code spelling, and the "after published" caveat is either dropped after merge or mirrored in the root row.
Suggested fix: as above. Grouping: with F21.

### F23 -- `actions/checkout@v6` is a mutable tag in a hardened, PAT-bearing template (Low)

Behavioral description: both jobs resolve `v6` at run time (today `d23441a48e516b6c34aea4fa41551a30e30af803` = v6.1.0) while the template SHA-pins its own selector and cites GitHub's hardening guide, which recommends full-SHA pinning.
Cited: S3 (CONFIRMED), C12 (CONFIRMED). Merge rationale: identical observation from the security and codebase audits.
File evidence: `github-runner/assets/ci.yml:25, 49`; `github-runner/references/ci.md:41`.
Acceptance check: `grep -n 'actions/checkout@' github-runner/assets/ci.yml` currently shows `@v6`; passes with a full commit SHA plus `# v6.1.0` comment, or an explicit documented trade-off in `ci.md`.
Suggested fix: pin to SHA and rely on Dependabot/Renovate for bumps. Grouping: with F4/F16 (hardening pass).

### F24 -- `.preparation.json` has no format stamp or version check (Low)

Behavioral description: a later helper release that adds or renames receipt fields leaves older receipts reporting `null`s with no indication of age, and an older helper silently drops newer fields.
Cited: P4 (CONFIRMED).
File evidence: `github-runner/scripts/prepare_runner.py:96-99, 129`.
Acceptance check: the receipt printed by `prepare` currently has no `format` key; passes when it carries `"format": 1` and `inspect` reports it and refuses a newer-than-supported value with a named message.
Suggested fix: as above. Grouping: with F9/F11 (receipt semantics and documented contract).

### F25 -- Inconsistent naming of the runtime account and of "label" (Low)

Behavioral description: the runtime account is `--expected-user` in one helper, `--account` in another, `UserName` in the plist and `$RUNNER_ACCOUNT` in docs; "label" means the routing label in `SKILL.md`, the launchd label in `macos_service.py --label` and platform labels in `RUNNER_LABELS`, so an operator passes the routing label to the renderer and gets a LaunchDaemon named after it.
Cited: U12 (CONFIRMED).
File evidence: `github-runner/scripts/prepare_runner.py:145`; `github-runner/scripts/macos_service.py:20, 23, 30-31`; `github-runner/SKILL.md:12`.
Acceptance check: `--help` of both helpers currently shows the divergent names; passes when both accept `--runtime-account` (old names as aliases) and the renderer's flag is `--launchd-label` with metavar `REVERSE_DNS_LABEL`.
Suggested fix: as above. Grouping: with F11 (contract pass).

### F26 -- `remote_command.py` rejections do not point at the right flag (Low)

Behavioral description: `--host admin@build-host` is rejected without mentioning `--admin-account`; `--host build-host:2222` is rejected as "Use a valid IP address" because the colon routes to the IPv6 branch although the user typed no IP.
Cited: U13 (CONFIRMED).
File evidence: `github-runner/scripts/remote_command.py:16-24`.
Acceptance check: the two invocations currently print the generic messages; passes when `@` and `:port` are detected explicitly ("user@ prefixes go in --admin-account"; "ports are not supported; use an SSH config alias").
Suggested fix: as above. Grouping: with F10 (message pass).

### F27 -- Facts restated in up to eight places (Low)

Behavioral description: the dedicated-account rule (8 copies), "Python 3.9+" (4), the test command (3 cwd conventions) and the hosted-label verification date (2) all agree today and will diverge on the first edit to one copy.
Cited: D7 (CONFIRMED).
File evidence: `github-runner/references/platforms.md:7` (canonical) and the locations listed in D7.
Acceptance check: `grep -rn '3.9+' README.md github-runner | wc -l` currently exceeds 1 and the account rule appears 8 times; passes when each fact has one canonical home and the others link to it.
Suggested fix: canonical homes as proposed in D7. Grouping: with F28/F29 (docs structure pass), after the content fixes.

### F28 -- `tests/scenarios.md` mixes a reusable spec with a dated evaluation log (Low)

Behavioral description: lines 40-58 carry tool versions, process history and absolute counts ("24 new helper tests and all 99 existing repository tests passed (123 total)") that are correct today and wrong after the next test added anywhere in the repo; the history ships to every installer via the skills CLI.
Cited: D8 (CONFIRMED).
File evidence: `github-runner/tests/scenarios.md:40-58`.
Acceptance check: `scenarios.md` currently contains absolute repository-wide counts; passes when the log lives in a dated `tests/evaluation-log.md` (or a clearly dated appendix) and counts are replaced by "all tests passed at `<sha>`".
Suggested fix: as above. Grouping: with F27.

### F29 -- `platforms.md` bundles five concerns the agent is told to read selectively (Low)

Behavioral description: `SKILL.md:26` says to use the target branch in `platforms.md`, but the 12.8 KB file loads common rules, Linux, macOS, Windows and availability into context for every session.
Cited: D9 (CONFIRMED).
File evidence: `github-runner/references/platforms.md:1-84`; `github-runner/SKILL.md:26`.
Acceptance check: optional split into `platforms-linux.md`, `platforms-macos.md`, `platforms-windows.md` with stub headings left behind so `SKILL.md:18,26`, `discovery.md:25`, `setup.md:30,32` and `verification.md:21` keep resolving (no inbound anchors exist today).
Suggested fix: as above, optional. Grouping: with F27/F28; do after F16 so the Linux branch is split in its corrected form.

### F30 -- No diagrams for the four decision-heavy processes (Low)

Behavioral description: "which condition sent my job to hosted?" and "LaunchAgent or LaunchDaemon?" are decision trees answered only by full prose reads; no diagram exists in scope.
Cited: D10 (CONFIRMED). Skeletons for four Mermaid diagrams are in the docs report section 6 (rendering BLOCKED locally: no Chrome for `mmdc`).
File evidence: `github-runner/SKILL.md:8-36`; `github-runner/references/ci.md:23-34`; `github-runner/references/credentials.md:5-9`; `github-runner/references/platforms.md:38-61`.
Acceptance check: `grep -c 'mermaid' github-runner/references/ci.md` is 0 today; passes when the selector flowchart renders (`mmdc -i <file>.mmd -o <file>.svg` with a local Chromium) and reflects F3's reason vocabulary.
Suggested fix: the selector flowchart first (supports F3's troubleshooting table), then the four-gate state diagram. Grouping: last; after F3 so the diagram shows the final routing logic.

## 3. Conflicts

Judgment conflicts (real signal; both views kept, with a recommendation):

- J1 (F3): the docs audit (D2) proposes a symptom-first troubleshooting table in `verification.md` and a flowchart; the codebase, process, change and ux audits (C4, P2, X3, U1) propose a closed-vocabulary `reason=` output from the selector. Recommendation: code first (the reason enum is the signal the table needs), then the table and diagram keyed on the enum. The ux audit additionally proposes failing hard on static configuration errors; the codebase audit's open question 2 flags the current one-hard-error/everything-silent split as accidental. Recommendation: fail hard on errors that can never succeed (`RUNNER_LABELS` not a JSON array, routing label equal to a default label, missing variables), keep fail-closed fallback for runtime conditions (busy, offline, API error); maintainer decision recorded in Open questions, Q2.
- J2 (F9): the process audit offers two directions (document `rm` + rerun, or `prepare --resume-incomplete`), the ux audit asks `inspect` to print a `next_action`, and the codebase audit's design tension proposes atomic `instance.partial-<pid>` + `rename()`. Recommendation: document the recovery and add `next_action` now (no new state semantics), evaluate the atomic-rename design before adding a resume flag; Open questions, Q4.
- J3 (F20): the codebase audit (C9) says widen the account regex to accept uppercase and dots; the ux audit (U7) says the message must at least state the actual rule. Recommendation: both; if the maintainer intends lowercase-only (Open questions, Q5), the message change alone resolves the finding.
- J4 (F18): the docs audit restructures `ci.md` (D4); the ux audit adds a guard step to `ci.yml` (U10). Recommendation: both; they address different moments (reading vs. running).
- J5 (F1): the change and codebase audits both ask whether refusing official archives is a deliberate "always extract natively" stance (Open questions, Q1). If so, the fix is to withdraw the receipt/inspect/resume promises in `setup.md`, `discovery.md` and `verification.md` rather than to accept symlinks. Recommendation: accept in-tree relative symlinks; the helper's only real input is the official archive.

Fact conflicts (resolved by evidence labels):

- FC1: the docs audit (open question 1, BLOCKED: no network) raised that `X-GitHub-Api-Version: 2026-03-10` might be rejected by GitHub and make every selection fall back silently. The change audit (CONFIRMED: identical responses for `1999-01-01`, `2022-11-28` and `2026-03-10`) and the codebase audit (CONFIRMED: `GET /versions` lists `2026-03-10`) both recorded it NOT REPRODUCED. Resolution: trust CONFIRMED; the header is valid and the question is closed. Not a backlog entry.
- FC2: the docs audit (BLOCKED) asked whether `actions/checkout@v6` exists; the change, codebase and security audits confirmed the tag (`d23441a...` = v6.1.0; latest release v7.0.1 per the change audit). Resolution: closed; the mutable-tag concern is F23.
- FC3: the security report's supply-chain inventory states that `npx skills add ... --skill github-runner` is "the repository-wide install convention already in the root README" (unlabeled inventory note, not a finding). The change, docs and codebase audits (X5, D6, C11, all CONFIRMED by reading the root README and both sibling READMEs) show the root convention is `@<skill>`. Resolution: trust the three CONFIRMED findings; the security inventory premise is suspect, with no effect on S1-S3. Reflected in F22.
- FC4: X2 (CONFIRMED) and C2 (PLAUSIBLE) assert the same reality (the official runner writes `.runner` with a BOM; `inspect` rejects it). This is a confidence-threshold difference, not a factual disagreement; both labels are preserved in F2.
- No CONFIRMED-vs-CONFIRMED contradictions were found; no nondeterminism entry is needed.

## 4. Cross-audit patterns

Flagged above their individual severities:

1. **Silent hosted fallback** (F3, F5, F6, F12): hit independently by five of six audits (change, codebase, docs, process, ux); the security audit's S1 also lands in the same code path (an attacker-routed run and a misconfigured run look identical). Fixing F3's reason output is the highest-leverage single change in the backlog: it is the prerequisite for F6's and F12's refusals to be diagnosable and for D2/D10's troubleshooting docs.
2. **Guards calibrated on synthetic fixtures, never on the product's real inputs** (F1, F2, F8, F14, F20): the change and codebase audits name this cause explicitly (codebase design tension 5); the ux audit hit its user-facing side. The symlink refusal, the digest regex, the BOM, the account regex and the non-pinning tests share one remedy: a golden-input test tier (checked-in official archive member manifest, real `.runner` byte prefix, real `digest` string).
3. **Refusal messages that state the rule, not the observed condition** (F5, F10, F19, F20, F26, and the `GITHUB_OUTPUT` message in F3/F11): found by the ux, process and codebase audits; one message-quality pass over all four helpers resolves them together.
4. **Contracts that live only in prose** (F11, F12, F16, and the uniqueness/collision gates): the codebase audit's design tension 1 ("guardrails live in prose, enforcement lives in the agent"), the docs audit's D5 and the security audit's weakened trust boundaries 2 and 3 describe the same shape; the suggested `preflight` subcommand (codebase design tension 1) would convert several manual gates into checkable ones.
5. **macOS path-alias trap** (F10): hit by the codebase, process, ux and docs audits, each from a different helper or document; the one existing warning (`platforms.md:54`) is the model for the fix.
6. **CI acceptance procedure fragility** (F7, F18): the codebase, process, docs and ux audits each found a way the documented acceptance run fails for reasons unrelated to the host; a restructured `ci.md` "Prepare the selector" with a bootstrap gate and a sequencing note addresses both.

## 5. What held up

- change: idempotent exclusive reservation and interrupted-state retention in `prepare`; refusal of existing artifacts in the renderer; trivially reversible change footprint; selector output contract correct for string and array labels; hosted-label allowlist current; PR events never receive the PAT; both shell boundaries in `remote_command.py`; plist keys match the official `darwin.svc.sh.template`; root README diff accurate; API version header valid (NOT REPRODUCED).
- codebase: selector trust gating, redirect refusal, env-only token and bounded paging exactly as documented; `prepare` path-safety (traversal, duplicates, reserved names, symlinked destination, wrong user, bad digest) with the destination left absent; `inspect` field filtering pinned by mutation; renderer artifacts 0600 and `plutil`-clean; Python 3.9 claim verified on 3.9.6; all 19 external URLs resolve.
- docs: every reference opens with "Read this when"; resource table routes by task; variable table matches `ci.yml` exactly; numeric limits in prose match code; all 44 relative links and the anchor resolve; documented check commands pass; `scenarios.md` counts accurate today; validation boundaries stated plainly.
- process: all three documented test recipes pass with stdin closed; two concurrent `prepare` invocations yield exactly one winner with no corruption; half-written staging never overwritten; `HOSTED_RUNNER` fails loudly before any API call; no secret-looking strings; `inputs.force_hosted` empty-on-push and `fromJSON` bare-string label both NOT REPRODUCED as defects.
- security: PR isolation and trusted-revision selector with `persist-credentials: false`; no expression interpolation in `run:` blocks; `permissions: contents: read`; `force_hosted` fails safe; archive extraction non-root, identity-verified, 0700, size-capped; macOS daemon plan system-domain only with the explicit "never svc.sh as root from runtime-writable storage"; credential guidance keeps tokens out of chat and logs; `.credentials` never read; no secrets in scope; stdlib-only helpers (no advisory surface).
- ux: `remote_command.py` success line correctly double-quoted; `prepare` refusals leave no debris and the rerun refusal names `inspect`; renderer ending states what happened and what did not; `Record execution machine` is the single most useful operator line; placeholder `checks` step says what to replace; `SKILL.md:36` report contract (verdict, gates, smallest next action) is right.

## 6. Open questions (maintainer-only, merged)

- Q1 (F1, F2): Is "official archives work with `prepare`" the intended contract (then F1 is a bug and the in-tree-symlink allowance is the fix), or is native extraction expected (then withdraw the receipt/inspect/resume promises in `setup.md`, `discovery.md`, `verification.md`)? Also confirm F1 on the Linux x64 asset with the same command (expected identical).
- Q2 (F3, F5, F6): Should configuration-class selector failures fail the job like `HOSTED_RUNNER` does, or stay silent fallbacks? Is a closed-vocabulary reason code acceptable on trusted events (nothing credential-adjacent in it)? Is the omission of `ubuntu-22.04-arm` and other table labels from `HOSTED_LABELS` deliberate policy? If so, publish the list and policy in `ci.md`.
- Q3 (F13): Is Windows an intended target for `prepare` (the README's "verified Windows Python executable" suggests yes), or only for the documented native procedure?
- Q4 (F9, F24): Should the skill own recovery from `incomplete` (resume flag / atomic rename) or only document `rm` + rerun? Relatedly, what is the runner-upgrade journey (the runner self-updates; re-running `prepare` ends at "Instance already exists")?
- Q5 (F20, F25): Are mixed-case macOS short names out of scope for `--account`? Is `--runtime-account` as a shared flag name acceptable?
- Q6 (F4, F16): Does the target repository's ruleset cover case-variant branch names, and does GitHub reject creating `MAIN` beside `main` there? (If both, F4 drops to Low.) Is an administrator-owned copy of `svc.sh` / a directly rendered systemd unit acceptable for Linux?
- Q7 (F12): Can the selector PAT list organization-group runners accessible to the repository? If not, F12's enforcement is partial and the manual gate stays documented as such.
- Q8 (F15): Should `--path` in `macos_service.py` remain at all, given `.path` precedence?
- Q9 (F21, F22, F28): Which install form is the house convention (`owner/repo@skill` or `--skill`)? Is PyYAML an accepted contributor dependency, or should the validator reference go? Is the evaluation history in `scenarios.md` meant to ship to installers?
- Q10 (F7, F18): Is all-events `cancel-in-progress: true` intentional for `workflow_dispatch` acceptance runs? Should the `select` job carry a bootstrap guard step?
- Q11 (security, no backlog entry): does launchd open `StandardOutPath`/`StandardErrorPath` as root before dropping to `UserName`? If so, a runtime-account symlink under `~/Library/Logs/<label>/` is a root write primitive on `KeepAlive` restart; next check on a disposable macOS VM: replace `stdout.log` with a symlink to a root-only path and `launchctl kickstart -k` the daemon.
- Q12 (security, pre-existing, out of scope): the repository root ships no `LICENSE` file while the new README row advertises public installation. Flagged for awareness only.
- Q13 (process backlog item 4, no finding ID): no step in the journey flips `TRUSTED_RUNNER_REF` back to `refs/heads/main` after the candidate merges; it would manifest as F3's silent hosted routing. Add to the `ci.md` acceptance/readback list?
- Python 3.9 floor: the change audit had no 3.9 interpreter (judged by reading); the codebase audit ran the suite on 3.9.6 and the docs audit parsed all files with `feature_version=(3,9)`. Closed by CONFIRMED evidence; no action.

Nothing in this backlog has been applied. Fix execution is the separate, human-gated `fix.md` step.

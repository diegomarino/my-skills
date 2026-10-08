# Change audit — `github-runner` skill (working tree) — 2026-10-08

- Audit: change (diff-scoped)
- Auditor model: Claude Fable 5.1 (`claude-fable-5-1`)
- Target: working tree, bounded by human override to `github-runner/**` (19 untracked files) + `git diff HEAD -- README.md`
- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263` (short `8d6598d`), branch `feat/github-runner`, tree DIRTY (explicit human opt-in)
- README diff sha256 (diff_checksum): `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502`
- Untracked-file list sha256: `c4d5171d5234790b844bffe002127e6911d2c6047b62b4fdc781ab32ca8d45a5`
- Per-file SHA-256 manifest: identical to the orchestrator's baseline at start and again immediately before writing this report. Run NOT compromised.
- Prior reports: none (docs/audits/ did not exist before this run; sibling audits of this run were not read, per override).
- Assumptions recorded: no human available; proceeded under the worker-common overrides. Read-only GET requests to api.github.com, docs.github.com, github.com release assets and raw.githubusercontent.com were made to verify claims against real inputs (no mutation, no credentials). The official runner archive was downloaded into a mktemp directory outside the project and inspected/extracted there only.

## 1. Verdict: needs-attention

I would not ship this as-is. The documents and the workflow template are careful and mostly hold up, but two of the four bundled helpers fail on the real inputs they exist for, and the 24 green tests cannot see it because every fixture is synthetic. `prepare_runner.py` refuses the current official `actions-runner-osx-arm64-2.338.0.tar.gz` (and by layout, every Linux/macOS release) because the archive carries six relative symlinks under `externals/node*/bin/`; the skill's "Prepare" step therefore has no working helper path and no `.preparation.json` receipt for its advertised readback. `prepare_runner.py inspect`, the designated safe readback for registration identity in three references, refuses any `.runner` file carrying the UTF-8 BOM that the runner's own `IOUtil.SaveObject` (`File.WriteAllText(..., Encoding.UTF8)`) emits. Neither is a design flaw in intent — both fail loudly — but both make the skill promise a verified, receipted path that an operator cannot actually take. Two Medium items (silent hosted fallback with no reason surfaced; the plist `--path` story contradicted by the runner's `.path` mechanism) and one Low collateral item (install instructions inconsistent with the repo convention) complete the set. Fix X1 and X2 (with real-layout fixtures), then this is shippable.

## 2. Summary table

| ID | Severity | Area | Issue | Location | Evidence |
| --- | --- | --- | --- | --- | --- |
| X1 | High | Contract break / half-finished | `prepare_runner.py prepare` refuses every official Linux/macOS runner archive (node symlinks in `externals/`), so the documented receipted preparation path cannot be taken | `github-runner/scripts/prepare_runner.py:80-82` | CONFIRMED |
| X2 | High | Contract break | `prepare_runner.py inspect` refuses real `.runner` files because the runner writes them with a UTF-8 BOM and the helper decodes without `utf-8-sig` | `github-runner/scripts/prepare_runner.py:126` | CONFIRMED |
| X3 | Medium | Observability | Selector collapses every misconfiguration and API failure into a silent hosted fallback with no non-secret reason, indistinguishable from "runner busy" | `github-runner/scripts/select_runner.py:57-64,90-93` | CONFIRMED |
| X4 | Medium | Collateral drift (misleading) | `--path`/plist `PATH` is documented as the service PATH, but `config.sh` writes `.path` and `runsvc.sh` exports it, overriding the plist; `ci.md` states the opposite of the runner's behavior | `github-runner/references/platforms.md:54`, `github-runner/scripts/macos_service.py:24,45`, `github-runner/references/ci.md:3` | CONFIRMED |
| X5 | Low | Collateral drift | Skill README install commands use a different form (`--skill`, "after this skill is published") from the root README and sibling skills (`diegomarino/my-skills@<skill>`, `-g` variant) | `github-runner/README.md:7-18` vs `README.md:10-11` | CONFIRMED |

## 3. Change map

What the diff touches:

- New skill directory `github-runner/` (19 files, all untracked): `SKILL.md` (4-step procedure), `README.md`, `agents/openai.yaml` (Codex UI metadata), six references (`discovery`, `credentials`, `setup`, `platforms`, `ci`, `verification`), four standard-library Python helpers (`prepare_runner.py`, `macos_service.py`, `remote_command.py`, `select_runner.py`), a workflow template `assets/ci.yml`, four unittest modules (24 tests) and `tests/scenarios.md` (behavioral evaluation record).
- Root `README.md`: adds the `github-runner` row to the skills table (line 20), rewords the Checks section ("Every skill ships its tests" -> "Skills with executable helpers ship automated tests") and adds a pointer to the skill's scenarios (lines 34-39).

Claims vs. behavior: there is no commit message, PR description or linked spec (the work is untracked). The claim is the skill's own description: carry a host "from an empty starting point through account preparation, registration, persistent services and verified project CI". The references deliver that as guidance; the helper layer partially does not (X1, X2).

Contracts the change participates in:

- Agent Skills portable format: directory with `SKILL.md` frontmatter `name` matching the folder and a `description`. Both present; `name: github-runner` matches.
- Repo convention (root README, sibling skills): one self-contained folder with `README.md`, `tests/` runnable via `cd <skill> && python3 -m unittest discover -s tests -v`. Verified that command works for this skill (24 tests pass from the skill dir and from the repo root).
- External inputs the helpers consume: official `actions/runner` release archives (`prepare`), the runner's `.runner` state file (`inspect`), the GitHub REST `List self-hosted runners for a repository` endpoint (`select_runner.py`), GitHub Actions expression/`runs-on` semantics (`ci.yml`), launchd plist keys and `runsvc.sh` (`macos_service.py`), OpenSSH argv (`remote_command.py`).
- Persisted formats introduced: `.preparation.json` receipt (`status`, `version`, `sha256`, `archive`, `account`) written by `prepare` and read by `inspect`; generated `<label>.plist` + `service-plan.txt`.

## 4. Coverage accounting

Read fully (every in-scope file, 1,282 lines): `github-runner/README.md`, `SKILL.md`, `agents/openai.yaml`, `assets/ci.yml`, `references/{ci,credentials,discovery,platforms,setup,verification}.md`, `scripts/{macos_service,prepare_runner,remote_command,select_runner}.py`, `tests/{scenarios.md,test_macos_service.py,test_prepare_runner.py,test_remote_command.py,test_select_runner.py}`; `git diff HEAD -- README.md` and `git show HEAD:README.md`.

Minimum context read outside scope: install lines and Checks sections of `speckit-package-tasks/README.md` and `speckit-orchestrate/README.md`, `speckit-package-tasks/SKILL.md` frontmatter (repo conventions); `.gitignore`.

Callers traced: `ci.yml` -> `select_runner.py` (env contract, `GITHUB_OUTPUT`, `fromJSON` consumer); references -> each helper's CLI; `inspect` -> `.runner`/`.preparation.json`; rendered plan -> `runsvc.sh`.

Tests and checks run (all in `/tmp/audit-gr.*` copies, `PYTHONDONTWRITEBYTECODE=1`, nothing written into the project; `.pyc` files verified byte-identical to baseline afterwards):

- `python3 -m unittest discover -s github-runner/tests -v` (Python 3.14.7): 24/24 pass. Same from the skill directory with `-s tests`: 24/24.
- `python3 -m py_compile` on all four scripts: OK.
- `actionlint github-runner/assets/ci.yml` (actionlint installed locally): OK.
- Relative-link check across all in-scope Markdown: no broken links.
- Secret-pattern scan of in-scope contents only: nothing found.
- Real-input checks (read-only network): `prepare` against the official `actions-runner-osx-arm64-2.338.0.tar.gz` with its published digest (X1); `tar -tzvf` entry-type census; BOM `.runner` fixture against `inspect` (X2); `actions/runner` source (`src/Runner.Sdk/Util/IOUtil.cs`, `src/Runner.Common/ConfigurationStore.cs`, `src/Misc/layoutbin/runsvc.sh`, `src/Misc/layoutroot/env.sh`, `darwin.svc.sh.template`); `api.github.com/meta` and the runners endpoint with `X-GitHub-Api-Version` values `1999-01-01`, `2022-11-28`, `2026-03-10`; `actions/checkout` latest release; the GitHub hosted-runner label docs page.

Discarded after investigation (NOT REPRODUCED): the selector's `X-GitHub-Api-Version: 2026-03-10` header. GitHub returned identical results for an obviously invalid version (`1999-01-01`), so an unrecognized value does not break lookups. `actions/checkout@v6` exists (latest is v7.0.1). All 14 `HOSTED_LABELS` entries appear on the current docs table; `macos-13`/`windows-2019` correctly absent.

Blind spots / BLOCKED: no Python 3.9 interpreter available (3.11/3.13/3.14 present); 3.9 compatibility judged by reading only. Linux `actions-runner-linux-x64-2.338.0.tar.gz` not downloaded (227 MB); the symlink finding is confirmed on the macOS archive and inferred for Linux from the shared `externals/node*` layout. Real registration, launchd bootstrap, systemd, Windows identity API, SSH, PAT/secret provisioning, reboot: BLOCKED by the override; the exact next checks are stated per finding. `npx skills add . --list` not run (would download the CLI).

## 5. Findings by hunt category (severity order)

### Contract breaks / half-finished changes

**X1 — High — CONFIRMED — `github-runner/scripts/prepare_runner.py:80-82`**
`prepare` refuses every official Linux/macOS runner archive.

Scenario: operator follows `references/setup.md:18-24` exactly, as the runtime account, with the official `actions-runner-osx-arm64-2.338.0.tar.gz` and its published digest `df4cebda…9df2`. Reproduced in a mktemp directory:

```
$ python3 prepare_runner.py prepare --archive .../actions-runner-osx-arm64-2.338.0.tar.gz \
    --sha256 df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2 \
    --version 2.338.0 --expected-user diego --directory /private/tmp/.../inst/runner
Preparation/inspection refused: "Archive links and special entries require manual review"   (exit 1)
```

Cause: the archive contains six relative symlinks (`./externals/node24/bin/{npm,npx,corepack}` and the same under `node20`, all `-> ../lib/node_modules/...`), and line 81 rejects any tar member that is neither a directory nor a regular file. `tar -tzvf` census: 9,390 files, 2,152 directories, 6 symlinks.

Why this is a defect and not a safety feature: the helper's only real input is the official archive, and the archive has shipped node with those symlinks for years. The skill then has no helper path through "Prepare": `setup.md:26` tells the agent to "prepare a reviewed native extraction instead of weakening guards", but a native extraction writes no `.preparation.json`, so `inspect` (the receipt readback promised in `discovery.md:27` and `verification.md:12,21`) reports `preparation: null` for every real instance, and the interrupted-state/resume guarantees in `setup.md:26` never apply. The tests (`tests/test_prepare_runner.py`) only use two-file synthetic tar/zip fixtures; `tests/scenarios.md:58` claims "Archive preparation interruption/preservation ... simulated" on that basis.

Impact: the central preparation workflow is unusable as documented on the only real input; agents under time pressure (scenario C) will fall to ad-hoc `tar xzf` with none of the guards.

Recommended direction: accept symlink members whose target is relative, contains no `..` escaping the instance, and resolves inside the instance directory (create with `os.symlink` after all regular files are written, or materialize them), keep refusing absolute/escaping links and hardlinks; add a fixture that mirrors the official layout (`externals/nodeNN/bin/npm -> ../lib/node_modules/npm/bin/npm-cli.js`) to `test_prepare_runner.py`; update `setup.md:26` and `README.md:38` to describe what is and is not accepted.

Acceptance check: in a mktemp directory outside the project, the exact command above (with the real archive and published digest) exits 0, prints a receipt with `"status": "prepared"`, and `ls -l <dir>/externals/node24/bin/npm` shows the in-tree symlink. Fails today with exit 1.

**X2 — High — CONFIRMED — `github-runner/scripts/prepare_runner.py:126`**
`inspect` refuses real `.runner` files (UTF-8 BOM).

Scenario: scenario B in `tests/scenarios.md:15` — the agent must correlate the local `.runner` `agentId`/`gitHubUrl` with the GitHub inventory using `prepare_runner.py inspect --directory ...` (`discovery.md:27`, `verification.md:21`, `README.md:38`). The runner persists `.runner` through `ConfigurationStore.SaveSettings` -> `IOUtil.SaveObject` -> `File.WriteAllText(path, json, Encoding.UTF8)` (`src/Runner.Common/ConfigurationStore.cs:358`, `src/Runner.Sdk/Util/IOUtil.cs:40-43`, fetched from `actions/runner@main`). `Encoding.UTF8` is the BOM-emitting UTF8Encoding, so the file begins with `EF BB BF`. Line 126 does `json.loads(path.read_text())` — default `utf-8`, not `utf-8-sig` — and `json.loads` rejects a leading BOM. Reproduced with a byte-exact fixture:

```
$ printf '\xef\xbb\xbf{"agentId":42,"agentName":"box","gitHubUrl":"https://github.com/acme/widget"}' > bomcase/.runner
$ python3 prepare_runner.py inspect --directory /private/tmp/.../bomcase
Preparation/inspection refused: "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)"   (exit 1)
```

The identical content without the BOM returns the expected report (exit 0). The existing test (`test_inspects_only_safe_registration_fields`) writes its fixture with `json.dumps` and therefore never sees the real format. Not exercised against a file produced by a live registration (BLOCKED: would require registering a runner); the writer side is verified at source level.

Impact: the skill's only sanctioned, credential-safe readback of registration identity fails on every real instance; the fallback is an agent reading `.runner` by hand next to `.credentials`, which the references are trying to prevent.

Recommended direction: read state files with `encoding='utf-8-sig'` (and tolerate `gitHubUrl` being absent/non-string without a traceback — today a non-string value reaches `urlsplit` and escapes the `except` on line 154); add a BOM-prefixed fixture to `test_prepare_runner.py`.

Acceptance check: the BOM fixture command above exits 0 and prints `"agentId": 42`. Fails today with exit 1.

### Observability

**X3 — Medium — CONFIRMED — `github-runner/scripts/select_runner.py:57-64,90-93` (consumer `assets/ci.yml:31-43`)**
Every reason for hosted fallback is silent.

Scenario: operator sets `TRUSTED_RUNNER_REF` to `main` instead of `refs/heads/main` (ci.md:18 does say `refs/heads/main`, but the variable is free text). `TRUSTED_EVENT` evaluates to `false` on every push forever; `select()` returns the fallback at line 64 without any API call; the job output is just `runner="ubuntu-24.04"`. The same single code path covers 13 distinct conditions (forced, untrusted, missing token/name/label, bad label, bad repo, non-github.com API URL, malformed `RUNNER_LABELS`, HTTP/JSON errors at lines 90-93 — including a 401 from an expired `RUNNER_READ_TOKEN` — and "no matching idle runner"). The only operator signal is the `Record execution machine` step printing a hosted runner name; nothing says why. `ci.md:31` documents the fallback list but gives the operator no way to tell an intentional fallback from a broken configuration or an expired PAT, which matters because the PAT has a finite expiry by design (`credentials.md:9`).

Impact: a persistent self-hosted host silently stops being used; CI costs and behavior change with no failure surfaced; recovery requires reading the selector source.

Recommended direction: return `(label, reason)` from `select()` with a fixed vocabulary (`forced`, `untrusted_event`, `missing_config`, `invalid_label`, `api_error`, `no_match`, `selected`) and emit it as a second `GITHUB_OUTPUT` line plus a `::notice::` on stdout — never the exception text (the comment on line 91 is right that exception strings may carry credentials). Assert the reason in `test_skips_api` and `test_api_error_and_custom_fallback`.

### Collateral drift

**X4 — Medium — CONFIRMED — `github-runner/references/platforms.md:54`, `github-runner/scripts/macos_service.py:24,45` (plan lines 41-46), `github-runner/references/ci.md:3`**
The service PATH story contradicts the runner.

Evidence from `actions/runner@main` and the downloaded 2.338.0 archive: `config.sh:74` does `source ./env.sh`; `env.sh:37` does `echo $PATH>.path`; `bin/runsvc.sh` (the entry point the rendered plist executes, with `WorkingDirectory` = runner dir) does `if [ -f ".path" ]; then export PATH=$(cat .path)`. So after any normal registration, `.path` exists and the plist's `EnvironmentVariables.PATH` is replaced by whatever PATH the runtime account had in the shell that ran `config.sh`.

Scenario: operator follows `platforms.md:54` ("Supply `--path` only for a verified controlled PATH; the default covers system tools, not Homebrew or project dependencies") and registers from an interactive shell with `/opt/homebrew/bin` or a user-writable directory first in PATH. The daemon runs with that PATH, not the rendered one; conversely, an operator who wants Homebrew tools will add `--path` and see no effect. `ci.md:3` ("services do not inherit interactive PATH") is the opposite of what `runsvc.sh` does on macOS/Linux. The rendered plan never mentions `.path`/`.env`.

Impact: a misleading privilege/toolchain boundary on the persistent host; debugging "tool not found"/"wrong tool" in CI starts from a false premise.

Recommended direction: document `.path`/`.env` precedence in `platforms.md` and `ci.md`; have the rendered plan tell the operator to inspect/set `.path` as the runtime account (that is the effective service PATH), and either drop `--path` or state that it applies only when `.path` is absent.

**X5 — Low — CONFIRMED — `github-runner/README.md:7-18` vs `README.md:10-11` (and sibling READMEs)**
Install instructions diverge from the repository convention.

The root README (unchanged lines 10-11) and both sibling skills document `npx skills add diegomarino/my-skills@<skill>` with a `-g` variant; the new skill README documents `npx skills add diegomarino/my-skills --skill github-runner`, qualified with "after this skill is published", and a local-worktree form. Whether both CLI forms work was not verified (would download the CLI). A reader comparing the two READMEs sees two different contracts for the same action.

Recommended direction: use the `@github-runner` form and the `-g` variant in the skill README to match the root table row that the diff adds; keep the local `--list` discovery line if desired.

### Idempotency, rollback, version skew, spec fidelity

No findings. See section 7.

## 6. Collateral checklist (update before merge)

- `github-runner/references/setup.md:26` and `github-runner/README.md:38`: describe accepted archive entries after X1 (in-tree relative symlinks).
- `github-runner/tests/test_prepare_runner.py`: add an official-layout fixture with `externals/nodeNN/bin/npm -> ../lib/node_modules/...` symlinks (X1) and a BOM-prefixed `.runner` fixture (X2).
- `github-runner/tests/scenarios.md:58`: the "archive preparation ... simulated" statement must be re-qualified once a real-layout fixture exists.
- `github-runner/references/platforms.md:54,60`, `github-runner/references/ci.md:3`, and the plan text in `macos_service.py:49-91`: document `.path`/`.env` precedence (X4).
- `github-runner/references/ci.md:31` and `test_select_runner.py`: document and assert the fallback reason output (X3).
- `github-runner/README.md:7-18`: align install commands with the root README (X5).

## 7. What held up

- Idempotency/interruption: `prepare` reserves the directory exclusively (`mkdir(mode=0o700)`), writes an `incomplete` receipt first, retains state on failure and refuses re-runs; `macos_service.py` uses `open('x')` and refuses existing artifacts, including dangling symlinks; both behaviors are tested (`test_interrupted_extraction_is_retained_and_retry_refused`, `test_refuses_existing_artifacts_and_symlink_output`).
- Rollback: nothing is mutated outside the new folder and two README hunks; reverting is deleting the folder and the hunks. No persisted format is shared with other skills.
- Version skew: the `.preparation.json` receipt is only read by the same helper; the selector output contract (`runner=<json>`, consumed by `fromJSON` in `runs-on`) is correct for both a string and a label array.
- Selector security posture: `HOSTED_RUNNER` is validated against an allowlist before any request (all 14 labels present on the current GitHub table; retired `macos-13`/`windows-2019` correctly absent; `ubuntu-22.04-arm` conservatively omitted); PR events never receive the PAT (`ci.yml:42` gates `secrets.RUNNER_READ_TOKEN` on `event_name != 'pull_request'` and the trusted ref); redirects are refused; token only from environment; 1 MiB/5 s/1,000-record bounds; exact-name plus local re-verification; `busy is not False` strictness. `actionlint` passes. `actions/checkout@v6` exists.
- `select` job env entries `GITHUB_REPOSITORY`/`GITHUB_API_URL` duplicate default variables (GitHub ignores overrides of default names); harmless because the values are identical.
- `remote_command.py`: both shell boundaries preserved (`shlex.join` twice), option injection rejected, IPv6 with zone IDs accepted; verified by tests and by reading.
- `macos_service.py`: generated keys match the official `darwin.svc.sh.template` approach (`runsvc.sh` entry point, `UserName`, `WorkingDirectory`, `RunAtLoad`, `KeepAlive`, logs under `~/Library/Logs/<label>`); the plan's `cp -n ./bin/runsvc.sh ./runsvc.sh` matches what the official installer does (`cp ./bin/runsvc.sh ./runsvc.sh`). `bin/runsvc.sh` is present and the root copy absent in the 2.338.0 archive, as scenario C assumes.
- Root README diff: the new table row and Checks rewording are accurate; `cd github-runner && python3 -m unittest discover -s tests -v` works as the root README promises; relative links resolve.
- No secret-like material in scope; the token-handling guidance in `credentials.md` is consistent with the helper code (tokens never printed, exception text suppressed).
- `X-GitHub-Api-Version: 2026-03-10`: investigated as a possible silent-fallback trigger; GitHub does not reject unknown versions on the queried endpoints (NOT REPRODUCED).

## 8. Open questions (maintainer)

- Is the intended contract for `prepare_runner.py` "official archives work" (then X1 is a bug) or "official archives are expected to need native extraction" (then the receipt/inspect/resume promises in `setup.md`, `discovery.md` and `verification.md` should be withdrawn)?
- Should `--path` in `macos_service.py` remain at all, given `.path` precedence?
- Python 3.9 is the documented floor; no 3.9 interpreter was available to confirm. `shlex.join` (3.8), `ipaddress` scope IDs (3.9) and the `tarfile`/`zipfile` calls used read as 3.9-compatible.
- The Linux x64 archive was not downloaded; confirm X1 there with the same command (expected identical, same `externals/node*` layout).

Audit complete. Report and sidecar written; no fixes applied, no Git state changed. STOP.

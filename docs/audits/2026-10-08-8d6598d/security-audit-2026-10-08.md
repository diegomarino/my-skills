# Security and supply-chain audit — `github-runner` skill

- Date: 2026-10-08
- Auditor: Claude Fable 5.1 (model id `claude-fable-5-1`), dispatched by an orchestrator; no human was available for questions, assumptions are recorded in section 8.
- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263` (short `8d6598d`), branch `feat/github-runner`, tree **DIRTY** by explicit human opt-in (` M README.md`, `?? github-runner/`, `?? docs/`). Root `README.md` diff-vs-HEAD sha256 `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502` re-verified by me and identical to the orchestrator baseline; every one of the 19 in-scope file SHA-256s matched `baseline.txt` before and after my checks.
- Scope: `github-runner/**` (19 untracked files, all read in full) plus the root `README.md` diff. This bounded target is treated as the whole product. No other skill, history, worktree or host was audited. Prior reports: none exist (`docs/audits/` was created by this run); no sibling report in the run directory was read.
- Rules honored: source read-only; tests executed only in a `mktemp -d` copy outside the project with `PYTHONDONTWRITEBYTECODE=1`; no live host, SSH, registration, service, credential, workflow-dispatch or external-mutating action; git state untouched.

## 1. Summary

| ID | Severity | Category | Issue | Evidence |
| --- | --- | --- | --- | --- |
| S1 | High | CI/CD trust boundary | `github.ref == vars.TRUSTED_RUNNER_REF` in `assets/ci.yml` is a case-insensitive GitHub-expression comparison, so a push to a case-variant branch (e.g. `refs/heads/MAIN`) that branch protection does not cover is routed to the persistent self-hosted host as "trusted" | PLAUSIBLE |
| S2 | Medium | Privilege boundary / supply chain | `references/platforms.md` instructs root to execute `./svc.sh` (install/start/status) from the runner directory owned by the CI runtime account; any code that ran as that account can rewrite the script root later runs | CONFIRMED |
| S3 | Low | Supply chain hygiene | `actions/checkout@v6` is a mutable tag (currently resolves to `d23441a…`, same as `v6.1.0`) in both jobs of the CI template, not a commit SHA | CONFIRMED |

Counts: Critical 0, High 1, Medium 1, Low 1. Evidence: CONFIRMED 2, PLAUSIBLE 1, BLOCKED 0 findings (blocked *checks* are listed in section 4). Secrets found: none.

## 2. Threat model

### Assets
- **The persistent self-hosted host** (its OS, the dedicated runtime account, the administrator account, anything on its LAN the runtime account can reach). Primary asset; the whole skill exists to put CI on it. [CONFIRMED by `references/discovery.md:29`, `references/platforms.md:20`]
- **Root on that host** — reached only through the administrator's interactive `sudo` steps the skill renders (`macos_service.py` plan, `remote_command.py`, `platforms.md` Linux/Windows sections). [CONFIRMED]
- **`RUNNER_READ_TOKEN`** — fine-grained PAT, Administration:read on one repo, stored as an Actions secret; used solely by the hosted `select` job. [CONFIRMED `assets/ci.yml:42`, `references/credentials.md:9`]
- **Registration token** — one-hour admin-scoped token for `config.sh`/`config.cmd`; the skill never handles its value, only guidance. [CONFIRMED `references/credentials.md:8,19-23`]
- **Runner `.credentials` / `.runner` state** — never read except safe identity fields of `.runner`. [CONFIRMED `scripts/prepare_runner.py:115-135`, test `test_inspects_only_safe_registration_fields`]
- **Ability to run code on the self-hosted host** (CI routing decision) — decided by `assets/ci.yml` + `scripts/select_runner.py`.
- **The runner distribution** — official archive, authoritative SHA-256 required before extraction. [CONFIRMED `scripts/prepare_runner.py:48,58-63`; `references/setup.md:14`]

### Surfaces
| Surface | Where input enters | Validation story |
| --- | --- | --- |
| GitHub events (`push`, `pull_request`, `workflow_dispatch`) | `assets/ci.yml:3-11` | PR events and non-trusted refs never reach self-hosted; no `${{ }}` interpolation inside any `run:` block (only env vars `$RUNNER_NAME` etc.). [CONFIRMED lines 41-42, 52-61] |
| Repository variables (`vars.*`) | `ci.yml:27,35-42` → selector env | Admin-controlled; regex/allowlist-checked in `select_runner.py:50-63,66-70`. [CONFIRMED] |
| `workflow_dispatch` input `force_hosted` | `ci.yml:40` | boolean type, only forces hosted (fail-safe direction). [CONFIRMED] |
| GitHub REST responses | `select_runner.py:24-32,74-89` | 1 MiB cap, 5 s timeout, redirects refused, shape/type checks, page-count consistency, exceptions swallowed to avoid token leakage. [CONFIRMED] |
| `GITHUB_OUTPUT` | `select_runner.py:99-101` | value is `json.dumps` of validated labels; newlines impossible. [CONFIRMED] |
| CLI args of the three local helpers | `macos_service.py:20-37`, `remote_command.py:12-29`, `prepare_runner.py:28-57` | regex + absolute/resolved path + no `..`/control chars; `shlex.quote`/`shlex.join` at every shell boundary. [CONFIRMED; 24 fixture tests pass] |
| Runner archive contents | `prepare_runner.py:35-40,73-94` | absolute/`..`/backslash/colon/NUL paths, links, specials, duplicates, registered-state names, 3 GiB / 100k entry limits refused; extracted into a freshly created 0700 directory with `xb`. [CONFIRMED] |
| `.runner` JSON on host | `prepare_runner.py:119-134` | symlink refused, 64 KiB cap, object check, URL userinfo/query refused, only four fields echoed. [CONFIRMED] |
| Branch/tag names | `ci.yml:41-42` | **compared case-insensitively — see S1.** |
| Files root executes (`svc.sh`, `runsvc.sh`, staged plist, transferred script) | `platforms.md:28-36`, `macos_service.py:65-81`, `remote_command.py:30` | Guidance only; no helper verifies ownership/bytes. See S2 and section 7. |

### Actors
- Anonymous / fork contributor: reaches `pull_request` only → hosted runner, no secrets. [CONFIRMED]
- Write collaborator: can push branches and dispatch workflows; intended to reach self-hosted only via `TRUSTED_RUNNER_REF` (expected to be branch-protected). **Can bypass via case-variant ref (S1).**
- Repository admin: controls `vars.*`, secrets, `RUNNER_SELECTOR_SHA`; fully trusted by design.
- Runtime account on the host: executes trusted-ref CI code; owns runner tree, `runsvc.sh`, `svc.sh`, logs. Must never gain root (S2 is the gap).
- Host administrator (human): performs every `sudo`/service/account step interactively; the skill renders, never executes. [CONFIRMED: no helper calls `subprocess`, `os.system`, `ssh`, `launchctl` — grep over `scripts/`]
- GitHub (api.github.com): third-party service receiving `RUNNER_READ_TOKEN`; URL hard-pinned, `GITHUB_API_URL` must equal `https://api.github.com`. [CONFIRMED `select_runner.py:63,76`]
- The AI agent running the skill: told repeatedly that inspection authorizes no mutation and that tokens never enter chat. [CONFIRMED `SKILL.md:20`, `credentials.md:17,21`]

### Trust boundaries
1. Untrusted PR code → hosted runner only; selector always runs trusted-revision code (`RUNNER_SELECTOR_SHA || default_branch`, `persist-credentials: false`, sparse checkout). [CONFIRMED `ci.yml:24-30`] Holds.
2. Trusted ref → persistent host. Enforced by `ci.yml:41-42` and whatever branch protection the maintainer applies. **Weakened by case-insensitive comparison (S1).**
3. Runtime account → root. Enforced by the human administrator reviewing rendered artifacts; renderer checks are syntactic only (stated in `platforms.md:16,56`). **Weakened on Linux by `sudo ./svc.sh` from the runtime-owned tree (S2).**
4. Operator workstation → target host: SSH with host-key checks kept on, credentials outside chat. [CONFIRMED `discovery.md:21`]
5. GitHub → selector: TLS via `urllib` default context, bearer token only to the pinned API origin. [CONFIRMED]

## 3. AuthN/AuthZ matrix

| Operation | Actor | Enforcement point |
| --- | --- | --- |
| Run job on hosted runner | anyone who can trigger `push`/`pull_request`/`dispatch` | `ci.yml:46` via selector fallback — GitHub's own repo permissions |
| Run job on self-hosted host | write collaborator pushing to `TRUSTED_RUNNER_REF`, or dispatching on it | `ci.yml:41` (`ENABLE_SELF_HOSTED`, non-PR, ref equality) + `select_runner.py:57` (`TRUSTED_EVENT`) — **ref equality is case-insensitive (S1)**; branch protection is external and documented as the maintainer's job (`ci.md:29`) |
| Receive `RUNNER_READ_TOKEN` | the `select` job only, same conditions | `ci.yml:42`; never passed to `checks` job [CONFIRMED] |
| List runners (API) | selector with PAT | `select_runner.py:57-63` guards + GitHub Administration:read |
| Register runner | host admin with registration token | outside skill; `setup.md:30` (interactive, `--token` omitted from recorded lines) |
| Create secret/variables | repo admin | outside skill; `credentials.md:17` (`gh secret set`, UI) |
| Install/convert service (root) | host administrator, interactive sudo | rendered plan only (`macos_service.py:77-81`, `platforms.md:28-36`); **root executes runtime-owned `svc.sh` on Linux (S2)** |
| Extract runner archive | runtime account (non-root enforced) | `prepare_runner.py:46-47,54-55` [CONFIRMED] |
| Inspect host state | any local user able to read the dir | `prepare_runner.py inspect` reads only identity fields; `.credentials` never opened [CONFIRMED] |
| Execute transferred script as root over SSH | host administrator | `remote_command.py` renders `sudo -- /bin/bash -- <script>`; bytes/ownership verification is manual guidance (`platforms.md:16`) — no MISSING row, but enforcement is human |
| Reboot / merge / cleanup | human only | `SKILL.md:34`, `verification.md:41` (explicitly out of scope for the agent) |

No operation lacks a row; two rows (self-hosted routing, root service install) have weakened enforcement — S1 and S2.

## 4. Coverage accounting

- Snapshot: `8d6598de262ea3bef0f947c30aa747d5c8ea7263`, dirty = true (opt-in). README diff sha256 `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502` (matches baseline). All 19 in-scope SHA-256s match `baseline.txt`; the 8 gitignored `.pyc` files are byte-identical before/after (ignored as non-source).
- Platform/toolchain: Darwin 25.6.0 arm64, Python 3.14.7, actionlint 1.7.12, gitleaks 8.30.1.
- Executed (in `/tmp/gr-audit.fU9LXm/github-runner`, an rsync copy excluding `__pycache__`, `PYTHONDONTWRITEBYTECODE=1`): `python3 -m unittest discover -s tests -v` → 24 tests OK; `python3 -m py_compile scripts/*.py` → OK. Nothing written into the project.
- Scanners: `actionlint github-runner/assets/ci.yml` → exit 0, no output. `gitleaks detect --no-git --source github-runner --redact` and same for `README.md` → "no leaks found" (file contents only; git history deliberately excluded per scope). Regex sweep for GitHub/AWS/Slack/OpenAI/JWT/private-key formats → no hits. Keyword review of `token|secret|password|credential` in scripts/tests → only fixture literals (`'private'`, `'secret'`, `DO-NOT-PRINT`).
- Dependency advisory lookups: **not applicable** — no manifest, lockfile, vendored code or third-party Python package exists; all four helpers import stdlib only (verified by reading every `import`). `pip-audit`/`osv-scanner` are not installed and would have had nothing to scan.
- Read-only external lookups (unauthenticated `curl` to api.github.com; `WebFetch` of docs.github.com): `actions/checkout` tag `v6` → `d23441a48e516b6c34aea4fa41551a30e30af803` (= `v6.1.0`); `actions/runner` latest `v2.338.0` publishes per-asset `sha256:` digests (supports `setup.md:10-14`); GitHub expressions doc: "GitHub ignores case when comparing strings" (supports S1).
- BLOCKED (require live systems; exact next check given): live creation of a case-variant branch in a disposable repo with this workflow to observe routing (S1); `sudo ./svc.sh` on a disposable Linux VM with a runtime-modified `svc.sh` (S2); launchd log-path open semantics on a disposable macOS VM (open question Q1); real registration/service/reboot acceptance (already declared unrun by the skill itself in `tests/scenarios.md:61`).
- Blind spots: Windows `current_account()` ctypes path untested (noted by the skill); `HOSTED_LABELS` and `X-GitHub-Api-Version: 2026-03-10` not re-verified against the primary table; behavioral scenarios in `tests/scenarios.md` are self-reported, not re-run; `npx skills add` installer behavior not executed (lifecycle scripts are read, never run).
- Excluded: `speckit-*` skills, git history, other worktrees, deployed hosts (out of the bounded target).

## 5. Findings

### CI/CD

**S1 — High — PLAUSIBLE — `github-runner/assets/ci.yml:41-42`**

Asset: the persistent self-hosted host (code execution as the runtime account). Actor: a write collaborator (or a compromised collaborator token) who cannot push to the protected trusted ref. Path: the only check that distinguishes "trusted" from "any push" is `github.ref == vars.TRUSTED_RUNNER_REF` (line 41, duplicated for the token on line 42). GitHub expression `==` on strings is case-insensitive ("GitHub ignores case when comparing strings" — expressions reference, fetched 2026-10-08). Git refs are byte-exact, so `refs/heads/MAIN` is a distinct, ordinarily unprotected branch while the expression evaluates `refs/heads/MAIN == refs/heads/main` as true. A push to such a branch yields `TRUSTED_EVENT=true`; the trusted-revision selector then returns the self-hosted label set and the `checks` job checks out the attacker's commit on the persistent host (`ci.yml:44-61`). `RUNNER_READ_TOKEN` is also handed to the `select` job on that push, but only trusted selector code consumes it, so the direct impact is host execution, not PAT leakage.

Why PLAUSIBLE rather than CONFIRMED: the case-insensitive comparison is confirmed from the primary docs; that GitHub accepts creation of a branch differing only by case from an existing protected branch, and that the maintainer's protection pattern does not already cover case variants, are not verified live (BLOCKED check listed in section 4). The reference text (`references/ci.md:29`) says "any user who can … push that ref can compromise the persistent host", which assumes exact-ref semantics the workflow does not provide. Blast radius: arbitrary code as the runtime account on the host, with whatever LAN/file access it has (`discovery.md:29`).

Recommended direction: do the trust decision byte-exactly inside the trusted selector — export `GITHUB_REF: ${{ github.ref }}` and `TRUSTED_RUNNER_REF: ${{ vars.TRUSTED_RUNNER_REF }}` to the `route` step and have `select_runner.py` return the hosted fallback unless `env['GITHUB_REF'] == env['TRUSTED_RUNNER_REF']` (Python string equality), keeping the YAML gate as defence in depth; additionally document in `references/ci.md` that the protection ruleset must cover case variants (e.g. a "restrict creations" rule or an fnmatch pattern such as `[Mm][Aa][Ii][Nn]`) and that `vars.TRUSTED_RUNNER_REF` must be exact. Add a regression test with `GITHUB_REF='refs/heads/MAIN'`.

Acceptance check: `cd <mktemp copy>/github-runner && PYTHONDONTWRITEBYTECODE=1 GITHUB_OUTPUT=/dev/null HOSTED_RUNNER=ubuntu-24.04 TRUSTED_EVENT=true GITHUB_REF=refs/heads/MAIN TRUSTED_RUNNER_REF=refs/heads/main GITHUB_REPOSITORY=acme/widget RUNNER_READ_TOKEN=x PREFERRED_RUNNER_NAME=w PREFERRED_RUNNER_LABEL=repo-ci RUNNER_LABELS='["Linux","X64"]' python3 scripts/select_runner.py` must print `runner="ubuntu-24.04"` before any API request. Today the selector ignores `GITHUB_REF` entirely and (with a stubbed API) would emit the self-hosted label array; after the fix it prints the fallback and `test_select_runner.py` carries a case-variant subtest.

### Privilege boundary / supply chain

**S2 — Medium — CONFIRMED — `github-runner/references/platforms.md:28-36`**

Asset: root on the Linux host. Actor: anyone whose code has executed as the runtime account (every trusted-ref CI job, or the S1 bypass), or any local compromise of that account. Path: the Linux procedure prints, as the primary example, `cd -- "$RUNNER_DIR"; sudo ./svc.sh install "$RUNNER_ACCOUNT"; sudo ./svc.sh start; sudo ./svc.sh status`. `$RUNNER_DIR` is required to be owned by the runtime account (`prepare_runner.py:54-55`, `platforms.md:24`), and `svc.sh` plus the `.service` file and `bin/*.template` it reads are therefore runtime-writable. Every later `sudo ./svc.sh …` (status, stop, uninstall) executes whatever that account has written, as root. The same page already states the hazard ("`svc.sh` is executable code run as root … do not execute arbitrary runtime-owned modifications as root", line 36) but keeps the unsafe form as the shown procedure and offers only "administrator-owned reviewed copies … when needed". The macOS branch avoids this correctly: the rendered plan uses system-domain `launchctl` only and says "Never execute svc.sh/runsvc.sh as root from runtime-writable storage" (`macos_service.py:67,87`). The Linux branch is inconsistent with it. Not reproduced live (BLOCKED check in section 4); the instruction text itself is the confirmed evidence.

Recommended direction: make the Linux procedure match the macOS one — run `svc.sh install` once, before the runner has executed any job, from an administrator-owned copy of the verified distribution's `svc.sh` and templates (or render the systemd unit directly as the skill already does for launchd), then manage the unit exclusively with `systemctl <verb> <exact-unit>`; state explicitly that `sudo ./svc.sh` must never be re-run on a runner that has executed jobs. Also warn that `.service` (runtime-writable) names the unit path `svc.sh` manipulates.

### Supply chain hygiene

**S3 — Low — CONFIRMED — `github-runner/assets/ci.yml:25` and `:49`**

Asset: integrity of both CI jobs (the PAT-bearing selector job and the self-hosted checks job). Actor: whoever can move the `v6` tag in `actions/checkout` (GitHub-owned, but a mutable pointer). Path: `uses: actions/checkout@v6` resolves at run time; verified today it points at `d23441a48e516b6c34aea4fa41551a30e30af803` (= `v6.1.0`). `references/ci.md:41` says to "refresh … action versions during actual deployment" but the template itself is unpinned, and the skill's hardening posture elsewhere (checkout of an immutable `RUNNER_SELECTOR_SHA`) is stricter than this. Recommended direction: pin to the full commit SHA with a `# v6.1.0` comment and rely on Dependabot/Renovate for bumps, or document the choice in the template comment.

Cross-reference: no single-chain code-level flaws were found; nothing is deferred to a codebase audit.

## 6. Supply-chain inventory

| Item | Status | Why |
| --- | --- | --- |
| `actions/checkout@v6` (ci.yml:25,49) | Flagged (S3) | mutable tag |
| GitHub-hosted `ubuntu-latest` for the PAT-bearing job (ci.yml:19) | Clean with documented gate | `ci.md:25` requires an inventory check that no self-hosted runner carries any hosted label |
| `actions/runner` distribution | Clean | official release, authoritative SHA-256 required before extraction, `--proto '=https'` download guidance (`setup.md:10-14`, `prepare_runner.py:58-63`); latest release publishes per-asset digests |
| `svc.sh` / `runsvc.sh` from the distribution | Flagged (S2, Linux); clean on macOS | root execution from runtime-owned tree vs. launchd-only management |
| Python helpers (4) | Clean | stdlib only (`argparse, hashlib, json, os, pathlib, plistlib, re, shlex, shutil, stat, tarfile, zipfile, urllib, ipaddress`); no manifests, lockfiles, vendoring or install scripts exist |
| Install path `npx skills add diegomarino/my-skills --skill github-runner` (`github-runner/README.md:10`) | Clean / pre-existing convention | fetches the repo default branch through the unpinned `skills` npm CLI; this is the repository-wide install convention already in the root README and not introduced by this change; reader-executed, no lifecycle scripts in this skill |
| `agents/openai.yaml` | Clean | display metadata only |
| License | Not applicable | no third-party code; note the repository itself ships no `LICENSE` file (pre-existing, outside scope — Q4) |

## 7. What held up

- PR isolation: PRs (including same-repo) never reach the host; selector runs the trusted revision with `persist-credentials: false` and sparse checkout; `RUNNER_READ_TOKEN` is withheld on PR events and never reaches the `checks` job. [CONFIRMED `ci.yml:24-30,41-42`]
- No expression interpolation in `run:` blocks; `permissions: contents: read`; `force_hosted` can only fail safe. [CONFIRMED]
- Selector: pinned API origin, redirects refused, 1 MiB / 5 s / 1000-record caps, strict shape checks, exceptions never printed (token-leak discipline), `HOSTED_RUNNER` allowlist enforced before any request, default/platform labels refused as routing labels. [CONFIRMED by code + 9 fixture tests]
- Archive preparation: non-root and identity-verified (not from `$USER`), parent ownership check, exclusive 0700 directory, path traversal/link/special/duplicate refusal, size limits, interrupted state retained. [CONFIRMED by code + 8 tests]
- Shell boundaries: `shlex.quote`/`shlex.join` everywhere a path reaches a shell; hostnames/accounts/paths regex-guarded against option injection; IPv6 handled via `ipaddress`. [CONFIRMED by 3 tests incl. `$(touch sentinel)` fixtures]
- macOS daemon plan: renders only, `UserName` = standard account, root/daemon/nobody refused, PATH entries must be absolute, artifacts 0600 with exclusive creation, system-domain `launchctl` only, explicit "never svc.sh as root from runtime-writable storage". [CONFIRMED]
- Credential guidance: registration token interactive and omitted from recorded lines; PAT is fine-grained, single-repo, Administration:read, finite expiry, entered via UI/`gh secret set`, never chat; secret names only are ever listed. [CONFIRMED `credentials.md`]
- `.credentials` is never read; `inspect` prints four identity fields and refuses symlinked or oversized state. [CONFIRMED + test]
- Checksum comparison of a public digest is non-constant-time — irrelevant (no secret compared). No other crypto exists. NOT REPRODUCED as an issue.
- Self-hosted job runs untrusted dependencies of trusted code on a non-ephemeral host: acknowledged as a design limit (`ci.md:29`, `platforms.md:20`), not a finding of this change.

## 8. Open questions (maintainer-only)

- Q1: launchd opens `StandardOutPath`/`StandardErrorPath` (`macos_service.py:46`, under the runtime account's `~/Library/Logs/<label>/`) — if the open happens as root before dropping to `UserName`, a runtime-account symlink there becomes a root write primitive on service restart (`KeepAlive`). The plan asks the admin to check for symlinks once, but the runtime account can replace the file afterwards. Unverifiable offline; next check: on a disposable macOS VM, replace `stdout.log` with a symlink to a root-only path and `launchctl kickstart -k` the daemon, then inspect the target. If root does the open, move logs to a root-owned directory with a runtime-writable file created by the administrator, or let `runsvc.sh` manage its own logging.
- Q2: Does the maintainer's branch protection/ruleset pattern cover case-variant branch names (S1)? If GitHub rejects creating `MAIN` beside `main` in the target repository, S1 drops to Low; this was not tested.
- Q3: `HOSTED_LABELS` (`select_runner.py:12-16`, "verified 2026-10-08") and `X-GitHub-Api-Version: 2026-03-10` were not re-verified against the primary table/API in this audit.
- Q4: The repository root has no `LICENSE` file; the new README row advertises the skill for public installation. Pre-existing and out of this change's scope, flagged for awareness only.
- Assumption recorded: with no human available, I treated "write collaborator excluded from the trusted ref by branch protection" as the intended threat actor for S1, matching `ci.md:29`'s own statement of the trust model.

STOP — report and sidecar written; no fixes applied, no git state mutated.

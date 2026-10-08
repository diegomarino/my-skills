# Codebase audit: `github-runner` skill (bounded target)

- Date: 2026-10-08
- Auditor model: Claude Fable 5.1 (`claude-fable-5-1`), dispatched by an orchestrator (no human in the loop; assumptions recorded in section 8)
- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263` (short `8d6598d`), branch `feat/github-runner`, tree DIRTY by explicit human opt-in
- Scoped `git diff HEAD -- README.md` sha256: `21779ad43faa6e44eb4aec8d789646116f95a28dbd633aaeb0f32c778cb23502` (re-verified at audit start and again before writing; matches the orchestrator baseline)
- Target: `github-runner/**` (19 untracked files, all read fully) plus the root `README.md` diff vs HEAD. Treated as the whole product. No prior reports exist; sibling reports in this run directory were deliberately not read.
- Sidecar: `codebase-audit-2026-10-08.md.findings.json` (same ID set as the summary table)

## 1. Summary

| ID | Severity | Area | Issue | Location | Evidence |
| --- | --- | --- | --- | --- | --- |
| C1 | High | Correctness / affordance | `prepare` refuses every current official Linux and macOS runner archive: the tarballs contain 6 relative symlinks under `externals/node{20,24}/bin`, and the helper rejects any link entry. The documented happy path never works with real inputs. | `github-runner/scripts/prepare_runner.py:80-82` | CONFIRMED |
| C2 | High | Correctness / affordance | `inspect` rejects a `.runner` file that starts with a UTF-8 BOM; the official runner writes `.runner` via `File.WriteAllText(..., Encoding.UTF8)`, which emits a BOM, so the documented "safe readback" path fails on real instances. | `github-runner/scripts/prepare_runner.py:126` | PLAUSIBLE |
| C3 | Medium | Alternative paths | Concurrency group is keyed only on workflow+ref with `cancel-in-progress: true`; the documented acceptance procedure (preferred run and `force_hosted` dispatch on the same final candidate) cancels its own first run if the two dispatches overlap. | `github-runner/assets/ci.yml:13-16`; `github-runner/references/ci.md:7,37` | CONFIRMED |
| C4 | Medium | Missing functionality / observability | The selector collapses ~15 distinct fallback causes (misspelled variable, untrusted ref, bad PAT, HTTP 4xx, busy, offline, label mismatch, truncated inventory) into an identical `runner="<hosted>"` line with no reason; a misconfiguration is indistinguishable from a busy runner, forever. | `github-runner/scripts/select_runner.py:57-93` | CONFIRMED |
| C5 | Medium | Boundary & safety / missing functionality | The selector queries by `name` only, so it never sees the inventory and cannot enforce the invariant the whole routing design rests on (custom label unique; no self-hosted runner carrying a hosted label). The gate is delegated to prose and manual inspection even though the code already pages a full inventory shape. | `github-runner/scripts/select_runner.py:75-76`; `github-runner/references/ci.md:25` | CONFIRMED |
| C6 | Medium | Incoherence | On Windows `prepare` silently drops two of its advertised guards (parent-directory ownership and "not root/elevated"), because both are gated on `hasattr(os, 'getuid'/'geteuid')`; docs promise the same "account/path guards" on all platforms. | `github-runner/scripts/prepare_runner.py:46,54`; `github-runner/references/setup.md:26` | CONFIRMED |
| C7 | Medium | Documentation / DX | `setup.md` tells the operator to take the asset `digest` field from `gh api .../releases/latest`; that field is `sha256:<hex>` and `prepare --sha256` rejects anything but bare hex ("Invalid digest or version"). | `github-runner/references/setup.md:10-14`; `github-runner/scripts/prepare_runner.py:48` | CONFIRMED |
| C8 | Medium | Test-suite confidence | Six safety guards are non-pinning: the three pagination guards (short page, 1000 cap, cross-page total), the 64 KiB state-file cap, the parent-ownership guard and the root guard can each be deleted with the suite still green. Root cause for the first three: `except Exception` swallows the mock harness's `IndexError`. | `github-runner/scripts/select_runner.py:82,88,90-92`; `github-runner/tests/test_select_runner.py:95-103`; `github-runner/scripts/prepare_runner.py:46,54,124` | CONFIRMED |
| C9 | Low | Affordance | macOS renderer rejects legitimate macOS short names containing uppercase or dots (`BuildCI`, `build.ci`) with the misleading message "Choose a dedicated standard runtime account." | `github-runner/scripts/macos_service.py:28` | CONFIRMED |
| C10 | Low | DX / documentation | `prepare`/`inspect` reject `/tmp/...` and `/var/...` on macOS (resolved to `/private/...`) with a generic message; only `platforms.md` warns about the alias, and only for the macOS renderer. | `github-runner/scripts/prepare_runner.py:28-32`; `github-runner/references/setup.md:18-24` | CONFIRMED |
| C11 | Low | Documentation / onboarding | Skill README references a `skill-creator scripts/quick_validate.py` that does not exist in this repository, and uses `npx skills add ... --skill` while the root README and both sibling skills use the `@<skill>` form. | `github-runner/README.md:10,48`; root `README.md:10-11` | CONFIRMED |
| C12 | Low | Incoherence / security posture | The PAT-bearing `select` job pins `actions/checkout@v6` by mutable tag while `ci.md` cites GitHub's hardening guide (which recommends full-SHA pinning) as the template's source. | `github-runner/assets/ci.yml:25,49`; `github-runner/references/ci.md:41` | CONFIRMED |

Counts: Critical 0, High 2, Medium 6, Low 4. Evidence: CONFIRMED 11, PLAUSIBLE 1, BLOCKED 0 (blocked checks are listed in section 3, not as findings), NOT REPRODUCED 0 as findings (3 investigated-and-discarded items in section 7).

## 2. System map

The product is an Agent Skill: a `SKILL.md` procedure (4 phases) that an agent follows, six reference documents, four standard-library Python helpers, one workflow template, and 24 unit tests. There is no package, build, or runtime beyond `python3 <script>`.

### Real execution paths

1. Agent path (CONFIRMED by reading `SKILL.md:10-36`): Discover -> Prepare and register -> Choose persistence and integrate CI -> Verify and report. Each phase links a reference; the references, not the helpers, carry almost all of the safety rules. `SKILL.md` frontmatter `name: github-runner` matches the directory and the description is a single trigger sentence (CONFIRMED).
2. `prepare_runner.py prepare` (CONFIRMED by execution in a temp dir): `checked_directory` -> identity/root guard -> digest+version regex -> destination absent -> parent is a dir owned by the caller -> archive regular file -> SHA-256 stream -> zip-or-tar detection -> per-entry validation (path, type, duplicates, reserved names, 3 GiB / 100,000 cap) -> entry-point check -> exclusive `mkdir(0o700)` -> write `.preparation.json` `incomplete` -> extract with `open('xb')` -> rewrite receipt `prepared`. Any exception after the `mkdir` leaves the directory and the `incomplete` receipt in place; a rerun is refused (CONFIRMED by `test_interrupted_extraction_is_retained_and_retry_refused`).
3. `prepare_runner.py inspect` (CONFIRMED): reads only `.runner` and `.preparation.json`, refuses symlinked state files and files >64 KiB, filters to `agentId/agentName/gitHubUrl` and `status/version/sha256/account`, refuses a `gitHubUrl` with userinfo/query/fragment.
4. `macos_service.py` (CONFIRMED): validates account/label/paths, requires an existing resolved output dir, renders `<label>.plist` (plutil-lint clean, verified) and `service-plan.txt` with exclusive creation and mode 0600. Never touches launchd.
5. `remote_command.py` (CONFIRMED): validates host (hostname regex, or `ipaddress.ip_address` when a colon is present, which accepts scoped IPv6 on 3.9+), admin account, absolute script path; prints `ssh -t -l <admin> -- <host> 'sudo -- /bin/bash -- <script>'` with both shell boundaries quoted. Never connects.
6. Workflow (CONFIRMED by reading `assets/ci.yml` and actionlint 1.7.12 clean): `select` job on `ubuntu-latest` sparse-checks-out `.github/scripts/select_runner.py` from `vars.RUNNER_SELECTOR_SHA || default_branch`, runs it with env derived from repository variables; `TRUSTED_EVENT` and `RUNNER_READ_TOKEN` are both gated on `ENABLE_SELF_HOSTED == 'true' && event != pull_request && TRUSTED_RUNNER_REF != '' && github.ref == TRUSTED_RUNNER_REF`. Output `runner=<json>` feeds `runs-on: ${{ fromJSON(...) }}` of `checks`. The `checks` step deliberately `exit 1` until replaced.
7. `select_runner.py select()` (CONFIRMED): `HOSTED_RUNNER` must be in the 14-entry `HOSTED_LABELS` allowlist or it raises before anything else (the only non-fallback error). Then any of: forced hosted, untrusted, missing name/label/token, invalid or default-platform label, malformed repo, non-github.com API URL -> fallback with no request. Otherwise parse `RUNNER_LABELS` (needs one OS and one arch label), build `required = ['self-hosted', label] + platform`, page `GET /repos/{repo}/actions/runners?name=<name>&per_page=100&page=N` up to 10 pages / 1000 records with 5 s timeout and 1 MiB cap and redirects refused, then `choose()` requires exactly one runner with that name, `status == 'online'`, `busy is False`, and all required labels (casefolded). Returns the label list, not the name.

### Key invariants and where they are enforced

- "No helper mutates a host, a service, GitHub, or git" — enforced in code for all four helpers (CONFIRMED: no subprocess, no network except the selector's read-only GET, no writes outside the reserved directory / staging dir).
- "Selector never calls the API on untrusted or forced events" — enforced in code (CONFIRMED, `select_runner.py:57-64`; `test_skips_api`).
- "Hosted fallback must be a standard label" — enforced in code (CONFIRMED) and the 14 labels all appear in the current public docs table (verified 2026-10-08 by fetching the page; `ubuntu-22.04-arm` exists but is omitted, consistent with the "conservative subset" claim).
- "Custom routing label is unique among all accessible runners; no self-hosted runner carries any hosted label used by the workflow" — NOT enforced in code; prose-only gate (`ci.md:25`). See C5.
- "Runtime account is standard and distinct; parent directory owned by it; not root" — enforced on POSIX only (CONFIRMED); silently skipped on Windows (C6).
- "Official archive is safe to extract" — enforced so strictly that the official archive itself is refused (C1).
- "Credentials never leak into logs" — enforced: exception text is suppressed in the selector, `inspect` filters fields (mutation m4 killed by `test_inspects_only_safe_registration_fields`), token read only from env (CONFIRMED).
- "Python 3.9+" — CONFIRMED: suite and `py_compile` pass under system `/usr/bin/python3` 3.9.6 and Python 3.14.7.

## 3. Coverage accounting

- Snapshot: HEAD `8d6598de262ea3bef0f947c30aa747d5c8ea7263`, tree DIRTY (root `README.md` modified; `github-runner/**` untracked). All 20 in-scope file SHA-256 values re-computed before writing and identical to the orchestrator manifest; the 8 gitignored `.pyc` files are byte-identical to the baseline (nothing was written into the project by this audit).
- Platform/toolchain: macOS Darwin 25.6.0 arm64; Python 3.14.7 (default `python3`) and 3.9.6 (`/usr/bin/python3`); actionlint 1.7.12; curl; git. `PYTHONDONTWRITEBYTECODE=1` exported for every helper/test execution; all executions happened in `mktemp -d /tmp/gr-audit.XXXXXX` copies outside the project.
- Read fully (19 + diff): `github-runner/README.md`, `SKILL.md`, `agents/openai.yaml`, `assets/ci.yml`, `references/{ci,credentials,discovery,platforms,setup,verification}.md`, `scripts/{macos_service,prepare_runner,remote_command,select_runner}.py`, `tests/{scenarios.md,test_macos_service,test_prepare_runner,test_remote_command,test_select_runner}.py`; `git diff HEAD -- README.md`.
- Read as minimum consumer context only: root `README.md` (whole file, to place the diff), `.gitignore`, `ls -R` of the two sibling skill folders and `grep 'npx skills add'` in their READMEs (install-syntax convention for C11). Not audited.
- Excluded: `github-runner/**/__pycache__` (gitignored, pre-existing), all other repository content, other worktrees, sibling audit reports in this run directory.
- Commands run (all read-only or in throwaway dirs): `git rev-parse HEAD`, `git status --porcelain --untracked-files=all`, `git diff HEAD -- README.md | shasum -a 256`, `shasum -a 256` manifests, `find`/`wc -l`; in the temp copy: `python3 -m unittest discover -s github-runner/tests -v` (24/24 OK on 3.14 and 3.9), `cd github-runner && python3 -m unittest discover -s tests` (root-README form, 24/24 OK), `python3 -m py_compile github-runner/scripts/*.py` (OK on both), `actionlint github-runner/assets/ci.yml` (clean), fixture executions of every helper (BOM `.runner`, `/tmp` alias, `sha256:` digest, misspelled variable, mixed-case account, `plutil -lint` on a rendered plist), 9 mutation runs on temp copies; read-only network GETs: `GET https://api.github.com/zen` with both API version headers, `GET /versions`, `GET /repos/actions/runner/releases/latest`, download of `actions-runner-osx-arm64-2.338.0.tar.gz` (sha256 verified against the published digest) and `actions-runner-win-x64-2.338.0.zip` to the temp dir, streamed `tar -tzv` of the linux-x64 asset, raw fetch of `actions/runner` `IOUtil.cs`, `ConfigurationStore.cs`, `darwin.svc.sh.template`, `git ls-remote --tags actions/checkout`, GET of the hosted-runner docs page, and a HEAD/GET link check of every external URL in scope (all 200).
- Secret scan: in-scope files only; no token/key patterns found (the literal `RUNNER_READ_TOKEN='private'` in tests is a fixture string).
- BLOCKED checks (not run; exact next check):
  - Live registration / `config.sh` / `svc.sh install` / `launchctl bootstrap` / `config.cmd` / reboot persistence: would run the rendered `service-plan.txt` on an authorized macOS host and `sudo ./svc.sh install "$RUNNER_ACCOUNT"` on an authorized systemd host, then `launchctl print system/<label>` and `gh api repos/O/R/actions/runners/<id>`.
  - Real `.runner` BOM (C2): `head -c 3 /path/to/instance/.runner | xxd` on any registered instance, then `python3 scripts/prepare_runner.py inspect --directory <resolved path>`.
  - Exactness of the `?name=` filter and the selector against a live inventory: `gh api "repos/O/R/actions/runners?name=<exact>"` with Administration:read; needs a repository with registered runners.
  - Windows identity path (`GetUserNameW`) and zip extraction on Windows: `python prepare_runner.py prepare ...` on a Windows host as the runtime account.
  - Real workflow dispatch pair for C3: two `gh workflow run ... --ref <candidate>` within a minute and `gh run list` showing the first as `cancelled`.
- Blind spots: `agents/openai.yaml` semantics for Codex were not validated against a Codex host; the Agent Skills validator (`quick_validate.py`) referenced by the README is not in this repo and was not run; behaviour of the skill prose when followed by an agent (scenarios A-D) was not re-executed, only read.

## 4. Findings by hunt category

### Correctness

**C1 — High — CONFIRMED — `prepare` refuses every current official Linux/macOS archive.**
`github-runner/scripts/prepare_runner.py:80-82`
Scenario: operator follows `setup.md` exactly: downloads `actions-runner-osx-arm64-2.338.0.tar.gz` (latest release at audit time), supplies its official digest `df4cebda…9df2`, a resolved empty parent, and the runtime user. Result: `Preparation/inspection refused: "Archive links and special entries require manual review"`, exit 1, nothing created. Cause: the official tarball contains six relative symlinks (`./externals/node20/bin/{npm,npx,corepack}` and the same for `node24`); the linux-x64 asset carries the identical six. The win-x64 zip has no special entries and passes the type check. So the helper works for the one platform whose archive was fixture-tested and refuses the two platforms that the macOS-centric scenarios (C, D) are about.
Why this path is vulnerable: the symlink policy was written from fixtures, never run against the artifact it exists to process; `scenarios.md:59` says archive handling was "simulated".
Impact: the documented happy path (`setup.md:20-26`) is impossible with real inputs; the escape hatch (`setup.md:26`, "prepare a reviewed native extraction") produces no `.preparation.json`, so `inspect` and the verification table's "Archive" and preparation readback can never be populated for a real instance. Not rated Critical only because native `tar -xzf` remains a workable manual path.
Reachability: public entry point (documented CLI).
Recommended direction: accept symlink entries whose link target, joined to the entry's parent and normalized with `PurePosixPath`, stays inside the instance root (no absolute, no `..` escape), and create them with `os.symlink`; keep refusing hard links, devices, and escaping targets. Add a test using a tarball with a relative in-tree symlink, and a test asserting the escaping case is still refused.
Acceptance check: `python3 scripts/prepare_runner.py prepare --archive actions-runner-osx-arm64-2.338.0.tar.gz --sha256 df4cebda25c86a886ed204e49fee63f5c2e7cec5f447b5c98440a826bbdf9df2 --version 2.338.0 --directory <resolved-parent>/instance --expected-user "$(id -un)"` currently exits 1 with the message above; passes when it exits 0, `.preparation.json` reads `prepared`, and `readlink instance/externals/node20/bin/npm` prints `../lib/node_modules/npm/bin/npm-cli.js`.

**C2 — High — PLAUSIBLE — `inspect` rejects BOM-prefixed `.runner` files, which is how the official runner writes them.**
`github-runner/scripts/prepare_runner.py:126` (`json.loads(path.read_text())`)
Scenario: a registered instance; the agent runs the documented readback (`discovery.md:27`, `verification.md:21`, `README.md:38`). Result (reproduced with a fixture whose first three bytes are `EF BB BF`): `Preparation/inspection refused: "Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)"`, exit 1. The same JSON without the BOM returns the identity report.
Why real files carry a BOM: `actions/runner` `src/Runner.Common/ConfigurationStore.cs:358` saves settings with `IOUtil.SaveObject`, which is `File.WriteAllText(path, json, Encoding.UTF8)` (`src/Runner.Sdk/Util/IOUtil.cs:42`); `Encoding.UTF8` has a preamble and that overload writes it. The real-file link is traced in source, not reproduced on a live instance (hence PLAUSIBLE; the exact check is in section 3).
Impact: the only coded "safe readback" of registration identity fails on every real instance, pushing the agent back to reading `.runner` by hand next to `.credentials`, which is precisely what the design tries to prevent.
Reachability: public entry point.
Recommended direction: `json.loads(path.read_text(encoding='utf-8-sig'))`; add a fixture test with the BOM.
Acceptance check: `printf '\xef\xbb\xbf{"agentId":42,"agentName":"box","gitHubUrl":"https://github.com/acme/widget"}' > <dir>/.runner && python3 scripts/prepare_runner.py inspect --directory <dir>` currently exits 1; passes when it prints `"agentId": 42`. On a real host: `head -c 3 .runner | xxd` shows `efbb bf`, then the same `inspect` succeeds.

### Alternative / unintended paths

**C3 — Medium — CONFIRMED — Acceptance procedure trips the template's own concurrency cancellation.**
`github-runner/assets/ci.yml:13-16`; `github-runner/references/ci.md:7,37`
Concurrency model: GitHub Actions workflow-level `concurrency: { group: preferred-ci-<workflow>-<ref>, cancel-in-progress: true }`; two runs in the same group cannot be in progress simultaneously, the newer cancels the older. Interleaving: `ci.md:7` says "dispatch both modes with `--ref`" on the same final candidate and `ci.md:37` requires both the preferred run and a `force_hosted` run on the **same** candidate. Both dispatches resolve to the same `github.ref`, so they share the group; `inputs.force_hosted` is not part of the key. If the second is dispatched before the first reaches a terminal state (the preferred run can sit queued for minutes on a busy host, which the docs themselves anticipate), the first is cancelled. `ci.md:33` warns "Concurrency cancellation is not success" but nowhere tells the operator to serialize the pair, and the `verification.md` evidence table expects both terminal conclusions.
Impact: a routine acceptance pass silently produces one `cancelled` conclusion; an agent following the docs retries and may burn the runner window or misreport.
Recommended direction: either include `inputs.force_hosted` (or `github.run_id` for `workflow_dispatch`) in the group key, or set `cancel-in-progress: ${{ github.event_name != 'workflow_dispatch' }}`, and state in `ci.md` that the two acceptance runs must be dispatched sequentially or carry distinct groups.

**C4 — Medium — CONFIRMED — Silent, reason-free fallback makes the router undiagnosable.**
`github-runner/scripts/select_runner.py:57-93`
Scenario (reproduced): set every variable correctly except misspell `PREFERRED_RUNNER_NAME` as `PREFERED_RUNNER_NAME`; run on the trusted ref. Output: `runner="ubuntu-24.04"`, exit 0, no other line. Identical output results from an expired PAT (HTTP 401), a revoked Administration:read permission (403), a renamed runner, a busy runner, a `RUNNER_LABELS` typo, a 10-page truncation, or a GHES API URL. Nothing in the job log distinguishes "your config is broken" from "the host is busy", and because the result is a successful hosted run the workflow stays green indefinitely.
Why vulnerable: the comment at line 91 justifies swallowing exceptions because their text may contain credentials; that argument covers exception *strings*, not a fixed enum of reason codes.
Impact: the security-sensitive trust gate (`TRUSTED_EVENT`) and the credential path can fail closed for weeks without anyone noticing; the documented diagnosis flow (`verification.md:37`, "queued needs labels/group/trust/capacity checks") has no signal to start from.
Recommended direction: have `select()` return `(label_or_list, reason)` with a closed set of constant reason strings (`forced`, `untrusted`, `missing-config`, `invalid-label`, `api-error`, `http-<status>`, `not-online`, `busy`, `labels-missing`, `inventory-incomplete`), print `::notice::runner selection: <reason>` and write `reason=` to `GITHUB_OUTPUT`; never include exception text. Keep the output contract for `runner`.

**C5 — Medium — CONFIRMED — The selector cannot enforce the uniqueness invariant it depends on.**
`github-runner/scripts/select_runner.py:75-76` (`?name=<name>` query), `choose()` returns a label set; `github-runner/references/ci.md:25,33`
Scenario: operator verifies today that `repo-ci` is unique. Next month a colleague registers a second runner (or an org-level group becomes accessible) carrying `repo-ci`, or someone labels a self-hosted box `ubuntu-latest`. The selector still finds exactly one runner *named* `worker`, idle, and emits `["self-hosted","repo-ci","Linux","X64"]`; GitHub then schedules the job on whichever labelled runner is free, including the unvetted one. The PAT-bearing `select` job itself lands on the mislabelled self-hosted box. The code never observed either collision because the `name` filter hides the rest of the inventory, so `ci.md:25-33` makes "inspect the full inventory and repeat it whenever labels/access change" a standing manual duty.
Why vulnerable: GitHub `runs-on` cannot target a runner by name; routing is by label set, so the only runtime-checkable invariant is "the label set identifies exactly this runner", and the code has the data shape (full paging up to 1000) but chooses the filtered query.
Impact: untrusted or unintended hosts can receive trusted-ref jobs and the selector's PAT; the "exactly one matching online runner" check gives a false sense of exclusivity.
Recommended direction: drop the `name` filter (or add a second unfiltered pass), then refuse (fallback with reason) when more than one runner carries the custom label, or when any self-hosted runner carries `HOSTED_RUNNER` or `ubuntu-latest` (the selector's own label); keep the name check as an identity assertion on the single survivor. Document that the manual gate remains for org-group runners the PAT cannot list.

### Incoherences

**C6 — Medium — CONFIRMED — Windows silently loses two of `prepare`'s advertised guards.**
`github-runner/scripts/prepare_runner.py:46` (`hasattr(os, 'geteuid') and os.geteuid() == 0`), `:54` (`hasattr(os, 'getuid') and ...st_uid != os.getuid()`); `github-runner/references/setup.md:26` ("account/path guards"), `platforms.md:72`.
Scenario: on Windows an elevated Administrator shell whose username equals `--expected-user` runs `prepare` into a parent directory owned by SYSTEM or another user. Both guards evaluate to "skip" (no `getuid`/`geteuid`), the archive is extracted, and the receipt records `account: <name>` as if the guard had held. `README.md:43` and `scenarios.md:59` only say the Windows identity API is "untested"; the docs that an operator follows promise the same guards on every platform.
Impact: the helper's main privilege-boundary promise (runtime account owns the tree; never elevated) is a no-op on the platform where the service install is itself elevated (`platforms.md:74`).
Recommended direction: either implement Windows equivalents (`ctypes` `IsUserAnAdmin`/token elevation check, owner SID of the parent via `GetNamedSecurityInfoW`) or refuse to run on Windows with an explicit "guards unavailable on this platform; use the documented native procedure" message and say so in `setup.md`.

**C7 — Medium — CONFIRMED — The documented digest source yields a value the helper rejects.**
`github-runner/references/setup.md:10-14` and `github-runner/scripts/prepare_runner.py:48`
Scenario: operator runs the `gh api repos/actions/runner/releases/latest --jq '{...digest...}'` command from `setup.md:10-11`; GitHub returns `"digest": "sha256:af4b794c…"` (verified live). Passing that to `--sha256` fails with `Invalid digest or version` (reproduced). The regex demands 64 bare hex characters and nothing in `setup.md` says to strip the prefix.
Impact: the first real invocation fails on a format detail; an agent is nudged to "fix" the digest by recomputing it from the download, which `setup.md:14` explicitly forbids.
Recommended direction: accept an optional `sha256:` prefix in `prepare()` (and reject any other algorithm prefix), or state the stripping step beside the `gh api` example.

### Test-suite confidence

**C8 — Medium — CONFIRMED — Six guards are non-pinning; three because the harness error is swallowed.**
`github-runner/scripts/select_runner.py:82,88,90-92`; `tests/test_select_runner.py:95-103`; `scripts/prepare_runner.py:46,54,124`
Mutation results (temp copies, suite otherwise green on 3.9 and 3.14):

| Mutation | Suite |
| --- | --- |
| delete `or len(batch) < 100` short-page guard | green (non-pinning) |
| delete `count > 1000` cap | green (non-pinning) |
| delete cross-page `count != total` consistency check | green (non-pinning) |
| `inspect` 64 KiB cap -> `if False` | green (non-pinning) |
| delete parent-ownership guard | green (no seam) |
| allow root (`geteuid() == 0` removed) | green (no seam) |
| `inspect` returns the whole dict | killed |
| drop `sudo` from the rendered SSH command | killed |
| `KeepAlive: False` | killed |

Mechanism for the first three: the test's `fetch` mock returns `pages[len(self.requests) - 1]`; when a deleted guard lets the loop request one page too many, the mock raises `IndexError`, which `select()`'s `except Exception` converts into the very fallback the test expects. `ci.md:31` advertises all three guards ("complete pages up to 1,000 records ... rejecting malformed or incomplete inventories") as safety properties.
Missing seams: the root and parent-ownership guards cannot be exercised without a second uid, so there is no regression seam at all; name it (a `prepare(..., identity=...)` injection point or an `os`-shim parameter) rather than leaving them untested.
Impact: the pagination and size invariants that the docs cite can regress silently; the suite's 24 green tests overstate what is pinned.
Recommended direction: make the mock raise a distinctive, non-`Exception` sentinel (e.g. `BaseException` subclass) or assert `len(self.requests)` for each pagination case; add a >64 KiB state-file test; add an injectable identity/ownership seam with tests for "root" and "parent owned by other uid".

### Affordance mismatches

**C9 — Low — CONFIRMED — Renderer rejects valid macOS account names with a misleading error.**
`github-runner/scripts/macos_service.py:28` (`[a-z_][a-z0-9_-]{0,63}`)
Scenario: the dedicated account was created as `BuildCI` or `build.ci` (both valid short names in Users & Groups / `sysadminctl`). Rendering fails with "Choose a dedicated standard runtime account.", which reads as a policy objection, not a character-set one; the operator cannot tell whether to rename the account.
Recommended direction: allow `[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}` and split the message into "reserved account" vs "unsupported characters".

### Developer experience / documentation

**C10 — Low — CONFIRMED — `/tmp` and `/var` aliases are refused by `prepare`/`inspect` without the warning the macOS renderer gets.**
`github-runner/scripts/prepare_runner.py:28-32`; `references/setup.md:18-24`, `discovery.md:27`, `verification.md:21`
Scenario: `inspect --directory /tmp/stage/instance` on macOS -> "Use an absolute resolved directory without symlinks" (reproduced), because `/tmp` resolves to `/private/tmp`. `platforms.md:54` explains this only for `macos_service.py --output-dir`; the preparation docs say "resolved" once in a placeholder path and never why.
Recommended direction: print the resolved path in the error ("`/tmp/x` resolves to `/private/tmp/x`; pass that") and add the alias note to `setup.md`.

**C11 — Low — CONFIRMED — README onboarding references a validator that is not in the repo and an install syntax that differs from every sibling.**
`github-runner/README.md:10,48`; root `README.md:10-11` (unchanged lines; context), sibling READMEs line 10-11
`README.md:48` says "run the skill-creator `scripts/quick_validate.py` against this directory" with no path or link; nothing named `quick_validate.py` exists in this repository, so a newcomer cannot run the "Format" check. `README.md:10` installs with `npx skills add diegomarino/my-skills --skill github-runner` while the root README (including the new table row's link target) and both sibling skills use `npx skills add diegomarino/my-skills@<skill>`; two syntaxes for one CLI in one repo.
Recommended direction: link the validator's origin (or drop the line) and align the install command with the repository form.

**C12 — Low — CONFIRMED — Mutable-tag action pin in the PAT-bearing job contradicts the cited hardening source.**
`github-runner/assets/ci.yml:25,49`; `references/ci.md:41`
`actions/checkout@v6` (tag exists; verified via `git ls-remote`) is a moving tag. The `select` job receives `RUNNER_READ_TOKEN`; `ci.md:41` names GitHub's security-hardening guide as a source, and that guide's standing recommendation for third-party actions is full-SHA pinning. A template whose stated purpose is a hardened trust boundary ships the softer form without saying why.
Recommended direction: pin to the full commit SHA with a `# v6` comment, or state in `ci.md` that tag pinning is an accepted trade-off for a first-party action.

## 5. Design tensions

1. **Guardrails live in prose, enforcement lives in the agent.** Roughly 330 lines of imperative discipline (references) govern a ~400-line helper set; the invariants with the largest blast radius (label uniqueness, hosted-label collision, "verify ownership before privileged writes", "stop the old LaunchAgent first") are all manual. The helpers validate syntax and refuse obvious misuse, but none can answer "is this deployment safe?" Alternative to weigh: a single `preflight` subcommand that takes the inventory JSON, the adapted workflow, and the variables, and emits the collision/uniqueness verdict the docs ask the agent to compute by hand. Fewer, checkable gates would also shrink `SKILL.md`'s cognitive load.
2. **Select-by-name, route-by-label.** GitHub cannot schedule a job onto a named runner, so the selector's "exactly one idle runner named X" is an availability probe, not a placement guarantee; placement is decided by the label set it emits. The design papers over this with the uniqueness duty (C5). Alternative: route through a dedicated runner group (org/enterprise) or make the selector verify uniqueness against the full inventory at run time; either makes the guarantee real instead of procedural.
3. **Fallback-as-universal-error-handler.** Falling back to hosted on every failure is a defensible fail-closed choice for trust, but it is also the error handler for configuration bugs, credential expiry, API drift and test-harness mistakes. The result is a system that cannot distinguish "safe by design" from "broken" (C4) and whose tests cannot pin its own guards (C8). Alternative: keep fail-closed routing but surface a closed-set reason and fail the job (not fall back) for configuration-class errors, as is already done for `HOSTED_RUNNER`.
4. **Exclusive reservation without a resume path.** `prepare` refuses any existing destination and preserves `incomplete` state, but offers no `verify`/`resume`, and the docs forbid "broad cleanup". With a real archive (9,390 files, 128-228 MB) an interruption is plausible, after which the only way forward is manual deletion that the prose discourages. Alternative: extract into a sibling `instance.partial-<pid>` directory and `rename()` atomically on success, which makes retries idempotent and keeps the receipt semantics.
5. **Guard strictness calibrated on fixtures, not on the product.** The symlink refusal (C1), the digest format (C7), the BOM (C2) and the account regex (C9) share a cause: each guard was derived from a threat model and tested against synthetic inputs, never against the official artefacts it exists to process. Alternative: add one "golden" test tier that reads a real release asset listing (checked in as a manifest, not the binary) and a real `.runner` byte prefix, so the guards are validated against reality before they are tightened further.

## 6. Expectation gaps

- Expected `prepare` to extract the official archive; found it refuses every Linux/macOS release (C1).
- Expected `inspect` to read a registered instance; found it rejects the BOM the official runner writes (C2).
- Expected the acceptance pair (preferred + forced hosted) to coexist; found the second dispatch can cancel the first (C3).
- Expected a misconfigured selector to say so; found an indistinguishable green hosted run (C4).
- Expected "exactly one matching online runner" to mean the job lands on that runner; found it only means the named runner exists and is idle (C5).
- Expected the same account/path guards on Windows; found silent no-ops (C6).
- Expected the documented `digest` to be accepted by `--sha256`; found a prefix mismatch (C7).
- Expected `platforms.md`'s `/tmp` alias warning to apply to all helpers; found it only on the renderer (C10).
- Expected the README "Format" check to be runnable; found a dangling reference (C11).
- Expected the `select` job to be SHA-pinned given the cited hardening guide; found a tag (C12).

## 7. What held up

- Selector trust gating: forced/untrusted/missing-config paths make no request (`test_skips_api`), redirects are refused, token is env-only, exception text never reaches logs, 1 MiB/5 s/10-page bounds match `ci.md:31` exactly. CONFIRMED.
- `X-GitHub-Api-Version: 2026-03-10` (`select_runner.py:27`) looked suspicious and was investigated: `GET /versions` lists `["2026-03-10","2022-11-28"]` and `/zen` returns 200 with that header. NOT REPRODUCED as a defect.
- `HOSTED_LABELS` allowlist: all 14 labels present in the current public docs table; retired `macos-13`/`windows-2019` absent; `ubuntu-22.04-arm` omitted (conservative subset, documented). CONFIRMED.
- `actions/checkout@v6` exists (`git ls-remote`). NOT REPRODUCED as a dead reference.
- All 19 external URLs in scope resolve (HTTP 200). NOT REPRODUCED as link rot.
- `prepare` path-safety: traversal, duplicate `./x` vs `x`, reserved names (`.runner`, `.credentials`, `.preparation.json`), symlinked destination, wrong user, bad digest, missing entry points all refused with the destination left absent; interrupted extraction retained and retry refused. CONFIRMED by tests and by fixture runs. The official win-x64 zip passes the type/path checks (276 entries, all attr 0, `config.cmd` and `bin/Runner.Listener.exe` present).
- `inspect` field filtering is pinned (mutation killed) and never reads `.credentials`. CONFIRMED.
- `macos_service.py`: rendered plist passes `plutil -lint`; keys match what `platforms.md:60` promises (RunAtLoad/KeepAlive/HOME/PATH/WorkingDirectory/UserName/log paths); exclusive creation with 0600; unsafe inputs leave the staging dir empty. CONFIRMED.
- `remote_command.py`: both shell boundaries preserved for apostrophes and `$(...)`; IPv6 including scoped and v4-mapped accepted; option/control injection rejected; `sudo` presence pinned (mutation killed). CONFIRMED.
- Python 3.9 claim: suite and compile pass on 3.9.6 and 3.14.7. CONFIRMED.
- Root README diff: table row link target exists, "Skills with executable helpers ship automated tests" and the `cd <skill> && python3 -m unittest discover -s tests -v` form both work for this skill (24/24). CONFIRMED.
- Workflow/script contract: env names, `'true'` literals, `fromJSON` on both string and array outputs, `GITHUB_OUTPUT` single-line JSON, select-failure skipping `checks`. CONFIRMED by reading plus actionlint.

## 8. Open questions (maintainer answers needed)

1. Is refusing symlinks in official archives (C1) a deliberate "always extract natively" stance? If so, `setup.md` should lead with the native path and `prepare` should be repositioned as verify-only; if not, the in-tree-relative-symlink allowance is the fix.
2. Should configuration-class selector failures (missing/misspelled variables, invalid `RUNNER_LABELS`) fail the job like `HOSTED_RUNNER` does, or stay as silent hosted fallback (C4)? The current split (one hard error, everything else silent) looks accidental.
3. Is Windows an intended target for `prepare` at all (C6), or only for the documented native procedure? The README's "Python 3.9+ ... verified Windows Python executable" suggests yes.
4. Can the selector PAT list organization-group runners accessible to the repository? If not, the full-inventory enforcement in C5 is only partial and the manual gate must stay documented as such.
5. Is the `--skill` vs `@<skill>` install syntax difference (C11) intentional (two CLI generations) or drift?
6. Assumption recorded: the orchestrator's override that "whole repo" means `github-runner/**` plus the README diff was applied; sibling skills, history, and the other report in this run directory were not read. The `--sha256` digest-prefix finding (C7) assumes the operator follows the `setup.md` example verbatim rather than the release-page checksum table.

Completion: report and sidecar written; no source, configuration, or git state was modified. This is the terminal action of the audit.

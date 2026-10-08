# setup-github-runner

Agent skill for checking a repository's self-hosted runners and carrying a user-selected local or remote macOS/Linux host from an empty starting point through account preparation, registration, persistent services and verified project CI with preferred-runner/hosted routing.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills), once the repository revision containing this skill is published:

```bash
npx skills add diegomarino/my-skills@setup-github-runner
# Add -g for user-level installation rather than the current project.
```

For this local worktree:

```bash
npx skills add . --list
npx skills add . --skill setup-github-runner
```

The portable format is a directory containing `SKILL.md` with YAML `name` and `description`, following the [Agent Skills specification](https://agentskills.io/specification). No plugin manifest is required. Optional `agents/openai.yaml` supplies Codex UI metadata.

## Use

Invoke `$setup-github-runner` explicitly in Codex or `/setup-github-runner` in [Claude Code](https://code.claude.com/docs/en/skills), then describe the repository, intended host and scope. Automatic invocation is disabled: Codex uses `policy.allow_implicit_invocation: false` in `agents/openai.yaml`; Claude Code uses `disable-model-invocation: true` in the skill frontmatter. A generic runner-related question is not an automatic trigger. Other agents must honor the explicit-only instruction; their support for these runtime controls may differ. Invocation syntax depends on the agent; it is not a shell command. The skill reports registration/access, host identity, service health, routing and any unchecked acceptance gates. It uses an available GitHub connector, authenticated `gh`, or GitHub UI; host access is required only for host checks and setup.

Diagnosis is read-only. Configuration follows the user's authorized scope; skill development never installs a live runner. The runtime account is dedicated and standard, distinct from the personal/admin account. Tokens stay in private local input or a secret-safe mechanism.

## Resources

| Resource | When to use |
| --- | --- |
| [Discovery](references/discovery.md) | Inventory the actual repository/host and establish missing access |
| [Credentials](references/credentials.md) | Prepare operator authentication, registration input or selector PAT/secret |
| [Setup](references/setup.md) | Select an official release, prepare a new instance and register it |
| [Platforms](references/platforms.md) | Create/verify the standard account and choose Linux or macOS service lifecycle |
| [CI](references/ci.md) | Configure the preferred selector and replace template checks with real project commands |
| [Verification](references/verification.md) | Read independent host/job/artifact receipts and diagnose a failing boundary |
| [prepare_runner.py](scripts/prepare_runner.py) | Verify/extract an archive without replacing an instance; inspect safe local state |
| [macos_service.py](scripts/macos_service.py) | Render a LaunchDaemon and concrete manual deployment plan |
| [remote_command.py](scripts/remote_command.py) | Render a quoted SSH invocation for a transferred privileged script |
| [select_runner.py](scripts/select_runner.py), [ci.yml](assets/ci.yml) | Copy/adapt the hosted selector and workflow into a target repository |

Helpers use Python 3.9+ and the standard library; discover/provision missing Python before use. Run them with `python3`, not by executable bits. Supported self-hosted targets are macOS and Linux; Windows host installation is outside scope. macOS data rendering and archive fixtures are tested locally; real account/service installation on Linux and macOS remains platform-specific live acceptance. The bundled selector supports github.com; GHES requires a reviewed adapter. The workflow deliberately fails until its project checks are supplied and requires explicit compatible `HOSTED_RUNNER` configuration.

## Helper interface

Use `prepare_runner.py prepare --help`, `prepare_runner.py inspect --help`, `macos_service.py --help`, or `remote_command.py --help` for argument meanings. Preparation requires a new instance path with a runtime-owned parent; rendering requires an existing private resolved staging directory. These helpers refuse conflicting state rather than overwrite it.

| Helper | Successful output | Failure |
| --- | --- | --- |
| Preparation | JSON receipt with `status: prepared`, version, digest and account; the instance contains `.preparation.json` | Nonzero exit and refusal reason; interrupted extraction retains `incomplete` state for [manual recovery](references/setup.md) |
| Inspection | JSON with directory/existence, safe registration identity and preparation fields; absent state is `null` | Nonzero exit for unsafe or malformed state; it never reads `.credentials` |
| macOS rendering | Paths of the new plist and manual command plan; no service activation | Nonzero exit for invalid inputs or existing artifacts |
| Remote command | One quoted SSH command; no connection or execution | Nonzero exit for invalid arguments |
| Selector | `runner=<JSON>` appended to `GITHUB_OUTPUT`, matching stdout; non-secret reason on stderr | Hosted fallback is successful routing; invalid fallback/output setup exits nonzero. See [inputs and reasons](references/ci.md). |

## Checks

Discovery: `npx skills add . --list` from the repository root. Workflow syntax requires [actionlint](https://github.com/rhysd/actionlint/blob/main/docs/install.md); follow its platform installation instructions (macOS Homebrew: `brew install actionlint`). The Python helpers and their tests need no third-party dependencies.

Optional authoring check: the `quick_validate.py` script belongs to the installed **skill-creator** skill, not this repository. Locate that skill using the agent's skill catalog and read its instructions. In Codex its usual location is `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py`; pass `setup-github-runner` as the argument. Older versions of that validator reject the documented Claude Code `disable-model-invocation` extension. If so, validate the standard fields using a temporary copy with only that extension removed, and separately check that the original boolean is `true` and the Codex implicit-invocation policy is `false`; do not remove the invocation controls from the shipped skill to satisfy an outdated validator. That validator imports PyYAML, so use an existing authoring environment with PyYAML or an isolated environment (for example `uv run --with pyyaml python /absolute/path/to/skill-creator/scripts/quick_validate.py setup-github-runner`). Do not add PyYAML to the runner helpers solely for authoring validation.

```bash
python3 -m unittest discover -s setup-github-runner/tests -v
python3 -m py_compile setup-github-runner/scripts/*.py
actionlint setup-github-runner/assets/ci.yml
```

Behavioral scenarios and observed results are in [tests/scenarios.md](tests/scenarios.md). The executable tests exercise selection, preparation guards, interrupted state, plist generation and remote quoting with fixtures/mocks. They do not prove a live runner, service, job or reboot works.

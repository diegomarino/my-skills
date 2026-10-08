# my-skills

Agent skills by [@diegomarino](https://github.com/diegomarino). Each folder is one self-contained skill: its `SKILL.md`, scripts, references, examples and tests live together, and each has its own README.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills), one skill at a time:

```bash
npx skills add diegomarino/my-skills@<skill>        # current project
npx skills add diegomarino/my-skills@<skill> -g     # all projects (user level)
```

Manual alternative: copy a skill folder into `~/.claude/skills/` (or `<repo>/.claude/skills/`).

## Skills

| Skill | What it does | Requires |
| --- | --- | --- |
| [`setup-github-runner`](setup-github-runner/) | Checks self-hosted runners and prepares a selected local/remote macOS/Linux host from zero through dedicated accounts, services and real CI with preferred-runner/hosted routing. | Python 3.9+ for bundled helpers; GitHub access and target host access for deployment |
| [`speckit-package-tasks`](speckit-package-tasks/) | Splits an approved [Spec Kit](https://github.com/github/spec-kit) `tasks.md` into a tracker-neutral `tasks-packages.md`: independently assignable packages with exact task coverage, dependency order, phase barriers and shared-path conflicts, checked by a deterministic validator. Planning only. | Python 3.9+ |
| [`speckit-orchestrate`](speckit-orchestrate/) | Runs those packages through assignment, independent review, verified delivery and cleanup with any executor (subagents, CLI agents, people) and delivery system, after a staged setup interview. Keeps an append-only evidence ledger. | Python 3.9+, git |

```bash
# Spec Kit: plan the work packages, then orchestrate them
npx skills add diegomarino/my-skills@speckit-package-tasks
npx skills add diegomarino/my-skills@speckit-orchestrate

# Set up a self-hosted GitHub Actions runner
npx skills add diegomarino/my-skills@setup-github-runner
```

The two Spec Kit skills work independently. When both are installed, `speckit-orchestrate` also runs the package validator.

## Checks

Skills with executable helpers ship automated tests:

```bash
cd <skill> && python3 -m unittest discover -s tests -v
```

`setup-github-runner` also includes [behavioral scenarios](setup-github-runner/tests/scenarios.md), helper fixtures and workflow syntax checks described in its README.

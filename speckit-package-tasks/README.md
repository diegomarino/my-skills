# speckit-package-tasks

Agent skill that turns an approved [Spec Kit](https://github.com/github/spec-kit) `tasks.md` into a tracker-neutral `tasks-packages.md`: coherent, independently assignable packages with exact source coverage, explicit dependency order, phase/story barriers, RED-with-GREEN grouping, and shared-path scheduling conflicts kept separate from dependencies. It plans and validates only; it never edits `tasks.md`, publishes issues, starts workers or touches code.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add diegomarino/my-skills@speckit-package-tasks        # this project
npx skills add diegomarino/my-skills@speckit-package-tasks -g     # all projects (user level)
```

Install `speckit-orchestrate` from the same repository to execute the packages afterwards. Manual alternative: copy this folder into `~/.claude/skills/` or `<repo>/.claude/skills/`; it is self-contained.

Runtime: Python 3.9+ (standard library only). `git` is used, when present, to find the repository root.

## Use

Ask the agent to package an approved feature ("split the tasks of specs/003-foo into work packages"), or invoke `/speckit-package-tasks` (append `regenerate` to replace an existing output). The scripts can also be run directly:

```bash
python3 scripts/work_packages.py resolve --json                      # find feature dir and a tasks.md with at least one task line
python3 scripts/work_packages.py validate specs/003-foo/tasks-packages.md [--json]
python3 scripts/work_packages.py promote specs/003-foo/tasks-packages.draft.md [--regenerate]
```

Exit codes: `0` ok (`validate` stays 0 when only warnings remain), `1` validation failed or `promote` refused because warnings remain (`WARNINGS_UNJUSTIFIED`), `2` usage/resolution error, `3` refused to replace an existing output.

Files written to the feature directory:
- **`tasks-packages.draft.md`** — the agent's working copy.
- **`tasks-packages.md`** — the promoted output. It is replaced only with `--regenerate`.
- **`tasks-packages.<UTC>.bak.md`** — the previous version, kept on every regeneration and never overwritten.

These names don't clash with an existing octooling `tasks-orca.md`, which stays untouched.

Format and diagnostics: [`references/tasks-packages-format.md`](references/tasks-packages-format.md). Worked example: [`examples/sample-feature`](examples/sample-feature/specs/001-account-login/).

## Checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/work_packages.py validate examples/sample-feature/specs/001-account-login/tasks-packages.md --repo-root examples/sample-feature
```

## Origin

Adapted from the octooling `speckit-orca` skill and its `audit`/`feature-dir` commands. Kept: package ids, heading/checkbox/field grammar, coverage, cycle, ordering, placeholder and path checks, feature-directory resolution order. Removed: Orca terminology, tracker aliases, parent/child integration branches, the four-wave ceiling. Added: verbatim task text, source hash binding, phase barriers, RED/GREEN co-location, prose dependency statements, declared scheduling conflicts, guarded promotion with backups.

## Limitations

- Phase barriers follow Spec Kit's documented model (shared phases gate, story phases are independent). A `tasks.md` that deliberately departs from it needs human judgment; the validator cannot be told about exceptions.
- Prose dependencies are recognized only in the form `T011 depends on T008/T010` (also `,`, `+`, `and`); other phrasings must be read by the agent.
- Feature resolution uses Spec Kit's bash `check-prerequisites.sh`; PowerShell-only installs fall back to `--feature-dir`, `SPECIFY_FEATURE_DIRECTORY` or `.specify/feature.json`.
- The validator proves structure, not meaning: a PASS still needs the semantic reread described in `SKILL.md`.

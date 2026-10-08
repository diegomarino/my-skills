---
name: speckit-package-tasks
description: Splits an approved Spec Kit tasks.md into a tracker-neutral tasks-packages.md of independently assignable packages (planning only). Use when asked to package, group or batch Spec Kit tasks for assignment, to validate an existing tasks-packages.md, or to regenerate it after tasks.md changed.
argument-hint: "Optional: regenerate"
---

# Spec Kit work packages

Turn an approved `tasks.md` into one tracker-neutral `tasks-packages.md`: a dependency graph of coherent packages, each carrying everything a worker needs. This skill is planning only. `tasks.md`, implementation code, trackers and workers stay untouched; publishing and execution belong to other workflows.

Scripts need Python 3.9+ and nothing else. Run them from the repository root; `SKILL_DIR` is this skill's folder (the base directory reported when the skill loads).

## 1. Resolve the source

```bash
python3 "$SKILL_DIR/scripts/work_packages.py" resolve --json [--feature-dir specs/NNN-name]
```

Use the resolved paths exactly; if `resolve` fails, ask the user for `--feature-dir`. `TASKS_FORMAT` means `tasks.md` has no `- [ ] T001 description` line: stop and report that, and do not draft. If `output_exists` is true and the user did not ask to `regenerate`, validate the existing file and report instead of drafting. When the request does not say the tasks are approved, confirm that with the user first. Read the repository's agent instructions (`AGENTS.md`, `CLAUDE.md`) and the whole `tasks.md`, including its Dependencies & Execution Order section, plus `spec.md`/`plan.md` where package acceptance needs them. Done when `resolve` exits 0 and every source is read.

## 2. Draft the graph

Write `tasks-packages.draft.md` in the feature directory using [`references/tasks-packages-format.md`](references/tasks-packages-format.md). `work_packages.py source-tasks --feature-dir <dir>` prints every task as a ready-to-paste Source tasks entry, grouped by phase, followed by the explicit dependencies and RED tasks the validator will enforce. Build the graph from source evidence only:

- **Coverage**: every source task appears in exactly one package, with its text copied verbatim.
- **Explicit dependencies**: every `(depends on T…)` clause and every "Tx depends on Ty" statement is ordered, inside one package or through a `Blocked by` path. Story-level links in prose ("US2 after the US1 checkpoint") are not machine-read: encode each one as `Blocked by` yourself.
- **Barriers**: shared phases (Setup, Foundational, Polish) wait for every earlier phase and gate every later one, and stay shared even if a task is labelled `[USn]`; user-story phases stay independent of each other unless the source links them.
- **RED with GREEN**: a failing-test task travels in the same package as every implementation task that depends on it, listed before them, so no package ever delivers a red test. A story-wide acceptance suite therefore pulls its whole story into one package; record that with a `Size justification`.
- **Parallel branches**: `Blocked by` records a source dependency or a phase barrier, never a convenient total order. Independent work stays unblocked.
- **Shared paths**: two packages that can run concurrently and share a primary path or an ownership write-path go under `## Scheduling conflicts`. That is a scheduling constraint; it never becomes `Blocked by`. Which ownership bullets count is in the format reference.
- **Self-sufficient packages**: objective, scope, constraints, ownership, primary paths, observable acceptance, verification and handoff together let a worker finish without opening `tasks.md`.
- **Checkboxes**: package checkboxes stay unchecked `[ ]`. Ticking one (`x` or `X`) is an error.

Where the source leaves a product decision, a dependency or an acceptance threshold open, keep the package `Ready: no — <the exact open question>` rather than inventing an answer. Done when `validate` has been run once on the draft, even if it fails.

## 3. Validate and repair

```bash
python3 "$SKILL_DIR/scripts/work_packages.py" validate specs/NNN-name/tasks-packages.draft.md
```

Loop generate → validate → repair → validate. Each `ERROR` names the package and a `fix:`; apply the smallest repair the diagnostic proves and rerun. Stop for human judgment when the repair would contradict explicit `tasks.md` text (for example, the source says Polish may start after one story while the phase barrier demands both), when it would require inventing semantics, or when a RED/GREEN repair would put more than 8 source tasks in one package or combine tasks that carry more than one distinct user-story label (split the test in `tasks.md`, or accept the large package; do not merge automatically). Which warnings a justification field silences, and which must be narrowed instead, is in [`references/tasks-packages-format.md`](references/tasks-packages-format.md). Done when validate is PASS and promote would succeed (no remaining warnings).

The validator is deterministic, not semantic. After PASS, reread each package against its source tasks: acceptance is observable, ownership boundaries are real, nothing was paraphrased into new behavior.

## 4. Promote

```bash
python3 "$SKILL_DIR/scripts/work_packages.py" promote specs/NNN-name/tasks-packages.draft.md [--regenerate]
```

`promote` revalidates and moves the draft into `tasks-packages.md`. It refuses while validation fails, or while any warning remains (`WARNINGS_UNJUSTIFIED`, draft unchanged). It refuses to replace an existing file unless the user explicitly asked to regenerate; with `--regenerate` it first keeps the previous version as `tasks-packages.<UTC>.bak.md`.

## Report

- resolved feature directory and how it was resolved
- package count, ready count, dependency depth, widest parallel level
- scheduling conflicts
- warnings with their justification
- open questions holding packages at `Ready: no`
- validator verdict and output path

Execution is a separate step (for example `speckit-orchestrate`); offer it rather than starting it.

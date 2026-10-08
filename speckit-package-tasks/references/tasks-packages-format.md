# tasks-packages.md format

The validator parses these forms exactly. A complete passing example lives in `examples/sample-feature/specs/001-account-login/tasks-packages.md`.

## Document skeleton

```markdown
---
feature: "001"
source: "specs/001-account-login/tasks.md"
source_sha256: "<tasks_sha256 from resolve>"
---

# Work packages: <feature title>

## Summary

<graph shape in prose: what gates what, which branches run in parallel, why>

## Scheduling conflicts

- `F001-P02` / `F001-P03`: `src/accounts/cli.py` — <why both packages touch it>

## F001-P01 — <title>
...one section per package...
```

- Front matter starts on line 1, has no BOM, and uses `key: "value"` with double quotes.
- `feature` must agree with the directory's `NNN-` prefix. `source` is the repository-relative path of this feature's `tasks.md`. `source_sha256` is its current hash, which binds the plan to the exact ledger it was derived from.
- `## Scheduling conflicts` is mandatory. Write `- None` when it is empty. List exactly the pairs of packages that can run concurrently (neither reaches the other through `Blocked by`) and that share a primary path or an ownership write-path. Backticked paths in Ownership count, except a bullet whose text starts with `Does not`, `Do not`, `Must not`, or `Never` (case insensitive). Paths are posix-normalized and trailing slashes are removed. A directory path overlaps every path beneath it. A compared path that normalizes to a single segment with no `/` and no `.` (a bare directory such as `src` or `tests`) is `BROAD_PATH`; narrow it. A root file such as `README.md` or `pyproject.toml` is specific and is not broad. That warning cannot be silenced.
- Package ids are `F<feature>-P<nn>`, numbered contiguously from `P01` in a topological order: every blocker has a lower number.

## Package section

```markdown
## F001-P02 — Password login

- [ ] F001-P02 [US1] Password login

**Ready**: yes

**Source tasks**:
- `T006` [US1] [RED] Write failing login tests ... in `tests/test_login.py`
- `T007` [US1] [GREEN] Implement `login(username, password)` in `src/accounts/login.py`

**Blocked by**:
- `F001-P01`

**Objective**: <one independently verifiable outcome>

**Scope**:
- <the coherent behavior this package owns, in execution order>

**Constraints**:
- <rules from spec/plan/repository instructions that bind this work, or None>

**Ownership**:
- <files/modules owned; what must not be touched>

**Primary paths**:
- `src/accounts/login.py`

**Acceptance criteria**:
- <observable result a reviewer can check>

**Verification**:
- <exact command or observable check>

**Handoff**:
- <what later packages may rely on, or "Terminal deliverable">
```

Syntax:
- The heading uses U+2014 (`—`) between the id and the title.
- The checkbox repeats the id and the title exactly and stays unchecked (`[ ]`). A marker of `x` or `X` is an error. Optional `[USn]` markers are informational.
- Fields are `**Name**: value`, with the colon outside the bold. A value either follows on the same line or continues as `- ` bullets. Indented lines continue the previous bullet.
- `Blocked by` is `None` or backticked ids only. A bare id is an error, so prose can never be mistaken for a dependency.

Meaning of each field:

| Field | Required | Meaning |
| --- | --- | --- |
| Ready | always | `yes`, or `no — <precise open question or blocker>`. Only `yes` packages may be assigned. |
| Source tasks | always | One entry per task: backticked id, then the task text copied verbatim from `tasks.md` (labels included). Order is execution order. |
| Blocked by | always | Logical dependencies only: an explicit source dependency or a phase barrier. |
| Objective | when ready | The single outcome that makes the package done. |
| Scope | when ready | The behavior to build; justify unusual sizing here. |
| Constraints | when ready | Binding rules; `None` is allowed. |
| Ownership | when ready | Owned files/modules and the do-not-touch boundary. Backticked paths are write-paths for conflict detection, except bullets that start with Does not / Do not / Must not / Never. |
| Primary paths | when ready | Backticked repository-relative paths that exist or are named in `tasks.md`. Together with ownership write-paths, used to detect shared-path conflicts. |
| Acceptance criteria | when ready | Observable results; enough for a worker and a reviewer without `tasks.md`. |
| Verification | when ready | Commands or checks that prove acceptance. |
| Handoff | when ready | What downstream packages may rely on. |
| Size justification | optional | Why a package stays outside 3–8 source tasks (for example a story-wide acceptance suite). Non-empty text silences the size warning and is listed in the summary. |
| Story mix justification | optional | Why one package carries more than one user-story label. Non-empty text silences the mixed-story warning. |
| Blocker justification | optional | A quote of the `tasks.md` sentence that justifies `Blocked by` edges the validator cannot derive. Non-empty text silences every `EXTRA_BLOCKER` warning on that package. |

A `Ready: no` package keeps every field it can state; the fields listed "when ready" become mandatory only at `Ready: yes`. Placeholders are rejected everywhere except in Source tasks text. In `Blocked by`, list direct dependencies; a blocker already reached through another listed blocker may be omitted.

## Source grammar the validator reads from tasks.md

- **Tasks**: `- [ ] T001 [P] [US1] [RED] text`. Indented lines continue the task text.
- **Phases**: `## Phase N: …`. A phase is a *story phase* when its heading says "User Story" or any of its tasks carries `[USn]`. Every other phase is *shared*. A heading that matches `\b(setup|foundational|polish)\b` (case insensitive) stays shared even when a task carries `[USn]`. A heading that says "User Story", and any other phase that becomes a story phase only because of `[USn]`, keep the rule above.
- **Barrier rule**: a shared phase must finish before any later phase starts, and waits for every earlier phase. Story phases do not wait for each other. Setup, Foundational, and Polish stay on this shared side of the barrier even if one of their tasks is labelled `[USn]`.
- **Explicit dependencies**: inline `(depends on T004)` clauses, and prose such as `T011 depends on T008/T010` anywhere in the file.
- **RED tasks**: `[RED]`-labelled tasks, plus every task under a `### …Tests…` subsection. `[RED→GREEN]` tasks are self-contained. The governed implementation is decided in this order:
  1. When implementation tasks explicitly depend on the test, **every one of them** shares its package and comes after it. A suite gating a whole story forces a whole-story package.
  2. Otherwise a `[RED]` task governs the next `[GREEN]` task (or else the next implementation task) in its phase.
  3. Otherwise a test-subsection task needs at least one implementation task of its phase and story after it in the same package.
- **Not machine-read**: story-level prose ("US2 after the US1 checkpoint"), parallel-example blocks and implementation strategy. Encode what they establish as `Blocked by` by hand.

## Diagnostics and repairs

`validate` exits 0 when the only findings are warnings (`ok` stays true) so the repair loop can read them. `promote` exits 1 with `WARNINGS_UNJUSTIFIED` and does not move the draft while any warning remains.

| Code | Repair |
| --- | --- |
| `MISSING_SOURCE_TASK` / `DUPLICATE_SOURCE_TASK` / `UNKNOWN_SOURCE_TASK` | Every task id exactly once; never invent ids. |
| `SOURCE_TASK_TEXT_MISMATCH` | Copy the text shown in `fix:` verbatim. |
| `SOURCE_CHANGED` | `tasks.md` changed after packaging. In a draft: re-derive the affected packages, then update `source_sha256`. In a promoted `tasks-packages.md`: report the drift and offer `regenerate`; edit it only through a regenerated draft. |
| `SOURCE_TASK_DEPENDENCY_UNORDERED` | Reorder within the package, or add the named blocker. |
| `PHASE_BARRIER_UNORDERED` | Add the named blocker. If `tasks.md` explicitly says otherwise, stop for human judgment. |
| `RED_SEPARATED_FROM_GREEN` | When merging the packages that own the test and its dependents would put more than 8 source tasks in one package, or would combine more than one user-story label, stop for human judgment: split the test in `tasks.md`, or accept the large package. Do not merge automatically. Smaller same-story repairs still merge those packages; moving the test next to only one dependent just moves the error. Add a `Size justification` if that smaller result is outside 3–8. |
| `EXTRA_BLOCKER` (warning) | A direct `Blocked by` edge that no task dependency, phase barrier, or other blocker path requires. Remove the edge, or quote the `tasks.md` sentence in `Blocker justification`. Not an error. |
| `BROAD_PATH` (warning) | A compared path (primary or ownership write-path) is a single segment with no `/` and no `.`. Narrow the path. Not silenceable. |
| `PACKAGE_CHECKBOX_CHECKED` | The package checkbox marker is `x` or `X`. Leave it as `[ ]`. |
| `PATH_CONFLICT_UNDECLARED` | List the pair under Scheduling conflicts. The shared paths may come from Primary paths or from ownership write-paths. Add `Blocked by` only if the source establishes a dependency. |
| `PATH_CONFLICT_STALE` | Remove the entry; the pair is ordered or no longer shares paths. |
| `BLOCKER_NOT_LOWER_NUMBERED` / `DEPENDENCY_CYCLE` | Renumber topologically. A real cycle means the grouping is wrong: split or merge packages. |
| `READY_FIELDS_INCOMPLETE` / `NOT_READY_WITHOUT_REASON` | Fill the fields, or state the open question after `no —`. |
| `PRIMARY_PATH_NOT_DECLARED` / `PRIMARY_PATH_OUTSIDE_REPOSITORY` | Use paths that exist or that `tasks.md` names, inside the repository. |
| `TEMPLATE_PLACEHOLDER` | Replace every `<…>` placeholder. |
| Syntax codes (`FRONT_MATTER_*`, `INVALID_*`, `PACKAGE_*`, `MISSING_FIELD`, `UNQUOTED_BLOCKER`) | Match the grammar above. |
| `WARNINGS_UNJUSTIFIED` (promote) | Not a validate diagnostic. Promote refuses, exit 1, draft unchanged, until every warning is repaired or silenced by the field named above. |

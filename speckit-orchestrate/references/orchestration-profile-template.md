# Run profile template

Copy into `<feature>/orchestration.md` and fill every value from the setup interview. `ledger.py check-profile <path>` validates the result.

```markdown
---
harness: "<who runs workers: claude-code-subagents | claude-cli | codex-cli | humans | ...>"
implement_model: "<model and effort for implementation, or n/a>"
review_model: "<model for independent review; prefer a different model or a fresh context>"
isolation: "<worktree | checkout | external>"
worktree_pattern: "<e.g. ../.worktrees/{feature}-{package}; required for worktree>"
branch_pattern: "<e.g. wp/{feature}/{package}; required for worktree>"
base_branch: "<delivery target, e.g. main>"
max_parallel: "<1 = sequential>"
review_by: "<agent | human>"
delivery_mode: "<local-merge | pull-request | patch | ...>"
merge_by: "<agent | human>"
tracker: "<none | tracker name>"
on_finish: "<what happens after the gate passes>"
authorized: "<comma-separated subset of assign, review, push, merge, tracker, release; empty asks every time>"
---

# Orchestration profile: <feature>

## Executor: <system name>
- identity: <what the assignment reference is>
- assign: <supported|human|unsupported> — evidence: <receipt>
- observe: <status> — evidence: <outcome + head>
- find: <status> — evidence: <lookup by operation key>
- release: <status> — evidence: <proof the resource is gone>

## Delivery: <system name>
- identity: <change ref + head + target>
- submit: <status> — evidence: <change reference>
- deliver: <status> — evidence: <merge receipt>
- observe_delivery: <status> — evidence: <observation in target>

## Tracker: <name, or omit the section when tracker is none>
- project_status: <status> — evidence: <write receipt>

## Instructions

<Service-specific commands for every supported operation, how the operation key is attached,
how the briefs in references/briefs.md are transported, the checks run on each worker return,
the integration verification command run on the target after each delivery, and the on-finish steps.>
```

Rules the checker enforces:
- Every operation of a present role is declared.
- `supported` and `human` operations name their evidence.
- `assign`, `observe` and `observe_delivery` cannot be `unsupported`.
- `max_parallel > 1` needs `worktree` or `external` isolation.
- `merge_by: "agent"` needs `deliver: supported` and the `merge` token in `authorized`.
- `authorized` is a comma-separated subset of `assign`, `review`, `push`, `merge`, `tracker`, `release`. Empty is allowed; an unknown token is an error.
- A tracker other than `none` needs a `## Tracker` section.

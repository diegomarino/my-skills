---
harness: "claude-code-subagents"
implement_model: "sonnet"
review_model: "opus"
isolation: "worktree"
worktree_pattern: "../.worktrees/{feature}-{package}"
branch_pattern: "wp/{feature}/{package}"
base_branch: "main"
max_parallel: "2"
review_by: "agent"
delivery_mode: "local-merge"
merge_by: "agent"
tracker: "none"
on_finish: "remove coordinator-created worktrees and merged package branches, then print the final summary"
authorized: "assign, review, merge, release"
---

# Orchestration profile: Claude Code subagents + local git

Starting point for the setup interview. Not tested against a live Claude Code session; confirm every operation with a dry run during setup.

## Executor: Claude Code subagents
- identity: the agent id returned when the subagent is launched
- assign: supported — evidence: the Agent tool launch result with its agent id
- observe: supported — evidence: the subagent's final report plus `git -C <worktree> rev-parse HEAD`
- find: unsupported
- release: supported — evidence: `git worktree remove <path>` exit 0 and the path absent from `git worktree list --porcelain`

## Delivery: local git
- identity: package branch + head SHA + base_branch
- submit: unsupported
- observe_delivery: supported — evidence: `git merge-base --is-ancestor <head> <base_branch>` exit 0
- deliver: supported — evidence: `git merge --no-ff <branch>` exit 0 and the merge commit SHA

## Instructions

- **Prepare.** `git worktree add -b wp/<feature>/<package> ../.worktrees/<feature>-<package> <base_branch>`, created from the base *after* the package's blockers were delivered. Record it with `ledger.py resource <path> --action created --owner coordinator --package <pkg> --via assign --evidence "<git output>"`. Coordinator-created worktrees are used instead of the Agent tool's own worktree isolation, which may branch from the remote default branch rather than the local base.
- **Assign.** One subagent per operation, through the Agent tool, always with an explicit `model` (`implement_model` for implement/fix, `review_model` for review); an omitted model inherits the session's. The prompt is the implementer brief from `references/briefs.md`: operation key on line 1, the worktree's absolute path as the only writable place, the package section verbatim, upstream facts, and the 15-line report contract.
- **Check each return** before recording `completed`:
  - `git -C <worktree> status --porcelain` is empty;
  - `git -C <worktree> rev-parse HEAD` equals the reported head and differs from the base;
  - `git -C <worktree> log --grep "Orchestration-Op: <op>"` finds the commit;
  - `git -C <worktree> diff --name-only <base>...HEAD` stays inside the package's ownership.
- **Review.** A new subagent (never the implementer resumed) on `review_model`, with the reviewer brief: `git diff <base>...<head>` saved to `<feature>/.orchestration/reviews/<op>.diff`, the acceptance criteria, the verification commands and the implementer report as claims.
- **Fix.** Resume the original implementer with the surviving findings for the first rounds; switch to a fresh subagent on a stronger model before the ledger's cap.
- **Lost result.** `find` is unsupported here. A commit carrying the operation trailer is evidence an assignment existed; its absence proves nothing. Ask the user and record `--via user --attested-by`.
- **Deliver.** From the main checkout on `base_branch`: `git merge --no-ff wp/<feature>/<package> -m "Deliver <package>"`, then `git merge-base --is-ancestor <head> <base_branch>`. Then run the integration verification: the project's full test command on `base_branch`.
- **Finish.** `git worktree remove <path>` and `git branch -d <branch>` for each delivered package; confirm with `git worktree list`.

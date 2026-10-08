---
harness: "codex-cli"
implement_model: "codex default model (confirm during setup)"
review_model: "a different model than implement_model (confirm during setup)"
isolation: "worktree"
worktree_pattern: "../.worktrees/{feature}-{package}"
branch_pattern: "wp/{feature}/{package}"
base_branch: "main"
max_parallel: "3"
review_by: "agent"
delivery_mode: "pull-request"
merge_by: "human"
tracker: "none"
on_finish: "leave PR branches until maintainers merge; remove coordinator-created worktrees of delivered packages; print the final summary"
authorized: "assign, review, push"
---

# Orchestration profile: Codex CLI workers + GitHub pull requests

Starting point for the setup interview. Not tested against live Codex or GitHub; verify `codex exec --help` and `gh auth status` during setup and adjust flags to the installed versions.

## Executor: Codex CLI (`codex exec`)
- identity: the log file `.orchestration/logs/<op key with : replaced by ->.jsonl` written by the run
- assign: supported — evidence: the background `codex exec` process started and its log file created
- observe: supported — evidence: the run's final message in its log plus `git -C <worktree> rev-parse HEAD`
- find: supported — evidence: presence or absence of the log file named by the operation key
- release: supported — evidence: `git worktree remove <path>` exit 0 and the path absent from `git worktree list --porcelain`

## Delivery: GitHub pull requests
- identity: PR URL + head SHA + base branch
- submit: supported — evidence: `gh pr create --base <base_branch> --head <branch>` returns the PR URL
- observe_delivery: supported — evidence: `gh pr view <url> --json state,baseRefName,headRefOid,mergeCommit` shows MERGED into base_branch
- deliver: human — evidence: a maintainer merged the PR (confirmed by observe_delivery)

## Instructions

- Assign: `codex exec -C <worktree> -m <model> --json "<brief>" > .orchestration/logs/<op>.jsonl 2>&1 &`. The brief starts with the operation key and contains the package section verbatim. It tells the worker to commit with trailer `Orchestration-Op: <op key>`, report the final SHA, and never push or merge.
- Review: run a fresh `codex exec` with `review_model` in a detached worktree at the pinned head (`git worktree add --detach <path> <head>`). Its brief is the diff against base plus the acceptance criteria.
- After a passing review, `git push -u origin <branch>` and `gh pr create`. The PR body lists the package's acceptance criteria and the reviewed head.
- **Observation with gh-delta** (when installed): read the run's observer on each inspect. Add this PR to it. Recording `delivered` still uses the `observe_delivery` evidence above.
- Record `delivered` only from `gh pr view` showing `MERGED` with `baseRefName == base_branch`. If `headRefOid` differs from the reviewed head, report a review gap.

---
harness: "claude-cli"
implement_model: "haiku"
review_model: "sonnet"
isolation: "worktree"
worktree_pattern: "{repo}/.worktrees/{package}"
branch_pattern: "wp/{package}"
base_branch: "main"
max_parallel: "2"
review_by: "agent"
delivery_mode: "pull-request"
merge_by: "agent"
tracker: "none"
on_finish: "remove package worktrees and merged local branches, then print the summary with per-session costs"
authorized: "assign, review, push, merge"
---

# Orchestration profile: `claude -p` workers + GitHub pull requests

Starting point for the setup interview. Exercised live in a pilot on 2026-10-07 (Claude Code 2.1.285, gh 2.101.0, a private GitHub repository): assignment, `find`, completion checks, review, fix, fresh review, PR creation, merge and delivery observation all worked. Confirm the flags against `claude --help` and `gh auth status` during setup.

## Executor: Claude Code CLI (`claude -p`)
- identity: session id = uuid5(NAMESPACE_URL, "<run name>:" + operation key), passed with --session-id
- assign: supported — evidence: the process started with that --session-id and its transcript file exists
- observe: supported — evidence: the result JSON (`subtype`, `session_id`, `total_cost_usd`) plus the completion checks
- find: supported — evidence: presence or absence of ~/.claude/projects/<cwd slug>/<session id>.jsonl
- release: supported — evidence: `git worktree remove` exit 0 and the path absent from `git worktree list`

## Delivery: GitHub pull requests
- identity: PR URL + head SHA + base_branch
- submit: supported — evidence: `gh pr create` returns the PR URL
- deliver: supported — evidence: `gh pr merge <url> --merge` exit 0
- observe_delivery: supported — evidence: `gh pr view <url> --json state,baseRefName,headRefOid,mergeCommit` shows MERGED into base_branch, and `git merge-base --is-ancestor <head> origin/<base_branch>` exit 0

## Instructions

- **Session ids** are deterministic, so `find` works after a lost result: `python3 -c "import uuid; print(uuid.uuid5(uuid.NAMESPACE_URL, '<run>:<op>'))"`, then look for `<id>.jsonl` under `~/.claude/projects/`.
- **Worktree**: `git worktree add -b wp/<pkg> .worktrees/<pkg> <base_branch>` after pulling delivered blockers; add `.worktrees/` to `.gitignore`.
- **Implementer**, run from the worktree, prompt = implementer brief:
  `claude -p --model <implement_model> --session-id <id> --output-format json --permission-mode acceptEdits --add-dir <reports dir> --allowedTools Read Edit Write Glob Grep "Bash(git add:*)" "Bash(git commit:*)" "Bash(git status:*)" "Bash(git diff:*)" "Bash(git log:*)" "Bash(git rev-parse:*)" "Bash(<test runner>:*)" -- "<brief>"`.
  Grant tools explicitly; do not use `--dangerously-skip-permissions`. `--output-format json` prints a JSON array whose last element is the result.
- **Reviewer**: same command with `--model <review_model>`, a new session id, `--permission-mode default` and read-only tools (`Read Glob Grep "Bash(git diff:*)" "Bash(git log:*)" "Bash(git show:*)"` plus the test runner).
- **Inherited configuration**: `claude -p` loads the user's global CLAUDE.md, output style and hooks, so reports may carry extra text; parse the report block. Expect roughly $0.10–0.25 per session for small packages.
- **Delivery**: `git push -u origin wp/<pkg>`, `gh pr create --base <base_branch> --head wp/<pkg>`, `gh pr merge <url> --merge`, `git pull`, then observe and run the full test command on the base branch.
- **Observation with gh-delta** (when installed): read the run's observer on each inspect. Add this PR to it. Recording `delivered` still uses the `observe_delivery` evidence above.
- **Clean-up**: deleting a test repository needs the `delete_repo` scope (`gh auth refresh -h github.com -s delete_repo`), which the user grants interactively.

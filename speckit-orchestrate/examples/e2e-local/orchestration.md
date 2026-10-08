---
harness: "local-script"
implement_model: "n/a (scripted worker)"
review_model: "n/a (scripted reviewer)"
isolation: "worktree"
worktree_pattern: "{repo}/.worktrees/{package}"
branch_pattern: "wp/{package}"
base_branch: "main"
max_parallel: "2"
review_by: "agent"
delivery_mode: "local-merge"
merge_by: "agent"
tracker: "none"
on_finish: "remove package worktrees and merged branches"
authorized: "assign, review, merge, release"
---

# Orchestration profile: local scripted worker (e2e example)

The worker is `worker.sh`, which makes a real commit in a real worktree. All evidence is local git output.

## Executor: worker.sh
- identity: the run id printed by worker.sh
- assign: supported — evidence: worker.sh exit 0 and its printed run id
- observe: supported — evidence: `git -C <worktree> rev-parse HEAD`
- find: supported — evidence: `git log --grep "Orchestration-Op: <op>" <branch>` finds the commit
- release: supported — evidence: `git worktree remove` exit 0 and the path absent from `git worktree list`

## Delivery: local git
- identity: package branch + head SHA + main
- submit: unsupported
- observe_delivery: supported — evidence: `git merge-base --is-ancestor <head> main` exit 0
- deliver: supported — evidence: `git merge --no-ff` exit 0 and the merge commit SHA

## Instructions

`run_e2e.py` plays the coordinator and follows `SKILL.md` literally. `worker.sh` plays the executor.

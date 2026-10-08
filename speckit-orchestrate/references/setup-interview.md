# Setup interview

Settle how the work will run before any assignment, one stage at a time. In each stage:

1. Start from the probe (`scripts/probe_env.py --feature-dir <dir>`) and any existing `orchestration.md`.
2. Propose a recommended answer for every question the facts support, and say which fact grounds it.
3. Say plainly what could not be verified (a CLI on PATH may still be unauthenticated; a model name may be unavailable).
4. Ask the user to confirm or change. Use the harness's structured question tool when there is one, at most four questions per stage.
5. Skip any question the environment or the user's request already answers. Re-ask only what changed. When the remaining stages fit in four questions, ask them together.

When a stage settles a capability the coordinator will rely on (a harness, a CLI, a forge), check it with one harmless dry operation before moving on: list sessions, `gh auth status`, `git worktree list`. If the check fails, offer the alternatives; never assume the capability works.

## Stage 1: Environment and plan

- Which feature runs, and is its `tasks-packages.md` valid and current? `ledger.py init` runs the `speckit-package-tasks` validator when that skill is installed beside this one, and always re-checks the graph and the source hash.
- A feature with `tasks.md` but no valid `tasks-packages.md` is not ready to orchestrate. Offer to produce one with `speckit-package-tasks` when it is installed, and otherwise stop. Packages, not tasks, are the unit of assignment.
- Base branch. Suggest the current branch or `default_branch_guess`. A dirty tree or a detached HEAD blocks setup until the user decides.

## Stage 2: Execution

- **Harness**: who runs the workers.
  - Options: in-session subagents, `claude -p`, `codex exec`, another CLI agent, people, or a cloud agent.
  - Recommend the current harness when `harness_hints` detects one, plus any agent CLI present on PATH.
- **Models**:
  - The implementation model and effort.
  - The review model. Recommend a different model, or at least a fresh context, so the review is independent.
  - Default to a medium-capability model with medium effort. Recommend a stronger model or effort only when the package has material technical complexity, ambiguity, high risk, or needs unusually deep review; state the reason in one sentence.
  - `n/a` for people.
- **Isolation**:
  - A worktree per package. Recommend this whenever git worktrees are supported and work may run in parallel. Agree the path pattern (e.g. `../.worktrees/{feature}-{package}`) and the branch pattern (e.g. `wp/{feature}/{package}`).
  - A shared checkout. Sequential only.
  - External. The workers bring their own environment.
- **Parallelism**: `max_parallel`.
  - Recommend the widest level reported by the package validator, capped by the user's cost and attention limits.
  - `1` means sequential.
  - Shared-path conflicts and dependencies still serialize work automatically.
  - Only open implement and fix operations count toward `max_parallel`; an open review does not take a slot.

## Stage 3: Review and delivery

- **Reviewer**: an independent agent with the review model, or a person. A review is always pinned to the exact head it judged, and a new commit needs a fresh review.
- **Delivery mode**:
  - Local merge into the base branch.
  - A PR/MR to a remote. Requires a remote and a forge CLI.
  - Patch or branch handover only.

  Recommend a PR when the probe shows a remote and the forge CLI passes its auth check (`gh auth status`, `glab auth status`). Otherwise recommend local merge.
- **Who merges**: the agent, only if the user explicitly authorizes it for this run, or a person. Recommend a person for PR delivery and the agent for local merge.
- **GitHub observation**: when PRs or issues live on GitHub and the probe finds `gh-delta`, recommend one observer for the whole run, left running from setup until `on_finish`. Dry-run `gh-delta --version`. The gh-delta skill starts it and owns its identity. This run reads that observer on each inspect. It does not launch a wait per PR and shut it down after the merge. gh-delta only observes: merges, comments and issue writes stay with the profile's `deliver` and tracker operations.
- **Authorization**: a comma-separated subset of `assign`, `review`, `push`, `merge`, `tracker`, `release`. Empty means every action asks first. Include `merge` when the agent merges. Anything outside the list asks first.

## Stage 4: Tracker and finish

- **Tracker**: none, or which one. Recommend `none` unless the user already tracks this feature somewhere. A tracker is a projection only: it is never the source of the graph or of delivery truth.
- **On finish**: options are
  - remove the coordinator-created worktrees and merged branches;
  - leave everything in place for inspection;
  - open a feature-level PR;
  - print the final summary;
  - send a notification.

  Recommend removing the coordinator-created worktrees and merged branches, then printing the summary.

## Close the interview

Write `<feature>/orchestration.md` from `orchestration-profile-template.md`: start from the closest `examples/profiles/*.md` or a profile the user supplied, and keep service-specific commands under `## Instructions`. Run `ledger.py check-profile <feature>/orchestration.md` until it passes, show the profile to the user, and only after confirmation run `ledger.py --feature-dir <feature> init`.

# Walkthrough: Claude Code subagents instead of a scripted worker

The e2e example (`e2e-local/`) runs a scripted executor that can answer every operation, including `find`. This walkthrough runs the same plan against a different executor model: Claude Code subagents working in coordinator-created worktrees, with local git delivery (`profiles/claude-code-subagents-local-git.md`). The comparison shows which steps change and where the coordinator must hand a decision to the user.

**Verification status.**
- Locally verified: the profile passes `check-profile`. The ledger behavior below is exercised by `tests/test_ledger.py::ExecutorModelWalkthrough` (the unsupported `find`, the user attestation, the retry numbering).
- Not verified: no live Claude Code session was driven by this walkthrough. Agent-tool details (the result shape, model names, how ids are surfaced) are untested assumptions that the setup interview must confirm with a dry run.

## Setup differences

| Interview answer | e2e-local | This model |
| --- | --- | --- |
| harness | `local-script` | `claude-code-subagents` |
| models | n/a | `sonnet` implements, `opus` reviews (a fresh subagent each time) |
| executor.find | supported (`git log --grep` on the op key) | **unsupported**: a lost Agent result cannot be looked up |
| executor.release | `git worktree remove` | same |
| max_parallel | 2 | 2, but the worktrees must not overlap |

## One package, step by step

```bash
L="python3 $SKILL_DIR/scripts/ledger.py --feature-dir specs/001-account-login"
$L next                                    # → start F001-P01 implement
$L request F001-P01 implement              # → op F001-P01:implement:1
git worktree add -b wp/001/F001-P01 ../.worktrees/001-F001-P01 main
$L resource ../.worktrees/001-F001-P01 --action created --owner coordinator --package F001-P01 \
   --via assign --evidence "git worktree add exit 0"
```

1. **Assign.** Launch a subagent: `model: sonnet`, and a prompt whose first line is `F001-P01:implement:1`, followed by the package section verbatim, the worktree path, and the commit-trailer rule. Record the receipt: `$L accepted F001-P01:implement:1 --assignment <agent id> --via assign --evidence "Agent launch returned <agent id>"`.
2. **Lost result (the case that differs).** If the session restarts before the receipt is recorded, the operation stays `implement-requested`, and `request` is refused with `UNCERTAIN_OPERATION`. With `find` unsupported, `absent --via find` is refused with `UNSUPPORTED_CAPABILITY`. The coordinator asks the user, who can check `git -C <worktree> log` or the session list. It then records their answer: `$L absent F001-P01:implement:1 --via user --attested-by <user> --evidence "<user>: no subagent running, worktree has no commits"`, or `accepted … --via user` if one does exist. Only then does `request` issue `F001-P01:implement:2`.
3. **Complete.** When the subagent reports, verify with `git -C <worktree> rev-parse HEAD` and record `completed … --head <sha> --via observe`.
4. **Review.** `$L request F001-P01 review` pins the head. Launch a new `opus` subagent (never resume the implementer) and give it the diff against `main` plus the acceptance criteria. Record `accepted` with the reviewer's agent id; a reuse of the implementer's id is refused (`REVIEW_NOT_INDEPENDENT`). Then record `reviewed --head <sha> --verdict …`. If the verdict is `changes-requested`, request `fix`, give a new subagent (or the original one) the findings, and require a fresh review of the new head.
5. **Deliver.** This happens only inside `authorized` (here: local merge, never push). Run `git merge --no-ff wp/001/F001-P01`, observe with `git merge-base --is-ancestor <head> main`, and record `delivered … --via observe_delivery`.
6. **Release.** Run `git worktree remove`, check `git worktree list`, then `resource … --action released --via release`.

## What would change for other models

- **People through GitHub Issues** (`profiles/humans-github-issues.md`): `assign` and `observe` are `human`, so every receipt needs `--attested-by`. `find` searches issue titles by op key. Resources belong to people, so `release` is unsupported and the ledger refuses to release a user-owned resource. Covered by `tests/test_ledger.py::ExecutorModelWalkthrough`.
- **Codex CLI + pull requests** (`profiles/codex-cli-github-pr.md`): `find` becomes a log-file lookup, delivery is a PR merged by a human, and `delivered` is recorded only from `gh pr view` showing MERGED into the base branch. This profile is checked only for structure; nothing was run against Codex or GitHub.

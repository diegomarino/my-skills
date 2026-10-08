# speckit-orchestrate

Agent skill that coordinates approved Spec Kit work packages (`tasks-packages.md`, produced by `speckit-package-tasks` or written by hand in the same format). It moves them through readiness selection, assignment, implementation, independent review, verified delivery and resource cleanup, and it keeps those facts distinct and evidenced. It works with any executor, delivery system and optional tracker that you describe in a run profile. It ships no service integration, does not simulate a universal executor, and never requires a tracker.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add diegomarino/my-skills@speckit-orchestrate          # this project
npx skills add diegomarino/my-skills@speckit-orchestrate -g       # all projects (user level)
npx skills add diegomarino/my-skills@speckit-package-tasks        # recommended: produces and validates the plan
```

The skill works alone; when `speckit-package-tasks` is installed beside it, its validator is used as well. Manual alternative: copy this folder into `~/.claude/skills/` or `<repo>/.claude/skills/`.

Runtime: Python 3.9+ (standard library only) and `git`.

## Use

Ask the agent to run or resume a feature ("orchestrate specs/003-foo", "continue the run"). Before anything executes, the agent interviews you in four stages ([`references/setup-interview.md`](references/setup-interview.md)):

1. Environment
2. Execution: harness, worker models, worktrees, parallelism
3. Review and delivery
4. Tracker and finish

Each stage comes with recommendations grounded in a read-only probe. The answers become `<feature>/orchestration.md`, which you confirm.

Scripts:

```bash
python3 scripts/probe_env.py --feature-dir specs/003-foo          # read-only environment facts
python3 scripts/ledger.py check-profile specs/003-foo/orchestration.md
python3 scripts/ledger.py --feature-dir specs/003-foo init
python3 scripts/ledger.py --feature-dir specs/003-foo next          # what may start / deliver / why others wait
python3 scripts/ledger.py --feature-dir specs/003-foo status
python3 scripts/ledger.py --feature-dir specs/003-foo gate          # exit 0 only when everything is verified
```

The recording commands are `request`, `accepted`, `absent`, `completed`, `reviewed`, `delivered` and `resource`. `halt` and `resume` stop and restart the line. `check-completion` is read-only. `--help` lists their flags. Exit codes: `0` ok, `1` refused or gate failed, `2` unreadable inputs.

## Integration contract

Full text: [`references/integration-contract.md`](references/integration-contract.md). Profile template: [`references/orchestration-profile-template.md`](references/orchestration-profile-template.md).

| Role | Operations | Identity |
| --- | --- | --- |
| Executor (required) | `assign`, `observe` (required); `find`, `release` (optional) | executor-issued assignment reference; review ≠ implementation |
| Delivery (required) | `observe_delivery` (required); `submit`, `deliver` | change reference + head SHA + target branch |
| Tracker (optional) | `project_status` | write receipt; projection only |

- **Operation status.** Each operation is declared `supported`, `human` (needs `--attested-by`) or `unsupported`.
- **Unsupported operations.** The ledger refuses evidence from an unsupported operation, and the decision goes to the user. If the system cannot say whether an assignment exists, `--via user --attested-by` records the person's answer as an attestation, never as a receipt.
- **Where commands live.** Service-specific commands live only in the profile's `## Instructions`.

Starting-point profiles live in [`examples/profiles/`](examples/profiles/): `claude -p` workers with GitHub PRs (exercised live), Claude Code subagents with local git, Codex CLI with GitHub PRs, and people via GitHub Issues.

## Safety properties

Each bullet names who enforces it. The ledger never sees git, the executor, or verification commands except through `check-completion` and the records the coordinator writes.

- **Append-only records.** Ledger: contiguous JSONL sequence numbers. A partial, reordered or removed record is refused, never repaired.
- **Duplicate execution.** Ledger: one active operation per package. Assignment references are unique.
- **Ordering and conflicts.** Ledger: direct blockers must already be delivered, shared primary paths stay serialized until delivery, and `max_parallel` counts only open implement and fix operations. An open review does not take a slot.
- **Completion.** Ledger: `check-completion` checks the worktree head, a clean tree, the `Orchestration-Op` trailer and ownership paths, including while halted. Coordinator: run it before `completed --outcome succeeded`, and still rerun the package verification commands. The ledger does not run those commands.
- **Delivery.** Ledger: `delivered` needs an `observe_delivery` observation into `base_branch`, delivered blockers, the package's current head, no open operation, and state `ready-to-deliver`. An external merge of the current head from `needs-review` or `changes-requested` needs `--attested-by` and `--evidence`; a head with no passing review stays a review-gap warning. A merge receipt alone is refused. A passing reviewed delivery needs no attestation.
- **Reviews.** Ledger: pinned to a head, assignment distinct from the implementer, stale heads refused.
- **Stop the line.** Ledger: `halt` refuses new `request`s and blocks `gate` until `resume --attested-by --evidence`. Coordinator: record `halt` for a failed integration check or any other stop-the-line failure. Independent authorized work does not continue while the line is stopped.
- **Authorization.** Ledger: `check-profile` accepts only the tokens `assign`, `review`, `push`, `merge`, `tracker` and `release`, and refuses `merge_by: agent` without `merge`. Coordinator: ask before any action outside that list. The ledger does not intercept git.
- **Resources.** Ledger: only coordinator-owned resources can be released, and not while their package is active.
- **Drift and rebind.** Ledger: new requests stop when the plan, profile or `tasks.md` changes. Settings stay at the bound snapshot until `init --rebind`. Rebind is refused while an operation is unconfirmed, if history would move onto different source tasks, or if a package with history would lose a blocker or a primary path (`REBIND_LOOSENS`, unless attested). Adding a blocker or a path is allowed.
- **Package validator.** Ledger: `init` runs the sibling `speckit-package-tasks` validator when it is installed and refuses a failing plan. Warnings do not fail init. If the validator is absent, init warns and records `plan_validated: false`, which `status` shows.

## Checks

```bash
python3 -m unittest discover -s tests -v       # ledger, profiles, probe, executor-model walkthrough, e2e
python3 examples/e2e-local/run_e2e.py          # temporary git repo, scripted worker, real git evidence
```

The walkthrough for a different executor model is [`examples/walkthrough-subagents.md`](examples/walkthrough-subagents.md).

## Origin

Adapted from the octooling `speckit-orca-dispatch`, `project-coordination` and `speckit-orca-publish` skills and their fleet/sync/dispatch-start state model.

Kept:
- Accepted, settled, delivered and released as separate facts.
- Operation keys and exact reconciliation in place of duplicate dispatch.
- Pinned, independent, fresh reviews.
- Delivery only from a fresh observation into the expected target.
- Action-scoped uncertainty.
- Ownership checks before release.
- Tracker as projection.

Removed: Orca's FIFO/terminal protocol, the octooling CLI, Linear/GitHub identities, integration branches, and notice/digest transport.

## Limitations

- **Records, not observations.** The ledger records evidence that the agent reports. It cannot observe external systems, so the quality of the evidence depends on the agent following the profile.
- **Live coverage is partial.** A pilot on 2026-10-07 ran the `claude -p` + GitHub PR profile end to end against a private repository. It covered setup interview, assignment with `find`, completion checks, review, fix, fresh review, PR merge, delivery observation and a stop-the-line on a plan defect. Claude Code subagents, Codex, GitLab and trackers remain untested; their profiles are starting points that the setup interview must dry-run.
- **Single coordinator per ledger.** One coordinator per ledger is assumed. Appends are locked with `fcntl` on POSIX, and Windows has no lock.
- **Tracker projection.** Tracker writes are not recorded in the ledger. Pending projections are reported by the agent, not enforced.
- **Probe limits.** The probe reports CLIs present on PATH, not whether they are authenticated.

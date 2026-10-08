# Integration contract

The skill coordinates three roles. They may be one system or three. Service-specific commands never live in `SKILL.md`; they live in the run profile (`<feature>/orchestration.md`), supplied by the user or adapted from `examples/profiles/`.

Every operation is declared with one status:

- `supported`: the coordinator can perform it and obtain the stated evidence.
- `human`: a person performs it or confirms it. The ledger records it only with `--attested-by`.
- `unsupported`: the system cannot do it. The ledger refuses evidence "from" it, and any decision that depends on it goes to a human. Never emulate an unsupported operation with a weaker one, and never fill its receipt in by inference.

## Executor (required)

Runs one assignment: implement, review or fix one package.

Identity: the executor-issued assignment reference (task id, session id, issue assignment, job id). It must differ between the implementation and the review of the same package.

| Operation | Input | Success evidence | Required |
| --- | --- | --- | --- |
| `assign` | operation key, package brief, branch/worktree, model | the executor's acceptance receipt carrying the assignment reference | supported or human |
| `observe` | assignment reference | a terminal outcome (succeeded/failed), and for success the produced head (commit SHA) plus any change reference | supported or human |
| `find` | operation key | proof that an assignment for this key exists (→ `accepted`) or provably does not (→ `absent`) | optional; without it, an unconfirmed assignment needs a human |
| `release` | resource reference | proof that the resource (worktree, session, sandbox) no longer exists | optional; without it, resources can only be retained |

The operation key (`F001-P02:implement:1`) must travel with the assignment (task title, branch name, prompt header) so that `find` can recognize it later.

## Delivery (required)

Integrates a reviewed head into the expected target (`base_branch`).

Identity: change reference (branch, PR/MR URL, patch path) plus head SHA plus target.

| Operation | Success evidence | Required |
| --- | --- | --- |
| `submit` | change reference pointing at the head | optional (`unsupported` when workers hand over commits directly) |
| `deliver` | merge/integration receipt | `supported` only if `merge_by: "agent"`; else `human` or `unsupported` |
| `observe_delivery` | a fresh observation that the head (or a commit containing it) is in the target: e.g. `git merge-base --is-ancestor <head> <target>` exit 0, or a forge reporting MERGED into the target | supported or human |

A `deliver` receipt alone is not delivery. Only `observe_delivery` evidence lets the ledger record `delivered`, and only for the package's current head once every direct blocker is delivered and the state is `ready-to-deliver`. An external merge from `needs-review` or `changes-requested` is recorded only with `--attested-by` and `--evidence`; a head that still has no passing review keeps the review-gap warning.

## Tracker (optional)

A projection of status for humans. It never decides the package graph, readiness or delivery.

| Operation | Success evidence |
| --- | --- |
| `project_status` | the tracker's write receipt (issue/comment id) |

Tracker writes happen after facts are recorded. A tracker failure never blocks recording an assignment, a completion or a delivery; it stays a pending projection to retry or report.

## Facts kept distinct

| Fact | Recorded by | Proven by |
| --- | --- | --- |
| Assignment requested | `request` | the ledger alone: an intent, before contacting the executor |
| Assignment accepted | `accepted` | `assign` receipt (or `find` hit) |
| Worker completed | `completed` | `observe` outcome + head |
| Review result | `reviewed` | `observe` on a distinct review assignment, pinned to the head |
| Delivered | `delivered` | `observe_delivery` observation in the expected target |
| Resource cleaned up | `resource --action released` | `release` evidence, coordinator-owned only |

Each fact is recorded only from its own evidence. A completion is not a delivery, a merge receipt is not an observation, and silence is not completion.

## Adding an integration

Write one profile section per role from `references/orchestration-profile-template.md`. Declare every operation, including the unsupported ones. Under `## Instructions`, give the exact commands, how the operation key is attached, and how each line of evidence is captured. Then run `ledger.py check-profile`. Try every `supported` operation once with a harmless dry run before relying on it; until then, report it as untested.

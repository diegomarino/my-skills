# Briefs, reports and decisions

Formats the coordinator uses with workers, reviewers and the user. A profile's `## Instructions` adapts the transport (prompt, issue body, file) but keeps these contents.

## Implementer brief (implement and fix)

In this order:

1. The operation key on the first line, for example `F001-P02:implement:1`.
2. A one-line role: "You implement one work package. You do not coordinate other workers."
3. Where to work: the absolute worktree or branch path as the only writable location.
4. The package section verbatim: objective, scope, constraints, ownership, source tasks, primary paths, acceptance criteria, verification, handoff.
5. Upstream facts: for each delivered blocker, its delivered head and its handoff, so the worker builds on what really landed.
6. For a fix: the pinned head under review and only the surviving findings, each with file:line.
7. Rules:
   - Raise contract problems before editing. Return `needs-context` rather than guess.
   - Run the package's verification commands.
   - Commit with the trailer `Orchestration-Op: <key>`.
   - Edit only inside the ownership boundary.
   - Never merge, push, or start other workers.
8. The report contract below.

## Worker report

The full report goes to `<feature>/.orchestration/reports/<op key with : replaced by ->.md`. The worker returns at most 15 lines:

```text
Status: done | done-with-concerns | blocked | needs-context
Op: F001-P02:implement:1
Head: <commit sha>            (or NOT COMMITTED)
Verification: <command> -> <result>
Changed: <paths>
Concerns: <one line each, or none>
```

Workers may inherit the user's global agent configuration (output style, prefixes, hooks), so parse the report block itself and ignore surrounding text.

The coordinator's response depends on the status:

- **done / done-with-concerns.** Run the completion checks in SKILL.md §2.5.
- **blocked / needs-context.** Something must change before reassigning: more context, a stronger model, a smaller scope, or a user decision. Never reassign it unchanged.

## Reviewer brief

A fresh context, read-only, with no subagents. Give it:

- the pinned base and head;
- the diff as a file (`git diff <base>...<head> > <feature>/.orchestration/reviews/<op>.diff`);
- the acceptance criteria verbatim;
- the verification commands;
- the implementer's report, labelled as claims to check.

Never tell a reviewer what not to flag.

Reviewer report:

```text
Verdict: pass | changes-requested | inconclusive
Head: <sha it reviewed>
Criteria: <each acceptance criterion: met / not met, with file:line evidence>
Findings: <Critical | Important | Minor, file:line, one line each>
Could not verify: <items the diff and commands could not prove>
Commands run: <command -> result>
```

The ledger only takes `pass` or `changes-requested`. Treat `inconclusive` as a failed review: record it as `completed --outcome failed` and request a fresh review with whatever was missing.

## Decision brief (to the user)

Bring the user one prepared decision at a time:

- the package and the operation key;
- what happened;
- the evidence;
- the options with their tradeoffs;
- your recommendation;
- the exact choices.

Record the answer through the ledger: `--via user --attested-by <name>` for whether an assignment exists, or `--attested-by` on a capped request.

## Progress line

After each pass, post one line:

`delivered 3/8 · in review P04 · implementing P05, P06 · waiting P07 (conflict with P06) · needs you: P08 (Ready: no)`.

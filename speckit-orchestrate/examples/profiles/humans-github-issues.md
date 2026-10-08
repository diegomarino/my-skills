---
harness: "humans"
implement_model: "n/a"
review_model: "n/a"
isolation: "external"
base_branch: "main"
max_parallel: "4"
review_by: "human"
delivery_mode: "pull-request"
merge_by: "human"
tracker: "github-issues"
on_finish: "comment the final summary on the feature tracking issue; leave branches to their authors"
authorized: "assign, tracker"
---

# Orchestration profile: people via GitHub Issues + pull requests

Starting point for teams where people implement and review. Here the tracker is also the assignment channel. Not tested against a live GitHub repository.

## Executor: people assigned through GitHub Issues
- identity: issue number + assignee login
- assign: human — evidence: issue URL plus the assignee's comment accepting the work
- observe: human — evidence: the assignee's completion comment naming the PR and head SHA
- find: supported — evidence: `gh issue list --search "<op key> in:title" --state all --json number,assignees` result
- release: unsupported

## Delivery: GitHub pull requests
- identity: PR URL + head SHA + base branch
- submit: human — evidence: the PR URL the assignee reports
- observe_delivery: supported — evidence: `gh pr view <url> --json state,baseRefName,headRefOid` shows MERGED into base_branch
- deliver: human — evidence: a maintainer merged the PR (confirmed by observe_delivery)

## Tracker: GitHub Issues
- project_status: supported — evidence: the comment URL returned by `gh issue comment`

## Instructions

- Assign: `gh issue create --title "<op key> <package title>" --body "<package section verbatim>"`. The coordinator records `accepted --attested-by <login>` only after the assignee confirms.
- Reviews are separate issues assigned to someone other than the implementer. The reviewer comments `pass` or `changes-requested` against the pinned head SHA.
- **Observation with gh-delta** (when installed): read the run's observer on each inspect. Add this PR, and the package issue, to it. Recording `delivered` still uses the `observe_delivery` evidence above.
- Nothing is released: people own their machines and branches.

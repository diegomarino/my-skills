# Independent verification and troubleshooting

Read after authorized deployment, and whenever a failure needs diagnosis. Do not infer deployment from generated resources or successful fixture tests. Keep each boundary distinct: dispatch accepted, queued, selected, started, intermediate checks passed, artifacts uploaded, complete terminal workflow conclusion.

## Evidence receipt

Capture non-secret evidence for the actual target:

| Gate | Independent readback |
| --- | --- |
| Repository | Host/repo identity, candidate commit, workflow/configuration, branch protections and variable/secret names |
| Archive | Official release URL, selected version/architecture and authoritative versus computed SHA256 |
| Host | OS/architecture, runtime account standard/non-admin, home/path ownership, session requirement, storage/power state |
| Service | Installed bytes/mode/owner, exact unit/domain, process PID/owner and service environment |
| Registration | Safe local ID/URL correlated with GitHub ID/name, access, labels and online/idle snapshot |
| Preferred CI | Final candidate, execution-machine log, actual job runner ID/name, real build/test/package outcomes and complete terminal conclusion |
| Hosted CI | Forced hosted on same final candidate, correct machine/toolchain, same real gates, complete terminal conclusion |
| Delivery | Artifact contents independently downloaded/read; PR URL/state; deployed main readback only after authorized/user merge |
| Restart | Authorized reboot, no graphical login if required, online/job readback; otherwise pending |

Use [prepare_runner.py](../scripts/prepare_runner.py) `inspect --directory /actual/resolved/path` for safe local registration/preparation state. For services, follow the native commands in [platforms](platforms.md), inspecting the exact service and PID, not every service on the host.

For GitHub, a populated non-secret target can read one runner and all jobs for a run:

```bash
gh api --hostname "$GITHUB_HOST" "repos/$REPOSITORY/actions/runners/$RUNNER_ID" \
  --jq '{id,name,status,busy,labels:[.labels[].name]}'
gh api --hostname "$GITHUB_HOST" --paginate --slurp \
  "repos/$REPOSITORY/actions/runs/$RUN_ID/jobs?per_page=100" \
  --jq '[.[].jobs[]|{id,name,status,conclusion,runner_id,runner_name,runner_group_name}]'
```

Wait for the preferred-host run to reach its terminal conclusion before dispatching forced hosted on the same ref: the template concurrency policy cancels overlapping runs. Read the run's head SHA and every required job's terminal conclusion as well. A PR merge commit and branch head are different candidates; choose and record the candidate being validated. When a fix changes it, rerun required preferred and hosted checks against the new candidate. A routing smoke is separate from product acceptance. Retain/read useful artifacts with a task-owned cache/download directory. If the user merges independently, fresh-read PR/main state and compare deployed configuration without disturbing their checkout.

## Diagnose one failing boundary

Read the complete relevant log, redact credentials and apply one targeted fix. For selector fallback, use its non-secret routing reason and the [reason/next-check table](ci.md#trust-and-fallback) before changing configuration. Registration failures need URL/permission/expiry checks; offline needs exact process/service/network checks; queued needs labels/group/trust/capacity checks; started job failures need account environment/toolchain/check log. Distinguish cache/path failures of local `gh` from GitHub failures; use task-owned `XDG_CACHE_HOME` when required. Do not change unrelated permissions/services or broaden tokens.

Check headless HOME/PATH, writable job-owned temporary directories, tool executable paths, SDK/keychain access and actual installer privilege needs. Inspect token file remnants without reading values, incomplete preparation receipts and original service backups before guarded resumption. A selected runner can become unavailable and remain queued; execution timeouts are not queue supervision. Multiple instances on one host can run concurrently, so per-instance busy does not prove host capacity.

Report explicit untested gates: live offline/busy transitions, queue disconnect, native platform startup/conversion, reboot/encryption unlock, signing, device/provider/production checks. Do not reboot, start production services, use private provider data, merge, or remove branches/worktrees as incidental verification/cleanup.

For clipboard delivery requested by the user, follow their actual platform/harness rules: print complete bytes first, copy from a concrete file, read back and compare byte count plus SHA256 before claiming success. On macOS Codex use escalated host `pbcopy` and `pbpaste`; never include credentials in the payload. Clipboard denial leaves the payload visible and explicitly uncopied.

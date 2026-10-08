# Discovery and access

Read before preparing a new installation or repository integration. These inputs come from the target, not the example: repository/hostname, default branch, host and connection, OS/architecture, administrator connection account, separate standard runtime account/home, instance directory, registration scope/name, unique routing label, hosted fallback, real CI commands and privilege boundary.

## Repository

Read agent instructions and `git status --short`, remotes and default branch. Preserve dirty/concurrent work; use an isolated branch/worktree for workflow changes. Read existing workflows, dependency/toolchain declarations and project build/test/package/installation commands. Inspect protection/ruleset policy, registered runners and accessible runner groups, and Actions variable/secret **names only**. Use an existing connector, authenticated `gh` for the actual hostname, or GitHub UI; create missing operator access using [credentials](credentials.md).

A complete repository-scoped inventory can use:

```bash
gh api --hostname "$GITHUB_HOST" --method GET \
  "repos/$REPOSITORY/actions/runners?per_page=100" --paginate --slurp \
  --jq '[.[].runners[] | {id,name,os,status,busy,labels:[.labels[].name]}]'
```

Populate non-secret variables from verified inputs. If remotes conflict, resolve the requested repository rather than selecting silently. An empty success proves only that scope is empty. Verify organization/enterprise group repository and workflow restrictions through Actions → Runners or [runner-group API](https://docs.github.com/en/rest/actions/self-hosted-runner-groups); an organization inventory alone does not prove repository access. Errors, inaccessible groups or incomplete pages remain **unknown**, not absent. Inventory all accessible labels before selecting a unique custom label.

## Host

A local runner may be installed on the current computer or another selected host. For remote access, establish the supported connection first; do not assume SSH exists or enable a service silently. The user may use a console or OS remote management instead. For SSH, verify the host-key fingerprint through an independent trusted channel, connection identity, reachability and key/password policy. Keep host-key checks enabled and credentials outside chat. If SSH server/client, access key or firewall rule is missing, prepare the target OS's documented setup with the administrator; keep access pending until a harmless identity command works.

Confirm the target is macOS or Linux; Windows host provisioning is outside this skill. Inventory OS release/architecture, hostname, tools, available storage, init/service manager, existing account memberships/homes, runner directories/services/process owners, outbound network/proxy access, disk encryption and power behavior. Use native tools (Linux `/etc/os-release`, `uname`, `id`; macOS `sw_vers`, `uname`, directory services). Inspect likely locations or supplied paths; missing checkout files do not establish host absence.

Distinguish the administrator connection account from the **dedicated non-administrator runtime account**. Verify privileges, ownership and ACLs. Ask whether that dedicated account can remain graphically logged in; do not infer it from the main user or SSH access. Choose service lifecycle using [platforms](platforms.md). If the account does not exist, create it using that platform branch before runner preparation.

Inspect only safe `.runner` identity fields, never `.credentials` files. With Python 3.9+ available on the target, [prepare_runner.py](../scripts/prepare_runner.py) `inspect --directory /resolved/instance` emits identity and preparation state. Correlate agentId and gitHubUrl with the exact GitHub scope; names alone are ambiguous. Service/process readback is still necessary. Keep unrelated instances unchanged.

For laptops, verify lid/sleep/wake, power, network availability and any authorized power-management changes; a sleeping machine cannot accept jobs. Runner traffic is outbound; normal registration requires no inbound router ports. CI can read whatever the runtime account can access, including local network services. Minimize that access before running trusted code.

Done when every input is evidenced or explicitly pending, including actual CI toolchain and account/session constraints. Pending access or identity blocks dependent mutations, not independent preparation.

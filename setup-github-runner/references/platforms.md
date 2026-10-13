# Accounts and persistent services

Read this when preparing a Linux/macOS host account or installing/converting its service. Discover the target OS, architecture, service manager, administrator connection account, **separate standard runtime account**, account home, runner directory and login availability. Hostname and hardware are inputs. Registration and runner files must be prepared before the service. Windows target installation is unsupported by this skill.

## Common preparation and privilege boundary

Inventory existing accounts, group memberships, runner directories, `.service` metadata, service definitions and process owners. Reuse only an account suitable for this repository's trusted code. Require a dedicated standard runtime account distinct from the primary personal and administrator connection accounts; one shared dedicated account for several runner instances is not strong isolation. Each instance needs its own directory and registration; repository-scoped runners need a separate instance per repository.

When the account is absent, prepare the applicable account-creation steps below. Confirm who can perform the administrator step. Passwords are entered locally in the user's terminal or OS UI, never chat. An inability to use noninteractive sudo means prepare unprivileged files first, then deliver a small reviewed privileged operation for interactive execution; retain authentication. Transfer substantial remote work as a validated script into a private collision-resistant staging directory, then provide a short quoted invocation. Establish SSH access and host identity independently; SSH is optional, not assumed. For a POSIX SSH target, render the short invocation with [remote_command.py](../scripts/remote_command.py) after transferring and verifying a reviewed script:

```bash
python3 scripts/remote_command.py --host "$SSH_HOST" \
  --admin-account "$ADMIN_ACCOUNT" --script "$REMOTE_SCRIPT"
```

It prints `ssh -t` with separately quoted local and remote arguments; it never connects or executes. The target script must already reside in administrator-controlled staging with inspected path components, ownership and permissions, and its bytes must match the reviewed local artifact. The generator validates syntax, not ownership, connection identity or privilege. Use the printed command only after installation authorization; the user enters sudo authentication in their own terminal. Put the connection username in `--admin-account`, not `user@host`; configure a nondefault port in an SSH config alias and pass that alias as `--host`.

Inspect resolved paths, ownership, ACLs and every path component for symlinks before privileged writes. Keep administrator staging inaccessible to the runtime account. Preserve unrelated instances. Conflicting destination files, backups or running listeners require inspection and a specific migration plan. Preserve interrupted state; completion is established by readback, not rerunning installation.

Only trusted contributions run on a persistent host. The runtime account can execute repository code; isolate its accessible files and credentials accordingly. Never give it administrator rights or personal operator credentials to satisfy a build installer. Provision necessary toolchains separately as administrator, then verify they run as the runtime account with its service environment.

Registration records PATH in the instance's `.path` and selected environment values in `.env`. The official [`runsvc.sh`](https://github.com/actions/runner/blob/main/src/Misc/layoutbin/runsvc.sh) exports `.path` when it exists, overriding the service definition's initial PATH. Inspect these files as the runtime account without logging secrets, and prepare any needed `.path` change there before verifying the effective service environment. Changing the service definition's PATH alone does not override `.path`.

### Host-wide job gate

Separate runner instances can execute jobs concurrently, even on one host. To join an existing gate, inspect its actual contract before configuring the new instance:

- Identify how acquisition excludes other jobs and how ownership lasts through the protected work after the started hook exits. A lock held only for the hook process does not serialize subsequent workflow steps. Check the shared lock path/namespace, required configuration and runtime-account access; per-instance locks do not coordinate the host.
- Reuse the complete acquire/release configuration, including `ACTIONS_RUNNER_HOOK_JOB_COMPLETED` when the gate uses it. Preserve unrelated hooks and settings; resolve conflicts before replacing anything. Do not invent a completion hook for a gate that releases another way.
- Establish the existing wait bound, failure behavior and recovery after cancellation, a missing completion callback or a crashed owner. A completed hook is not guaranteed after a process/host crash. Do not clear an apparent stale lock without verifying ownership and the existing recovery procedure. If these semantics are missing or unsafe, keep gate integration pending and report the specific gap.

Before the new instance accepts its first job, verify required absolute hook paths, readable/executable files, interpreters and lock/config access as its runtime account. Keep scripts outside runner application directories with the extension appropriate to their language. Apply the verified settings without duplicate keys, start the new service only within installation authorization, or restart only that exact service while idle if already running. Environment changes require a runner restart; preserve unrelated services. Read back effective non-secret settings. GitHub's [hook contract](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/run-scripts) runs hooks synchronously as the service account; a missing or failing started hook prevents normal job execution.

For authorized live acceptance, observe overlapping job requests on different instances: the second must wait while the first owns the gate, then proceed after release. Check bounded-wait failure and cancellation/recovery using the existing safe procedure or an isolated fixture; do not crash a live host for validation. Report which cases were exercised and which remain pending. Review [CI timing](ci.md#choose-the-routing-policy) separately.

When serialization is wanted but no gate exists, discuss a single organization-scoped runner shared by eligible trusted repositories: one instance handles one job at a time, with other jobs waiting before assignment. Use the [organization registration and group procedure](setup.md#choose-registration-scope-and-access) and scope-specific [credentials](credentials.md). Other instances on the host would still run independently. Changing registration scope or replacing existing instances needs its own migration plan and authorization, not an automatic conversion during repository-scoped installation.

## Linux

Discover distribution and PID 1/service manager. Inspect `getent passwd`, `id`, sudo policy and actual memberships rather than assuming an Ubuntu account layout. For a missing account, use the distribution's documented account utility and local `--help`/manual. A system service account may use a non-login shell; choose a home and preparation mechanism that support this installation. On Debian/Ubuntu, inspect `adduser --help` and its installed manual, create the selected account with administrator authority, and omit sudo/docker/other privileged groups. Other distributions use their own documented tooling. Verify resulting UID, groups, home ownership and access to the selected runner directory. Give access only to this instance; avoid recursive ownership changes outside it.

For **systemd** hosts, after registration generates `svc.sh`, the [official service procedure](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application) accepts the runtime username. Install once from the verified distribution, before releasing the instance to jobs, with concurrent runtime-account writes prevented:

```bash
# Substitute verified values in a reviewed script; inspect the official distribution first.
cd -- "$RUNNER_DIR"
sudo ./svc.sh install "$RUNNER_ACCOUNT"
```

`svc.sh` is executable code run as root: validate its release provenance and protect the runner tree from concurrent writes during privileged installation. If this instance has already run jobs, obtain fresh administrator-controlled verified resources and a reviewed installation plan rather than executing its unchecked `svc.sh` as root. No administrator-owned copy is safe merely by ownership; inspect every script/template it loads and the working directory.

Treat the runtime-writable `.service` as a **candidate** unit name, not authority. Independently locate the installed exact unit; inspect its root-owned definition and path/ACLs, and verify `User`, `WorkingDirectory` and `ExecStart` match this account and runner instance. Set `RUNNER_UNIT` only to that verified single unit name. Manage the installed unit through systemd rather than repeatedly executing runtime-writable scripts as root:

```bash
# RUNNER_UNIT is the independently verified installed unit, not an unchecked .service value.
sudo systemctl start -- "$RUNNER_UNIT"
systemctl status -- "$RUNNER_UNIT"
systemctl is-enabled -- "$RUNNER_UNIT"
```

Verify enabled/active state, exact process owner, permissions and GitHub online/idle. Stop/restart only this exact unit when authorized; avoid wildcard commands. On another service manager, prepare its supported service with `runsvc.sh` as the entry point; systemd commands are inapplicable.

## macOS: graphical login or headless daemon

Create a missing **Standard** account via [Apple's Users & Groups procedure](https://support.apple.com/guide/mac-help/add-a-user-or-group-mchl3e281fc9/mac), selecting the target macOS version. For a remote-only target, first read the actual target's `sysadminctl --help` and account directory state, then prepare the administrator-approved creation command using its documented options and private local password input. If secure noninteractive provisioning cannot be established, give the administrator the official Users & Groups console procedure above; mark account creation pending until the account and home are independently read back. Do not invent UID, primary group, home path or password syntax. Check `id`, `dscl . -read /Users/ACCOUNT NFSHomeDirectory UniqueID PrimaryGroupID`, and admin group membership. Verify sudo policy separately; absence from `admin` alone is not proof of no delegated privileges.

Ask whether **this dedicated account**, not the connection account, can remain graphically logged in. Inspect its actual `gui/UID` domain. SSH and `su` do not establish a graphical login. The official [macOS service script](https://github.com/actions/runner/blob/main/src/Misc/layoutbin/darwin.svc.sh.template) installs a LaunchAgent under its home and runs without sudo. If that login lifecycle satisfies the user's requirements, prepare `./svc.sh install`, `start`, and `status` as that runtime account and verify the GUI/domain behavior.

When login-independent service is required, use a root-owned LaunchDaemon with `UserName` set to the standard account. GitHub's [custom service guidance](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application) requires the `runsvc.sh` entry point. Prepare it **as the runtime account** from the verified distribution's `bin/runsvc.sh` if absent; inspect and preserve any existing copy.

Use [the renderer](../scripts/macos_service.py) on the target or in a private resolved staging directory. It renders a plist and a **manual reviewed command plan**, without installing anything:

```bash
python3 scripts/macos_service.py --account "$RUNNER_ACCOUNT" \
  --home "$RUNNER_HOME" --runner-dir "$RUNNER_DIR" \
  --label "$SERVICE_LABEL" --output-dir "$STAGING_DIR"
```

The output directory must already exist and have no symlink path components. On macOS, resolve `/tmp`/`/var` aliases before passing it. `--label` is the unique **launchd service label**, not the GitHub routing label. `--account` accepts existing mixed-case/dotted short names but does not verify account privileges. Supply `--path` only for a verified controlled initial plist PATH; the default covers system tools, not Homebrew or project dependencies, and the runner's `.path` overrides it when present. Review both generated artifacts and the instance's effective PATH. If generated locally for a remote target, transfer to private administrator staging. Set the plan's required `STAGED_PLIST` variable to the actual resolved **target** plist path before validation or privileged installation; the plan intentionally does not embed the workstation output path.

Before privileged deployment, verify a standard non-root/non-admin account, matching directory-service home, registered instance identity, path ownership/ACLs and no other listener for this instance. The renderer validates syntax, **not those live facts**. Verify log directory/file paths are writable by the runtime account and neither symlinks nor unrelated files. Validate with `plutil -lint`.

For LaunchAgent conversion, read the original plist's label and runner path. Stop/disable that exact label in its actual user/gui domain, confirm the listener has stopped, and move the original plist to a disabled backup only after refusing a conflicting backup (including dangling symlinks). Refuse an existing daemon destination. Preserve `.service` metadata and document that it describes the old agent. Install only the reviewed plist with root:wheel ownership and mode 0644 under `/Library/LaunchDaemons`; use **system-domain** `launchctl bootstrap`, `print`, and `bootout` for the daemon. `svc.sh` continues to manage the old LaunchAgent.

Read back installed plist bytes, permissions, service PID and process owner, then GitHub online/idle and actual CI. `RunAtLoad`/`KeepAlive`, explicit HOME/PATH, `WorkingDirectory`, runtime account and writable log locations are generated. Add `SessionCreate`, `ProcessType` or other keys only after checking target launchd documentation and real application requirements. Signing, interactive keychains and GUI tools need separate tests.

## Unsupported targets

Windows host provisioning, archive preparation and service installation are outside this skill's supported target scope. If discovery identifies Windows, report that boundary and stop target mutations; use a separately reviewed Windows procedure. Hosted Windows CI can still be selected when it matches the project's checks.

## Availability and independent acceptance

The runner connects outbound to GitHub; normal setup needs no inbound router forwarding. Check firewall/proxy requirements, host sleep behavior and storage. Keep sleep/power changes within authorization. A sleeping host cannot run CI. Disk encryption can require an unlock after restart before services are available. Login-free daemon setup does not prove reboot acceptance: perform that separately only with restart authorization.

Verify service state, process identity, file ownership/permissions, environment, exact GitHub registration and online/idle status. Execute real project checks on this host and compatible hosted fallback at the final candidate. Report the daemon/agent choice and login prerequisite explicitly.

**Validation boundary:** bundled renderer tests cover generated plist semantics, input guards, quoting and preserved output files. They do not create accounts or install/convert services. Native Linux/macOS service startup, reboot, encrypted-disk unlock and interactive tooling remain live acceptance checks.

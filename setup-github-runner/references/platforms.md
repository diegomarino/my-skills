# Accounts and persistent services

Read this when preparing a Linux/macOS host account or installing/converting its service. Discover the target OS, architecture, service manager, administrator connection account, **separate standard runtime account**, account home, runner directory and login availability. Hostname and hardware are inputs. Registration and runner files must be prepared before the service. Windows target installation is unsupported by this skill.

## Common preparation and privilege boundary

Inventory existing accounts, group memberships, runner directories, `.service` metadata, service definitions and process owners. Reuse only an account suitable for this repository's trusted code. Require a dedicated standard runtime account distinct from the primary personal and administrator connection accounts; one shared dedicated account for several runner instances is not strong isolation. Require a separate directory and registration per repository.

When the account is absent, prepare the applicable account-creation steps below. Confirm who can perform the administrator step. Passwords are entered locally in the user's terminal or OS UI, never chat. An inability to use noninteractive sudo means prepare unprivileged files first, then deliver a small reviewed privileged operation for interactive execution; retain authentication. Transfer substantial remote work as a validated script into a private collision-resistant staging directory, then provide a short quoted invocation. Establish SSH access and host identity independently; SSH is optional, not assumed. For a POSIX SSH target, render the short invocation with [remote_command.py](../scripts/remote_command.py) after transferring and verifying a reviewed script:

```bash
python3 scripts/remote_command.py --host "$SSH_HOST" \
  --admin-account "$ADMIN_ACCOUNT" --script "$REMOTE_SCRIPT"
```

It prints `ssh -t` with separately quoted local and remote arguments; it never connects or executes. The target script must already reside in administrator-controlled staging with inspected path components, ownership and permissions, and its bytes must match the reviewed local artifact. The generator validates syntax, not ownership, connection identity or privilege. Use the printed command only after installation authorization; the user enters sudo authentication in their own terminal. Put the connection username in `--admin-account`, not `user@host`; configure a nondefault port in an SSH config alias and pass that alias as `--host`.

Inspect resolved paths, ownership, ACLs and every path component for symlinks before privileged writes. Keep administrator staging inaccessible to the runtime account. Preserve unrelated instances. Conflicting destination files, backups or running listeners require inspection and a specific migration plan. Preserve interrupted state; completion is established by readback, not rerunning installation.

Only trusted contributions run on a persistent host. The runtime account can execute repository code; isolate its accessible files and credentials accordingly. Never give it administrator rights or personal operator credentials to satisfy a build installer. Provision necessary toolchains separately as administrator, then verify they run as the runtime account with its service environment.

Registration records PATH in the instance's `.path` and selected environment values in `.env`. The official [`runsvc.sh`](https://github.com/actions/runner/blob/main/src/Misc/layoutbin/runsvc.sh) exports `.path` when it exists, overriding the service definition's initial PATH. Inspect these files as the runtime account without logging secrets, and prepare any needed `.path` change there before verifying the effective service environment. Changing the service definition's PATH alone does not override `.path`.

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

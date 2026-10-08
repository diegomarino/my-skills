#!/usr/bin/env python3
"""Render a macOS runner LaunchDaemon and review plan; never install or start it."""
import argparse
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shlex


def absolute(value, argument):
    path = PurePosixPath(value)
    if not value.startswith('/') or str(path) != value or value == '/' or any(ord(c) < 32 for c in value) or '..' in path.parts:
        raise ValueError(f'{argument}: {value!r} must be a resolved absolute non-root path without control characters.')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account', required=True, help='Verified dedicated standard runtime account on the target.')
    parser.add_argument('--home', required=True, help='Resolved absolute home of that account on the target.')
    parser.add_argument('--runner-dir', required=True, help='Resolved absolute registered instance directory on the target.')
    parser.add_argument('--label', required=True, help='Unique launchd service label; not the GitHub routing label.')
    parser.add_argument('--path', default='/usr/bin:/bin:/usr/sbin:/sbin', help='Initial plist PATH; runner .path overrides it if present.')
    parser.add_argument('--output-dir', required=True, type=Path, help='Existing resolved local staging directory; artifacts must not exist.')
    args = parser.parse_args()
    try:
        if args.account.casefold() in {'root', 'daemon', 'nobody'}:
            raise ValueError(f'--account: {args.account!r} is reserved; choose a verified dedicated standard runtime account.')
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', args.account):
            raise ValueError(f'--account: {args.account!r} must be a short name using letters, digits, underscores, dots or hyphens.')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,199}', args.label):
            raise ValueError(f'--label: {args.label!r} must be a unique launchd service label containing letters, digits, dots, or hyphens.')
        home, runner = absolute(args.home, '--home'), absolute(args.runner_dir, '--runner-dir')
        for component in args.path.split(':'):
            absolute(component, '--path component')
        output = args.output_dir.absolute()
        if not output.is_dir():
            raise ValueError(f'--output-dir: {str(output)!r} must already exist as a directory.')
        if output.resolve() != output:
            raise ValueError(f'--output-dir: {str(output)!r} resolves to {str(output.resolve())!r}; pass the resolved path after inspection.')
        plist_path, plan_path = output / (args.label + '.plist'), output / 'service-plan.txt'
        if os.path.lexists(plist_path) or os.path.lexists(plan_path):
            raise ValueError('Output artifacts already exist; inspect them or use a new staging directory.')
        logs = f'{home}/Library/Logs/{args.label}'
        plist = {'Label': args.label, 'ProgramArguments': [f'{runner}/runsvc.sh'],
                 'UserName': args.account, 'WorkingDirectory': runner,
                 'RunAtLoad': True, 'KeepAlive': True,
                 'EnvironmentVariables': {'HOME': home, 'PATH': args.path, 'ACTIONS_RUNNER_SVC': '1'},
                 'StandardOutPath': f'{logs}/stdout.log', 'StandardErrorPath': f'{logs}/stderr.log'}
        q = shlex.quote
        daemon = f'/Library/LaunchDaemons/{args.label}.plist'
        plan = f'''Review and execute one stage at a time on the selected macOS host.
This is a command plan, not an automated installer. Read references/platforms.md first.
Fresh-check account, registration identity, ownership, symlinks, service conflicts and listeners.
The account must be standard, non-admin; its directory-service home must equal {home}.
Runner directory must resolve to {runner} on the target, owned by {args.account}.
Service label must be unique across system and user domains; inspect .service for prior label/path.

Preparation: run as the standard runtime account, never root.
cd -- {q(runner)}
# If runsvc.sh is missing, inspect verified distribution bin/runsvc.sh then copy without overwriting:
# cp -n ./bin/runsvc.sh ./runsvc.sh && chmod u+x ./runsvc.sh
# If present, inspect it and preserve it. Stop the exact foreground listener before conversion.
# Registration captures PATH in .path and variables in .env; inspect both as this account.
# runsvc.sh's .path overrides the plist PATH when present. Set .path to the reviewed target PATH
# as this account if needed, then read back the effective environment; --path alone does not replace it.
mkdir -p -- {q(logs)}
# Check log directories and files are owned by this account and have no symlink components.
# Ensure stdout.log/stderr.log are regular writable files or absent.

Validate the generated plist transferred to a private administrator-owned staging directory:
# Set this to the resolved target path of {args.label}.plist after transfer/ownership checks.
# For a local target, use the resolved output path; do not reuse a workstation path on a remote host.
STAGED_PLIST=''
: "${{STAGED_PLIST:?Set STAGED_PLIST to the reviewed target plist path}}"
/usr/bin/plutil -lint "$STAGED_PLIST"
# Inspect all keys and paths. Never execute svc.sh/runsvc.sh as root from runtime-writable storage.

If an original LaunchAgent exists: inspect its Label/ProgramArguments, confirm this exact instance,
stop it in its actual launchctl user/gui domain, disable its exact service target, verify no listener,
and move its plist to a same-directory .disabled-backup only after ruling out an existing backup.
If no agent exists, confirm .service and launchctl have no alternate registered listener.
Recheck that {daemon} and every intended backup are absent (including dangling symlinks),
and /Library/LaunchDaemons is root-owned and not writable by the runtime account.
Keep original .service metadata for inspection; svc.sh now describes the old LaunchAgent.

After those checks and authorization, install only the reviewed data file:
sudo /usr/bin/install -o root -g wheel -m 0644 "$STAGED_PLIST" {q(daemon)}
sudo /usr/bin/plutil -lint {q(daemon)}
sudo /bin/launchctl bootstrap system {q(daemon)}
sudo /bin/launchctl print {q('system/' + args.label)}
# On interruption, inspect state and installed bytes before resuming; never repeat install blindly.
# On bootstrap failure retain the plist, backup and logs for diagnosis.

Read back installed ownership/mode/bytes, process UID, logs and GitHub registration online/idle.
Read the service PID from launchctl print, then inspect that exact PID with ps -o user,pid,command -p PID.
Only system-domain launchctl manages this daemon: svc.sh manages the original LaunchAgent.
Stopping this exact daemon, when authorized:
sudo /bin/launchctl bootout {q('system/' + args.label)}
Reboot acceptance, login-free startup, keychain/tool access and actual CI are separate live checks.
'''
        # Exclusive creation preserves existing artifacts, including dangling symlinks.
        with plist_path.open('xb') as stream:
            os.chmod(plist_path, 0o600)
            stream.write(plistlib.dumps(plist))
        with plan_path.open('x', encoding='utf-8') as stream:
            os.chmod(plan_path, 0o600)
            stream.write(plan)
        print(f'Rendered {plist_path} and {plan_path}; no service changes made.')
    except (ValueError, OSError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    main()

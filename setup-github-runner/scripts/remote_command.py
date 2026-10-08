#!/usr/bin/env python3
"""Render a short SSH invocation for an already transferred, reviewed POSIX script."""
import argparse
import ipaddress
from pathlib import PurePosixPath
import re
import shlex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Verified SSH hostname, alias or IP; no user@ prefix.')
    parser.add_argument('--admin-account', required=True, help='Verified SSH administrator connection account; separate from the runtime account.')
    parser.add_argument('--script', required=True, help='Resolved absolute path on the remote POSIX host.')
    args = parser.parse_args()
    if '@' in args.host:
        parser.error('--host: put the user from user@host in --admin-account and pass only the host.')
    if args.host.count(':') == 1 and re.fullmatch(r'[^:]+:[0-9]+', args.host):
        parser.error('--host: ports are not supported here; use an SSH config alias with its Port configured.')
    if ':' in args.host:
        try:
            if not re.fullmatch(r'[A-Za-z0-9.:%_-]+', args.host):
                raise ValueError('Unsafe address characters')
            ipaddress.ip_address(args.host)
        except ValueError:
            parser.error('--host: use a valid IPv6 address without whitespace or shell syntax; configure ports through an SSH config alias.')
    elif not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.host):
        parser.error('--host: use a hostname or SSH config alias without whitespace or shell syntax.')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', args.admin_account):
        parser.error('--admin-account: use the actual SSH administrator account name, without option or shell syntax.')
    path = PurePosixPath(args.script)
    if not args.script.startswith('/') or str(path) != args.script or args.script == '/' or '..' in path.parts or any(ord(c) < 32 for c in args.script):
        parser.error('--script: use a resolved absolute non-root path on the target without control characters.')
    remote = shlex.join(['sudo', '--', '/bin/bash', '--', args.script])
    print(shlex.join(['ssh', '-t', '-l', args.admin_account, '--', args.host, remote]))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Verify and unpack a runner archive without overwriting an instance; inspect safely."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
from urllib.parse import urlsplit
import posixpath


def current_account():
    if not hasattr(os, 'geteuid'):
        raise ValueError('This helper supports macOS/Linux hosts only')
    import pwd
    return pwd.getpwuid(os.geteuid()).pw_name


def checked_directory(directory):
    directory = Path(directory)
    if not directory.is_absolute() or directory != directory.resolve():
        raise ValueError(f'Use an absolute resolved directory without symlinks: {str(directory)!r} resolves to {str(directory.resolve())!r}; pass the resolved path')
    return directory


def member_path(name):
    path = PurePosixPath(name)
    if ('\\' in name or path.is_absolute() or '..' in path.parts
            or not path.parts or ':' in name or any(ord(char) < 32 for char in name)):
        raise ValueError(f'Unsafe archive path: {name!r}')
    return path


def prepare(archive, digest, directory, version, expected_user):
    directory = checked_directory(directory)
    archive = Path(archive)
    actual_user = current_account()
    if os.geteuid() == 0:
        raise ValueError('Refusing root; run as the verified standard runtime account')
    if expected_user != actual_user:
        raise ValueError(f'Current account {actual_user!r} is not expected runtime account {expected_user!r}')
    digest = digest.removeprefix('sha256:')
    if not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
        raise ValueError('SHA256 must be 64 hex characters, optionally prefixed with sha256:')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', version):
        raise ValueError('Invalid runner version')
    if directory.exists():
        raise ValueError(f'Instance already exists: {str(directory)!r}; inspect it. For incomplete preparation, retain it and use a new directory; see references/setup.md for scoped recovery')
    if not directory.parent.is_dir():
        raise ValueError('Prepare the parent directory first')
    if hasattr(os, 'getuid') and directory.parent.stat().st_uid != os.getuid():
        raise ValueError('Parent directory must belong to the runtime account')
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('Archive must be a regular file')
    with archive.open('rb') as source:
        actual = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b''):
            actual.update(block)
        if actual.hexdigest() != digest.lower():
            raise ValueError(f'Archive checksum mismatch: expected {digest.lower()}, computed {actual.hexdigest()}')
        source.seek(0)
        with tarfile.open(fileobj=source, mode='r:*') as bundle:
            names = set()
            entries = []
            links = {}
            total = 0
            for item in bundle.getmembers():
                if item.name in {'.', './'}:
                    continue
                path = member_path(item.name)
                if not (item.isdir() or item.isfile() or item.issym()):
                    raise ValueError(f'Unsupported archive entry (hardlink or special file): {item.name!r}')
                if path in names or str(path) in {'.runner', '.credentials', '.preparation.json'}:
                    raise ValueError(f'Conflicting or registered archive state: {item.name!r}')
                names.add(path)
                total += item.size
                if total > 3 * 1024 ** 3 or len(names) > 100000:
                    raise ValueError('Archive exceeds preparation limits')
                if item.issym():
                    target = item.linkname
                    if (not target or target.startswith('/') or '\\' in target or ':' in target
                            or any(ord(char) < 32 for char in target)):
                        raise ValueError(f'Unsafe archive symlink: {item.name!r} -> {target!r}')
                    resolved = member_path(posixpath.normpath(str(path.parent / target)))
                    links[path] = resolved
                entries.append((path, item))
            files = {path for path, item in entries if item.isfile()}
            dirs = {path for path, item in entries if item.isdir()}
            for path, item in entries:
                for parent in path.parents:
                    if parent in files or parent in links:
                        raise ValueError(f'Archive entry has non-directory parent: {str(path)!r}')
                    dirs.add(parent)
            required = {PurePosixPath('config.sh'), PurePosixPath('bin/Runner.Listener')}
            if not required <= files:
                missing = ', '.join(sorted(str(path) for path in required - files))
                raise ValueError(f'Archive is missing runner entry points: {missing}')
            for path, target in links.items():
                seen = {path}
                while True:
                    if any(parent in links or parent in files for parent in target.parents):
                        raise ValueError(f'Archive symlink has non-directory target parent: {str(path)!r}')
                    if target not in links:
                        break
                    if target in seen:
                        raise ValueError(f'Archive symlink cycle: {str(path)!r}')
                    seen.add(target)
                    target = links[target]
                if target not in files and target not in dirs:
                    raise ValueError(f'Archive symlink target is missing: {str(path)!r} -> {str(target)!r}')
            directory.mkdir(mode=0o700)  # Exclusive reservation; incomplete state is retained.
            receipt = {'status': 'incomplete', 'version': version, 'sha256': digest.lower(),
                       'archive': archive.name, 'account': expected_user}
            receipt_file = directory / '.preparation.json'
            receipt_file.write_text(json.dumps(receipt, indent=2) + '\n')
            for path, item in entries:
                target = directory.joinpath(*path.parts)
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o755)
                elif item.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    with bundle.extractfile(item) as stream, target.open('xb') as output:
                        shutil.copyfileobj(stream, output)
                    target.chmod(0o755 if item.mode & 0o111 else 0o644)
            # Create validated links last so extraction never writes through a link.
            for path, item in entries:
                if item.issym():
                    target = directory.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                    target.symlink_to(item.linkname)
            receipt['status'] = 'prepared'
            receipt_file.write_text(json.dumps(receipt, indent=2) + '\n')
            return receipt


def inspect(directory):
    directory = checked_directory(directory)
    report = {'directory': str(directory), 'exists': directory.is_dir(), 'registration': None,
              'preparation': None}
    for filename, key in [('.runner', 'registration'), ('.preparation.json', 'preparation')]:
        path = directory / filename
        if path.is_symlink():
            raise ValueError('Inspection refuses linked state files')
        if path.exists():
            if path.stat().st_size > 65536:
                raise ValueError('State file is too large')
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError('State file must be an object')
            fields = ('agentId', 'agentName', 'gitHubUrl') if key == 'registration' else ('status', 'version', 'sha256', 'account')
            if key == 'registration':
                identity_url = data.get('gitHubUrl', '')
                if not isinstance(identity_url, str):
                    raise ValueError('Registration gitHubUrl must be a string')
                url = urlsplit(identity_url)
                if url.username or url.password or url.query or url.fragment:
                    raise ValueError('Registration URL contains non-identity data')
            report[key] = {field: data.get(field) for field in fields}
            if key == 'preparation' and data.get('status') == 'incomplete':
                report['next_action'] = 'Retain this instance for inspection; prepare into a new directory. See references/setup.md for scoped manual recovery.'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare', help='Verify digest and reserve a new instance directory')
    prep.add_argument('--archive', type=Path, required=True, help='Official macOS/Linux tar archive already downloaded')
    prep.add_argument('--sha256', required=True, help='Official authoritative hex digest, optionally prefixed with sha256:')
    prep.add_argument('--version', required=True, help='Selected official runner version, recorded in receipt')
    prep.add_argument('--expected-user', required=True, help='Dedicated runtime account; must equal actual OS account')
    prep.add_argument('--directory', type=Path, required=True, help='New absolute resolved instance path; parent must exist and belong to runtime account')
    check = commands.add_parser('inspect', help='Print safe local identity and preparation receipt')
    check.add_argument('--directory', type=Path, required=True, help='Absolute resolved instance path to inspect without reading credentials')
    args = parser.parse_args()
    try:
        report = (prepare(args.archive, args.sha256, args.directory, args.version, args.expected_user)
                  if args.command == 'prepare' else inspect(args.directory))
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, tarfile.TarError) as error:
        parser.exit(1, 'Preparation/inspection refused: ' + json.dumps(str(error)) + '\n')


if __name__ == '__main__':
    main()

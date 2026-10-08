import hashlib
import importlib.util
import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_runner.py'
spec = importlib.util.spec_from_file_location('prepare_runner', SCRIPT)
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)
CURRENT_ACCOUNT = preparer.current_account
RUNTIME_ACCOUNT = 'fixture-runner'


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.target = self.base / 'instance'
        # Exercise preparation as a standard account even in root-based CI containers.
        for mocked in (patch.object(preparer, 'current_account', return_value=RUNTIME_ACCOUNT),
                       patch.object(preparer.os, 'geteuid', return_value=1001),
                       patch.object(preparer.os, 'getuid', return_value=self.base.stat().st_uid)):
            mocked.start()
            self.addCleanup(mocked.stop)

    def archive(self, members=None, links=None):
        entries = members or {'config.sh': b'config', 'bin/Runner.Listener': b'runner'}
        path = self.base / 'runner.tar.gz'
        with tarfile.open(path, 'w:gz') as bundle:
            for name, data in entries.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o755
                bundle.addfile(info, io.BytesIO(data))
            for name, target in (links or {}).items():
                info = tarfile.TarInfo(name)
                info.type, info.linkname = tarfile.SYMTYPE, target
                bundle.addfile(info)
        return path

    def run_prepare(self, path, digest=None, extra=()):
        args = [str(SCRIPT), 'prepare', '--archive', str(path),
            '--sha256', digest or hashlib.sha256(path.read_bytes()).hexdigest(),
            '--version', 'fixture-1', '--directory', str(self.target),
            '--expected-user', RUNTIME_ACCOUNT, *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with patch.object(sys, 'argv', args), redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                preparer.main()
            except SystemExit as error:
                code = error.code
        return subprocess.CompletedProcess(args, code, stdout.getvalue(), stderr.getvalue())

    def test_prepares_verified_archive_and_records_receipt(self):
        path = self.archive()
        result = self.run_prepare(path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / 'config.sh').read_bytes(), b'config')
        receipt = json.loads((self.target / '.preparation.json').read_text())
        self.assertEqual(receipt['status'], 'prepared')
        self.assertEqual(receipt['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_bad_digest_or_missing_binary_leaves_destination_absent(self):
        for members, digest in [(None, '0' * 64), ({'config.sh': b'x'}, None)]:
            with self.subTest(members=members):
                result = self.run_prepare(self.archive(members), digest)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.target.exists())

    def test_preserves_existing_instance_and_refuses_traversal(self):
        self.target.mkdir()
        (self.target / 'unrelated').write_text('keep')
        result = self.run_prepare(self.archive())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.target / 'unrelated').read_text(), 'keep')
        self.target = self.base / 'second'
        result = self.run_prepare(self.archive({'../escaped': b'bad', 'config.sh': b'x',
                                               'bin/Runner.Listener': b'x'}))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / 'escaped').exists())
        self.assertFalse(self.target.exists())

    def test_destination_symlink_guard(self):
        self.target = self.base / 'linked'
        actual = self.base / 'other'
        actual.mkdir()
        self.target.symlink_to(actual, target_is_directory=True)
        self.assertNotEqual(self.run_prepare(self.archive()).returncode, 0)
        self.assertEqual(list(actual.iterdir()), [])

    @unittest.skipUnless(hasattr(os, 'geteuid'), 'Unix identity guard')
    def test_account_identity_is_not_taken_from_environment(self):
        import pwd
        from types import SimpleNamespace
        with patch.dict(os.environ, {'LOGNAME': 'counterfeit-account', 'USER': 'counterfeit-account'}), \
             patch.object(pwd, 'getpwuid', return_value=SimpleNamespace(pw_name=RUNTIME_ACCOUNT)) as lookup:
            self.assertEqual(CURRENT_ACCOUNT(), RUNTIME_ACCOUNT)
            lookup.assert_called_once_with(1001)

    def test_archive_links_and_duplicate_paths_are_refused(self):
        path = self.archive()
        with tarfile.open(path, 'w:gz') as bundle:
            link = tarfile.TarInfo('config.sh')
            link.type, link.linkname = tarfile.SYMTYPE, '/etc/passwd'
            bundle.addfile(link)
        self.assertNotEqual(self.run_prepare(path).returncode, 0)
        self.assertFalse(self.target.exists())
        path = self.archive({'config.sh': b'x', './config.sh': b'y', 'bin/Runner.Listener': b'x'})
        self.assertNotEqual(self.run_prepare(path).returncode, 0)
        self.assertFalse(self.target.exists())

    def test_inspects_only_safe_registration_fields(self):
        self.target.mkdir()
        (self.target / '.runner').write_text('\ufeff' + json.dumps({'agentId': 42, 'agentName': 'box',
            'gitHubUrl': 'https://github.com/acme/widget', 'secret': 'DO-NOT-PRINT'}))
        (self.target / '.credentials').write_text('DO-NOT-PRINT')
        result = subprocess.run([sys.executable, str(SCRIPT), 'inspect', '--directory',
            str(self.target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['registration']['agentId'], 42)
        self.assertNotIn('DO-NOT-PRINT', result.stdout + result.stderr)

    def test_official_node_layout_and_prefixed_digest(self):
        members = {'config.sh': b'config', 'bin/Runner.Listener': b'runner'}
        links = {}
        for version in ('20', '24'):
            for command, suffix in [('npm', 'npm/bin/npm-cli.js'),
                                    ('npx', 'npm/bin/npx-cli.js'),
                                    ('corepack', 'corepack/dist/corepack.js')]:
                target = 'externals/node' + version + '/lib/node_modules/' + suffix
                members[target] = b'node-script'
                links['externals/node' + version + '/bin/' + command] = '../lib/node_modules/' + suffix
        path = self.archive(members, links)
        result = self.run_prepare(path, 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(result.returncode, 0, result.stderr)
        for name, target in links.items():
            self.assertEqual(os.readlink(self.target / name), target)
            self.assertEqual((self.target / name).read_bytes(), b'node-script')

    def test_link_escape_cycle_parent_and_hardlink_refused(self):
        for links in ({'bad': '../outside'}, {'bad': '/etc/passwd'},
                      {'bad': 'other', 'other': 'bad'},
                      {'bin': 'elsewhere'}, {'bad': 'missing'}):
            with self.subTest(links=links):
                result = self.run_prepare(self.archive(links=links))
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.target.exists())
        path = self.archive()
        with tarfile.open(path, 'w:gz') as bundle:
            link = tarfile.TarInfo('bad')
            link.type, link.linkname = tarfile.LNKTYPE, 'config.sh'
            bundle.addfile(link)
        self.assertNotEqual(self.run_prepare(path).returncode, 0)
        self.assertFalse(self.target.exists())

    def test_state_size_and_url_type_are_guarded(self):
        self.target.mkdir()
        for value in (b'x' * 65537, b'{"gitHubUrl": 42}'):
            (self.target / '.runner').write_bytes(value)
            result = subprocess.run([sys.executable, str(SCRIPT), 'inspect', '--directory',
                str(self.target)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('Traceback', result.stderr)

    def test_digest_algorithms_and_alias_diagnostics(self):
        path = self.archive()
        for digest in ('sha512:' + '0' * 64, 'sha256:' + '0' * 63):
            result = self.run_prepare(path, digest)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(self.target.exists())
        result = self.run_prepare(path, '0' * 64)
        self.assertIn('expected ' + '0' * 64, result.stderr)
        self.assertIn('computed ' + hashlib.sha256(path.read_bytes()).hexdigest(), result.stderr)
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        result = self.run_prepare(path, extra=('--directory', str(alias / 'instance')))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(str(self.target), result.stderr)
        self.assertFalse(self.target.exists())

    def test_identity_and_parent_ownership_guards(self):
        module = preparer
        path = self.archive()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with patch.object(module.os, 'geteuid', return_value=0):
            with self.assertRaisesRegex(ValueError, 'root'):
                module.prepare(path, digest, self.target, 'fixture', 'root')
        with patch.object(module, 'current_account', return_value='other-account'):
            with self.assertRaisesRegex(ValueError, 'other-account'):
                module.prepare(path, digest, self.target, 'fixture', 'runtime')
        with patch.object(module.os, 'getuid', return_value=-1):
            with self.assertRaisesRegex(ValueError, 'Parent directory'):
                module.prepare(path, digest, self.target, 'fixture', module.current_account())
        self.assertFalse(self.target.exists())

    def test_interrupted_extraction_is_retained_and_retry_refused(self):
        module = preparer
        path = self.archive()
        with patch.object(module.shutil, 'copyfileobj', side_effect=OSError('fixture interruption')):
            with self.assertRaises(OSError):
                module.prepare(path, hashlib.sha256(path.read_bytes()).hexdigest(),
                               self.target, 'fixture-1', RUNTIME_ACCOUNT)
        receipt = json.loads((self.target / '.preparation.json').read_text())
        self.assertEqual(receipt['status'], 'incomplete')
        report = module.inspect(self.target)
        self.assertEqual(report['preparation']['status'], 'incomplete')
        self.assertIn('new directory', report['next_action'])
        self.assertNotEqual(self.run_prepare(path).returncode, 0)
        self.assertEqual(receipt, json.loads((self.target / '.preparation.json').read_text()))


if __name__ == '__main__':
    unittest.main()

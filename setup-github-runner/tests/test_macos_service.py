"""The renderer writes reviewable artifacts; never changes the host service."""
import pathlib
import plistlib
import subprocess
import shlex
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'macos_service.py'


class MacOSServiceTests(unittest.TestCase):
    def render(self, directory, *extra):
        return subprocess.run([sys.executable, str(SCRIPT), '--account', 'ci-user',
                               '--home', '/Users/ci-user', '--runner-dir', '/Volumes/CI/runner one',
                               '--label', 'org.example.widget-ci', '--output-dir', str(pathlib.Path(directory).absolute()),
                               *extra], capture_output=True, text=True)

    def test_renders_daemon_and_review_plan_without_service_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.render(pathlib.Path(temp).resolve())
            self.assertEqual(result.returncode, 0, result.stderr)
            plist = plistlib.loads((pathlib.Path(temp) / 'org.example.widget-ci.plist').read_bytes())
            self.assertEqual(plist['UserName'], 'ci-user')
            self.assertEqual(plist['ProgramArguments'], ['/Volumes/CI/runner one/runsvc.sh'])
            self.assertEqual(plist['EnvironmentVariables']['HOME'], '/Users/ci-user')
            self.assertTrue(plist['KeepAlive'])
            self.assertEqual(plist['StandardOutPath'], '/Users/ci-user/Library/Logs/org.example.widget-ci/stdout.log')
            self.assertEqual(len(list(pathlib.Path(temp).iterdir())), 2)
            plan = (pathlib.Path(temp) / 'service-plan.txt').read_text()
            self.assertIn("system/org.example.widget-ci", plan)
            self.assertIn("'/Volumes/CI/runner one'", plan)
            self.assertIn('STAGED_PLIST=', plan)
            self.assertIn('/usr/bin/plutil -lint "$STAGED_PLIST"', plan)
            self.assertIn('-m 0644 "$STAGED_PLIST"', plan)
            self.assertNotIn(str(pathlib.Path(temp).resolve()), plan)
            self.assertIn('.path overrides', plan)

    def test_accepts_existing_mixed_case_and_dotted_account_names(self):
        for account in ['Build', 'build.ci']:
            with self.subTest(account=account), tempfile.TemporaryDirectory() as temp:
                result = self.render(pathlib.Path(temp).resolve(), '--account', account)
                self.assertEqual(result.returncode, 0, result.stderr)
                plist = plistlib.loads((pathlib.Path(temp) / 'org.example.widget-ci.plist').read_bytes())
                self.assertEqual(plist['UserName'], account)

    def test_errors_identify_argument_and_resolved_staging_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp).resolve()
            for extra, flag in [(('--account', 'root'), '--account'),
                                (('--home', 'relative'), '--home'),
                                (('--path', '.:/usr/bin'), '--path')]:
                with self.subTest(extra=extra):
                    result = self.render(root, *extra)
                    self.assertIn(flag, result.stderr.splitlines()[-1])
            linked = root / 'alias'
            linked.symlink_to(root, target_is_directory=True)
            result = self.render(linked)
            self.assertIn('--output-dir', result.stderr)
            self.assertIn(str(root), result.stderr)

    def test_quotes_target_paths_as_literal_arguments(self):
        runner = "/Volumes/CI/runner ' $(touch sentinel)"
        with tempfile.TemporaryDirectory() as temp:
            result = self.render(pathlib.Path(temp).resolve(), '--runner-dir', runner)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = (pathlib.Path(temp) / 'service-plan.txt').read_text()
            command = next(line for line in plan.splitlines() if line.startswith('cd -- '))
            self.assertEqual(shlex.split(command), ['cd', '--', runner])
            plist = plistlib.loads((pathlib.Path(temp) / 'org.example.widget-ci.plist').read_bytes())
            self.assertEqual(plist['ProgramArguments'], [runner + '/runsvc.sh'])

    def test_rejects_unsafe_or_unresolved_target_inputs(self):
        for extra in [('--account', 'root'), ('--account', 'admin user'),
                      ('--label', '../escape'), ('--runner-dir', '/tmp/../runner'),
                      ('--runner-dir', 'relative'), ('--home', '/'),
                      ('--runner-dir', '/tmp/runner\ncommand'),
                      ('--path', '.:/usr/bin'), ('--path', '/usr/bin::/bin')]:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp:
                result = self.render(pathlib.Path(temp).resolve(), *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(pathlib.Path(temp).iterdir()), [])

    def test_refuses_existing_artifacts_and_symlink_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp).resolve()
            artifact = root / 'org.example.widget-ci.plist'
            artifact.write_text('previous')
            self.assertNotEqual(self.render(pathlib.Path(temp).resolve()).returncode, 0)
            self.assertEqual(artifact.read_text(), 'previous')
            self.assertFalse((root / 'service-plan.txt').exists())
            target = root / 'real'
            target.mkdir()
            (root / 'link').symlink_to(target, target_is_directory=True)
            self.assertNotEqual(self.render(root / 'link').returncode, 0)
            self.assertEqual(list(target.iterdir()), [])


if __name__ == '__main__':
    unittest.main()

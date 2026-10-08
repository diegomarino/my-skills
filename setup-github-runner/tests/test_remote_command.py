"""Remote command rendering must preserve both shell parsing boundaries."""
import pathlib
import shlex
import subprocess
import sys
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'remote_command.py'


class RemoteCommandTests(unittest.TestCase):
    def render(self, host='build-host.example', path="/private/tmp/task ' $(touch sentinel).sh", user='host-admin'):
        return subprocess.run([sys.executable, str(SCRIPT), '--host', host,
                               '--admin-account', user, '--script', path], capture_output=True, text=True)

    def test_preserves_host_and_script_across_both_shell_boundaries(self):
        script = "/private/tmp/task ' $(touch sentinel).sh"
        result = self.render(path=script)
        self.assertEqual(result.returncode, 0, result.stderr)
        local = shlex.split(result.stdout)
        self.assertEqual(local[:5], ['ssh', '-t', '-l', 'host-admin', '--'])
        self.assertEqual(local[5], 'build-host.example')
        self.assertEqual(shlex.split(local[6]), ['sudo', '--', '/bin/bash', '--', script])
        self.assertEqual(len(local), 7)

    def test_rejects_invalid_transport_inputs(self):
        for kwargs in [{'host': '-oProxyCommand=anything'}, {'host': 'host name'},
                       {'host': 'host\ncommand'}, {'host': 'host;command'},
                       {'host': 'admin@host'}, {'host': 'foo::bar'}, {'host': 'fe80::1%en0;command'}, {'user': '-root'}, {'user': 'a b'},
                       {'path': 'relative'}, {'path': '/tmp/../script'}, {'path': '/tmp/a\nscript'}]:
            with self.subTest(kwargs=kwargs):
                result = self.render(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')

    def test_accepts_ipv6_with_separate_admin_account(self):
        for host in ['2001:db8::10', '::1', '::ffff:192.0.2.1', 'fe80::1%en0']:
            with self.subTest(host=host):
                result = self.render(host=host, path='/tmp/task.sh')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(shlex.split(result.stdout)[5], host)

    def test_common_ssh_formats_have_actionable_errors(self):
        for host, hint in [('admin@build-host', '--admin-account'),
                           ('build-host:2222', 'SSH config alias')]:
            with self.subTest(host=host):
                result = self.render(host=host)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(hint, result.stderr.splitlines()[-1])
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()

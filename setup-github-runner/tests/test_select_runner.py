import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'select_runner.py'
spec = importlib.util.spec_from_file_location('select_runner', PATH)
selector = importlib.util.module_from_spec(spec)
if PATH.exists():
    spec.loader.exec_module(selector)


def runner(**changes):
    value = dict(name='worker', status='online', busy=False,
                 labels=[{'name': x} for x in ['self-hosted', 'repo-ci', 'Linux', 'X64']])
    value.update(changes)
    return value


class SelectorTests(unittest.TestCase):
    def select(self, pages=None, **changes):
        env = dict(GITHUB_REPOSITORY='acme/widget', RUNNER_READ_TOKEN='private',
                   PREFERRED_RUNNER_NAME='worker', PREFERRED_RUNNER_LABEL='repo-ci',
                   RUNNER_LABELS='["Linux", "X64"]', HOSTED_RUNNER='ubuntu-24.04',
                   TRUSTED_EVENT='true', GITHUB_EVENT_NAME='push',
                   GITHUB_REF='refs/heads/main', TRUSTED_RUNNER_REF='refs/heads/main')
        env.update(changes)
        self.requests = []
        self.reasons = []
        def fetch(url, token, timeout):
            self.requests.append((url, token, timeout))
            if isinstance(pages, Exception):
                raise pages
            return pages[len(self.requests) - 1]
        return selector.select(env, fetch, self.reasons.append)

    def test_online_idle(self):
        self.assertEqual(self.select([{'total_count': 1, 'runners': [runner()]}]),
                         ['self-hosted', 'repo-ci', 'Linux', 'X64'])
        self.assertIn('name=worker', self.requests[0][0])
        self.assertEqual(self.requests[0][2], 5)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.reasons, ['selected'])

    def test_dispatch_and_exact_ref_boundary(self):
        page = {'total_count': 1, 'runners': [runner()]}
        self.assertIsInstance(self.select([page], GITHUB_EVENT_NAME='workflow_dispatch'), list)
        self.assertEqual(len(self.requests), 1)
        for ref in ['refs/heads/MAIN', 'refs/heads/main ', '', 'refs/heads/other']:
            with self.subTest(ref=ref):
                self.assertEqual(self.select([], GITHUB_REF=ref), 'ubuntu-24.04')
                self.assertEqual(self.requests, [])
                self.assertEqual(self.reasons, ['untrusted-ref'])

    def test_unavailable_and_malformed(self):
        for candidate in [runner(status='offline'), runner(busy=True), runner(busy=0),
                          runner(name='other'), runner(labels=[{'name': 'self-hosted'}]),
                          {}, runner(labels=[{'name': 'self-hosted'}, None])]:
            with self.subTest(candidate=candidate):
                self.assertEqual(self.select([{'total_count': 1, 'runners': [candidate]}]), 'ubuntu-24.04')
                self.assertEqual(len(self.requests), 1)
        for page in [{}, {'total_count': 0, 'runners': []}, [],
                     {'total_count': 1, 'runners': 'bad'}, {'total_count': '1', 'runners': []},
                     {'total_count': 2, 'runners': [runner()]},
                     {'total_count': 2, 'runners': [runner(), runner()]}]:
            with self.subTest(page=page):
                self.assertEqual(self.select([page]), 'ubuntu-24.04')
                self.assertEqual(len(self.requests), 1)

    def test_skips_api(self):
        for changes in [dict(FORCE_HOSTED='true'), dict(TRUSTED_EVENT='false'),
                        dict(TRUSTED_EVENT=''), dict(RUNNER_READ_TOKEN=''),
                        dict(GITHUB_REF='refs/heads/MAIN'), dict(TRUSTED_RUNNER_REF=''),
                        dict(GITHUB_EVENT_NAME='pull_request'), dict(GITHUB_EVENT_NAME='schedule'),
                        dict(PREFERRED_RUNNER_NAME=''), dict(PREFERRED_RUNNER_LABEL=''),
                        dict(RUNNER_LABELS='not json'), dict(RUNNER_LABELS='[]'),
                        dict(RUNNER_LABELS='["Linux"]'), dict(GITHUB_REPOSITORY='../secret'),
                        dict(RUNNER_LABELS='["Windows", "X64"]'),
                        dict(GITHUB_API_URL='https://attacker.invalid'),
                        dict(GITHUB_REPOSITORY='acme/..'),
                        dict(PREFERRED_RUNNER_LABEL='self-hosted'),
                        dict(PREFERRED_RUNNER_LABEL='Linux'),
                        dict(PREFERRED_RUNNER_LABEL='macOS'),
                        dict(PREFERRED_RUNNER_LABEL='Windows'),
                        dict(PREFERRED_RUNNER_LABEL='x64'),
                        dict(PREFERRED_RUNNER_LABEL='ARM'),
                        dict(PREFERRED_RUNNER_LABEL='ARM64'),
                        dict(PREFERRED_RUNNER_LABEL='bad\nlabel')]:
            with self.subTest(changes=changes):
                self.assertEqual(self.select([], **changes), 'ubuntu-24.04')
                self.assertEqual(self.requests, [])

    def test_explicit_hosted_required_before_api(self):
        for value in ['', 'bad\nlabel', '["ubuntu-latest"]', 'self-hosted', 'repo-ci', 'Linux', 'ubuntu-made-up']:
            for changes in [{}, {'TRUSTED_EVENT': 'false'}, {'FORCE_HOSTED': 'true'}]:
                with self.subTest(value=value, changes=changes):
                    with self.assertRaises(ValueError):
                        self.select([], HOSTED_RUNNER=value, **changes)
                    self.assertEqual(self.requests, [])

    def test_verified_standard_fallbacks(self):
        for label in ['ubuntu-24.04-arm', 'windows-2025', 'macos-15-intel']:
            with self.subTest(label=label):
                self.assertEqual(self.select([], HOSTED_RUNNER=label, FORCE_HOSTED='true'), label)
                self.assertEqual(self.requests, [])

    def test_api_error_and_custom_fallback(self):
        self.assertEqual(self.select(ValueError('invalid JSON secret'), HOSTED_RUNNER='macos-15'), 'macos-15')
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.reasons, ['api-error'])

    def test_safe_fallback_reasons(self):
        for changes, reason in [(dict(FORCE_HOSTED='true'), 'forced'),
                                (dict(RUNNER_READ_TOKEN=''), 'missing-config:RUNNER_READ_TOKEN'),
                                (dict(RUNNER_LABELS='secret invalid JSON'), 'invalid-platform-labels'),
                                (dict(GITHUB_REF='refs/heads/MAIN'), 'untrusted-ref')]:
            with self.subTest(reason=reason):
                self.assertEqual(self.select([], **changes), 'ubuntu-24.04')
                self.assertEqual(self.reasons, [reason])
                self.assertEqual(self.requests, [])
        for candidate, reason in [(runner(busy=True), 'busy-or-invalid-state'),
                                  (runner(status='offline'), 'not-online'),
                                  (runner(name='other'), 'no-unique-match'),
                                  (runner(labels=[]), 'labels-missing')]:
            with self.subTest(reason=reason):
                self.select([{'total_count': 1, 'runners': [candidate]}])
                self.assertEqual(self.reasons, [reason])
                self.assertEqual(len(self.requests), 1)
        for code in [401, 403, 429, 500]:
            self.select(HTTPError('https://secret.invalid', code, 'private token', {}, None))
            self.assertEqual(self.reasons, ['http-' + str(code)])
            self.assertEqual(len(self.requests), 1)

    def test_hosted_error_quotes_rejected_value(self):
        with self.assertRaises(ValueError) as caught:
            self.select([], HOSTED_RUNNER='bad\n::error::label')
        message = str(caught.exception)
        self.assertIn('"bad\\n::error::label"', message)
        self.assertIn('ubuntu-24.04', message)
        self.assertNotIn('\n', message)
        self.assertEqual(self.requests, [])

    def test_pagination_and_incomplete_inventory(self):
        first = [runner(name='other') for _ in range(100)]
        self.assertEqual(self.select([{'total_count': 101, 'runners': first},
                                     {'total_count': 101, 'runners': [runner()]}]),
                         ['self-hosted', 'repo-ci', 'Linux', 'X64'])
        self.assertIn('page=2', self.requests[1][0])
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.select([{'total_count': 101, 'runners': first},
                                     {'total_count': 101, 'runners': []}]), 'ubuntu-24.04')
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.reasons, ['inventory-incomplete'])
        self.assertEqual(self.select([{'total_count': 1001, 'runners': first}]), 'ubuntu-24.04')
        self.assertEqual(len(self.requests), 1)

    def test_http_json_boundary(self):
        class Response:
            def __init__(self, content):
                self.content = content
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return self.content[:limit]
        class Opener:
            def open(self, request, timeout):
                self.request, self.timeout = request, timeout
                return Response(content)
        opener = Opener()
        for content in [b'{"total_count":0,"runners":[]}', b'not-json', b'x' * (1024 * 1024 + 1)]:
            with self.subTest(length=len(content)), patch.object(selector, 'build_opener', return_value=opener):
                if content.startswith(b'{'):
                    self.assertEqual(selector.fetch_page('https://api.github.com/test', 'secret', 5),
                                     {'total_count': 0, 'runners': []})
                    self.assertEqual(opener.request.get_header('Authorization'), 'Bearer secret')
                    self.assertEqual(opener.timeout, 5)
                else:
                    with self.assertRaises(ValueError):
                        selector.fetch_page('https://api.github.com/test', 'secret', 5)
        self.assertIsNone(selector.NoRedirect().redirect_request(None, None, 302, '', {},
                                                                  'https://attacker.invalid'))

    def test_output_json(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out'
            result = subprocess.run([sys.executable, str(PATH)], env={'GITHUB_OUTPUT': str(output), 'HOSTED_RUNNER': 'ubuntu-24.04'},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text().split('=', 1)[1]), 'ubuntu-24.04')
            self.assertIn('Runner routing: untrusted-event', result.stderr)


if __name__ == '__main__':
    unittest.main()

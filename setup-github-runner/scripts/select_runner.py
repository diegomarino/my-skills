#!/usr/bin/env python3
"""Select a verified idle runner, or a hosted label; no third-party dependencies."""
import json
import os
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


# Verified standard labels: GitHub's hosted-runner table, 2026-10-08.
# Add labels only after checking the official table; custom larger runners need a reviewed adapter.
HOSTED_LABELS = {
    'ubuntu-latest', 'ubuntu-22.04', 'ubuntu-24.04', 'ubuntu-24.04-arm',
    'windows-latest', 'windows-2022', 'windows-2025', 'windows-11-arm',
    'macos-latest', 'macos-14', 'macos-15', 'macos-26', 'macos-15-intel', 'macos-26-intel',
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_page(url, token, timeout):
    request = Request(url, headers={'Authorization': 'Bearer ' + token,
                                   'Accept': 'application/vnd.github+json',
                                   'X-GitHub-Api-Version': '2026-03-10'})
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError('Oversize response')
        return json.loads(body)


def choose(runners, name, required, fallback, report):
    matches = [item for item in runners if isinstance(item, dict) and item.get('name') == name]
    if len(matches) != 1:
        report('no-unique-match')
        return fallback
    runner = matches[0]
    labels = runner.get('labels')
    if runner.get('status') != 'online':
        report('not-online')
        return fallback
    if runner.get('busy') is not False:
        report('busy-or-invalid-state')
        return fallback
    if (not isinstance(labels, list)
            or not all(isinstance(item, dict) and isinstance(item.get('name'), str) for item in labels)):
        report('invalid-runner-labels')
        return fallback
    actual = {item['name'].casefold() for item in labels}
    if not {label.casefold() for label in required} <= actual:
        report('labels-missing')
        return fallback
    report('selected')
    return required


def select(env, fetch=fetch_page, report=None):
    if report is None:
        report = lambda reason: print('Runner routing: ' + reason, file=sys.stderr)
    fallback = env.get('HOSTED_RUNNER', '')
    if fallback not in HOSTED_LABELS:
        raise ValueError('Invalid HOSTED_RUNNER ' + json.dumps(fallback, ensure_ascii=True)
                         + '; choose one of: ' + ', '.join(sorted(HOSTED_LABELS)))
    def hosted(reason):
        report(reason)
        return fallback
    name = env.get('PREFERRED_RUNNER_NAME', '')
    label = env.get('PREFERRED_RUNNER_LABEL', '')
    token = env.get('RUNNER_READ_TOKEN', '')
    repo = env.get('GITHUB_REPOSITORY', '')
    if env.get('FORCE_HOSTED') == 'true':
        return hosted('forced')
    if (env.get('TRUSTED_EVENT') != 'true'
            or env.get('GITHUB_EVENT_NAME') not in {'push', 'workflow_dispatch'}):
        return hosted('untrusted-event')
    # GitHub expression equality ignores case; enforce the authorization boundary here.
    if not env.get('TRUSTED_RUNNER_REF') or env.get('GITHUB_REF') != env['TRUSTED_RUNNER_REF']:
        return hosted('untrusted-ref')
    for variable in ['PREFERRED_RUNNER_NAME', 'PREFERRED_RUNNER_LABEL', 'RUNNER_READ_TOKEN']:
        if not env.get(variable):
            return hosted('missing-config:' + variable)
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', label)
            or label.casefold() in {'self-hosted', 'linux', 'macos', 'windows', 'x64', 'arm', 'arm64'}):
        return hosted('invalid-routing-label')
    if (not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', repo)
            or repo.split('/')[1] in {'.', '..'}):
        return hosted('invalid-repository')
    if env.get('GITHUB_API_URL', 'https://api.github.com') != 'https://api.github.com':
        return hosted('unsupported-api')
    try:
        platform = json.loads(env.get('RUNNER_LABELS', ''))
        if (not isinstance(platform, list) or not all(isinstance(x, str) and x for x in platform)
                or not {'linux', 'macos'} & {x.casefold() for x in platform}
                or not {'x64', 'arm64', 'arm'} & {x.casefold() for x in platform}):
            return hosted('invalid-platform-labels')
    except (ValueError, TypeError):
        return hosted('invalid-platform-labels')
    try:
        required = list(dict.fromkeys(['self-hosted', label] + platform))
        runners = []
        total = None
        for page in range(1, 11):
            query = urlencode({'name': name, 'per_page': 100, 'page': page})
            data = fetch(f'https://api.github.com/repos/{repo}/actions/runners?{query}', token, 5)
            if (not isinstance(data, dict) or type(data.get('total_count')) is not int
                    or not isinstance(data.get('runners'), list)):
                return hosted('invalid-api-data')
            count = data['total_count']
            batch = data['runners']
            if count < 0 or count > 1000 or len(batch) > 100 or (total is not None and count != total):
                return hosted('inventory-incomplete')
            total = count
            runners.extend(batch)
            if len(runners) == total:
                return choose(runners, name, required, fallback, report)
            if len(runners) > total or len(batch) < 100:
                return hosted('inventory-incomplete')
    except HTTPError as error:
        return hosted('http-' + str(error.code))
    except Exception:
        # Lookup failures are routing failures; exception strings can contain credentials.
        return hosted('api-error')
    return hosted('inventory-incomplete')


if __name__ == '__main__':
    try:
        result = select(os.environ)
        line = 'runner=' + json.dumps(result, separators=(',', ':')) + '\n'
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(line)
        print(line, end='')
    except ValueError as error:
        raise SystemExit(str(error))
    except (KeyError, OSError):
        raise SystemExit('Invalid selector output path')

"""Exercise the publication adapter at its authenticated HTTP and RSA boundaries."""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[2]
SHA = 'a' * 40
BRANCH = 'publication/gitlab-7-aaaaaaaaaaaa'
MR = 'https://gitlab.com/bijux-oss/bijux-std/-/merge_requests/7'
EVIDENCE = 'https://gitlab.com/bijux-oss/bijux-std/-/pipelines/99'
REPOSITORY = {'id': 42, 'full_name': 'bijux/bijux-std', 'default_branch': 'main',
              'owner': {'login': 'bijux'}, 'archived': False, 'disabled': False}
PERMISSIONS = {'contents': 'write', 'pull_requests': 'write', 'statuses': 'write',
               'workflows': 'write', 'administration': 'read', 'metadata': 'read'}


def pull_request(*, merged=False, state='open', sha=SHA):
    return {'number': 17, 'html_url': 'https://github.com/bijux/bijux-std/pull/17',
            'state': state, 'merged': merged, 'merged_at': '2026-11-15T00:00:00Z' if merged else None,
            'head': {'sha': sha, 'ref': BRANCH, 'repo': REPOSITORY},
            'base': {'ref': 'main', 'repo': REPOSITORY},
            'body': f'Canonical GitLab merge request: {MR}\n\nValidation evidence: {EVIDENCE}\n',
            'labels': [{'name': 'gitlab-publication'}]}


class Response(io.BytesIO):
    def __init__(self, body, *, status=200, headers=None, url=None):
        super().__init__(body if isinstance(body, bytes) else json.dumps(body).encode())
        self.status = status
        self.headers = {'Content-Type': 'application/json', **(headers or {})}
        self.url = url

    def geturl(self):
        return self.url


class Transport:
    def __init__(self, routes):
        self.routes = list(routes)
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if not self.routes:
            raise AssertionError('Unexpected authenticated request: ' + request.get_method())
        method, path, value = self.routes.pop(0)
        if request.get_method() != method or request.full_url != 'https://api.github.com' + path:
            raise AssertionError('Authenticated request differs from its expected operation')
        if not 0 < timeout <= 20:
            raise AssertionError('Authenticated HTTP timeout is unbounded')
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, Response):
            value = Response(value, status=201 if method == 'POST' and not is_label_attachment(path) else 200)
        if value.url is None:
            value.url = request.full_url
        return value


def is_label_attachment(path):
    return path.endswith('/issues/17/labels')


def mirror_rows(*, enabled=False, repository=None):
    return [('GET', '/repos/bijux/bijux-std', REPOSITORY if repository is None else repository),
            ('GET', '/repos/bijux/bijux-std/actions/permissions', {'enabled': enabled})]


def search_path(page=1):
    return f'/repos/bijux/bijux-std/pulls?state=all&head=bijux%3Apublication%2Fgitlab-7-aaaaaaaaaaaa&base=main&per_page=100&page={page}'


class GitHubPublicationTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'shared/bijux-gitlab/publication/github.py'
        self.assertTrue(path.is_file(), 'Publication requires a bounded, source-owned GitHub mirror adapter')
        spec = importlib.util.spec_from_file_location('bijux_publication_github', path)
        self.adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.adapter)

    def client(self, routes):
        transport = Transport(routes)
        return self.adapter.GitHub('bijux/bijux-std', 42, 'inert-private-token', opener=transport), transport

    def test_mirror_requires_exact_repository_identity_main_and_disabled_actions(self):
        client, transport = self.client(mirror_rows())
        self.assertEqual(client.verify_mirror(), {'repository': 'bijux/bijux-std', 'repository_id': 42,
                                                 'actions_enabled': False})
        self.assertFalse(transport.routes)
        for change in ({'id': 43}, {'id': True}, {'full_name': 'someone/bijux-std'},
                       {'default_branch': 'master'}, {'archived': True}, {'disabled': True}):
            client, _ = self.client(mirror_rows(repository={**REPOSITORY, **change}))
            with self.subTest(change=change), self.assertRaises(ValueError): client.verify_mirror()
        for enabled in (True, 0, None, 'false'):
            client, _ = self.client(mirror_rows(enabled=enabled))
            with self.subTest(enabled=enabled), self.assertRaises(ValueError): client.verify_mirror()

    def test_status_is_native_gitlab_validation_and_checks_actions_before_and_after(self):
        status = {'context': 'gitlab / validation', 'state': 'success', 'target_url': EVIDENCE}
        client, transport = self.client(mirror_rows() + [('POST', '/repos/bijux/bijux-std/statuses/' + SHA, status)] + mirror_rows())
        self.assertEqual(client.status(SHA, EVIDENCE), status)
        payload = json.loads(transport.requests[2].data)
        self.assertEqual(payload, {**status, 'description': 'Validated by the canonical GitLab pipeline'})
        self.assertFalse(transport.routes)
        client, transport = self.client(mirror_rows(enabled=True))
        with self.assertRaises(ValueError): client.status(SHA, EVIDENCE)
        self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))
        client, _ = self.client(mirror_rows() + [('POST', '/repos/bijux/bijux-std/statuses/' + SHA, status)] + mirror_rows(enabled=True))
        with self.assertRaises(ValueError): client.status(SHA, EVIDENCE)

    def test_invalid_input_never_becomes_an_authenticated_request(self):
        for repository in ('someone/repo', 'bijux/repo?access=1', 'bijux/../repo', 'https://github.com/bijux/repo'):
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                self.adapter.GitHub(repository, 42, 'inert-private-token')
        for token in ('', 'token\nAuthorization: other'):
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.adapter.GitHub('bijux/bijux-std', 42, token)
        for sha, url in (('HEAD', EVIDENCE), (SHA, 'http://gitlab.com/example'),
                         (SHA, EVIDENCE + '?token=inert'), (SHA, 'https://gitlab.com.evil/bijux-oss/repo/-/pipelines/1')):
            client, transport = self.client([])
            with self.subTest(sha=sha, url=url), self.assertRaises(ValueError): client.status(sha, url)
            self.assertFalse(transport.requests)

    def test_creation_uses_exact_existing_branch_and_links_canonical_review_and_evidence(self):
        routes = mirror_rows() + [
            ('GET', search_path(), []),
            ('GET', '/repos/bijux/bijux-std/git/ref/heads/' + BRANCH, {'ref': 'refs/heads/' + BRANCH, 'object': {'type': 'commit', 'sha': SHA}}),
            ('POST', '/repos/bijux/bijux-std/pulls', pull_request()),
            ('GET', '/repos/bijux/bijux-std/labels/gitlab-publication', {'name': 'gitlab-publication'}),
            ('POST', '/repos/bijux/bijux-std/issues/17/labels', [{'name': 'gitlab-publication'}]),
        ] + mirror_rows()
        client, transport = self.client(routes)
        result = client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
        self.assertEqual(result['number'], 17)
        self.assertEqual(result['url'], 'https://github.com/bijux/bijux-std/pull/17')
        payload = json.loads(next(request.data for request in transport.requests if request.get_method() == 'POST' and request.full_url.endswith('/pulls')))
        self.assertEqual(payload['head'], BRANCH)
        self.assertEqual(payload['base'], 'main')
        self.assertIn(MR, payload['body'])
        self.assertIn(EVIDENCE, payload['body'])
        self.assertTrue(all(not request.full_url.endswith('/merge') for request in transport.requests))
        self.assertFalse(transport.routes)

    def test_existing_open_or_merged_pr_is_reused_without_duplicate_creation(self):
        for merged, state in ((False, 'open'), (True, 'closed')):
            pr = pull_request(merged=merged, state=state)
            routes = mirror_rows() + [('GET', search_path(), [pr]),
                ('GET', '/repos/bijux/bijux-std/pulls/17', pr),
                ('GET', '/repos/bijux/bijux-std/labels/gitlab-publication', {'name': 'gitlab-publication'}),
                ('POST', '/repos/bijux/bijux-std/issues/17/labels', [{'name': 'gitlab-publication'}])] + mirror_rows()
            client, transport = self.client(routes)
            with self.subTest(merged=merged):
                self.assertEqual(client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)['number'], 17)
                self.assertFalse(any(request.get_method() == 'POST' and request.full_url.endswith('/pulls') for request in transport.requests))
                self.assertFalse(transport.routes)

    def test_closed_unmerged_ambiguous_or_foreign_pr_is_preserved_without_replacement(self):
        for rows in ([pull_request(), pull_request()], [{**pull_request(), 'head': {**pull_request()['head'], 'sha': 'b' * 40}}]):
            client, transport = self.client(mirror_rows() + [('GET', search_path(), rows)])
            with self.subTest(rows=rows), self.assertRaises(ValueError): client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
            self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))
        pr = pull_request(state='closed')
        client, transport = self.client(mirror_rows() + [('GET', search_path(), [pr]), ('GET', '/repos/bijux/bijux-std/pulls/17', pr)])
        with self.assertRaises(ValueError): client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
        self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))

    def test_branch_mr_and_sha_must_agree_before_any_network_operation(self):
        for branch, mr in ((BRANCH + 'x', MR), (BRANCH, MR.replace('/7', '/8')),
                           (BRANCH, MR.replace('bijux-oss', 'someone'))):
            client, transport = self.client([])
            with self.subTest(branch=branch, mr=mr), self.assertRaises(ValueError): client.ensure_pr(branch, SHA, mr, EVIDENCE)
            self.assertFalse(transport.requests)
        client, transport = self.client(mirror_rows() + [('GET', search_path(), []),
            ('GET', '/repos/bijux/bijux-std/git/ref/heads/' + BRANCH, {'ref': 'refs/heads/' + BRANCH, 'object': {'type': 'commit', 'sha': 'b' * 40}})])
        with self.assertRaises(ValueError): client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
        self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))

    def test_all_state_search_paginates_before_deciding_to_create(self):
        pr = pull_request()
        next_url = 'https://api.github.com' + search_path(2)
        routes = mirror_rows() + [('GET', search_path(), Response([], headers={'Link': f'<{next_url}>; rel="next"'})),
            ('GET', search_path(2), [pr]), ('GET', '/repos/bijux/bijux-std/pulls/17', pr),
            ('GET', '/repos/bijux/bijux-std/labels/gitlab-publication', {'name': 'gitlab-publication'}),
            ('POST', '/repos/bijux/bijux-std/issues/17/labels', [{'name': 'gitlab-publication'}])] + mirror_rows()
        client, transport = self.client(routes)
        self.assertEqual(client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)['number'], 17)
        self.assertFalse(transport.routes)

    def test_label_is_created_and_applied_when_absent(self):
        pr = pull_request()
        absent = HTTPError('https://api.github.com/redacted', 404, 'Not Found', {}, io.BytesIO(b'not logged'))
        routes = mirror_rows() + [('GET', search_path(), [pr]), ('GET', '/repos/bijux/bijux-std/pulls/17', pr),
            ('GET', '/repos/bijux/bijux-std/labels/gitlab-publication', absent),
            ('POST', '/repos/bijux/bijux-std/labels', {'name': 'gitlab-publication'}),
            ('POST', '/repos/bijux/bijux-std/issues/17/labels', [{'name': 'gitlab-publication'}])] + mirror_rows()
        client, transport = self.client(routes)
        self.assertEqual(client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)['number'], 17)
        label_write = next(request for request in transport.requests if request.get_method() == 'POST' and request.full_url.endswith('/issues/17/labels'))
        self.assertEqual(json.loads(label_write.data), {'labels': ['gitlab-publication']})
        self.assertFalse(transport.routes)

    def test_acknowledgement_polls_for_native_merged_state_without_merge_api(self):
        routes = mirror_rows() + [('GET', '/repos/bijux/bijux-std/pulls/17', pull_request()),
            ('GET', '/repos/bijux/bijux-std/pulls/17', pull_request(merged=True, state='closed'))] + mirror_rows()
        client, transport = self.client(routes)
        with patch.object(self.adapter.time, 'sleep'):
            result = client.acknowledge_pr(17, SHA)
        self.assertIs(result['merged'], True)
        self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))
        self.assertFalse(transport.routes)

    def test_acknowledgement_refuses_wrong_head_or_unmerged_poll_exhaustion(self):
        client, _ = self.client(mirror_rows() + [('GET', '/repos/bijux/bijux-std/pulls/17', pull_request(merged=True, state='closed', sha='b' * 40))])
        with self.assertRaises(ValueError): client.acknowledge_pr(17, SHA)
        client, transport = self.client(mirror_rows() + [('GET', '/repos/bijux/bijux-std/pulls/17', pull_request())] * 6)
        with patch.object(self.adapter.time, 'sleep'), self.assertRaises(ValueError): client.acknowledge_pr(17, SHA)
        self.assertEqual(len(transport.requests), 8)

    def test_transport_refuses_redirect_html_duplicate_json_and_oversized_body_without_secret_leak(self):
        failure = HTTPError('https://api.github.com/inert-private-token', 302, 'inert-private-token',
                            {'Location': 'https://evil.example/inert-private-token'}, io.BytesIO(b'inert-private-token'))
        for value in (failure, URLError('inert-private-token'),
                      Response(b'<html>inert-private-token</html>'), Response(b'{"id":42,"id":43}'),
                      Response(b'x' * (4 * 1024 * 1024 + 1)),
                      Response(REPOSITORY, url='https://evil.example/inert-private-token')):
            client, transport = self.client([('GET', '/repos/bijux/bijux-std', value)])
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError) as caught: client.verify_mirror()
            self.assertNotIn('inert-private-token', str(caught.exception))
            self.assertEqual(len(transport.requests), 1)

    def test_default_transport_disables_redirects_and_headers_use_only_explicit_token(self):
        opened = []
        transport = Transport(mirror_rows())
        with patch.object(self.adapter, 'build_opener', side_effect=lambda *handlers: (opened.extend(handlers), transport)[1]):
            client = self.adapter.GitHub('bijux/bijux-std', 42, 'explicit-only')
            client.verify_mirror()
        self.assertTrue(opened)
        self.assertIsNone(opened[0].redirect_request(None, None, 302, None, {}, 'https://evil.example'))
        for request in transport.requests:
            self.assertEqual(request.get_header('Authorization'), 'Bearer explicit-only')
            self.assertIsNone(request.get_header('Cookie'))

    def key(self):
        if not shutil.which('openssl'): self.skipTest('OpenSSL is unavailable for RSA boundary verification')
        parent = ROOT / 'artifacts/gitlab-publication'
        parent.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(scratch.cleanup)
        key = Path(scratch.name) / 'publisher.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(key)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        return key

    def installation(self, **changes):
        return {'id': 22, 'app_id': 11, 'account': {'login': 'bijux'}, 'repository_selection': 'selected',
                'permissions': PERMISSIONS, 'suspended_at': None, **changes}

    def minted(self, **changes):
        return {'token': 'minted-inert-token', 'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=50)).isoformat(),
                'permissions': PERMISSIONS, 'repository_selection': 'selected', **changes}

    def factory_routes(self, installation=None, minted=None, repositories=None):
        return [('GET', '/app/installations/22', self.installation() if installation is None else installation),
                ('POST', '/app/installations/22/access_tokens', self.minted() if minted is None else minted),
                ('GET', '/installation/repositories?per_page=100', {'total_count': 1, 'repositories': [REPOSITORY]} if repositories is None else repositories)]

    def test_real_rs256_jwt_and_minted_token_are_scoped_to_exact_installation_and_repository(self):
        key = self.key()
        transport = Transport(self.factory_routes())
        self.assertEqual(self.adapter.installation_token(11, 22, key, 42, opener=transport), 'minted-inert-token')
        token = transport.requests[0].get_header('Authorization').removeprefix('Bearer ')
        header, payload, signature = token.split('.')
        decode = lambda value: base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))
        self.assertEqual(json.loads(decode(header)), {'alg': 'RS256', 'typ': 'JWT'})
        claims = json.loads(decode(payload))
        self.assertEqual(claims['iss'], '11')
        self.assertGreater(claims['exp'], datetime.now(timezone.utc).timestamp())
        self.assertLessEqual(claims['exp'] - claims['iat'], 9 * 60)
        public = key.with_name('publisher.pub')
        signature_path = key.with_name('signature.bin')
        public.write_bytes(subprocess.check_output(['openssl', 'pkey', '-in', str(key), '-pubout'], stderr=subprocess.PIPE))
        signature_path.write_bytes(decode(signature))
        verified = subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(public), '-signature', str(signature_path)],
                                  input=(header + '.' + payload).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        self.assertEqual(verified.returncode, 0)
        self.assertEqual(json.loads(transport.requests[1].data), {'repository_ids': [42], 'permissions': PERMISSIONS})
        self.assertEqual(transport.requests[2].get_header('Authorization'), 'Bearer minted-inert-token')
        self.assertFalse(transport.routes)

    def test_factory_refuses_foreign_all_repository_suspended_or_wrong_permission_installation(self):
        key = self.key()
        for change in ({'app_id': 12}, {'id': 23}, {'account': {'login': 'someone'}},
                       {'repository_selection': 'all'}, {'suspended_at': '2026-11-15T00:00:00Z'},
                       {'permissions': {**PERMISSIONS, 'actions': 'write'}}):
            transport = Transport([('GET', '/app/installations/22', self.installation(**change))])
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.adapter.installation_token(11, 22, key, 42, opener=transport)
            self.assertEqual(len(transport.requests), 1)

    def test_factory_rejects_overbroad_expired_or_missing_minted_token_evidence(self):
        key = self.key()
        for change in ({'token': ''}, {'permissions': {**PERMISSIONS, 'administration': 'write'}},
                       {'repository_selection': 'all'}, {'expires_at': '2000-01-01T00:00:00Z'},
                       {'expires_at': (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}):
            transport = Transport(self.factory_routes(minted=self.minted(**change))[:2])
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.adapter.installation_token(11, 22, key, 42, opener=transport)
            self.assertEqual(len(transport.requests), 2)
        for repositories in ({'total_count': 2, 'repositories': [REPOSITORY, {**REPOSITORY, 'id': 43}]},
                             {'total_count': 1, 'repositories': [{**REPOSITORY, 'id': 43}]},
                             {'total_count': 1, 'repositories': [{**REPOSITORY, 'full_name': 'someone/repo'}]}):
            transport = Transport(self.factory_routes(repositories=repositories))
            with self.subTest(repositories=repositories), self.assertRaises(ValueError):
                self.adapter.installation_token(11, 22, key, 42, opener=transport)

    def test_validation_and_review_links_must_belong_to_the_same_native_project(self):
        client, transport = self.client([])
        with self.assertRaises(ValueError):
            client.ensure_pr(BRANCH, SHA, MR, EVIDENCE.replace('bijux-std', 'bijux-core'))
        self.assertFalse(transport.requests)

    def test_pr_creation_race_reuses_exact_native_pr_instead_of_retrying_post(self):
        pr = pull_request()
        race = HTTPError('https://api.github.com/redacted', 422, 'not logged', {}, io.BytesIO())
        routes = mirror_rows() + [('GET', search_path(), []),
            ('GET', '/repos/bijux/bijux-std/git/ref/heads/' + BRANCH,
             {'ref': 'refs/heads/' + BRANCH, 'object': {'type': 'commit', 'sha': SHA}}),
            ('POST', '/repos/bijux/bijux-std/pulls', race), ('GET', search_path(), [pr]),
            ('GET', '/repos/bijux/bijux-std/pulls/17', pr),
            ('GET', '/repos/bijux/bijux-std/labels/gitlab-publication', {'name': 'gitlab-publication'}),
            ('POST', '/repos/bijux/bijux-std/issues/17/labels', [{'name': 'gitlab-publication'}])] + mirror_rows()
        client, transport = self.client(routes)
        self.assertEqual(client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)['number'], 17)
        self.assertEqual(sum(request.get_method() == 'POST' and request.full_url.endswith('/pulls')
                             for request in transport.requests), 1)
        self.assertFalse(transport.routes)

    def test_pr_pagination_refuses_foreign_links_and_finite_page_exhaustion(self):
        for next_url in ('https://evil.example/' + search_path(2),
                         'https://api.github.com/repos/someone/repo/pulls?page=2'):
            client, transport = self.client(mirror_rows() + [('GET', search_path(),
                Response([], headers={'Link': f'<{next_url}>; rel="next"'}))])
            with self.subTest(next_url=next_url), self.assertRaises(ValueError):
                client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
            self.assertEqual(len(transport.requests), 3)
        routes = mirror_rows() + [('GET', search_path(page), Response([], headers={
            'Link': f'<https://api.github.com{search_path(page + 1)}>; rel="next"'})) for page in range(1, 11)]
        client, transport = self.client(routes)
        with self.assertRaises(ValueError): client.ensure_pr(BRANCH, SHA, MR, EVIDENCE)
        self.assertEqual(len(transport.requests), 12)
        self.assertTrue(all(request.get_method() == 'GET' for request in transport.requests))

    def test_status_requires_exact_server_acknowledgement(self):
        wrong = {'context': 'github / validation', 'state': 'success', 'target_url': EVIDENCE}
        client, _ = self.client(mirror_rows() + [('POST', '/repos/bijux/bijux-std/statuses/' + SHA, wrong)])
        with self.assertRaises(ValueError): client.status(SHA, EVIDENCE)

    def test_transport_enforces_content_length_and_whole_body_deadline(self):
        for response in (Response(REPOSITORY, headers={'Content-Length': '999'}),
                         Response(REPOSITORY, headers={'Content-Length': str(5 * 1024 * 1024)})):
            client, _ = self.client([('GET', '/repos/bijux/bijux-std', response)])
            with self.assertRaises(ValueError): client.verify_mirror()
        client, _ = self.client([('GET', '/repos/bijux/bijux-std', REPOSITORY)])
        with patch.object(self.adapter.time, 'monotonic', side_effect=[0, 1, 21]), self.assertRaises(ValueError):
            client.verify_mirror()

    def test_non_rsa_key_cannot_emit_a_jwt_declaring_rs256(self):
        key = self.key()
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'EC', '-pkeyopt', 'ec_paramgen_curve:P-256', '-out', str(key)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        transport = Transport([])
        with self.assertRaises(ValueError):
            self.adapter.installation_token(11, 22, key, 42, opener=transport)
        self.assertFalse(transport.requests)

    def test_signing_errors_do_not_echo_key_path_contents_or_subprocess_diagnostics(self):
        key = self.key()
        key.write_text('private-key-content-that-must-not-escape')
        with self.assertRaises(ValueError) as caught:
            self.adapter.installation_token(11, 22, key, 42, opener=Transport([]))
        self.assertNotIn(str(key), str(caught.exception))
        self.assertNotIn('private-key-content', str(caught.exception))

    def test_transient_get_status_retries_before_any_publication_write(self):
        for code in (502, 503, 504):
            error = HTTPError('https://api.github.com/redacted', code, 'inert-private-token', {}, io.BytesIO())
            client, transport = self.client([('GET', '/repos/bijux/bijux-std', error)] + mirror_rows())
            with self.subTest(code=code), patch.object(self.adapter.time, 'sleep'):
                self.assertFalse(client.verify_mirror()['actions_enabled'])
            self.assertEqual(len(transport.requests), 3)
            self.assertFalse(transport.routes)

    def test_transient_get_retries_stop_after_three_attempts(self):
        errors = [HTTPError('https://api.github.com/redacted', 503, 'not retained', {}, io.BytesIO()) for _ in range(4)]
        client, transport = self.client([('GET', '/repos/bijux/bijux-std', error) for error in errors])
        with patch.object(self.adapter.time, 'sleep'), self.assertRaises(ValueError): client.verify_mirror()
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(len(transport.routes), 1)

    def test_small_numeric_retry_after_is_honored_without_resetting_get_deadline(self):
        error = HTTPError('https://api.github.com/redacted', 429, 'not retained', {'Retry-After': '1'}, io.BytesIO())
        client, transport = self.client([('GET', '/repos/bijux/bijux-std', error)] + mirror_rows())
        now = [100.0]
        def sleep(seconds): now[0] += seconds
        with patch.object(self.adapter.time, 'monotonic', side_effect=lambda: now[0]), \
                patch.object(self.adapter.time, 'sleep', side_effect=sleep):
            self.assertFalse(client.verify_mirror()['actions_enabled'])
        self.assertEqual(now[0], 101.0)
        self.assertEqual(transport.timeouts[:2], [20.0, 19.0])
        self.assertFalse(transport.routes)

    def test_retry_after_refuses_long_malformed_and_missing_delays_without_waiting(self):
        for value in ('9999999999', '-1', 'NaN', 'Wed, 01 Jan 2050 00:00:00 GMT', None):
            headers = {} if value is None else {'Retry-After': value}
            error = HTTPError('https://api.github.com/redacted', 429, 'inert-private-token', headers, io.BytesIO())
            client, transport = self.client([('GET', '/repos/bijux/bijux-std', error)])
            with self.subTest(value=value), patch.object(self.adapter.time, 'sleep') as sleep, self.assertRaises(ValueError) as caught:
                client.verify_mirror()
            sleep.assert_not_called()
            self.assertEqual(len(transport.requests), 1)
            self.assertNotIn('inert-private-token', str(caught.exception))

    def test_transient_post_failure_is_never_blindly_retried(self):
        error = HTTPError('https://api.github.com/redacted', 502, 'inert-private-token', {}, io.BytesIO())
        status = {'state': 'success', 'context': 'gitlab / validation', 'target_url': EVIDENCE}
        client, transport = self.client(mirror_rows() + [
            ('POST', '/repos/bijux/bijux-std/statuses/' + SHA, error),
            ('POST', '/repos/bijux/bijux-std/statuses/' + SHA, status)])
        with patch.object(self.adapter.time, 'sleep') as sleep, self.assertRaises(ValueError): client.status(SHA, EVIDENCE)
        sleep.assert_not_called()
        self.assertEqual(sum(request.get_method() == 'POST' for request in transport.requests), 1)
        self.assertEqual(len(transport.routes), 1)

    def test_retry_cannot_outlive_the_original_get_time_budget(self):
        error = HTTPError('https://api.github.com/redacted', 503, 'not retained', {}, io.BytesIO())
        client, transport = self.client([('GET', '/repos/bijux/bijux-std', error),
                                          ('GET', '/repos/bijux/bijux-std', REPOSITORY)])
        now = [100.0]
        def exhausted(seconds): now[0] += 21
        with patch.object(self.adapter.time, 'monotonic', side_effect=lambda: now[0]), \
                patch.object(self.adapter.time, 'sleep', side_effect=exhausted), self.assertRaises(ValueError):
            client.verify_mirror()
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(len(transport.routes), 1)

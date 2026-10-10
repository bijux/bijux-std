"""Refuse unowned workflow inputs before transport or filesystem writes."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('workflow_artifacts', ROOT / 'tests/bijux-docs/execution/workflow_artifacts.py')
ARTIFACTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARTIFACTS)


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as stream:
        for name, body in entries:
            stream.writestr(name, body)
    return output.getvalue()


class API:
    repository = 'bijux/bijux-std'

    def __init__(self, responses, body):
        self.responses, self.body, self.calls = responses, body, []

    def json(self, endpoint):
        self.calls.append(endpoint)
        return copy.deepcopy(self.responses[endpoint])

    def archive(self, artifact_id):
        self.calls.append(('download', artifact_id))
        return self.body


class WorkflowArtifactOwnershipTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.identity = {'run_id': 123, 'attempt': 2, 'head': 'a' * 40, 'checkout_sha': 'b' * 40,
                         'source_tree': 'c' * 40, 'workflow_id': 456,
                         'workflow_path': '.github/workflows/bijux-std.yml', 'head_branch': 'feat/docs-reader'}
        self.roles = {'fixtures': {'job_name': 'std / navigation fixtures',
                                  'artifact_prefix': 'docs-navigation-fixtures', 'upload_step': 'Retain immutable fixtures'}}
        self.body = archive([('producer-envelope.json', b'{"source":"current"}'), ('site/index.html', b'<h1>Current</h1>')])
        self.job = {'id': 22, 'name': 'std / navigation fixtures', 'run_id': 123, 'run_attempt': 2,
                    'head_sha': 'a' * 40, 'status': 'completed', 'conclusion': 'success',
                    'created_at': '2026-01-01T00:00:00Z', 'started_at': '2026-01-01T00:01:00Z',
                    'completed_at': '2026-01-01T00:03:59Z', 'steps': [
                        {'name': 'Produce fixtures', 'status': 'completed', 'conclusion': 'success',
                         'started_at': '2026-01-01T00:01:01Z', 'completed_at': '2026-01-01T00:03:40Z'},
                        {'name': 'Retain immutable fixtures', 'status': 'completed', 'conclusion': 'success',
                         'started_at': '2026-01-01T00:03:41Z', 'completed_at': '2026-01-01T00:03:58Z'}]}
        self.old = {**copy.deepcopy(self.job), 'id': 11, 'run_attempt': 1, 'conclusion': 'cancelled'}
        self.artifact = {'id': 33, 'name': 'docs-navigation-fixtures-' + 'b' * 40 + '-2',
                         'digest': 'sha256:' + hashlib.sha256(self.body).hexdigest(), 'size_in_bytes': len(self.body),
                         'expired': False, 'created_at': '2026-01-01T00:03:45Z', 'expires_at': '2026-02-01T00:00:00Z',
                         'workflow_run': {'id': 123, 'head_sha': 'a' * 40, 'head_branch': 'feat/docs-reader',
                                          'repository_id': 789, 'head_repository_id': 789}}
        prefix = 'repos/bijux/bijux-std/'
        self.paths = {'run': prefix + 'actions/runs/123', 'job': prefix + 'actions/jobs/22',
                      'artifact': prefix + 'actions/artifacts/33'}
        self.responses = {
            self.paths['run']: {'id': 123, 'run_attempt': 2, 'head_sha': 'a' * 40, 'workflow_id': 456,
                                'path': '.github/workflows/bijux-std.yml', 'head_branch': 'feat/docs-reader',
                                'repository': {'id': 789, 'full_name': 'bijux/bijux-std'},
                                'head_repository': {'id': 789, 'full_name': 'bijux/bijux-std'}},
            prefix + 'actions/workflows/456': {'id': 456, 'path': '.github/workflows/bijux-std.yml'},
            prefix + 'git/commits/' + 'a' * 40: {'sha': 'a' * 40, 'tree': {'sha': 'c' * 40}},
            prefix + 'git/commits/' + 'b' * 40: {'sha': 'b' * 40, 'tree': {'sha': 'c' * 40},
                                                'parents': [{'sha': 'd' * 40}, {'sha': 'a' * 40}]},
            self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1': {'total_count': 1, 'jobs': [self.job]},
            self.paths['run'] + '/jobs?filter=all&per_page=100&page=1': {'total_count': 2, 'jobs': [self.old, self.job]},
            self.paths['run'] + '/artifacts?per_page=100&page=1': {'total_count': 1, 'artifacts': [self.artifact]},
            self.paths['job']: self.job, self.paths['artifact']: self.artifact,
        }
        self.api = API(self.responses, self.body)
        self.now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    def select(self):
        return ARTIFACTS.select(self.api, ARTIFACTS.observe(self.api, self.identity), self.roles, now=self.now)

    def test_actual_latest_owner_and_failed_predecessor_are_distinct_and_retained(self):
        observed = ARTIFACTS.observe(self.api, self.identity)
        selected = ARTIFACTS.select(self.api, observed, self.roles, now=self.now)
        self.assertEqual(observed['history']['jobs'][0]['conclusion'], 'cancelled')
        self.assertEqual(selected['fixtures']['owner_job']['id'], 22)
        self.assertEqual(selected['fixtures']['artifact']['id'], 33)
        self.assertEqual(selected['fixtures']['identity'], self.identity)
        self.assertIn('does not certify', selected['fixtures']['limits'][0])

    def test_exact_source_workflow_repository_ref_and_preview_tree_are_mandatory(self):
        baseline = copy.deepcopy(self.responses)
        cases = [(self.paths['run'], key, value) for key, value in
                 [('id', 124), ('run_attempt', 3), ('head_sha', 'e' * 40), ('workflow_id', 457),
                  ('path', '.github/workflows/foreign.yml'), ('head_branch', 'main')]]
        cases += [('repos/bijux/bijux-std/actions/workflows/456', 'path', '.github/workflows/foreign.yml'),
                  ('repos/bijux/bijux-std/git/commits/' + 'b' * 40, 'tree', {'sha': 'e' * 40}),
                  (self.paths['run'], 'head_repository', {'full_name': 'foreign/fork', 'id': 789})]
        for endpoint, key, value in cases:
            with self.subTest(key=key, value=value):
                self.responses.clear(); self.responses.update(copy.deepcopy(baseline))
                self.responses[endpoint][key] = value
                with self.assertRaises(ValueError): self.select()

    def test_preview_parent_and_identity_shape_cannot_be_guessed(self):
        self.responses['repos/bijux/bijux-std/git/commits/' + 'b' * 40]['parents'].reverse()
        with self.assertRaisesRegex(ValueError, 'preview merge'): self.select()
        self.identity['unowned'] = True
        with self.assertRaisesRegex(ValueError, 'Exact workflow identity'): self.select()

    def test_all_pages_are_retained_and_role_lookup_fetches_only_needed_owner(self):
        rows = [{**self.job, 'id': number + 100, 'name': 'unneeded-' + str(number)} for number in range(101)]
        payloads = [{'total_count': 101, 'jobs': rows[:100]}, {'total_count': 101, 'jobs': rows[100:]}]
        calls = []
        def fetch(endpoint):
            calls.append(endpoint)
            return payloads[len(calls) - 1]
        result = ARTIFACTS.pages(fetch, 'repos/bijux/bijux-std/actions/runs/123/jobs?filter=all', 'jobs')
        self.assertEqual(len(result['jobs']), 101)
        self.assertEqual(len(result['pages']), 2)
        self.select()
        self.assertEqual([call for call in self.api.calls if '/actions/jobs/' in call], [self.paths['job']])

    def test_short_duplicate_changed_total_and_overfull_api_pages_are_refused(self):
        cases = [{'total_count': 2, 'jobs': [self.job]}, {'total_count': 2, 'jobs': [self.job, self.job]},
                 {'total_count': 0, 'jobs': [self.job]}, {'total_count': True, 'jobs': []}]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError): ARTIFACTS.pages(lambda _: payload, 'jobs', 'jobs')
        pages = [{'total_count': 101, 'jobs': [{**self.job, 'id': i + 1} for i in range(100)]},
                 {'total_count': 102, 'jobs': [{**self.job, 'id': 101}]}]
        with self.assertRaisesRegex(ValueError, 'changed during pagination'):
            ARTIFACTS.pages(lambda _: pages.pop(0), 'jobs', 'jobs')

    def test_latest_cannot_hide_newer_or_duplicate_owner_or_missing_history(self):
        endpoint = self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'
        for newest in [{**self.job, 'id': 44, 'run_attempt': 3}, {**self.job, 'id': 44},
                       {**self.job, 'id': 44, 'name': 'hidden owner'}]:
            with self.subTest(newest=newest):
                self.responses[endpoint] = {'total_count': 3, 'jobs': [self.old, self.job, newest]}
                with self.assertRaises(ValueError): self.select()

    def test_old_success_cannot_hide_latest_failure_cancel_pending_or_duration(self):
        self.old['conclusion'] = 'success'
        for state in [('completed', 'failure'), ('completed', 'cancelled'), ('in_progress', None), ('queued', None)]:
            with self.subTest(state=state):
                self.job['status'], self.job['conclusion'] = state
                with self.assertRaisesRegex(ValueError, 'terminal-success'): self.select()
        self.job.update(status='completed', conclusion='success', completed_at='2026-01-01T00:04:00Z')
        with self.assertRaisesRegex(ValueError, '180-second'): self.select()

    def test_earlier_latest_success_needs_future_explicit_lineage_not_attempt_comparison(self):
        self.job['run_attempt'] = 1
        self.responses[self.paths['run'] + '/jobs?filter=all&per_page=100&page=1'] = {'total_count': 1, 'jobs': [self.job]}
        with self.assertRaisesRegex(ValueError, 'Cross-attempt'): self.select()

    def test_wrong_history_run_head_and_future_attempt_are_refused(self):
        for key, value in [('run_id', 124), ('head_sha', 'e' * 40), ('run_attempt', 3)]:
            with self.subTest(key=key):
                baseline = self.old[key]; self.old[key] = value
                with self.assertRaisesRegex(ValueError, 'History'): self.select()
                self.old[key] = baseline

    def test_exact_artifact_name_digest_expiry_and_upload_interval_are_required(self):
        cases = [('name', 'docs-navigation-fixtures-' + 'a' * 40 + '-2'), ('digest', None), ('expired', True),
                 ('expires_at', '2026-01-01T00:00:00Z'), ('created_at', '2026-01-01T00:01:10Z'),
                 ('size_in_bytes', ARTIFACTS.MAX_ARCHIVE_BYTES + 1)]
        for key, value in cases:
            with self.subTest(key=key):
                original = self.artifact[key]; self.artifact[key] = value
                with self.assertRaises(ValueError): self.select()
                self.artifact[key] = original

    def test_artifact_run_repository_head_and_branch_cannot_be_forged(self):
        for key, value in [('id', 124), ('head_sha', 'e' * 40), ('head_branch', 'main'),
                           ('repository_id', 790), ('head_repository_id', 790)]:
            with self.subTest(key=key):
                original = self.artifact['workflow_run'][key]; self.artifact['workflow_run'][key] = value
                with self.assertRaisesRegex(ValueError, 'Artifact workflow'): self.select()
                self.artifact['workflow_run'][key] = original

    def test_role_alias_missing_owner_duplicate_artifact_and_reobserved_change_fail(self):
        self.roles['alias'] = dict(self.roles['fixtures'])
        with self.assertRaisesRegex(ValueError, 'Duplicate source-owned job'): self.select()
        del self.roles['alias']; self.roles['fixtures']['job_name'] = 'unregistered owner'
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate latest'): self.select()
        self.roles['fixtures']['job_name'] = self.job['name']
        self.responses[self.paths['artifact']] = {**self.artifact, 'digest': 'sha256:' + 'f' * 64}
        with self.assertRaisesRegex(ValueError, 'Artifact changed'): self.select()

    def test_duplicate_artifact_id_or_name_and_future_artifact_do_not_supply_an_owner(self):
        endpoint = self.paths['run'] + '/artifacts?per_page=100&page=1'
        for duplicate in [{**self.artifact, 'name': 'other-artifact'}, {**self.artifact, 'id': 34}]:
            with self.subTest(duplicate=duplicate):
                self.responses[endpoint] = {'total_count': 2, 'artifacts': [self.artifact, duplicate]}
                with self.assertRaisesRegex(ValueError, 'Duplicate'): self.select()
        self.responses[endpoint] = {'total_count': 1, 'artifacts': [{**self.artifact, 'name': self.artifact['name'][:-1] + '3'}]}
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate exact'): self.select()

    def test_missing_failed_or_outside_upload_step_is_not_creator_proof(self):
        self.job['steps'][1]['conclusion'] = 'failure'
        with self.assertRaisesRegex(ValueError, 'failed or nonterminal'): self.select()
        self.job['steps'][1]['conclusion'] = 'success'; self.job['steps'][1]['name'] = 'Unowned uploader'
        with self.assertRaisesRegex(ValueError, 'owned upload'): self.select()
        self.job['steps'][1]['name'] = 'Retain immutable fixtures'
        self.job['steps'][1]['started_at'] = '2026-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'outside owner'): self.select()

    def test_download_hash_size_and_pinned_owner_reobservation_precede_any_output(self):
        pin = self.select()['fixtures']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            destination = Path(temporary) / 'owned'
            self.api.body = self.body[:-1]
            with self.assertRaisesRegex(ValueError, 'byte count'): ARTIFACTS.download(self.api, pin, destination)
            self.assertFalse(destination.exists())
            self.api.body = b'x' + self.body[1:]
            with self.assertRaisesRegex(ValueError, 'digest mismatch'): ARTIFACTS.download(self.api, pin, destination)
            self.assertFalse(destination.exists())
            self.api.body = self.body
            self.job['conclusion'] = 'cancelled'
            with self.assertRaisesRegex(ValueError, 'Pinned owner changed|actual latest'): ARTIFACTS.download(self.api, pin, destination)
            self.assertFalse(destination.exists())

    def test_successful_download_retains_exact_body_digests_and_refuses_merge(self):
        pin = self.select()['fixtures']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            destination = Path(temporary) / 'owned'
            receipt = ARTIFACTS.download(self.api, pin, destination)
            self.assertEqual(receipt['files']['site/index.html'], hashlib.sha256(b'<h1>Current</h1>').hexdigest())
            self.assertEqual((destination / 'site/index.html').read_bytes(), b'<h1>Current</h1>')
            with self.assertRaisesRegex(ValueError, 'collision'): ARTIFACTS.download(self.api, pin, destination)
            self.assertEqual((destination / 'site/index.html').read_bytes(), b'<h1>Current</h1>')

    def test_retained_pin_refuses_new_run_attempt(self):
        pin = self.select()['fixtures']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            destination = Path(temporary) / 'owned'
            self.responses[self.paths['run']]['run_attempt'] = 3
            with self.assertRaisesRegex(ValueError, 'superseded or changed'):
                ARTIFACTS.download(self.api, pin, destination)

    def test_retained_pin_refuses_new_failed_or_pending_latest_owner_while_old_job_is_unchanged(self):
        pin = self.select()['fixtures']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            destination = Path(temporary) / 'owned'
            for status, conclusion in [('completed', 'failure'), ('queued', None), ('in_progress', None), ('completed', 'success')]:
                with self.subTest(status=status, conclusion=conclusion):
                    newer = {**self.job, 'id': 44, 'status': status, 'conclusion': conclusion}
                    self.responses[self.paths['run'] + '/jobs?filter=latest&per_page=100&page=1'] = {'total_count': 1, 'jobs': [newer]}
                    with self.assertRaisesRegex(ValueError, 'no longer the actual latest'):
                        ARTIFACTS.download(self.api, pin, destination)
                    self.assertFalse(destination.exists())
            self.assertFalse(any(isinstance(call, tuple) and call[0] == 'download' for call in self.api.calls))

    def test_new_owner_during_download_is_refused_before_materialization(self):
        pin = self.select()['fixtures']
        original = self.api.archive
        def superseded(artifact_id):
            result = original(artifact_id)
            self.responses[self.paths['run']]['run_attempt'] = 3
            return result
        self.api.archive = superseded
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            destination = Path(temporary) / 'owned'
            with self.assertRaisesRegex(ValueError, 'superseded or changed'):
                ARTIFACTS.download(self.api, pin, destination)
            self.assertFalse(destination.exists())

    def test_symlink_parent_or_destination_never_receives_artifact_writes(self):
        pin = self.select()['fixtures']
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as temporary:
            root = Path(temporary); (root / 'real').mkdir(); (root / 'link').symlink_to(root / 'real', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'ordinary directory'):
                ARTIFACTS.download(self.api, pin, root / 'link/owned')
            with self.assertRaisesRegex(ValueError, 'collision'):
                ARTIFACTS.download(self.api, pin, root / 'link')
            self.assertEqual(list((root / 'real').iterdir()), [])

    def test_traversal_duplicate_symlink_file_directory_collision_and_size_limits_fail(self):
        for name in ['../escape', '/escape', 'site//index', 'site/./index', 'site\\escape', 'C:escape', 'site/\x00bad']:
            if '\x00' in name:
                # ZIP writers truncate NULs; retain a control byte the writer preserves.
                name = 'site/\x01bad'
            with self.subTest(name=name):
                data = archive([(name, b'x')])
                with self.assertRaises(ValueError): ARTIFACTS.archive_members(data, 'sha256:' + hashlib.sha256(data).hexdigest())
        for entries in [[('same', b'a'), ('same', b'b')], [('parent', b'a'), ('parent/child', b'b')]]:
            with self.subTest(entries=entries):
                data = archive(entries)
                with self.assertRaises(ValueError): ARTIFACTS.archive_members(data, 'sha256:' + hashlib.sha256(data).hexdigest())
        link = zipfile.ZipInfo('link'); link.create_system = 3; link.external_attr = (stat.S_IFLNK | 0o777) << 16
        data = archive([(link, b'../outside')])
        with self.assertRaisesRegex(ValueError, 'Nonregular'):
            ARTIFACTS.archive_members(data, 'sha256:' + hashlib.sha256(data).hexdigest())
        with patch.object(ARTIFACTS, 'MAX_EXPANDED_BYTES', 1):
            with self.assertRaisesRegex(ValueError, 'Expanded'):
                ARTIFACTS.archive_members(self.body, 'sha256:' + hashlib.sha256(self.body).hexdigest())


class WorkflowArtifactTransportTests(unittest.TestCase):
    def test_bearer_token_stays_at_api_origin_and_cdn_request_has_no_authorization(self):
        class Opener:
            def __init__(self): self.requests = []
            def open(self, request, timeout):
                self.requests.append(request)
                if len(self.requests) == 1:
                    raise HTTPError(request.full_url, 302, 'Found', {'Location': 'https://owned.blob.core.windows.net/artifact?sig=secret'}, None)
                response = io.BytesIO(b'zip'); response.status = 200; response.headers = {}
                return response
        opener = Opener(); api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=opener)
        self.assertEqual(api.archive(33), b'zip')
        self.assertEqual(opener.requests[0].get_header('Authorization'), 'Bearer private-token')
        self.assertIsNone(opener.requests[1].get_header('Authorization'))
        with self.assertRaisesRegex(ValueError, 'confined'):
            api._read('https://owned.blob.core.windows.net/', authenticated=True, maximum=10)

    def test_untrusted_cdn_https_downgrade_and_network_error_are_refused_without_secret(self):
        class Opener:
            location = 'https://attacker.invalid/artifact'
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 302, 'Found', {'Location': self.location}, None)
        opener = Opener(); api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=opener)
        with self.assertRaisesRegex(ValueError, 'Unrecognized'): api.archive(33)
        opener.location = 'http://owned.blob.core.windows.net/artifact'
        with self.assertRaisesRegex(ValueError, 'HTTPS'): api.archive(33)
        opener.open = lambda *args, **kwargs: (_ for _ in ()).throw(URLError('sig=secret private-token'))
        with self.assertRaisesRegex(ValueError, '^GitHub transport could not complete$'): api.archive(33)

    def test_transport_errors_identify_origin_and_safe_rate_limit_headers_only(self):
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url + '?sig=secret', 403, 'private-token',
                    {'X-RateLimit-Remaining':'0', 'X-RateLimit-Reset':'1760112000',
                     'Retry-After':'private-token', 'Authorization':'private-token'}, io.BytesIO(b'secret'))
        api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=Opener())
        with self.assertRaisesRegex(ValueError, '^GitHub API transport failed with HTTP 403') as raised:
            api.json('repos/bijux/bijux-std/actions/runs/123')
        self.assertIn('x-ratelimit-remaining=0', str(raised.exception))
        self.assertNotIn('secret', str(raised.exception))
        self.assertNotIn('private-token', str(raised.exception))
        with self.assertRaisesRegex(ValueError, '^artifact CDN transport failed with HTTP 403'):
            api._read('https://owned.blob.core.windows.net/archive?sig=secret', authenticated=False, maximum=10)

    def test_json_duplicate_keys_cross_repository_redirect_and_byte_limit_are_refused(self):
        class Opener:
            body = b'{"id":1,"id":2}'
            def open(self, request, timeout):
                response = io.BytesIO(self.body); response.status = 200; response.headers = {}
                return response
        opener = Opener(); api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=opener)
        with self.assertRaisesRegex(ValueError, 'Duplicate API JSON'): api.json('repos/bijux/bijux-std/actions/runs/123')
        with self.assertRaisesRegex(ValueError, 'outside'): api.json('repos/foreign/repo/actions/runs/123')
        with patch.object(ARTIFACTS, 'MAX_JSON_BYTES', 2):
            with self.assertRaisesRegex(ValueError, 'byte limit'): api.json('repos/bijux/bijux-std/actions/runs/123')


class WorkflowAdmissionDeadlineTests(unittest.TestCase):
    def test_one_absolute_deadline_covers_all_requests_and_never_restarts(self):
        now = [0.0]
        class Opener:
            def __init__(self): self.timeouts = []
            def open(self, request, timeout):
                self.timeouts.append(timeout)
                response = io.BytesIO(b'{"id":1}'); response.status = 200; response.headers = {}
                return response
        opener = Opener()
        api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=opener,
                                  deadline_seconds=10, clock=lambda: now[0])
        api.json('repos/bijux/bijux-std/actions/runs/123')
        now[0] = 7
        api.json('repos/bijux/bijux-std/actions/runs/123')
        self.assertEqual(opener.timeouts, [10, 3])
        now[0] = 10
        with self.assertRaisesRegex(ValueError, 'deadline expired'): api.json('repos/bijux/bijux-std/actions/runs/123')
        self.assertEqual(len(opener.timeouts), 2)

    def test_slow_chunk_bodies_refresh_live_socket_remaining_timeout_and_refuse_expiry(self):
        now, timeouts, reads = [0.0], [], []
        class Socket:
            def settimeout(self, timeout): timeouts.append(timeout)
        class Response(io.BytesIO):
            status = 200
            headers = {}
            fp = type('FP', (), {'raw': type('Raw', (), {'_sock': Socket()})()})()
            def read1(self, size):
                reads.append(size); now[0] += 4
                return b'x'
        class Opener:
            def open(self, request, timeout): return Response()
        api = ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', opener=Opener(),
                                  deadline_seconds=10, clock=lambda: now[0])
        with self.assertRaisesRegex(ValueError, 'deadline expired'): api.archive(33)
        self.assertEqual(timeouts, [10, 6, 2])
        self.assertEqual(len(reads), 3)
        self.assertTrue(all(size <= 64 * 1024 for size in reads))

    def test_deadline_cannot_be_disabled_or_raised_and_reservation_precedes_body_expansion(self):
        for value in (0, 121, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, '120 seconds'):
                    ARTIFACTS.GitHubAPI('bijux/bijux-std', 'private-token', deadline_seconds=value)
        body = archive([('ordinary', b'bytes')])
        def refused(size):
            self.assertEqual(size, 5)
            raise ValueError('shared expanded budget refused')
        with patch.object(zipfile.ZipFile, 'read', side_effect=AssertionError('expanded before reservation')):
            with self.assertRaisesRegex(ValueError, 'shared expanded budget'):
                ARTIFACTS.archive_members(body, 'sha256:' + hashlib.sha256(body).hexdigest(), reserve=refused)


if __name__ == '__main__':
    unittest.main()

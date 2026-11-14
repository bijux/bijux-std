"""Reject missing executions, failed newest retries and fabricated run identities."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'shared/bijux-gitlab/evidence'
HEAD = 'a' * 40


def load(name):
    path = EVIDENCE / (name + '.py')
    spec = importlib.util.spec_from_file_location('bijux_gitlab_test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(identifier=11, name='browser', **changes):
    row = {'id': identifier, 'name': name, 'pipeline': {'id': 30, 'project_id': 17, 'sha': HEAD},
           'commit': {'id': HEAD}, 'status': 'success', 'allow_failure': False,
           'created_at': '2026-11-14T12:00:00Z', 'started_at': '2026-11-14T12:00:01Z',
           'finished_at': '2026-11-14T12:00:30Z', 'duration': 29.0,
           'runner': {'id': 55, 'description': 'public runner'}, 'tag_list': [],
           'artifacts_file': {'filename': 'artifacts.zip', 'size': 100},
           'artifacts': [{'file_type': 'archive', 'size': 100, 'filename': 'artifacts.zip', 'file_format': 'zip'}],
           'artifacts_expire_at': '2099-12-01T00:00:00Z', 'erased_at': None}
    return {**row, **changes}


class NativeJobQualificationTests(unittest.TestCase):
    def qualify(self, rows):
        self.assertTrue((EVIDENCE / 'jobs.py').is_file(), 'Native GitLab job gate is missing')
        return load('jobs').qualify_jobs(rows, project_id=17, pipeline_id=30, commit_sha=HEAD,
                                       required_names={'browser', 'standard'}, frontend_names={'browser'})

    def test_complete_native_jobs_retain_raw_identity_and_whole_job_budget(self):
        rows = [job(), job(12, 'standard')]
        result = self.qualify(rows)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['selected_jobs']['browser']['job_id'], 11)
        self.assertEqual(result['selected_jobs']['browser']['seconds'], 29.0)
        self.assertEqual(result['raw_jobs'], rows)
        self.assertEqual(result['strict_frontend_limit_seconds'], 180)
        self.assertNotIn('workflow_attempt', result)

    def test_latest_failed_or_running_retry_never_reuses_older_success(self):
        for status in ('failed', 'canceled', 'running', 'manual', 'skipped'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.qualify([job(), job(12, 'standard'), job(13, status=status)])

    def test_latest_success_preserves_failed_original_without_global_attempt(self):
        result = self.qualify([job(status='failed'), job(12, 'standard'), job(13)])
        self.assertEqual(result['selected_jobs']['browser']['job_id'], 13)
        self.assertEqual(result['raw_jobs'][0]['status'], 'failed')

    def test_missing_duplicate_or_foreign_identity_is_refused(self):
        rows = [job(), job(12, 'standard')]
        for mutation in ('missing', 'duplicate', 'zero', 'project', 'pipeline', 'commit', 'pipeline-sha'):
            altered = copy.deepcopy(rows)
            if mutation == 'missing': altered.pop()
            elif mutation == 'duplicate': altered.append(copy.deepcopy(altered[0]))
            elif mutation == 'zero': altered[0]['id'] = 0
            elif mutation == 'project': altered[0]['pipeline']['project_id'] = 18
            elif mutation == 'pipeline': altered[0]['pipeline']['id'] = 31
            elif mutation == 'commit': altered[0]['commit']['id'] = 'b' * 40
            else: altered[0]['pipeline']['sha'] = 'b' * 40
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.qualify(altered)

    def test_frontend_budget_includes_setup_transfer_and_cleanup(self):
        for ended in ('2026-11-14T12:03:01Z', '2026-11-14T12:03:02Z'):
            with self.subTest(ended=ended), self.assertRaises(ValueError):
                self.qualify([job(finished_at=ended), job(12, 'standard')])
        self.qualify([job(finished_at='2026-11-14T12:03:00.999Z'), job(12, 'standard')])

    def test_missing_timezone_reversed_clock_and_queue_order_are_refused(self):
        for changes in ({'started_at': None}, {'started_at': '2026-11-14T12:00:01'},
                        {'finished_at': '2026-11-14T12:00:00Z'},
                        {'created_at': '2026-11-14T12:00:02Z'}, {'runner': None}, {'allow_failure': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.qualify([job(**changes), job(12, 'standard')])

    def test_active_caller_is_retained_but_cannot_count_as_completed_required_job(self):
        result = self.qualify([job(), job(12, 'standard'), job(14, 'report', status='running')])
        self.assertEqual(set(result['selected_jobs']), {'browser', 'standard'})
        self.assertEqual(len(result['raw_jobs']), 3)

    def test_boolean_native_ids_cannot_equal_positive_numeric_ids(self):
        self.assertTrue((EVIDENCE / 'jobs.py').is_file(), 'Native GitLab job gate is missing')
        module = load('jobs')
        for pipeline in ({'id': True, 'project_id': 1, 'sha': HEAD}, {'id': 1, 'project_id': True, 'sha': HEAD}):
            with self.subTest(pipeline=pipeline), self.assertRaises(ValueError):
                module.qualify_jobs([job(pipeline=pipeline)], project_id=1, pipeline_id=1, commit_sha=HEAD,
                                    required_names={'browser'}, frontend_names={'browser'})


class NativeTraceSectionTests(unittest.TestCase):
    def parse(self, trace):
        self.assertTrue((EVIDENCE / 'trace.py').is_file(), 'Native GitLab trace gate is missing')
        return load('trace').parse_sections(trace, started_at='2026-11-14T12:00:01Z', finished_at='2026-11-14T12:00:30Z')

    def marker(self, kind, epoch, name='step_script', options=''):
        return f'\x1b[0Ksection_{kind}:{epoch}:{name}{options}\r\x1b[0K'.encode()

    def test_actual_native_sections_retain_observed_times_without_github_steps(self):
        start = 1794657601
        trace = self.marker('start', start, options='[collapsed=true]') + b'actual command output\n' + self.marker('end', start + 20)
        result = self.parse(trace)
        self.assertEqual(result['status'], 'observed')
        self.assertEqual(result['sections'][0]['seconds'], 20)
        self.assertEqual(result['sections'][0]['name'], 'step_script')

    def test_no_markers_is_explicitly_unavailable(self):
        result = self.parse(b'plain runner log\n')
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['sections'], [])

    def test_provider_timestamped_records_preserve_real_marker_offsets_and_lifecycle(self):
        data = (b'2026-11-14T12:00:01.123456Z 00O section_start:1794657601:step_script\r\x1b[0K\n'
                b'2026-11-14T12:00:01.123457Z 00O+\x1b[0Kordinary runner output\n'
                b'2026-11-14T12:00:21.234567Z 00O+section_end:1794657621:step_script\r\x1b[0K\n')
        result = self.parse(data)
        self.assertEqual(result['status'], 'observed')
        self.assertEqual(result['sections'][0]['name'], 'step_script')
        self.assertEqual(result['sections'][0]['seconds'], 20)
        self.assertEqual(result['sections'][0]['start_offset'], 0)
        self.assertEqual(result['trace_bytes'], len(data))

    def test_timestamped_records_refuse_incomplete_or_malformed_native_sections(self):
        for data in (b'2026-11-14T12:00:01.123456Z 00O section_start:1794657601:step_script\r\x1b[0K\n',
                     b'2026-11-14T12:00:01.123456Z 00O+section_start:invalid:step_script\r\x1b[0K\n'):
            with self.subTest(data=data), self.assertRaises(ValueError): self.parse(data)

    def test_partial_crossed_or_outside_job_sections_are_refused(self):
        start = 1794657601
        for data in (self.marker('start', start), self.marker('end', start),
                     self.marker('start', start) + self.marker('end', start + 1, 'other'),
                     self.marker('start', start) + self.marker('end', start + 31),
                     self.marker('start', start) + self.marker('end', start - 1),
                     b'\x1b[0Ksection_start:invalid:step_script\r\x1b[0K'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.parse(data)

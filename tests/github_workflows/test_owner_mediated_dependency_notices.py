"""Actual bot check-name and event boundaries preserve human verification ownership."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from .policy_fixtures import MODULE, ROOT
from .test_dependency_pr_admission import observed_condition

POLICY = {'schema': 1, 'dependency_pull_requests': 'notification-only',
          'dependency_merge': 'owner-consolidation', 'main_verification': 'accepted-pull-request'}


class OwnerMediatedDependencyNoticeTests(unittest.TestCase):
    def source(self):
        return {'on': {'push': {'branches': ['main']}, 'pull_request': None,
                       'pull_request_target': None, 'pull_request_review': None,
                       'merge_group': None, 'workflow_dispatch': None},
                'jobs': {'check': {'name': 'std / standard', 'if': '${{ always() }}',
                                  'needs': 'build', 'strategy': {'matrix': {'python': ['3.11', '3.14']}},
                                  'steps': [{'run': 'make lint'}]}}}

    def test_actual_family_has_uniform_notification_and_explicit_master_exception(self):
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        repositories = [repo['name'] for repo in manifest['repositories']]
        self.assertEqual(len(repositories), 12)
        policies = MODULE.validate_manifest(manifest, repositories)
        for name, policy in policies.items():
            self.assertEqual(policy['dependency_pull_requests'], 'notification-only', name)
            self.assertEqual(policy['dependency_merge'], 'owner-consolidation', name)
            self.assertEqual(policy['main_verification'], 'existing-events' if name == 'bijux-masterclass' else 'accepted-pull-request', name)

    def test_original_bot_author_denies_all_PR_events_without_claiming_required_name(self):
        projected = MODULE.project_dependency_pull_requests('owned', self.source(), POLICY)
        job = projected['jobs']['check']
        for event in ['pull_request', 'pull_request_target', 'pull_request_review']:
            for actor in ['human-owner', 'dependabot[bot]']:
                self.assertFalse(observed_condition(job['if'], event, 'dependabot[bot]', actor))
        self.assertEqual(job['name'], MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX + 'std / standard')
        self.assertNotEqual(job['name'], 'std / standard')
        self.assertEqual(job['needs'], 'build')
        self.assertEqual(job['strategy'], self.source()['jobs']['check']['strategy'])
        self.assertEqual(job['steps'], self.source()['jobs']['check']['steps'])

    def test_human_and_manual_names_resolve_without_any_prefix(self):
        prefix = MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX
        for author in ['human-owner', '', None]:
            expression = prefix.removeprefix('${{').removesuffix('}}').replace('github.event.pull_request.user.login', repr(author)).replace('github.event.pull_request.head.ref', repr('feature')).replace('&&', ' and ').replace('||', ' or ')
            self.assertEqual(eval(expression, {'__builtins__': {}}, {}), '')
        expression = prefix.removeprefix('${{').removesuffix('}}').replace('github.event.pull_request.user.login', repr('dependabot[bot]')).replace('github.event.pull_request.head.ref', repr('feature')).replace('&&', ' and ').replace('||', ' or ')
        self.assertEqual(eval(expression, {'__builtins__': {}}, {}), 'unverified dependency / ')

    def test_projection_is_idempotent_and_keeps_source_owned_bytes(self):
        source = self.source(); before = copy.deepcopy(source)
        projected = MODULE.project_dependency_pull_requests('owned', source, POLICY)
        self.assertEqual(MODULE.project_dependency_pull_requests('owned', projected, POLICY), projected)
        self.assertEqual(source, before)

    def test_generated_dependency_lock_proposals_share_notice_guards_and_distinct_names(self):
        job = MODULE.project_dependency_pull_requests('owned', self.source(), POLICY)['jobs']['check']
        notice = MODULE.parse_workflow((ROOT / 'shared/bijux-gh/workflows/dependency-notice.yml').read_bytes(), 'notice')['jobs']['notice']
        for event in ['pull_request', 'pull_request_target', 'pull_request_review']:
            self.assertFalse(observed_condition(job['if'], event, 'github-actions[bot]', branch='automation/dependency-lock-refresh'))
            self.assertTrue(observed_condition(job['if'], event, 'github-actions[bot]', branch='automation/documentation-reader'))
            self.assertTrue(observed_condition(job['if'], event, 'bijux', branch='automation/dependency-lock-refresh'))
        for author, branch, expected in [('dependabot[bot]', 'ordinary', True),
                                          ('github-actions[bot]', 'automation/dependency-lock-refresh', True),
                                          ('github-actions[bot]', 'automation/documentation-reader', False),
                                          ('bijux', 'automation/dependency-lock-refresh', False)]:
            self.assertEqual(observed_condition(notice['if'], 'pull_request_target', author, branch=branch), expected)
            expression = MODULE.dependency_prs.UNVERIFIED_JOB_PREFIX.removeprefix('${{').removesuffix('}}').replace('github.event.pull_request.user.login', repr(author)).replace('github.event.pull_request.head.ref', repr(branch)).replace('&&', ' and ').replace('||', ' or ')
            self.assertEqual(eval(expression, {'__builtins__': {}}, {}), 'unverified dependency / ' if expected else '')

    def test_push_verification_is_removed_but_human_manual_and_merge_queue_remain(self):
        source = self.source(); projected = MODULE.project_automatic_events('ci', source, POLICY)
        self.assertNotIn('push', projected['on'])
        self.assertEqual(projected['jobs'], source['jobs'])
        self.assertEqual(set(projected['on']), set(source['on']) - {'push'})

    def test_master_human_events_and_manual_publication_jobs_remain_unchanged(self):
        policy = dict(POLICY, main_verification='existing-events')
        source = self.source()
        self.assertEqual(MODULE.project_automatic_events('owned', source, policy), source)
        manual = {'on': {'workflow_dispatch': None, 'workflow_call': None}, 'jobs': {'deploy': {'steps': [{'run': 'owned publisher'}]}}}
        self.assertEqual(MODULE.project_dependency_pull_requests('deploy-docs', manual, policy), manual)

    def test_notification_requires_enabled_notice_and_owner_consolidation(self):
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        for field in ['allowlist', 'merge']:
            bad = copy.deepcopy(manifest); repo = bad['repositories'][0]
            if field == 'allowlist': repo['workflow_allowlist'].remove('dependency-notice')
            else: repo['workflow_execution_policy']['dependency_merge'] = 'canonical'
            with self.assertRaisesRegex(ValueError, 'notification-only requires'):
                MODULE.validate_manifest(bad, [repo['name']])

    def test_boolean_or_arbitrary_main_merge_values_are_refused(self):
        manifest = json.loads((ROOT / '.github/standards/repo-config.manifest.json').read_text())
        for key, value in [('main_verification', False), ('main_verification', 'skip-all'), ('dependency_merge', True), ('dependency_merge', 'automerge')]:
            bad = copy.deepcopy(manifest); bad['repositories'][0]['workflow_execution_policy'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                MODULE.validate_manifest(bad, [bad['repositories'][0]['name']])

    def test_owned_workflow_admission_refuses_unguarded_and_false_required_names(self):
        source = self.source(); source['on'].pop('push')
        with self.assertRaisesRegex(ValueError, 'dependency job admission'):
            MODULE.validate_owned_execution({'.github/workflows/owned.yml': source}, POLICY)
        projected = MODULE.project_dependency_pull_requests('owned', source, POLICY)
        MODULE.validate_owned_execution({'.github/workflows/owned.yml': projected}, POLICY)
        projected['jobs']['check']['name'] = 'std / standard'
        with self.assertRaisesRegex(ValueError, 'dependency job admission'):
            MODULE.validate_owned_execution({'.github/workflows/owned.yml': projected}, POLICY)

    def test_owned_workflow_admission_has_no_main_push_path_exemption(self):
        projected = MODULE.project_dependency_pull_requests('dependency-graph', self.source(), POLICY)
        with self.assertRaisesRegex(ValueError, 'duplicate push verification'):
            MODULE.validate_owned_execution({'.github/workflows/dependency-graph.yml': projected}, POLICY)

    def test_schedule_is_retained_while_owned_PR_jobs_are_denied_to_bots(self):
        source = self.source(); source['on']['schedule'] = [{'cron': '0 0 * * 1'}]
        projected = MODULE.project_automatic_events('owned', source, POLICY)
        projected = MODULE.project_dependency_pull_requests('owned', projected, POLICY)
        self.assertEqual(projected['on']['schedule'], source['on']['schedule'])
        MODULE.validate_owned_execution({'.github/workflows/owned.yml': projected}, POLICY)

    def test_notice_is_single_readonly_bot_job_without_checkout_or_product_commands(self):
        source = MODULE.parse_workflow((ROOT / 'shared/bijux-gh/workflows/dependency-notice.yml').read_bytes(), 'dependency-notice')
        projected = MODULE.project_dependency_pull_requests('dependency-notice', source, POLICY)
        self.assertEqual(projected, source)
        self.assertEqual(set(source['on']), {'pull_request_target'})
        self.assertEqual(set(source['jobs']), {'notice'})
        job = source['jobs']['notice']
        self.assertEqual(job['timeout-minutes'], 1)
        self.assertEqual(source['permissions'], {'contents': 'read'})
        self.assertTrue(all('uses' not in step for step in job['steps']))
        script = job['steps'][0]['run']
        for command in ['make ', 'pip ', 'cargo ', 'npm ', 'git ', 'curl ', 'gh ', 'graphql']:
            self.assertNotIn(command, script)
        self.assertIn('verification did not run', script)
        bad = copy.deepcopy(source); bad['jobs']['verification'] = {'name': 'std / standard'}
        with self.assertRaisesRegex(ValueError, 'one distinct read-only bot notice job'):
            MODULE.project_dependency_pull_requests('dependency-notice', bad, POLICY)
        for mutation in [{'permissions': {'contents': 'write'}}, {'strategy': {'matrix': {'runner': ['ubuntu-latest']}}},
                         {'container': 'expensive-image'}, {'timeout-minutes': 10},
                         {'steps': [{'uses': 'actions/checkout@' + 'a' * 40}]}]:
            bad = copy.deepcopy(source); bad['jobs']['notice'].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'one distinct read-only bot notice job'):
                MODULE.project_dependency_pull_requests('dependency-notice', bad, POLICY)

    def test_ambiguous_run_followthrough_is_refused(self):
        source = self.source(); source['on'].pop('push'); source['on']['workflow_run'] = {'workflows': ['verify'], 'types': ['completed'], 'branches': ['main']}
        source = MODULE.project_dependency_pull_requests('owned', source, POLICY)
        with self.assertRaisesRegex(ValueError, 'bounded manual docs followthrough'):
            MODULE.validate_owned_execution({'.github/workflows/owned.yml': source}, POLICY)

    def test_manual_docs_followthrough_requires_actual_successful_main_admission(self):
        source = {'on': {'workflow_run': {'workflows': ['deploy-docs'], 'types': ['completed'], 'branches': ['main']}, 'workflow_dispatch': None}, 'jobs': {'smoke': {'if': "${{ github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main' }}"}}}
        MODULE.validate_owned_execution({'.github/workflows/owned.yml': source}, POLICY)
        bad = copy.deepcopy(source); bad['jobs']['smoke']['if'] = '${{ always() }}'
        with self.assertRaisesRegex(ValueError, 'successful-main admission'):
            MODULE.validate_owned_execution({'.github/workflows/owned.yml': bad}, POLICY)

    def test_manual_followthrough_guards_cannot_escape_through_disjunction_or_quoted_text(self):
        events = {'workflow_run': {'workflows': ['deploy-docs'], 'types': ['completed'], 'branches': ['main']}, 'workflow_dispatch': None}
        successful = "github.event_name == 'workflow_run' && github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.head_branch == 'main'"
        for condition in [f'({successful}) || always()',
                          "github.event_name != 'workflow_run' || always()",
                          "contains('github.event_name != ''workflow_run''', 'workflow_run')",
                          "github.event_name == 'workflow_run' && contains('github.event.workflow_run.conclusion == ''success'' && github.event.workflow_run.head_branch == ''main''', 'success')"]:
            document = {'on': events, 'jobs': {'smoke': {'if': '${{ ' + condition + ' }}'}}}
            with self.subTest(condition=condition), self.assertRaisesRegex(ValueError, 'successful-main admission'):
                MODULE.validate_owned_execution({'.github/workflows/owned.yml': document}, POLICY)
        for condition in [successful, f'({successful}) && always()',
                          "github.event_name != 'workflow_run' && (always() || success())"]:
            document = {'on': events, 'jobs': {'smoke': {'if': '${{ ' + condition + ' }}'}}}
            MODULE.validate_owned_execution({'.github/workflows/owned.yml': document}, POLICY)

    def test_actual_notice_treats_dependency_metadata_as_data_and_never_executes_it(self):
        source = MODULE.parse_workflow((ROOT / 'shared/bijux-gh/workflows/dependency-notice.yml').read_bytes(), 'dependency-notice')
        fixture_root = ROOT / 'artifacts/dependency-notification/notice-fixtures'
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
            fixture = Path(directory)
            marker = fixture / 'unexpected-execution'
            summary = fixture / 'summary.md'
            hostile = '$(touch ' + str(marker) + ')'
            env = {**os.environ, 'GITHUB_STEP_SUMMARY': str(summary), 'PR_URL': hostile, 'PR_HEAD': hostile}
            subprocess.run(['bash', '-c', source['jobs']['notice']['steps'][0]['run']], cwd=fixture, env=env, check=True, capture_output=True)
            self.assertFalse(marker.exists())
            self.assertIn(hostile, summary.read_text())
            self.assertIn('did not run', summary.read_text())


if __name__ == '__main__':
    unittest.main()

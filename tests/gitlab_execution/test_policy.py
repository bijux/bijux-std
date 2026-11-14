from __future__ import annotations

import copy
import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SHA, HEAD = 'a' * 40, 'b' * 40


def policy():
    path = ROOT / 'shared/bijux-gitlab/policy.py'
    if not path.is_file():
        raise AssertionError('canonical review requires native GitLab policy admission')
    return runpy.run_path(str(path))


def environment():
    return {'CI_PROJECT_ID':'88948041','CI_PROJECT_PATH':'bijux-oss/bijux-std',
            'CI_SERVER_URL':'https://gitlab.com','CI_PIPELINE_SOURCE':'merge_request_event',
            'CI_MERGE_REQUEST_IID':'12','CI_COMMIT_SHA':HEAD,
            'CI_DEFAULT_BRANCH':'main','CI_COMMIT_BRANCH':'feature',
            'CI_COMMIT_REF_PROTECTED':'false'}


def merge_request():
    return {'iid':12,'target_project_id':88948041,'target_branch':'main','state':'opened',
            'sha':HEAD,'diff_refs':{'head_sha':HEAD},'author':{'username':'bijux'},
            'labels':['owner-self-signoff'],'draft':False,'work_in_progress':False,
            'merge_commit_sha':None}


class CanonicalReviewTests(unittest.TestCase):
    def test_owner_signoff_binds_real_native_mr_head(self):
        result = policy()['validate_review'](environment(), lambda path:merge_request())
        self.assertEqual(result['merge_request_iid'], 12)
        self.assertEqual(result['review'], 'owner-self-signoff')
        self.assertIs(result['publication_authorization'], False)

    def test_missing_or_wrong_head_project_and_owner_signoff_fail_closed(self):
        for change in ({'sha':SHA}, {'target_project_id':1}, {'labels':[]},
                       {'state':'closed'}, {'draft':True}, {'diff_refs':{'head_sha':SHA}}):
            mr=merge_request(); mr.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy()['validate_review'](environment(), lambda path:mr)

    def test_other_authors_need_actual_owner_approval(self):
        mr=merge_request(); mr['author']={'username':'contributor'}; mr['labels']=[]
        def read(path):
            return {'approved_by':[{'user':{'username':'bijux'}}]} if path.endswith('/approvals') else mr
        self.assertEqual(policy()['validate_review'](environment(), read)['review'], 'owner-approved')
        for approvals in ({}, {'approved_by':[]}, {'approved_by':[{'user':{'username':'someone'}}]}):
            def denied(path):
                return approvals if path.endswith('/approvals') else mr
            with self.subTest(approvals=approvals), self.assertRaises(ValueError):
                policy()['validate_review'](environment(), denied)

    def test_owner_approval_cannot_borrow_a_racing_mr_head(self):
        mr=merge_request(); mr['author']={'username':'contributor'}
        reads=[mr, {'approved_by':[{'user':{'username':'bijux'}}]}, {**mr,'sha':SHA}]
        with self.assertRaises(ValueError):
            policy()['validate_review'](environment(), lambda path:reads.pop(0))

    def test_main_requires_one_actual_merged_mr_at_exact_merge_commit(self):
        env={**environment(),'CI_PIPELINE_SOURCE':'push','CI_COMMIT_SHA':SHA,
             'CI_COMMIT_BRANCH':'main','CI_COMMIT_REF_PROTECTED':'true'}
        mr={**merge_request(),'state':'merged','merge_commit_sha':SHA}
        def read(path):
            return [mr] if '/repository/commits/' in path else mr
        result=policy()['validate_review'](env,read)
        self.assertEqual(result['scope'],'accepted-main-review')
        for rows in ([], [mr,mr], [{**mr,'merge_commit_sha':HEAD}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                policy()['validate_review'](env, lambda path:rows)

    def test_feature_push_is_validation_only_and_unsupported_release_ref_is_blocked(self):
        env={**environment(),'CI_PIPELINE_SOURCE':'push'}
        def unexpected(path):
            raise AssertionError('ordinary branch validation must not claim review admission')
        result=policy()['validate_review'](env,unexpected)
        self.assertEqual(result['scope'],'branch-validation')
        self.assertIs(result['publication_authorization'],False)
        with self.assertRaises(ValueError):
            policy()['validate_review']({**env,'CI_COMMIT_TAG':'v1.0.0'},unexpected)

    def test_public_review_reader_has_no_ambient_authentication_and_rejects_redirect_paths(self):
        import io
        import os
        from unittest.mock import patch
        module=policy(); namespace=module['public_read'].__globals__
        class Response(io.BytesIO):
            status=200
            headers={'X-Next-Page':''}
        class Transport:
            def open(self,request,timeout):
                self.request=request
                return Response(b'{"iid":12}')
        transport=Transport()
        with patch.dict(namespace,{'build_opener':lambda *args:transport}), \
                patch.dict(os.environ,{'CI_JOB_TOKEN':'inert-private-token','GH_TOKEN':'inert-session-token'}):
            self.assertEqual(module['public_read']('/projects/88948041/merge_requests/12'),{'iid':12})
        self.assertEqual(transport.request.get_method(),'GET')
        headers=dict(transport.request.header_items())
        self.assertFalse(any('token' in name.lower() or 'authorization' in name.lower() for name in headers))
        for path in ('https://another.host/','/projects/1/merge_requests/12',
                     '/projects/88948041/merge_requests/12/approve'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                module['public_read'](path)

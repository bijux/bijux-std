"""Keep two-destination acknowledgements truthful across partial publication."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


class PublicationCoordinationTests(unittest.TestCase):
    def module(self):
        path=ROOT/'shared/bijux-gitlab/publication/coordinator.py'
        self.assertTrue(path.is_file(), 'Two mirror writes need a source-owned coordinator')
        spec=importlib.util.spec_from_file_location('bijux_publication_coordinator',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

    def proof(self):
        return {'name':'bijux-std','project_id':88948041,'project_path':'bijux-oss/bijux-std',
                'commit_sha':'b'*40,'parent_pipeline_id':123,'report_job_id':456,'mr_iid':7,
                'canonical_mr_url':'https://gitlab.com/bijux-oss/bijux-std/-/merge_requests/7',
                'evidence_url':'https://gitlab.com/bijux-oss/bijux-std/-/pipelines/123',
                'route':{'name':'bijux-std','project_id':88948041,'project_path':'bijux-oss/bijux-std',
                         'github_repository_id':1212849789,'personal_gitlab_project_id':88949531}}

    def test_partial_failure_retains_successful_destination_and_replay_is_idempotent(self):
        module=self.module();events=[];main={'github':'a'*40,'gitlab':'a'*40};failure=[True]
        class GitHub:
            def verify_mirror(self):events.append('github/settings');return {'repository_id':1212849789,'actions_enabled':False}
            def status(self,*args):events.append('status')
            def ensure_pr(self,*args):events.append('pr');return {'number':8,'url':'https://github.com/bijux/bijux-std/pull/8'}
            def acknowledge_pr(self,*args):events.append('merged');return {'number':8,'merged':True,'head_sha':'b'*40}
        def verify():events.append('gitlab/settings');return {'id':88949531,'builds_access_level':'disabled'}
        def publish(host,branch,candidate):
            events.append((host,branch))
            if host=='gitlab' and failure[0]:raise ValueError('simulated unavailable destination')
            before=main[host] if branch=='main' else candidate
            if branch=='main':main[host]=candidate
            return {'before':before,'after':candidate,'status':'unchanged' if before==candidate else 'published'}
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            path=Path(folder)/'receipt.json'
            result=module.coordinate(self.proof(),GitHub(),verify,publish,path)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['destinations']['github']['after'],'b'*40)
            self.assertEqual(main['gitlab'],'a'*40)
            failure[0]=False
            result=module.coordinate(self.proof(),GitHub(),verify,publish,path)
            self.assertEqual(result['status'],'published')
            self.assertEqual(result['destinations']['github']['status'],'unchanged')
            self.assertEqual(main['gitlab'],'b'*40)
            self.assertLess(events.index('pr'),events.index(('github','main')))
            self.assertTrue(path.is_file())

    def test_wrong_destination_or_executing_mirror_prevents_any_write(self):
        module=self.module()
        class GitHub:
            def verify_mirror(self):return {'repository_id':1212849789,'actions_enabled':True}
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            def forbidden(*args):self.fail('No destination may mutate before identity/execution checks')
            with self.assertRaises(ValueError):
                module.coordinate(self.proof(),GitHub(),forbidden,forbidden,Path(folder)/'receipt.json')
        for key,value in [('github_repository_id',1),('personal_gitlab_project_id',1),('project_id',1)]:
            proof=self.proof();proof['route'][key]=value
            with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder, self.subTest(key=key), self.assertRaises(ValueError):
                module.coordinate(proof,GitHub(),lambda:{},lambda *args:None,Path(folder)/'receipt.json')

    def test_indirect_pr_acknowledgement_is_required_for_complete_publication(self):
        module=self.module()
        class GitHub:
            def verify_mirror(self):return {'repository_id':1212849789,'actions_enabled':False}
            def status(self,*args):pass
            def ensure_pr(self,*args):return {'number':1,'url':'https://github.com/bijux/bijux-std/pull/1'}
            def acknowledge_pr(self,*args):raise ValueError('PR is not merged')
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            result=module.coordinate(self.proof(),GitHub(),lambda:{'id':88949531,'builds_access_level':'disabled'},
                                     lambda *args:{'before':'a'*40,'after':'b'*40,'status':'published'},Path(folder)/'receipt.json')
            self.assertEqual(result['status'],'partial')
            self.assertNotIn('gitlab',result['destinations'])

    def test_real_admission_and_github_adapter_share_pipeline_and_receipt_links(self):
        import json
        import urllib.parse
        from tests.gitlab_publication import test_admission, test_github
        fixture=test_admission.PublicationAdmissionTests(methodName='test_completed_std_parent_and_actual_bridge_admit_only_accepted_merge_commit')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        proof=fixture.admit();sha=proof['commit_sha'];state={'merged':False};observed=[]
        github_path=ROOT/'shared/bijux-gitlab/publication/github.py'
        spec=importlib.util.spec_from_file_location('coordinator_actual_github',github_path)
        github=importlib.util.module_from_spec(spec);spec.loader.exec_module(github)
        repo={**test_github.REPOSITORY,'id':1212849789}
        branch=f'publication/gitlab-7-{sha[:12]}'
        pipeline='https://gitlab.com/bijux-oss/bijux-std/-/pipelines/200'
        def pr():
            return {'number':8,'html_url':'https://github.com/bijux/bijux-std/pull/8',
                'state':'closed' if state['merged'] else 'open','merged':state['merged'],
                'head':{'sha':sha,'ref':branch,'repo':repo},'base':{'ref':'main','repo':repo},
                'body':proof['canonical_mr_url']+'\n'+pipeline}
        class NativeResponses:
            def open(self,request,timeout):
                path=urllib.parse.urlsplit(request.full_url).path;method=request.get_method();value=None
                if path=='/repos/bijux/bijux-std':value=repo
                elif path.endswith('/actions/permissions'):value={'enabled':False}
                elif '/statuses/' in path:
                    value=json.loads(request.data);observed.append(value['target_url'])
                elif path.endswith('/pulls') and method=='GET':value=[]
                elif '/git/ref/heads/' in path:value={'ref':'refs/heads/'+branch,'object':{'type':'commit','sha':sha}}
                elif path.endswith('/pulls') and method=='POST':value=pr()
                elif path.endswith('/pulls/8'):value=pr()
                elif path.endswith('/labels/gitlab-publication'):value={'name':'gitlab-publication'}
                elif path.endswith('/issues/8/labels'):value=[{'name':'gitlab-publication'}]
                else:raise AssertionError('Unexpected native operation')
                status=201 if method=='POST' and not path.endswith('/issues/8/labels') else 200
                return test_github.Response(value,status=status,url=request.full_url)
        gh=github.GitHub('bijux/bijux-std',1212849789,'inert-token',opener=NativeResponses())
        def publish(host,ref,candidate):
            if (host,ref)==('github','main'):state['merged']=True
            return {'before':'a'*40,'after':candidate,'status':'published'}
        result=self.module().coordinate(proof,gh,lambda:{'id':88949531,'builds_access_level':'disabled'},
                                       publish,fixture.root/'artifacts/publication/receipt.json')
        self.assertEqual(result['status'],'published')
        self.assertEqual(observed,[pipeline])
        self.assertEqual(result['acceptance_url'],proof['evidence_url'])

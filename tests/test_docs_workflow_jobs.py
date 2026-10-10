"""Physical owner, carried projection and active caller authority counterexamples."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'tests/bijux-docs/execution/workflow_lineage.py'
SPEC = importlib.util.spec_from_file_location('physical_lineage_tests', PATH)
LINEAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINEAGE)
JOBS = LINEAGE.JOBS


class API:
    repository = 'bijux/bijux-std'
    def __init__(self, responses, archive):
        self.responses, self.body, self.calls = responses, archive, []
    def json(self, endpoint):
        self.calls.append(endpoint)
        return copy.deepcopy(self.responses[endpoint])
    def archive(self, artifact_id):
        self.calls.append(('archive', artifact_id))
        return self.body


class PhysicalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.prefix = 'repos/bijux/bijux-std/'
        self.runpath = self.prefix + 'actions/runs/123'
        self.identity = dict(run_id=123, attempt=2, head='a'*40, checkout_sha='a'*40,
                             source_tree='b'*40, workflow_id=456,
                             workflow_path='.github/workflows/bijux-std.yml', head_branch='ci/docs-reader')
        run = dict(id=123, head_sha='a'*40, head_branch='ci/docs-reader', workflow_id=456,
                   path=self.identity['workflow_path'], repository={'id':789,'full_name':API.repository},
                   head_repository={'id':789,'full_name':API.repository}, check_suite_id=99)
        self.runs = [{**run, 'run_attempt':1, 'run_started_at':'2026-01-01T00:00:00Z'},
                     {**run, 'run_attempt':2, 'run_started_at':'2026-01-01T00:02:00Z'}]
        self.producer = self.job(11,1,'std / navigation fixtures', '2026-01-01T00:00:01Z','2026-01-01T00:01:00Z')
        self.old_browser = self.job(12,1,'std / navigation contrast-desktop / chromium',
                                    '2026-01-01T00:00:02Z','2026-01-01T00:01:00Z')
        self.copy = {**copy.deepcopy(self.producer),'id':101,'run_attempt':2,
                     'created_at':'2026-01-01T00:02:05Z',
                     'check_run_url':'https://api.github.com/'+self.prefix+'check-runs/101'}
        self.browser = self.job(22,2,self.old_browser['name'],'2026-01-01T00:02:02Z','2026-01-01T00:02:41Z')
        self.browser['conclusion']='failure'
        self.queued = {**copy.deepcopy(self.browser),'id':21,'created_at':'2026-01-01T00:02:01Z',
                       'started_at':None,'completed_at':None,'steps':[],'runner_id':0,'runner_name':'',
                       'status':'queued','conclusion':None,
                       'check_run_url':'https://api.github.com/'+self.prefix+'check-runs/21'}
        self.responses = {self.runpath:self.runs[1],self.prefix+'actions/workflows/456':
                          {'id':456,'path':self.identity['workflow_path']},
                          self.prefix+'git/commits/'+'a'*40:{'sha':'a'*40,'tree':{'sha':'b'*40}}}
        for attempt,rows in [(1,[self.producer,self.old_browser]),(2,[self.copy,self.queued,self.browser])]:
            self.responses[self.runpath+'/attempts/'+str(attempt)]=self.runs[attempt-1]
            self.responses[self.runpath+'/attempts/'+str(attempt)+'/jobs?per_page=100&page=1']={'total_count':len(rows),'jobs':rows}
        for row in [self.producer,self.old_browser,self.copy,self.queued,self.browser]:
            self.responses[self.prefix+'actions/jobs/'+str(row['id'])]=row
            self.responses[self.prefix+'check-runs/'+str(row['id'])]=self.check(row)
        output=io.BytesIO()
        receipt={'source_head':'a'*40,'workflow_run_id':'123','workflow_attempt':'1'}
        with zipfile.ZipFile(output,'w')as stream:stream.writestr('producer-envelope.json',json.dumps(receipt))
        self.body=output.getvalue()
        self.artifact=dict(id=33,name='docs-navigation-fixtures-'+'a'*40+'-1',digest='sha256:'+hashlib.sha256(self.body).hexdigest(),size_in_bytes=len(self.body),expired=False,created_at='2026-01-01T00:00:50Z',expires_at='2026-02-01T00:00:00Z',workflow_run={'id':123,'head_sha':'a'*40,'head_branch':'ci/docs-reader','repository_id':789,'head_repository_id':789})
        self.responses[self.runpath+'/artifacts?per_page=100&page=1']={'total_count':1,'artifacts':[self.artifact]}
        self.responses[self.prefix+'actions/artifacts/33']=self.artifact
        self.api=API(self.responses,self.body)
        self.roles={'producer':dict(job_name=self.producer['name'],artifact_prefix='docs-navigation-fixtures',upload_step='Retain immutable fixtures')}

    def job(self,identifier,attempt,name,start,end):
        return dict(id=identifier,run_id=123,run_attempt=attempt,head_sha='a'*40,
                    head_branch='ci/docs-reader',workflow_name='bijux-std',name=name,status='completed',
                    conclusion='success',created_at=start,started_at=start,completed_at=end,
                    runner_id=identifier+100,runner_name='owned runner '+str(identifier),labels=['ubuntu-latest'],
                    check_run_url='https://api.github.com/'+self.prefix+'check-runs/'+str(identifier),
                    steps=[dict(number=1,name='Retain immutable fixtures',status='completed',
                                conclusion='success',started_at=start,completed_at=end)])

    def check(self,row):
        return dict(id=row['id'],url=row['check_run_url'],name=row['name'],head_sha=row['head_sha'],
                    check_suite={'id':99},app={'id':15368,'slug':'github-actions'},
                    external_id='browser-execution' if row['name']==self.old_browser['name'] else 'producer-'+str(row['id']),
                    status=row['status'],conclusion=row['conclusion'],started_at=row['started_at'],completed_at=row['completed_at'])

    def observe(self,caller=None):
        return LINEAGE.observe_source(self.api,self.identity,reconcile=True,caller=caller)

    def activate(self):
        self.browser.update(status='in_progress',conclusion=None,completed_at=None)
        self.browser['steps'][0].update(status='in_progress',conclusion=None,completed_at=None)
        self.responses[self.prefix+'check-runs/22']=self.check(self.browser)

    def test_raw_projection_and_reservation_retained_new_failure_precedes_old_success(self):
        before=copy.deepcopy(self.responses);s=self.observe();o=s.observation
        self.assertEqual({r['name']:r['id'] for r in o['latest']['jobs']},{self.producer['name']:11,self.browser['name']:22})
        self.assertEqual(o['execution_reconciliation']['aliases'][0]['projection']['id'],101)
        self.assertEqual(o['execution_reconciliation']['reservations'][0]['physical_job_id'],22)
        self.assertEqual(o['execution_reconciliation']['raw_rows'],5)
        self.assertEqual(self.responses,before)
        self.assertEqual(s.verify_jobs([self.browser['name']])[0]['conclusion'],'failure')
        self.assertFalse(any('filter=' in str(c) for c in self.api.calls))

    def test_original_success_body_retains_attempt_one_and_cannot_be_recreated_from_audit(self):
        s=self.observe();item=s.admit(self.roles,now=datetime(2026,1,2,tzinfo=timezone.utc))['producer']
        self.assertEqual(item.pointer()['owner_attempt'],1)
        item.verify_receipt('producer-envelope.json',item.read('producer-envelope.json'))
        with self.assertRaises(ValueError):LINEAGE.SourceObservation(self.api,s.export_record())
        with self.assertRaises(ValueError):LINEAGE.ArtifactInput(item.pointer(),{})

    def test_active_caller_admits_old_producer_before_browser_finishes(self):
        self.activate();s=self.observe(self.browser['name']);item=s.admit(self.roles,now=datetime(2026,1,2,tzinfo=timezone.utc))['producer']
        self.assertEqual(item.pointer()['owner_job_id'],11)
        self.assertEqual(s.verify_jobs([self.browser['name']])[0]['status'],'in_progress')
        self.assertNotIn(self.prefix+'actions/jobs/22',s.export_record()['authoritative_per_id'])
        self.assertNotIn(self.prefix+'check-runs/22',s.export_record()['authoritative_per_id'])

    def test_active_caller_runner_and_check_binding_cannot_change_during_refresh(self):
        self.activate();s=self.observe(self.browser['name'])
        self.responses[self.prefix+'check-runs/22']['external_id']='new binding'
        with self.assertRaises(ValueError):s.verify_jobs([self.browser['name']])
        self.responses[self.prefix+'check-runs/22']=self.check(self.browser)
        self.browser['runner_id']+=1
        with self.assertRaises(ValueError):s.verify_jobs([self.browser['name']])

    def test_missing_or_foreign_active_caller_cannot_authorize_needed_execution(self):
        self.activate()
        for caller in [None,'std / foreign']:
            with self.subTest(caller=caller):
                if caller is None:
                    s=self.observe();self.assertTrue(s.observation['execution_reconciliation']['unresolved'])
                    with self.assertRaises(ValueError):s.verify_jobs([self.browser['name']])
                else:
                    with self.assertRaises(ValueError):self.observe(caller)

    def test_ambiguous_current_physical_owner_refuses(self):
        extra=self.job(23,2,self.browser['name'],'2026-01-01T00:02:03Z','2026-01-01T00:02:42Z')
        frame=self.responses[self.runpath+'/attempts/2/jobs?per_page=100&page=1'];frame['jobs'].append(extra);frame['total_count']+=1
        with self.assertRaises(ValueError):self.observe()

    def test_unmatched_reservation_cannot_grant_role_success(self):
        self.responses[self.prefix+'check-runs/21']['external_id']='different'
        s=self.observe();self.assertTrue(s.observation['execution_reconciliation']['unresolved'])
        with self.assertRaises(ValueError):s.verify_jobs([self.browser['name']])

    def test_projection_step_runner_source_and_time_drift_refuse(self):
        for key,value in [('runner_id',999),('steps',[]),('head_sha','f'*40),('completed_at','2026-01-01T00:02:30Z')]:
            old=copy.deepcopy(self.copy)
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.copy[key]=value;self.observe()
            self.copy.clear();self.copy.update(old)

    def test_reservation_may_project_exact_actual_steps_without_owning_a_runner(self):
        self.queued['steps']=copy.deepcopy(self.browser['steps'])
        s=self.observe()
        self.assertEqual(s.observation['execution_reconciliation']['reservations'][0]['physical_job_id'],22)
        self.queued['steps'][0]['name']='foreign operation'
        s=self.observe()
        with self.assertRaises(ValueError):s.verify_jobs([self.browser['name']])

    def test_live_original_check_source_authority_refuses(self):
        for key,value in [('app',{'id':1,'slug':'github-actions'}),('check_suite',{'id':100}),('head_sha','f'*40),('name','foreign'),('url','https://foreign.invalid/check-runs/11'),('completed_at','2026-01-01T00:01:01Z')]:
            row=self.responses[self.prefix+'check-runs/11'];old=copy.deepcopy(row)
            with self.subTest(key=key),self.assertRaises(ValueError):
                row[key]=value;self.observe()
            row.clear();row.update(old)

    def test_live_original_job_change_refuses(self):
        self.responses[self.prefix+'actions/jobs/11']={**self.producer,'runner_id':999}
        with self.assertRaises(ValueError):self.observe()

    def test_missing_authoritative_original_or_projection_refuses(self):
        for identifier in [11,101]:
            endpoint=self.prefix+'actions/jobs/'+str(identifier);old=self.responses.pop(endpoint)
            with self.subTest(identifier=identifier),self.assertRaises(KeyError):self.observe()
            self.responses[endpoint]=old

    def test_collection_caller_role_is_required_before_api_admission(self):
        path=PATH.with_name('workflow_collection.py')
        spec=importlib.util.spec_from_file_location('physical_collection_tests',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for stage,caller in [('producer',None),('producer','producer'),('producer','foreign'),('navigation','persisted')]:
            with self.subTest(stage=stage,caller=caller),self.assertRaisesRegex(ValueError,'caller'):
                module.collect(self.api,self.identity,stage,ROOT/'artifacts',reconcile=True,caller=caller)
        self.assertEqual(self.api.calls,[])

    def test_collection_bridges_exact_native_role_before_producer_admission(self):
        path=PATH.with_name('workflow_collection.py')
        spec=importlib.util.spec_from_file_location('physical_collection_tests',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        state={key:self.identity[key] for key in ['checkout_sha','source_tree']}
        with patch.object(module,'checkout_state',return_value=state),patch.object(module.LINEAGE,'observe_source',side_effect=ValueError('admission boundary'))as observe:
            with self.assertRaisesRegex(ValueError,'admission boundary'):
                module.collect(self.api,self.identity,'producer',ROOT/'artifacts',reconcile=True,caller='browser-contrast-desktop-chromium')
            observe.assert_called_once_with(self.api,self.identity,reconcile=True,caller=self.browser['name'])
        self.assertEqual(self.api.calls,[])

    def test_incomplete_attempt_page_refuses(self):
        self.responses[self.runpath+'/attempts/2/jobs?per_page=100&page=1']['total_count']=4
        with self.assertRaises(ValueError):self.observe()

    def test_foreign_attempt_source_and_attempt_bound_refuse(self):
        old=copy.deepcopy(self.runs[0]);self.runs[0]['head_sha']='f'*40
        with self.assertRaises(ValueError):self.observe()
        self.runs[0].clear();self.runs[0].update(old);self.identity['attempt']=9
        with self.assertRaises(ValueError):JOBS.capture(self.api,self.identity,LINEAGE.ARTIFACTS.pages)

    def test_actual_active_caller_has_runner_and_current_step(self):
        self.activate()
        for key,value in [('runner_id',0),('steps',[]),('created_at','2026-01-01T00:02:40Z')]:
            old=copy.deepcopy(self.browser)
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.browser[key]=value;self.observe(self.browser['name'])
            self.browser.clear();self.browser.update(old)

    def test_source_change_during_refresh_revokes_admission(self):
        s=self.observe();self.responses[self.runpath]={**self.runs[1],'run_attempt':3}
        with self.assertRaises(ValueError):s.admit(self.roles,now=datetime(2026,1,2,tzinfo=timezone.utc))
        self.assertFalse(any(isinstance(c,tuple) for c in self.api.calls))

    def test_new_physical_attempt_during_refresh_revokes_old_producer(self):
        s=self.observe();row=self.job(30,2,self.producer['name'],'2026-01-01T00:02:04Z','2026-01-01T00:02:44Z');row['conclusion']='cancelled'
        frame=self.responses[self.runpath+'/attempts/2/jobs?per_page=100&page=1'];frame['jobs'].append(row);frame['total_count']+=1
        self.responses[self.prefix+'actions/jobs/30']=row;self.responses[self.prefix+'check-runs/30']=self.check(row)
        with self.assertRaises(ValueError):s.admit(self.roles,now=datetime(2026,1,2,tzinfo=timezone.utc))
        self.assertFalse(any(isinstance(c,tuple) for c in self.api.calls))

    def test_expired_or_misattributed_artifact_refuses_before_download(self):
        for key,value in [('expired',True),('name','docs-navigation-fixtures-'+'a'*40+'-2'),('created_at','2026-01-01T00:02:40Z')]:
            old=copy.deepcopy(self.artifact)
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.artifact[key]=value;s=self.observe();s.admit(self.roles,now=datetime(2026,1,2,tzinfo=timezone.utc))
            self.artifact.clear();self.artifact.update(old)

    def test_unmodified_physical_success_has_positive_terminal_ownership(self):
        self.browser['conclusion']='success';self.responses[self.prefix+'check-runs/22']=self.check(self.browser)
        s=self.observe();self.assertEqual(s.verify_jobs([self.browser['name']])[0]['conclusion'],'success')
        self.assertFalse(s.observation['execution_reconciliation']['unresolved'])

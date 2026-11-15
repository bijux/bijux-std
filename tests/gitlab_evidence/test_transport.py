"""Keep public evidence reads fixed to immutable native owners and safe bodies."""
import hashlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
import warnings
from urllib.error import HTTPError
import zipfile

from tests.gitlab_evidence.test_jobs import EVIDENCE, HEAD, ROOT, job, load


class Response(io.BytesIO):
    def __init__(self, value, headers=None):
        data = value if isinstance(value, bytes) else json.dumps(value).encode()
        super().__init__(data)
        self.status = 200
        self.headers = {'Content-Length': str(len(data)), **(headers or {})}


class PublicTransportTests(unittest.TestCase):
    pipeline_url = 'https://gitlab.com/api/v4/projects/17/pipelines/30/jobs?include_retried=true&per_page=100&page=1'
    project_url = 'https://gitlab.com/api/v4/projects/17'
    raw_url = 'https://gitlab.com/bijux/bijux-std/-/jobs/11/raw'
    artifact_url = 'https://gitlab.com/api/v4/projects/17/jobs/11/artifacts'

    def client(self, responses, *, read_token=None, project_path=None):
        self.requests = []
        class Opener:
            def open(inner, request, timeout):
                self.requests.append(request)
                value = responses[request.full_url]
                if callable(value): value = value()
                if isinstance(value, Exception): raise value
                return value
        return load('api').GitLabAPI(17, opener=Opener(), read_token=read_token, project_path=project_path)

    def responses(self, *, rows=None, body=b'owned native body'):
        rows = rows if rows is not None else [job(artifacts_file={'filename':'artifacts.zip','size':len(body)})]
        return {self.pipeline_url: lambda: Response(rows, {'X-Page':'1','X-Next-Page':''}),
                self.project_url: Response({'id':17,'path_with_namespace':'bijux/bijux-std'}),
                self.raw_url: Response(body, {'Content-Type':'text/plain; charset=utf-8'}),
                self.artifact_url: Response(body)}

    def redirect(self, endpoint, location):
        return HTTPError(endpoint,302,'redirect',{'Location':location},io.BytesIO())

    def test_all_retried_pages_are_retained_without_session_credentials(self):
        base = self.pipeline_url[:-1]
        first = [job(index+1,'owner-'+str(index)) for index in range(100)]
        api = self.client({base+'1':Response(first,{'X-Page':'1','X-Next-Page':'2'}),
                           base+'2':Response([job(101)],{'X-Page':'2','X-Next-Page':''})})
        self.assertEqual(len(api.pipeline_jobs(30)),101)
        self.assertEqual(len(api.observations),2)
        for request in self.requests:
            self.assertIsNone(request.get_header('Authorization'))
            self.assertIsNone(request.get_header('Private-token'))
            self.assertEqual(request.get_method(),'GET')

    def test_ambiguous_pagination_and_duplicate_jobs_are_refused(self):
        for headers in ({'X-Page':'1'}, {'X-Page':'2','X-Next-Page':''}, {'X-Page':'1','X-Next-Page':'3'}):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                self.client({self.pipeline_url:Response([job()],headers)}).pipeline_jobs(30)
        with self.assertRaises(ValueError):
            self.client({self.pipeline_url:Response([job(),job()],{'X-Page':'1','X-Next-Page':''})}).pipeline_jobs(30)

    def test_job_lookup_uses_only_complete_public_snapshot_and_returns_defensive_copy(self):
        api = self.client(self.responses())
        observed = api.job(11,pipeline_id=30,commit_sha=HEAD)
        observed['status']='failed'
        self.assertEqual(api.job(11,pipeline_id=30,commit_sha=HEAD)['status'],'success')
        self.assertEqual([request.full_url for request in self.requests],[self.pipeline_url])
        with self.assertRaises(ValueError): api.job(999,pipeline_id=30,commit_sha=HEAD)
        self.assertEqual(len(self.requests),1)

    def test_explicit_final_snapshot_refresh_exposes_newer_retry_without_reusing_old_cache(self):
        rows=[job()]
        responses=self.responses(rows=rows)
        api=self.client(responses)
        self.assertEqual(api.job(11,pipeline_id=30,commit_sha=HEAD)['status'],'success')
        rows.append(job(12,status='failed'))
        self.assertEqual(len(api.pipeline_jobs(30)),2)
        self.assertEqual(api.job(12,pipeline_id=30,commit_sha=HEAD)['status'],'failed')
        self.assertEqual(len(self.requests),2)

    def test_failed_public_snapshot_read_blocks_without_any_token_fallback(self):
        api=self.client({self.pipeline_url:HTTPError(self.pipeline_url,403,'forbidden',{},io.BytesIO())})
        with self.assertRaisesRegex(ValueError,'Public GitLab evidence read unavailable'):
            api.job(11,pipeline_id=30,commit_sha=HEAD)

    def test_foreign_job_project_pipeline_and_commit_are_refused_before_raw_reads(self):
        for altered in (job(12),job(pipeline={'id':31,'project_id':17,'sha':HEAD}),
                        job(pipeline={'id':30,'project_id':18,'sha':HEAD}),job(commit={'id':'b'*40})):
            with self.subTest(altered=altered),self.assertRaises(ValueError):
                self.client(self.responses(rows=[altered])).trace(11,pipeline_id=30,commit_sha=HEAD)
            self.assertEqual(len(self.requests),1)

    def test_trace_and_artifact_use_immutable_job_membership_and_public_project_path(self):
        body=b'owned native body'
        api=self.client(self.responses(body=body),project_path='bijux/bijux-std')
        self.assertEqual(api.trace(11,pipeline_id=30,commit_sha=HEAD),body)
        self.assertEqual(api.artifact(11,pipeline_id=30,commit_sha=HEAD),body)
        urls=[request.full_url for request in self.requests]
        self.assertIn(self.raw_url,urls)
        self.assertNotIn('https://gitlab.com/api/v4/projects/17/jobs/11',urls)
        self.assertNotIn('https://gitlab.com/api/v4/projects/17/jobs/11/trace',urls)
        self.assertEqual(urls.count(self.pipeline_url),1)

    def test_public_project_metadata_must_bind_exact_id_and_expected_safe_path(self):
        for project in ({'id':18,'path_with_namespace':'bijux/bijux-std'},
                        {'id':17,'path_with_namespace':'another/project'},
                        {'id':17,'path_with_namespace':'../project'},
                        {'id':17,'path_with_namespace':'bijux/project?token=unowned'},
                        {'id':17,'path_with_namespace':'bijux/project%2Fother'}):
            responses=self.responses();responses[self.project_url]=Response(project)
            with self.subTest(project=project),self.assertRaises(ValueError):
                self.client(responses,project_path='bijux/bijux-std').trace(11,pipeline_id=30,commit_sha=HEAD)
            self.assertNotIn(self.raw_url,[request.full_url for request in self.requests])

    def test_html_binary_empty_and_signin_redirect_are_not_native_plaintext_traces(self):
        for body,content_type in ((b'<html>sign in</html>','text/html'),
                                  (b'<!DOCTYPE html><html>login</html>','text/plain'),
                                  (b'\x00binary','application/octet-stream'),(b'','text/plain')):
            responses=self.responses();responses[self.raw_url]=Response(body,{'Content-Type':content_type})
            with self.subTest(body=body),self.assertRaises(ValueError):
                self.client(responses).trace(11,pipeline_id=30,commit_sha=HEAD)
        responses=self.responses();responses[self.raw_url]=self.redirect(self.raw_url,'https://gitlab.com/users/sign_in')
        with self.assertRaises(ValueError):self.client(responses).trace(11,pipeline_id=30,commit_sha=HEAD)

    def test_metadata_redirects_are_refused(self):
        responses=self.responses();responses[self.pipeline_url]=self.redirect(self.pipeline_url,'https://unowned.example/token')
        with self.assertRaisesRegex(ValueError,'redirect'):
            self.client(responses).pipeline_jobs(30)

    def test_approved_artifact_and_raw_trace_storage_redirects_strip_credentials_and_signed_urls(self):
        for kind in ('artifact','trace'):
            body=b'public native bytes'
            responses=self.responses(body=body)
            endpoint=self.artifact_url if kind=='artifact' else self.raw_url
            storage='https://storage.googleapis.com/gitlab-artifacts/owned?signature=private-query-value'
            responses[endpoint]=self.redirect(endpoint,storage)
            responses[storage]=Response(body,{'Content-Type':'text/plain'})
            api=self.client(responses,read_token='dedicated-fixture-read-token')
            self.assertEqual(getattr(api,kind)(11,pipeline_id=30,commit_sha=HEAD),body)
            for header in ('Private-token','Authorization','Job-token'):
                self.assertIsNone(self.requests[-1].get_header(header))
            if kind=='trace':
                raw_request=next(request for request in self.requests if request.full_url==self.raw_url)
                self.assertIsNone(raw_request.get_header('Private-token'))
            self.assertNotIn('private-query-value',json.dumps(api.observations))

    def test_storage_redirects_reject_hostile_origins_without_query_in_errors(self):
        for location in ('http://storage.googleapis.com/a','https://user@storage.googleapis.com/a',
                         'https://storage.googleapis.com:444/a','https://unowned.example/a',
                         'https://storage.googleapis.com.evil.example/a'):
            for kind in ('artifact','trace'):
                responses=self.responses();endpoint=self.artifact_url if kind=='artifact' else self.raw_url
                responses[endpoint]=self.redirect(endpoint,location+'?signature=secret-query')
                with self.subTest(location=location,kind=kind),self.assertRaises(ValueError) as refused:
                    getattr(self.client(responses),kind)(11,pipeline_id=30,commit_sha=HEAD)
                self.assertNotIn('secret-query',str(refused.exception))

    def test_artifact_redirect_depth_is_bounded(self):
        responses=self.responses()
        storage=['https://artifacts.gitlab-static.net/body-'+str(index) for index in range(5)]
        responses[self.artifact_url]=self.redirect(self.artifact_url,storage[0])
        for index in range(4):responses[storage[index]]=self.redirect(storage[index],storage[index+1])
        with self.assertRaises(ValueError):self.client(responses).artifact(11,pipeline_id=30,commit_sha=HEAD)
        for error in responses.values():
            if isinstance(error,HTTPError):error.close()


def archive(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as stream:
        for name, body, mode in entries:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = mode << 16
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                stream.writestr(info, body)
    return output.getvalue()


class ArtifactArchiveTests(unittest.TestCase):
    def module(self):
        self.assertTrue((EVIDENCE / 'archive.py').is_file(), 'Native artifact body admission is missing')
        return load('archive')

    def test_physical_archive_members_are_hashed_and_materialized_without_overwrite(self):
        data = archive([('artifacts/docs/receipt.json', b'{"passed":true}', stat.S_IFREG | 0o644)])
        module = self.module()
        members = module.archive_members(data)
        self.assertEqual(members['files_sha256'], {'artifacts/docs/receipt.json': hashlib.sha256(b'{"passed":true}').hexdigest()})
        owner = ROOT / 'artifacts/qualification/gitlab-evidence'; owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as folder:
            destination = Path(folder) / 'admitted'
            record = module.extract(data, destination)
            self.assertEqual((destination / 'artifacts/docs/receipt.json').read_bytes(), b'{"passed":true}')
            self.assertEqual(record['archive_sha256'], hashlib.sha256(data).hexdigest())
            with self.assertRaises(ValueError): module.extract(data, destination)

    def test_traversal_links_duplicate_members_and_file_directory_collision_fail_before_write(self):
        entries = [('../escape', b'x', stat.S_IFREG | 0o644), ('/escape', b'x', stat.S_IFREG | 0o644),
                   ('a\\escape', b'x', stat.S_IFREG | 0o644), ('link', b'../outside', stat.S_IFLNK | 0o777)]
        module = self.module()
        for entry in entries:
            with self.subTest(entry=entry), self.assertRaises(ValueError): module.archive_members(archive([entry]))
        for rows in ([('a', b'x', stat.S_IFREG | 0o644), ('a/b', b'x', stat.S_IFREG | 0o644)],
                     [('a', b'x', stat.S_IFREG | 0o644), ('a', b'y', stat.S_IFREG | 0o644)]):
            with self.assertRaises(ValueError): module.archive_members(archive(rows))

    def test_corrupt_or_oversized_archives_are_refused(self):
        module = self.module()
        with self.assertRaises(ValueError): module.archive_members(b'not a zip')
        module.MAX_MEMBER_BYTES = 3
        with self.assertRaises(ValueError): module.archive_members(archive([('a', b'1234', stat.S_IFREG | 0o644)]))

    def test_embedded_null_member_name_is_not_silently_truncated(self):
        data = archive([('ownedXname', b'body', stat.S_IFREG | 0o644)]).replace(b'ownedXname', b'owned\x00name')
        with self.assertRaises(ValueError): self.module().archive_members(data)

    def test_empty_owned_directories_are_preserved(self):
        data = archive([('empty/', b'', stat.S_IFDIR | 0o755), ('receipt.json', b'{}', stat.S_IFREG | 0o644)])
        owner = ROOT / 'artifacts/qualification/gitlab-evidence'; owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as folder:
            destination = Path(folder) / 'admitted'
            self.module().extract(data, destination)
            self.assertTrue((destination / 'empty').is_dir())

    def test_linked_destination_ancestor_is_refused(self):
        data = archive([('receipt.json', b'{}', stat.S_IFREG | 0o644)])
        owner = ROOT / 'artifacts/qualification/gitlab-evidence'; owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as folder:
            parent = Path(folder); (parent / 'actual').mkdir(); (parent / 'linked').symlink_to(parent / 'actual')
            with self.assertRaises(ValueError): self.module().extract(data, parent / 'linked/admitted')
            self.assertFalse((parent / 'actual/admitted').exists())

    def test_collection_budget_is_reserved_before_expanding_each_member(self):
        data = archive([('receipt.json', b'1234', stat.S_IFREG | 0o644)])
        def reserve(size):
            if size > 3:
                raise ValueError('Native collection byte reservation exceeded')
        with self.assertRaisesRegex(ValueError, 'reservation exceeded'):
            self.module().archive_members(data, reserve=reserve)

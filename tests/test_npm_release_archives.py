from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('npm_release',ROOT/'shared/bijux-gh/scripts/npm_release.py')
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REPOSITORY='bijux/bijux-ro-crate-node'
COMMIT='a'*40
PACKAGE={'name':'@bijux/ro-crate-core','version':'0.1.0','directory':'core'}


class NpmArchiveTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'artifacts/tests').mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'artifacts/tests')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def archive(self, mutate=None, alias=None):
        package={'name':PACKAGE['name'],'version':'0.1.0','publishConfig':{'access':'public'},
                 'repository':{'type':'git','url':'git+https://github.com/'+REPOSITORY+'.git','directory':'packages/core'}}
        if mutate: mutate(package)
        path=self.root/'package.tgz'
        with tarfile.open(path,'w:gz') as archive:
            value=json.dumps(package).encode();member=tarfile.TarInfo('package/package.json');member.size=len(value)
            archive.addfile(member,io.BytesIO(value))
            if alias:
                member=tarfile.TarInfo(alias);member.size=1;archive.addfile(member,io.BytesIO(b'x'))
        return path

    def test_inspected_identity_uses_the_exact_archive_bytes(self):
        archive=self.archive()
        result=MODULE.validate_archive(archive,PACKAGE,REPOSITORY)
        self.assertEqual(result['sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(result['integrity'],'sha512-'+base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode())

    def test_root_private_wrong_source_and_unpublishable_dependencies_fail(self):
        for change in [lambda p:p.update(private=True),lambda p:p.update(version='0.2.0'),
                       lambda p:p.update(name='root'),lambda p:p.update(repository={}),
                       lambda p:p.update(publishConfig={'access':'restricted'}),
                       lambda p:p.update(optionalDependencies={'other':'file:../other'}),
                       lambda p:p.update(peerDependencies={'other':'workspace:*'})]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                MODULE.validate_archive(self.archive(change),PACKAGE,REPOSITORY)
        for name in ['../escape','package/../escape','package/./package.json','package/package.json']:
            with self.subTest(name=name),self.assertRaises(ValueError):
                MODULE.validate_archive(self.archive(alias=name),PACKAGE,REPOSITORY)

    def test_candidate_run_cannot_be_a_fork_pr_failed_run_or_other_source(self):
        value={'id':123,'repository':{'full_name':REPOSITORY},'head_repository':{'full_name':REPOSITORY},
               'head_sha':COMMIT,'head_branch':'main','event':'workflow_dispatch','status':'completed',
               'conclusion':'success','workflow_id':12}
        MODULE.validate_run(value,REPOSITORY,COMMIT,{'id':12,'path':'.github/workflows/package-candidate.yml'})
        for change in [{'event':'pull_request'},{'head_sha':'b'*40},{'conclusion':'failure'},
                       {'workflow_id':13},{'head_repository':{'full_name':'other/fork'}},{'head_branch':'feature'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                MODULE.validate_run({**value,**change},REPOSITORY,COMMIT,{'id':12,'path':'.github/workflows/package-candidate.yml'})

    def test_disabled_publication_fails_without_any_api_or_registry_calls(self):
        path=self.root/'.github/standards';path.mkdir(parents=True)
        (path/'repo-config.manifest.json').write_text(json.dumps({'repositories':[{
            'name':'bijux-ro-crate-node','workflow_allowlist':['release-npm'],
            'release_env':[{'key':'BIJUX_NPM_ENABLED','value':False}]}]}))
        with patch.object(MODULE,'api') as api,patch.object(MODULE,'run') as command:
            with self.assertRaisesRegex(ValueError,'disabled'):
                MODULE.prepare(self.root,REPOSITORY,COMMIT,'v0.1.0',12)
        api.assert_not_called();command.assert_not_called()

    def test_only_structured_404_is_a_missing_registry_version(self):
        for code in ['ENEEDAUTH','E401','ECONNRESET']:
            result=subprocess.CompletedProcess([],1,json.dumps({'error':{'code':code}}),'')
            with patch.object(MODULE.subprocess,'run',return_value=result),self.assertRaises(ValueError):
                MODULE.registry_integrity(PACKAGE['name'],'0.1.0')
        result=subprocess.CompletedProcess([],1,json.dumps({'error':{'code':'E404'}}),'')
        with patch.object(MODULE.subprocess,'run',return_value=result):
            self.assertIsNone(MODULE.registry_integrity(PACKAGE['name'],'0.1.0'))

    def test_recovery_skips_identical_bytes_and_never_overwrites_a_conflict(self):
        archive=self.archive();record=MODULE.validate_archive(archive,PACKAGE,REPOSITORY)
        folder=self.root/'artifacts/publication';folder.mkdir(parents=True)
        plan={'repository':REPOSITORY,'commit':COMMIT,'tag':'v0.1.0','registry':MODULE.REGISTRY,'packages':[record]}
        (folder/'npm-plan.json').write_text(json.dumps(plan))
        for existing,allowed in [(record['integrity'],True),('sha512-other',False)]:
            with patch.object(MODULE,'configuration',return_value=({'BIJUX_NPM_RELEASE_VERSION':'0.1.0'},[PACKAGE])), \
                 patch.object(MODULE,'inspect_archives',return_value=[record]), \
                 patch.object(MODULE,'run',return_value=COMMIT) as command, \
                 patch.object(MODULE.runpy,'run_path',return_value={'admit':Mock()}), \
                 patch.object(MODULE,'registry_integrity',return_value=existing):
                if allowed:
                    self.assertTrue(MODULE.publish(self.root,REPOSITORY,COMMIT,'v0.1.0')['complete'])
                else:
                    with self.assertRaisesRegex(ValueError,'different bytes'):
                        MODULE.publish(self.root,REPOSITORY,COMMIT,'v0.1.0')
                self.assertFalse(any(c.args[0][:2]==['npm','publish'] for c in command.call_args_list))

    def test_partial_failure_retains_the_published_core_and_failed_attempt(self):
        archive=self.archive();core=MODULE.validate_archive(archive,PACKAGE,REPOSITORY)
        validator={**core,'name':'@bijux/ro-crate-validator','archive':str(self.root/'validator.tgz')}
        folder=self.root/'artifacts/publication';folder.mkdir(parents=True)
        plan={'repository':REPOSITORY,'commit':COMMIT,'tag':'v0.1.0','registry':MODULE.REGISTRY,'packages':[core,validator]}
        (folder/'npm-plan.json').write_text(json.dumps(plan))
        def command(args):
            if args[:2]==['npm','publish'] and args[2]==validator['archive']:
                raise subprocess.CalledProcessError(1,args)
            return COMMIT
        admission=Mock()
        with patch.object(MODULE,'configuration',return_value=({'BIJUX_NPM_RELEASE_VERSION':'0.1.0'},[PACKAGE])), \
             patch.object(MODULE,'inspect_archives',return_value=[core,validator]), \
             patch.object(MODULE,'run',side_effect=command) as commands, \
             patch.object(MODULE.runpy,'run_path',return_value={'admit':admission}), \
             patch.object(MODULE,'registry_integrity',side_effect=[None,core['integrity'],None]), \
             self.assertRaises(subprocess.CalledProcessError):
            MODULE.publish(self.root,REPOSITORY,COMMIT,'v0.1.0')
        saved=json.loads((folder/'npm-receipt.json').read_text())
        self.assertFalse(saved['complete'])
        self.assertEqual([p['state'] for p in saved['packages']],['published','publication-attempted'])
        writes=[c.args[0] for c in commands.call_args_list if c.args[0][:2]==['npm','publish']]
        self.assertEqual([c[2] for c in writes],[core['archive'],validator['archive']])
        self.assertTrue(all('--ignore-scripts' in c for c in writes))
        self.assertEqual(admission.call_count,3)


    def test_decompression_is_bounded_before_tar_metadata_is_parsed(self):
        archive=self.archive()
        with patch.object(MODULE,'MAX_UNCOMPRESSED',256),self.assertRaisesRegex(ValueError,'decompression budget'):
            MODULE.validate_archive(archive,PACKAGE,REPOSITORY)


    def test_candidate_receipts_bind_source_lock_archive_bytes_and_dependency_order(self):
        destination=self.root/'candidate'
        (destination/'reports').mkdir(parents=True)
        (destination/'packages').mkdir()
        (self.root/'package-lock.json').write_text('{}\n')
        (destination/'reports/candidate-commit.txt').write_text(COMMIT)
        (destination/'reports/candidate-tree.txt').write_text('tree-identity')
        (destination/'reports/package-lock.sha256').write_text(hashlib.sha256((self.root/'package-lock.json').read_bytes()).hexdigest()+'  package-lock.json\n')
        core=self.archive();core.rename(destination/'packages/core.tgz')
        def validator(p):
            p['name']='@bijux/ro-crate-validator'
            p['repository']['directory']='packages/validator'
            p['dependencies']={PACKAGE['name']:'0.1.0'}
        self.archive(validator).rename(destination/'packages/validator.tgz')
        packages=[PACKAGE,{'name':'@bijux/ro-crate-validator','version':'0.1.0','directory':'validator'}]
        records=[MODULE.validate_archive(destination/'packages'/filename,p,REPOSITORY)
                 for filename,p in zip(['core.tgz','validator.tgz'],packages)]
        manifest=destination/'packages/manifest.json'
        manifest.write_text(json.dumps(records))
        with patch.object(MODULE,'run',return_value='tree-identity'):
            result=MODULE.inspect_archives(self.root,destination,packages,REPOSITORY,COMMIT)
            self.assertEqual([r['name'] for r in result],[p['name'] for p in packages])
            self.assertTrue(all(not Path(r['archive']).is_absolute() for r in result))
            bad=copy.deepcopy(records);bad[0]['sha256']='0'*64
            manifest.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError,'digest'):
                MODULE.inspect_archives(self.root,destination,packages,REPOSITORY,COMMIT)
            manifest.write_text(json.dumps(records[::-1]))
            with self.assertRaisesRegex(ValueError,'precede'):
                MODULE.inspect_archives(self.root,destination,packages[::-1],REPOSITORY,COMMIT)
            manifest.write_text(json.dumps(records))
            for file,bad,message in [('candidate-commit.txt','b'*40,'source'),
                                     ('candidate-tree.txt','another-tree','tree'),
                                     ('package-lock.sha256','0'*64,'lock')]:
                path=destination/'reports'/file;original=path.read_bytes();path.write_text(bad)
                with self.subTest(file=file),self.assertRaisesRegex(ValueError,message):
                    MODULE.inspect_archives(self.root,destination,packages,REPOSITORY,COMMIT)
                path.write_bytes(original)

    def test_symbolic_and_hard_link_archive_members_are_refused(self):
        for kind in [tarfile.SYMTYPE,tarfile.LNKTYPE]:
            path=self.archive()
            with tarfile.open(path,'r:gz') as source:
                package=source.extractfile('package/package.json').read()
            with tarfile.open(path,'w:gz') as archive:
                member=tarfile.TarInfo('package/package.json');member.size=len(package)
                archive.addfile(member,io.BytesIO(package))
                member=tarfile.TarInfo('package/linked.js');member.type=kind;member.linkname='../outside'
                archive.addfile(member)
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'regular files'):
                MODULE.validate_archive(path,PACKAGE,REPOSITORY)

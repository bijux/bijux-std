"""Keep mirror credentials and writes outside ordinary validation jobs."""
import importlib.util
import json
from io import BytesIO
import tempfile
import os
import subprocess
import sys
from pathlib import Path
import unittest
from types import ModuleType
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


class PublicationDeliveryTests(unittest.TestCase):
    def test_entrypoint_loads_its_owned_modules_without_rebinding_documentation_publication(self):
        foreign = ModuleType('publication')
        foreign.__file__ = str(ROOT / 'shared/bijux-docs/tooling/quality/publication/__init__.py')
        previous_path = list(sys.path)
        with patch.dict(sys.modules, {'publication': foreign}):
            try:
                cli = module(ROOT / 'shared/bijux-gitlab/publication/cli.py', 'isolated_publication_cli')
            except ImportError as error:
                self.fail(f'The entrypoint must load its own modules despite a documentation package: {error}')
            for name in ('admission', 'coordinator', 'github', 'refs'):
                self.assertEqual(Path(getattr(cli, name).__file__), ROOT / f'shared/bijux-gitlab/publication/{name}.py')
            self.assertIs(sys.modules['publication'], foreign)
        self.assertEqual(sys.path, previous_path)

    def test_publication_uses_a_child_bridge_after_completed_report(self):
        pipeline=module(ROOT/'shared/bijux-gitlab/pipeline.py','delivery_pipeline')
        result=pipeline.compose(ROOT)
        self.assertIn('publish / mirrors',result,'Publication must be a separate child pipeline')
        bridge=result['publish / mirrors']
        self.assertEqual(bridge['needs'],['std / report'])
        self.assertEqual(bridge['trigger']['strategy'],'depend')
        self.assertEqual(bridge['variables']['BIJUX_PARENT_PIPELINE_ID'],'$CI_PIPELINE_ID')
        self.assertIn('BIJUX_MIRROR_PUBLICATION_READY',bridge['rules'][0]['if'])
        self.assertIn('CI_COMMIT_REF_PROTECTED',bridge['rules'][0]['if'])
        self.assertIn('CI_DEFAULT_BRANCH',bridge['rules'][0]['if'])
        self.assertNotIn('publish / mirrors',pipeline.job_contracts(ROOT))
        self.assertNotIn('allow_failure',bridge)

    def test_child_is_protected_canonical_main_with_only_publication_environment(self):
        path=ROOT/'shared/bijux-gitlab/ci/publication.yml'
        self.assertTrue(path.is_file(),'Protected mirror publication needs a source-owned child configuration')
        child=json.loads(path.read_text());job=child['publication / mirrors']
        self.assertEqual(job['environment'],{'name':'publication','action':'prepare'})
        self.assertEqual(job['resource_group'],'accepted-mirror-publication')
        self.assertFalse(job['interruptible'])
        self.assertEqual(job['artifacts']['paths'],['artifacts/publication/receipts/'])
        rule=child['workflow']['rules'][0]['if']
        for field in ('CI_PROJECT_ID','CI_PROJECT_PATH','CI_COMMIT_REF_PROTECTED','CI_PIPELINE_SOURCE','parent_pipeline'):
            self.assertIn(field,rule)
        self.assertEqual(child['workflow']['rules'][-1],{'when':'never'})
        self.assertNotIn('BIJUX_MIRROR_GITHUB_APP_KEY',json.dumps(child))

    def test_readback_token_can_only_read_the_declared_personal_mirror(self):
        path=ROOT/'shared/bijux-gitlab/publication/cli.py'
        self.assertTrue(path.is_file(),'The native entrypoint must own credential and destination boundaries')
        cli=module(path,'delivery_cli')
        self.assertTrue(callable(cli.verify_gitlab_mirror))
        with self.assertRaises(ValueError):cli.verify_gitlab_mirror(1,'inert')
        with self.assertRaises(ValueError):cli.verify_gitlab_mirror(88949531,'')

    def test_settings_readback_rejects_public_projection_and_preserves_no_extra_fields(self):
        cli=module(ROOT/'shared/bijux-gitlab/publication/cli.py','settings_cli')
        class Response(BytesIO):
            status=200
            def geturl(self):return 'https://gitlab.com/api/v4/projects/88949531'
        class Opener:
            def __init__(self,record):self.record=record;self.request=None
            def open(self,request,timeout):
                self.request=request
                return Response(json.dumps(self.record).encode())
        public=Opener({'id':88949531,'path_with_namespace':'bijux/bijux-std'})
        with self.assertRaises(ValueError):cli.verify_gitlab_mirror(88949531,'inert',opener=public)
        full={'id':88949531,'path_with_namespace':'bijux/bijux-std','builds_access_level':'disabled','default_branch':'main',
              'shared_runners_enabled':False,'group_runners_enabled':False,'auto_devops_enabled':False}
        successful=Opener({**full,'private_field':'not retained'})
        self.assertEqual(cli.verify_gitlab_mirror(88949531,'inert',opener=successful),full)
        self.assertEqual(successful.request.method,'GET')
        for key in ('shared_runners_enabled','group_runners_enabled','auto_devops_enabled'):
            with self.subTest(key=key),self.assertRaises(ValueError):
                cli.verify_gitlab_mirror(88949531,'inert',opener=Opener({**full,key:True}))

    def test_credentials_have_an_isolated_environment_and_are_removed_after_failure(self):
        cli=module(ROOT/'shared/bijux-gitlab/publication/cli.py','credentials_cli')
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
            root=Path(directory);key=root/'source-key';key.write_text('inert private key')
            with self.assertRaisesRegex(RuntimeError,'simulated failure'):
                with cli.credential_environment(root,{'PATH':'/usr/bin:/bin','HOME':'/sensitive',
                       'GH_TOKEN':'host-wide','GIT_CONFIG_GLOBAL':'/sensitive','SSH_AUTH_SOCK':'/sensitive'},'scoped-token',key) as env:
                    self.assertNotIn('GH_TOKEN',env)
                    self.assertNotIn('SSH_AUTH_SOCK',env)
                    self.assertTrue(Path(env['HOME']).is_relative_to(root/'artifacts'))
                    self.assertIn('StrictHostKeyChecking=yes',env['GIT_SSH_COMMAND'])
                    self.assertIn('IdentityAgent=none',env['GIT_SSH_COMMAND'])
                    self.assertIn('-F /dev/null',env['GIT_SSH_COMMAND'])
                    self.assertIn('GlobalKnownHostsFile=/dev/null',env['GIT_SSH_COMMAND'])
                    auth=Path(env['GIT_ASKPASS']).parent
                    self.assertEqual((auth/'gitlab-key').stat().st_mode&0o777,0o600)
                    raise RuntimeError('simulated failure')
            self.assertFalse(auth.exists())

    def test_credential_artifacts_cannot_follow_a_symlink(self):
        cli=module(ROOT/'shared/bijux-gitlab/publication/cli.py','symlink_cli')
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
            base=Path(directory);root=base/'checkout';root.mkdir();outside=base/'outside';outside.mkdir()
            key=base/'source-key';key.write_text('inert private key')
            (root/'artifacts').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(ValueError):
                with cli.credential_environment(root,{'PATH':'/usr/bin:/bin'},'scoped-token',key):pass
            self.assertEqual(list(outside.iterdir()),[])

    def test_error_handler_refuses_symlinked_output_and_preserves_existing_receipt(self):
        entry=ROOT/'shared/bijux-gitlab/publication/cli.py'
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
            base=Path(directory);root=base/'checkout';root.mkdir();outside=base/'outside';outside.mkdir()
            subprocess.run(['git','init','--quiet',str(root)],check=True)
            (root/'artifacts').symlink_to(outside,target_is_directory=True)
            result=subprocess.run([sys.executable,'-B',str(entry)],cwd=root,
                env={'PATH':os.environ['PATH']},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(list(outside.iterdir()),[])
            (root/'artifacts').unlink()
            target=root/'artifacts/publication/receipts/blocked.json';target.parent.mkdir(parents=True)
            target.write_text('existing owner evidence')
            result=subprocess.run([sys.executable,'-B',str(entry)],cwd=root,
                env={'PATH':os.environ['PATH']},capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(target.read_text(),'existing owner evidence')

    def test_default_branch_movement_invalidates_mirror_settings(self):
        cli=module(ROOT/'shared/bijux-gitlab/publication/cli.py','default_branch_cli')
        class Response(BytesIO):
            status=200
            def geturl(self):return 'https://gitlab.com/api/v4/projects/88949531'
        class Opener:
            def open(self,request,timeout):
                return Response(json.dumps({'id':88949531,'path_with_namespace':'bijux/bijux-std',
                    'builds_access_level':'disabled','shared_runners_enabled':False,
                    'group_runners_enabled':False,'auto_devops_enabled':False,'default_branch':'other'}).encode())
        with self.assertRaises(ValueError):cli.verify_gitlab_mirror(88949531,'inert',opener=Opener())

    def test_iac_profile_explicitly_selects_the_shared_native_publication_adapter(self):
        source=json.loads((ROOT/'.github/standards/repository-profiles.json').read_text())
        profiles={row['name']:row for row in source['repositories']}
        self.assertIn('bijux-iac',profiles,'IaC adoption must explicitly select the GitLab capability')
        self.assertEqual(profiles['bijux-iac']['standard_capabilities'],['common','gitlab'])
        rendered=json.loads((ROOT/'.github/standards/repo-config.manifest.json').read_text())
        self.assertEqual(next(row for row in rendered['repositories'] if row['name']=='bijux-iac'),profiles['bijux-iac'])

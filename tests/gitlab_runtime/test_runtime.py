from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / 'shared/bijux-gitlab/runtime'
BUILDER = 'moby/buildkit@sha256:ef70e34495a1730a7c8e20e98fedd9fab328efd6ecfb37365ac464aa0627eb58'
BASE = 'mcr.microsoft.com/playwright@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d'


class RuntimeBuildTests(unittest.TestCase):
    def config(self):
        path = ROOT / 'shared/bijux-gitlab/ci/runtime.yml'
        self.assertTrue(path.is_file(),'the native runtime builder must have a source-owned pipeline')
        return json.loads(path.read_text())

    def test_pipeline_pins_rootless_builder_and_only_runs_fixed_canonical_branch(self):
        config=self.config()
        guard=config['workflow']['rules'][0]['if']
        for value in ('88948041','bijux-oss/bijux-std','ci/gitlab-runtime','push','web'):
            self.assertIn(value,guard)
        self.assertEqual(config['workflow']['rules'][-1],{'when':'never'})
        job=config['ci / runtime build']
        self.assertEqual(job['image'],{'name':BUILDER,'entrypoint':['']})
        self.assertNotIn('services',job)
        self.assertNotIn('privileged',job)
        self.assertNotIn('before_script',job)
        self.assertEqual(job['script'],['sh shared/bijux-gitlab/runtime/build.sh'])
        self.assertEqual(job['artifacts']['paths'],['artifacts/runtime-build/receipt.json','artifacts/runtime-build/buildkit.json'])
        self.assertIn('artifacts/runtime-build/auth/**',job['artifacts']['exclude'])

    def test_root_include_keeps_existing_standards_for_other_refs(self):
        # JSON is a YAML subset and keeps provider-specific parsing out of the bootstrap.
        config=json.loads((ROOT/'.gitlab-ci.yml').read_text())
        self.assertEqual(len(config['include']),2)
        runtime,standards=config['include']
        self.assertEqual(runtime['local'],'shared/bijux-gitlab/ci/runtime.yml')
        self.assertEqual(standards['local'],'shared/bijux-gitlab/ci/standards.yml')
        self.assertEqual(runtime['rules'],[{'if':'$CI_COMMIT_BRANCH == "ci/gitlab-runtime" && ($CI_PIPELINE_SOURCE == "push" || $CI_PIPELINE_SOURCE == "web")'}])
        self.assertEqual(standards['rules'],[
            {'if':'$CI_PIPELINE_SOURCE == "merge_request_event"'},
            {'if':'$CI_COMMIT_BRANCH != "ci/gitlab-runtime" || ($CI_PIPELINE_SOURCE != "push" && $CI_PIPELINE_SOURCE != "web")'}])
        self.assertNotIn('CI_COMMIT_REF_NAME',runtime['rules'][0]['if'])

    def test_dockerfile_preserves_exact_base_and_only_installs_current_system_packages(self):
        path=RUNTIME/'Dockerfile'
        self.assertTrue(path.is_file(),'runtime image must use the existing immutable browser base')
        source=path.read_text()
        self.assertEqual(source.splitlines()[0],'FROM '+BASE)
        for package in ('python3','python3-venv','python3-yaml','git','make','curl',
                        'ca-certificates','perl','shellcheck','xz-utils','jq'):
            self.assertIn(package,source)
        for directive in ('COPY','ADD','ARG','ENV'):
            self.assertFalse(any(line.startswith(directive+' ') for line in source.splitlines()))
        self.assertNotIn('pip install',source)
        self.assertNotIn('npm install',source)
        self.assertIn('rm -rf /var/lib/apt/lists/*',source)

    def run_builder(self, *, failure=False, changes=None):
        self.assertTrue((RUNTIME/'build.sh').is_file(),'runtime builder must fail closed before registry access')
        owner=ROOT/'artifacts/tests/gitlab-runtime';owner.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as name:
            root=Path(name)/'checkout'
            subprocess.run(['git','clone','--quiet','--shared','--no-hardlinks',str(ROOT),str(root)],check=True)
            target=root/'shared/bijux-gitlab/runtime';target.mkdir(parents=True,exist_ok=True)
            for filename in ('Dockerfile','build.sh'):
                shutil.copyfile(RUNTIME/filename,target/filename)
            binaries=Path(name)/'bin';binaries.mkdir()
            builder=binaries/'buildctl-daemonless.sh'
            builder.write_text('''#!/bin/sh
set -eu
printf 'retrieving https://registry.example.invalid/blob?signature=inert-signed-url\\n'
test -s "$DOCKER_CONFIG/config.json"
test "$("$FIXTURE_PYTHON" -c 'import os,stat; print(oct(stat.S_IMODE(os.stat(os.environ["DOCKER_CONFIG"]+"/config.json").st_mode))[2:])')" = 600
printf '%s\\n' "$@" > "$CI_PROJECT_DIR/artifacts/runtime-build/argv.log"
if [ "${FIXTURE_FAIL:-}" = 1 ]; then exit 17; fi
while [ "$#" -gt 0 ]; do
  if [ "$1" = --metadata-file ]; then shift; metadata=$1; fi
  shift
done
printf '{"containerimage.digest":"sha256:%s"}\\n' "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" > "$metadata"
''')
            builder.chmod(0o755)
            sha=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
            environment={**os.environ,'PATH':str(binaries)+os.pathsep+os.environ['PATH'],
                'GITLAB_CI':'true','CI_SERVER_URL':'https://gitlab.com','CI_PROJECT_ID':'88948041',
                'CI_PROJECT_PATH':'bijux-oss/bijux-std','CI_PROJECT_DIR':str(root),
                'CI_COMMIT_SHA':sha,'CI_COMMIT_BRANCH':'ci/gitlab-runtime','CI_COMMIT_REF_NAME':'ci/gitlab-runtime',
                'CI_PIPELINE_SOURCE':'push','CI_PIPELINE_ID':'123','CI_JOB_ID':'456',
                'CI_JOB_IMAGE':BUILDER,'CI_REGISTRY':'registry.gitlab.com',
                'CI_REGISTRY_IMAGE':'registry.gitlab.com/bijux-oss/bijux-std',
                'CI_JOB_TOKEN':'inert-native-job-token','CI_DEBUG_TRACE':'false',
                'FIXTURE_FAIL':'1' if failure else '0','FIXTURE_PYTHON':__import__('sys').executable}
            environment.pop('CI_MERGE_REQUEST_IID',None)
            environment.update(changes or {})
            result=subprocess.run(['sh',str(target/'build.sh')],cwd=root,env=environment,text=True,capture_output=True)
            output=root/'artifacts/runtime-build'
            receipt=json.loads((output/'receipt.json').read_text()) if (output/'receipt.json').exists() else None
            arguments=(output/'argv.log').read_text() if (output/'argv.log').exists() else None
            self.assertFalse((output/'auth/config.json').exists(),'ephemeral registry authentication must be removed')
            self.assertNotIn('inert-native-job-token',result.stdout+result.stderr+json.dumps(receipt))
            self.assertNotIn('inert-signed-url',result.stdout+result.stderr)
            return result,receipt,arguments

    def test_success_records_exact_digest_job_tag_and_dockerfile_hash(self):
        result,receipt,arguments=self.run_builder()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(receipt['status'],'built')
        self.assertEqual(receipt['image_digest'],'sha256:'+'a'*64)
        self.assertEqual(receipt['image_tag'],'registry.gitlab.com/bijux-oss/bijux-std/ci-runtime:job-456')
        self.assertIs(receipt['product_release'],False)
        self.assertEqual(len(receipt['dockerfile_sha256']),64)
        self.assertIn('--frontend\ndockerfile.v0',arguments)
        self.assertIn('context=',arguments)
        self.assertIn('runtime',arguments)
        self.assertNotIn('CI_JOB_TOKEN',arguments)

    def test_builder_failure_stays_failed_and_still_removes_authentication(self):
        result,receipt,_=self.run_builder(failure=True)
        self.assertEqual(result.returncode,17)
        self.assertEqual(receipt['status'],'failed')
        self.assertNotIn('image_digest',receipt)

    def test_mirror_mr_wrong_ref_and_registry_are_rejected_before_build(self):
        for change in ({'CI_PROJECT_ID':'1'},{'CI_PROJECT_PATH':'bijux/bijux-std'},
                       {'CI_PIPELINE_SOURCE':'merge_request_event'},{'CI_COMMIT_BRANCH':'main'},
                       {'CI_MERGE_REQUEST_IID':'12'},{'CI_REGISTRY_IMAGE':'registry.example.invalid/other'},
                       {'CI_DEBUG_TRACE':'true'},{'CI_COMMIT_SHA':'b'*40}):
            with self.subTest(change=change):
                result,receipt,arguments=self.run_builder(changes=change)
                self.assertNotEqual(result.returncode,0)
                self.assertIsNone(arguments)
                self.assertIsNone(receipt)

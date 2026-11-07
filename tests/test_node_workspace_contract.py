from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NodeWorkspaceContractTests(unittest.TestCase):
    def test_node_selection_contains_only_common_and_node_owners(self):
        result = subprocess.run(['bash', str(ROOT/'shared/bijux-checks/scripts/resolve-shared-directories.sh'),
                                 '--select', str(ROOT/'shared/bijux-checks/bijux-std-checks.yml'), 'node'],
                                text=True, capture_output=True, check=True)
        self.assertEqual(set(result.stdout.splitlines()), {
            'shared/bijux-makes', 'shared/bijux-makes-node', 'shared/bijux-checks', 'shared/bijux-gh'})

    def test_targets_delegate_without_publication_and_keep_owned_artifacts(self):
        (ROOT/'artifacts/tests').mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts/tests') as directory:
            root=Path(directory)
            (root/'package.json').write_text(json.dumps({'private':True,'workspaces':['packages/*']}))
            (root/'Makefile').write_text('include '+str(ROOT/'shared/bijux-makes-node/workspace.mk')+'\n')
            npm=root/'npm'
            npm.write_text('#!/bin/sh\nprintf "%s|%s|%s|%s\\n" "$*" "$NPM_CONFIG_CACHE" "$NPM_CONFIG_LOGS_DIR" "$TMPDIR" >> "$BIJUX_TEST_OUTPUT"\n')
            npm.chmod(0o755)
            env={k:v for k,v in os.environ.items() if k not in {'TMPDIR','NPM_CONFIG_CACHE','NPM_CONFIG_LOGS_DIR'}}
            env['BIJUX_TEST_OUTPUT']=str(root/'commands.txt')
            command=['make','NPM='+str(npm),'node-install','node-build','node-test','node-check']
            result=subprocess.run(command,cwd=root,env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            rows=[line.split('|') for line in (root/'commands.txt').read_text().splitlines()]
            self.assertEqual([r[0] for r in rows],['ci','run build','test','run check:workspace','run check:types'])
            for row in rows:
                for location in row[1:]: self.assertTrue(Path(location).is_relative_to(root/'artifacts'))
            (root/'package.json').write_text(json.dumps({'private':False,'workspaces':['packages/*']}))
            before=(root/'commands.txt').read_bytes()
            denied=subprocess.run(command,cwd=root,env=env,text=True,capture_output=True)
            self.assertNotEqual(denied.returncode,0)
            self.assertEqual((root/'commands.txt').read_bytes(),before)

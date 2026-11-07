from pathlib import Path
import runpy
import unittest

ROOT=Path(__file__).resolve().parents[1]
POLICY=runpy.run_path(str(ROOT/'.github/scripts/check_workflow_projection.py'))['POLICY']


class NpmPublicationGuardTests(unittest.TestCase):
    def test_real_and_staged_registry_writes_are_publishers(self):
        for command in ['npm publish package.tgz --access public','npm stage publish package.tgz',
                        'pnpm publish','yarn npm publish','python3 .bijux/shared/bijux-gh/scripts/npm_release.py publish','npm publish --dry-run; npm publish',
                        'npm publish --dry-run && cargo publish','echo --dry-run; npm publish']:
            with self.subTest(command=command):
                self.assertTrue(POLICY.publication.external_publisher({'steps':[{'run':command}]}))
                with self.assertRaisesRegex(ValueError,'renamed publisher'):
                    POLICY.validate_publication_calls({'renamed.yml':{'jobs':{'write':{'steps':[{'run':command}]}}}},
                                                      {'publication_entrypoints':{}})

    def test_read_only_package_preparation_is_allowed(self):
        for command in ['npm ci','npm pack --ignore-scripts','npm publish package.tgz --dry-run',
                        'npm run build','npm view @bijux/example@0.1.0 dist.integrity --json']:
            with self.subTest(command=command):
                self.assertFalse(POLICY.publication.external_publisher({'steps':[{'run':command}]}))

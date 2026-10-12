"""Catalogue receipt identities agree with independent physical tree admission."""
from pathlib import Path
import importlib.util
import tempfile
import types
import unittest

REPO = Path(__file__).resolve().parents[3]
SHARED = REPO / 'shared/bijux-docs'
OUTPUT = REPO / 'artifacts/catalogue-input-identity-tests'
OUTPUT.mkdir(parents=True, exist_ok=True)


def load(name):
    path = SHARED / 'security' / (name + '.py')
    spec = importlib.util.spec_from_file_location('bijux_input_test_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InputIdentity(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.recipe = load('catalogue_recipe')
        self.identity = load('build_identity')
        self.context = object.__new__(self.recipe.CatalogueDerivation)
        self.context.root, self.context.shared = self.root, SHARED
        self.context.inputs = {'docs/assets/navigation.js': b'prefix-file\n',
                               'docs/assets/navigation/module.js': b'prefix-directory\n',
                               'docs/capstone-docs/index.md': b'dashed-prefix\n',
                               'docs/capstone/index.md': b'directory-prefix\n'}
        for name, content in self.context.inputs.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        configuration = types.SimpleNamespace(content=b'site_name: input identity\n')
        self.context.plan = types.SimpleNamespace(configuration=configuration, documents=[])
        path = self.root / self.recipe.CONFIGURATION
        path.parent.mkdir(parents=True)
        path.write_bytes(configuration.content)
        self.config = types.SimpleNamespace(docs_dir=str(self.root / 'docs'), theme={})

    def test_prefix_siblings_use_independent_tree_identity(self):
        record, = self.context.input_records(self.config)
        self.assertEqual(record, {'path': 'docs',
                                  'sha256': self.identity.tree_identity(self.root / 'docs')})
        string_order = [{'path': name.removeprefix('docs/'), 'sha256': self.recipe.digest(data)}
                        for name, data in sorted(self.context.inputs.items())]
        self.assertNotEqual(record['sha256'], self.recipe.json_digest({'files': string_order}))

    def test_changed_document_bytes_refuse_before_identity(self):
        (self.root / 'docs/assets/navigation/module.js').write_bytes(b'changed\n')
        with self.assertRaisesRegex(ValueError, 'changed, missing or extra bytes'):
            self.context.input_records(self.config)

    def test_missing_document_refuses_before_identity(self):
        (self.root / 'docs/capstone/index.md').unlink()
        with self.assertRaisesRegex(ValueError, 'changed, missing or extra bytes'):
            self.context.input_records(self.config)

    def test_unowned_document_refuses_before_identity(self):
        (self.root / 'docs/unowned.md').write_bytes(b'unowned\n')
        with self.assertRaisesRegex(ValueError, 'changed, missing or extra bytes'):
            self.context.input_records(self.config)

    def test_custom_theme_has_same_identity(self):
        path = self.root / 'theme/navigation/module.html'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'custom-template\n')
        self.context.inputs['theme/navigation/module.html'] = path.read_bytes()
        self.config.theme['custom_dir'] = str(self.root / 'theme')
        record = self.context.input_records(self.config)[1]
        self.assertEqual(record, {'path': 'theme',
                                  'sha256': self.identity.tree_identity(self.root / 'theme')})

    def test_changed_custom_theme_refuses_before_identity(self):
        path = self.root / 'theme/navigation.html'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'changed-template\n')
        self.context.inputs['theme/navigation.html'] = b'original-template\n'
        self.config.theme['custom_dir'] = str(self.root / 'theme')
        with self.assertRaisesRegex(ValueError, 'custom renderer input differs'):
            self.context.input_records(self.config)


if __name__ == '__main__':
    unittest.main(verbosity=2)

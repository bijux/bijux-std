"""Bind typed catalogue renderer events to exact captured source and runtime usage."""
from pathlib import Path
import importlib.util
import tempfile
import types
import unittest

from fixture_source import create_fixture

HERE = Path(__file__).resolve()
REPO = next(parent for parent in HERE.parents
            if (parent / 'shared/bijux-docs/security/catalogue_recipe.py').is_file())
OUTPUT = REPO / 'artifacts/catalogue-renderer-tests'
OUTPUT.mkdir(parents=True, exist_ok=True)


def load(path):
    spec = importlib.util.spec_from_file_location('bijux_catalogue_test_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RendererAuthority(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=OUTPUT)
        self.addCleanup(directory.cleanup)
        self.root = create_fixture(REPO, Path(directory.name) / 'source')
        self.shared = self.root / '.bijux/shared/bijux-docs'
        self.recipe = load(self.shared / 'security/catalogue_recipe.py')
        self.context = self.recipe.derive(self.root, self.shared, self.recipe.RECIPE)
        self.configuration = self.context.configuration(self.root / 'artifacts/site')
        self.capabilities = load(self.shared / 'security/producer_capabilities.py')

    def test_actual_registered_source_owned_callbacks(self):
        result = self.capabilities.preflight(self.configuration, self.root, catalogue=self.context)
        callbacks = [record for record in result['callbacks']
                     if record['class'] == 'reviewed-standard-catalogue']
        self.assertEqual([record['event'] for record in callbacks], ['files', 'page_read_source'])
        self.assertTrue(all(record['source'] == 'security/catalogue_sources.py' for record in callbacks))
        self.assertEqual(result['revision']['source_config']['fallback_to_build_date'], True)
        self.assertFalse(result['revision']['publication_history_verified'])

    def test_foreign_plugin_instance_cannot_use_owned_name(self):
        self.configuration.plugins['bijux/catalogue-sources'] = self.context.helper.CatalogueSourcePlugin(self.context.sources)
        with self.assertRaisesRegex(ValueError, 'exact producer-owned'):
            self.capabilities.preflight(self.configuration, self.root, catalogue=self.context)

    def test_foreign_registered_callback_cannot_use_owned_source(self):
        clone = self.context.helper.CatalogueSourcePlugin(self.context.sources)
        self.configuration.plugins.events['page_read_source'] = [clone.on_page_read_source]
        with self.assertRaises(ValueError):
            self.capabilities.callback_records(self.configuration, self.root, self.context)

    def test_changed_registered_code_cannot_use_owned_filename(self):
        namespace = {}
        code = compile('def forged(self, page, config):\n    return "forged"\n',
                       self.context.helper.__file__, 'exec')
        exec(code, namespace)
        self.configuration.plugins.events['page_read_source'] = [
            types.MethodType(namespace['forged'], self.context.plugin)]
        with self.assertRaises(ValueError):
            self.capabilities.callback_records(self.configuration, self.root, self.context)

    def test_changed_helper_source_cannot_certify_loaded_callbacks(self):
        path = Path(self.context.helper.__file__)
        path.write_text(path.read_text().replace('return self.sources.read(page)', 'return "forged"'))
        with self.assertRaises(ValueError):
            self.capabilities.callback_records(self.configuration, self.root, self.context)

    def test_native_publication_history_uses_each_original(self):
        result = self.capabilities.revision_history(self.configuration, self.root,
                                                    publication=True, catalogue=self.context)
        self.assertTrue(result['publication_history_verified'])
        self.assertTrue(result['fallback_preserved'])

    def test_unknown_effective_owner_selection_rejected(self):
        context = self.context
        context.plan.configuration  # Explicitly source-derived; no arbitrary config dispatch.
        (self.root / 'artifacts/mkdocs.root.yml').write_text('site_name: wrong owner\n')
        with self.assertRaisesRegex(ValueError, 'configuration differs'):
            context.configuration(self.root / 'artifacts/site')


if __name__ == '__main__':
    unittest.main(verbosity=2)

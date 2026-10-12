"""Bind typed catalogue renderer events to exact captured source and runtime usage."""
from pathlib import Path
import importlib.util
import re
import subprocess
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

    def test_native_source_actions_retain_originals_body_routes_and_history(self):
        from mkdocs.commands.build import build
        from mkdocs.structure.files import Files
        from mkdocs.structure.pages import Page

        self.assertEqual(self.configuration.edit_uri, 'edit/main/')
        files = self.context.sources.files(Files([]), self.configuration)
        before = {}
        revision = self.configuration.plugins['git-revision-date-localized']
        revision.on_config(self.configuration)
        for document in self.context.sources.documents:
            page = Page(None, files.get_file_from_path(document.route), self.configuration)
            page.read_source(self.configuration)
            before[document.route] = (page.url, page.markdown, revision._get_commit(page, False))
            self.assertEqual(page.edit_url,
                             'https://github.com/bijux/bijux-masterclass/edit/main/' + document.source)
            subprocess.run(['git', '-C', str(self.root), 'cat-file', '-e',
                            'HEAD:' + document.source], check=True, capture_output=True)
        build(self.configuration)
        rendered = {}
        for document in self.context.sources.documents:
            page = Page(None, files.get_file_from_path(document.route), self.configuration)
            page.read_source(self.configuration)
            self.assertEqual((page.url, page.markdown, revision._get_commit(page, False)),
                             before[document.route])
            html = (Path(self.configuration.site_dir) / page.file.dest_uri).read_text()
            rendered[document.route] = html
            self.assertIn('href="' + page.edit_url + '"', html)
            self.assertIn('href="' + page.edit_url.replace('/edit/', '/raw/') + '"', html)
            self.assertNotIn('/main/docs/programs/', html)
            self.assertEqual(page.file.content_bytes, self.context.inputs[document.source])
            (OUTPUT / ('source-actions-' + document.route.replace('/', '-').replace('.md', '.html'))).write_text(html)
        # Reproduce the original docs-root action prefix with the same native
        # inputs. The action URLs are the only rendered bytes allowed to change.
        self.configuration.edit_uri = 'edit/main/docs/'
        build(self.configuration)
        for document in self.context.sources.documents:
            page = Page(None, files.get_file_from_path(document.route), self.configuration)
            original = (Path(self.configuration.site_dir) / page.file.dest_uri).read_text()
            normalized = original
            for action in ('edit', 'raw'):
                prefix = 'https://github.com/bijux/bijux-masterclass/' + action + '/main/'
                self.assertIn(prefix + 'docs/' + document.source, original)
                normalized = normalized.replace(prefix + 'docs/' + document.source,
                                                prefix + document.source)
            self.assertEqual(normalized, rendered[document.route])
            (OUTPUT / ('original-prefix-' + document.route.replace('/', '-').replace('.md', '.html'))).write_text(original)

    def test_supplied_source_action_repository_prefix_and_template_are_refused(self):
        from mkdocs.exceptions import Abort

        owner = self.root / 'mkdocs.yml'
        original = owner.read_bytes()
        for changes in ({'repo_url': 'https://github.com/bijux/other'},
                        {'edit_uri': 'edit/release/docs/'}, {'edit_uri': 'edit/main/'},
                        {'edit_uri': ''},
                        {'edit_uri_template': 'edit/main/{path}'}):
            with self.subTest(changes=changes):
                # The owner has an ENV-tagged URL; preserve that authored input.
                text = original.decode()
                for name, value in changes.items():
                    text = re.sub(r'^' + name + r':.*\n', '', text, flags=re.MULTILINE)
                    text += name + ': ' + repr(value) + '\n'
                owner.write_text(text)
                subprocess.run(['git', '-C', str(self.root), 'add', 'mkdocs.yml'], check=True)
                subprocess.run(['git', '-C', str(self.root), 'commit', '-qm',
                                'test(docs): bind source action configuration refusal'], check=True)
                captured = self.recipe.shared_module(self.shared / 'security/producer_authority.py').repository_files(self.root)
                originals = {name: data for name, data in captured.items()
                             if name in {self.recipe.OWNER, 'mkdocs.shared.yml', *self.recipe.GENERATOR}
                             or name.startswith('programs/') and (name.endswith('.md') or name.endswith('/mkdocs.yml'))}
                generator = self.recipe.captured_generator(self.root, originals)
                plan = generator.build_plan(originals, environment={})
                for name, data in plan.output_bytes().items():
                    (self.root / name).write_bytes(data)
                context = self.recipe.derive(self.root, self.shared, self.recipe.RECIPE)
                # Native strict configuration can reject a conflicting template
                # before the recipe checks the supported source-action convention.
                with self.assertRaisesRegex((ValueError, Abort),
                                            'catalogue source actions require|configuration warnings'):
                    context.configuration(self.root / 'artifacts/refused-site')

    def test_ordinary_docs_keep_their_configured_docs_edit_prefix(self):
        import io
        from mkdocs.config import load_config
        from mkdocs.structure.files import File
        from mkdocs.structure.pages import Page

        original = self.root / 'docs/ordinary.md'
        original.write_text('# Ordinary authored documentation\n')
        subprocess.run(['git', '-C', str(self.root), 'add', 'docs/ordinary.md'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'commit', '-qm',
                        'test(docs): author ordinary docs source control'], check=True)
        configuration = load_config(config_file=io.BytesIO((
            'site_name: Ordinary docs\n'
            'repo_url: https://github.com/bijux/bijux-masterclass\n'
            'edit_uri: edit/main/docs/\n'
            f'docs_dir: {self.root}/docs\nsite_dir: {self.root}/artifacts/ordinary-site\n'
        ).encode()))
        page = Page(None, File('ordinary.md', configuration.docs_dir,
                               configuration.site_dir, True), configuration)
        self.assertEqual(configuration.edit_uri, 'edit/main/docs/')
        self.assertEqual(page.edit_url,
                         'https://github.com/bijux/bijux-masterclass/edit/main/docs/ordinary.md')
        self.assertNotIn('bijux/catalogue-sources', configuration.plugins)


if __name__ == '__main__':
    unittest.main(verbosity=2)

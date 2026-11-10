"""Exercise live native authority reuse without executing a native renderer."""
from __future__ import annotations

from contextlib import ExitStack
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / 'shared/bijux-docs'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


producer = load('native_admission_producer', SHARED / 'security/producer_authority.py')
builder = load('native_admission_builder', SHARED / 'tooling/security/publication_builder.py')
renderer = load('native_admission_renderer', SHARED / 'security/render_publication.py')


class LiveProducerTests(unittest.TestCase):
    def setUp(self):
        owner = ROOT / 'artifacts/native-publication-admission/tests'
        owner.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=owner)
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name) / 'consumer'
        self.root.mkdir()
        (self.root / '.gitignore').write_text('artifacts/\n')
        (self.root / 'mkdocs.yml').write_text('site_name: Controlled\n')
        (self.root / 'article.md').write_text('Owned article\n')
        (self.root / 'callback.py').write_text('OWNED = True\n')
        for args in (('init', '-q'), ('add', '.gitignore', 'mkdocs.yml', 'article.md', 'callback.py'),
                     ('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture source')):
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)
        self.source = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()
        self.shared = Path(scratch.name) / 'standard'
        (self.shared / 'security').mkdir(parents=True)
        (self.shared / 'security/renderer-producer-admission.json').write_text('{}')
        self.runtime = Path(scratch.name) / 'runtime'
        self.runtime.write_text('owned installed bytes')
        self.site = self.root / 'artifacts/docs/site'
        self.reference = self.root / 'artifacts/native-reference'
        worker = 'assets/worker.js'
        html = '<html><script src="assets/worker.js"></script><script id="__config" type="application/json">' + json.dumps({'base': '.', 'search': worker}) + '</script></html>'
        for folder in (self.site, self.reference):
            (folder / 'assets').mkdir(parents=True)
            (folder / worker).write_text('owned worker')
            (folder / 'search').mkdir()
            (folder / 'search/search_index.json').write_text('{"docs":[]}')
            (folder / 'index.html').write_text(html)
        self.capabilities = {'hooks': [{'source': 'callback.py', 'source_sha256': producer.digest((self.root / 'callback.py').read_bytes()), 'inputs': []}]}
        self.current_capabilities = copy.deepcopy(self.capabilities)
        self.configuration = SimpleNamespace(site_url='https://bijux.io/bijux-fixture/')
        self.epoch = {'source_sha': self.source}
        self.checkpoint = {'config': {'path': 'mkdocs.yml'}, 'repository_source': {'sha': self.source},
                           'render_epoch': self.epoch, 'site_url': self.configuration.site_url}
        self.build = {'config': self.checkpoint['config'], 'render_epoch': self.epoch,
                      'renderer': {'fixture': 'actual controlled dependencies'}, 'resolved_config_sha256': 'c' * 64}
        self.resolved_config = 'c' * 64
        self.owner_selection = None
        self.identity = SimpleNamespace(verify_source=lambda *a: None,
            render_epoch_matches=lambda a, b: a == b, source_render_epoch=lambda *a: self.epoch,
            renderer=lambda *a: self.build['renderer'], configuration_identity=lambda *a: self.resolved_config)
        self.modules = {
            'build_identity.py': self.identity,
            'csp.py': SimpleNamespace(embedded_module=lambda: SimpleNamespace(__package__='controlled_admission')),
            'producer_capabilities.py': SimpleNamespace(preflight=lambda *a, **kw: self.current_capabilities, verify_outputs=lambda *a: None),
            'publication.py': SimpleNamespace(qualified_redirects=lambda *a: {}),
            'script_authority.py': SimpleNamespace(verify_ordinary=lambda *a, **kw: {}),
        }
        runtime_bytes = self.runtime.read_bytes()
        def unchanged(*a, **kw):
            producer.require(self.runtime.read_bytes() == runtime_bytes, 'controlled installed runtime changed')
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(producer, 'module', side_effect=lambda path: self.modules[path.name]))
        self.stack.enter_context(patch.object(producer, 'profiles', return_value=SimpleNamespace(unchanged=unchanged)))
        self.stack.enter_context(patch('mkdocs.config.load_config', return_value=self.configuration))
        interactive = ModuleType('controlled_admission.interactive_rendering')
        interactive.configured_owner = lambda config: self.owner_selection
        self.stack.enter_context(patch.dict(sys.modules, {interactive.__name__: interactive}))
        self.prepared = self.make_prepared()

    def make_prepared(self):
        value = producer.PreparedProducer(self.root, 'mkdocs.yml', self.shared, self.shared, self.reference,
            producer.files(self.root, source=True, publication_source=True), producer.files(self.shared, source=True),
            producer.files(self.reference), {'worker': 'assets/worker.js'}, {}, 'c' * 64, copy.deepcopy(self.capabilities), {}, True)
        value.selected_site = self.site
        value.reader_source = None
        value.source_recipe = None
        value.derivation = None
        value.source_sha = self.source
        return value

    def verify(self, value):
        return producer.verify_publication(self.root, self.site, self.shared, self.build, {}, self.checkpoint, prepared=value)

    def test_live_and_default_reconstruction_produce_the_same_complete_authority(self):
        with patch.object(producer, 'prepare', side_effect=lambda *a, **kw: self.make_prepared()) as prepare:
            original = self.verify(None)
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual(self.verify(self.prepared), original)
            self.assertEqual(prepare.call_count, 1)
        self.assertFalse(original['verification_only'])

    def test_source_config_standard_runtime_callback_reference_and_site_drift_refuse(self):
        cases = {
            'source': (self.root / 'article.md', 'changed source'),
            'config': (self.root / 'mkdocs.yml', 'changed configuration'),
            'standard': (self.shared / 'security/renderer-producer-admission.json', 'changed standard'),
            'runtime': (self.runtime, 'changed installed bytes'),
            'reference': (self.reference / 'index.html', 'changed reference'),
            'site': (self.site / 'index.html', 'changed served body'),
        }
        for name, (path, changed) in cases.items():
            original = path.read_bytes()
            with self.subTest(name=name):
                path.write_text(changed)
                try:
                    with self.assertRaises(ValueError):
                        self.verify(self.prepared)
                finally:
                    path.write_bytes(original)
        self.current_capabilities['unexpected_callback'] = True
        with self.assertRaisesRegex(ValueError, 'callback/source/history changed'):
            self.verify(self.prepared)

    def test_same_class_object_cannot_answer_for_another_requested_context(self):
        for root, site in ((self.root.parent, self.site), (self.root, self.reference)):
            with self.subTest(root=root, site=site), self.assertRaisesRegex(ValueError, 'another publication context'):
                producer.verify_publication(root, site, self.shared, self.build, {}, self.checkpoint, prepared=self.prepared)
        self.resolved_config = 'd' * 64
        with self.assertRaisesRegex(ValueError, 'current resolved config'):
            self.verify(self.prepared)
        self.resolved_config = 'c' * 64
        self.owner_selection = 'requested-owner.json'
        self.prepared.reader_source = SimpleNamespace(repository=self.root, descriptor_name='previous-owner.json')
        with self.assertRaisesRegex(ValueError, 'another report descriptor'):
            self.verify(self.prepared)

    def test_serialized_foreign_and_wrong_publication_contexts_refuse(self):
        foreign = load('foreign_producer_class', SHARED / 'security/producer_authority.py')
        alien = foreign.PreparedProducer.__new__(foreign.PreparedProducer)
        for value in ({'status': 'passed'}, object(), alien):
            with self.subTest(value=type(value).__name__), self.assertRaisesRegex(ValueError, 'original live'):
                self.verify(value)
        incomplete = producer.PreparedProducer.__new__(producer.PreparedProducer)
        with self.assertRaisesRegex(ValueError, 'another publication context'):
            self.verify(incomplete)
        changes = {'root': self.root.parent, 'shared': self.root.parent, 'selected_site': self.reference,
                   'config': 'another.yml', 'source_sha': '0' * 40, 'publication_scope': False}
        for key, value in changes.items():
            original = getattr(self.prepared, key)
            with self.subTest(context=key):
                setattr(self.prepared, key, value)
                try:
                    with self.assertRaisesRegex(ValueError, 'another publication context'):
                        self.verify(self.prepared)
                finally:
                    setattr(self.prepared, key, original)


class ComposedEntrypointTests(unittest.TestCase):
    def test_build_cli_selects_the_existing_renderer_and_live_admission(self):
        options = SimpleNamespace(config='mkdocs.yml', site_dir='artifacts/docs/site', site_url='https://bijux.io/bijux-fixture/',
            source_recipe=None, reader_owner=None, interactive_report_owner='owned/report.json', policy='artifacts/policy.json')
        command = builder.arguments('build', options, 'a' * 40)
        self.assertEqual(command[:3], [str(SHARED / 'security/render_publication.py'), '--config', 'mkdocs.yml'])
        self.assertIn('--admit', command)
        self.assertEqual(command[-2:], ['--policy', options.policy])
        self.assertNotIn('--bytes-only', command)
        self.assertIn('owned/report.json', command)
        standalone = builder.arguments('verify', SimpleNamespace(), 'a' * 40)
        self.assertEqual(standalone[-1], '--require-qualified')

    def test_admission_requires_a_real_qualified_build_before_optional_renderer_imports(self):
        with self.assertRaisesRegex(ValueError, 'qualified source'):
            renderer.build_artifact(ROOT, 'mkdocs.yml', 'artifacts/docs/site', admission_policy=SHARED / 'security/policy.json')


class ComposedManifestTests(unittest.TestCase):
    """Use the existing receipt fixture; the native renderer itself is not qualified here."""
    def setUp(self):
        self.base = load('native_admission_receipt_fixture', ROOT / 'tests/test_docs_publication_security.py')
        self.fixture = self.base.QualifiedPublicationTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def compose(self, reject_policy=False):
        f = self.fixture
        f.paths['build'] = 'artifacts/website-security/build-identity.json'
        f.paths['verification'] = 'artifacts/website-security/site-verification.json'
        f.write_records()
        shared = f.root / '.bijux/shared/bijux-docs'
        module = self.base.publication.producer_module(shared)
        original_verifier = module.verify_publication
        observed = []
        def prepare(*args, **kwargs):
            reference = args[4]
            reference.mkdir()
            value = SimpleNamespace(reader_source=None, output=reference)
            observed.append(value)
            return value
        module.prepare = Mock(side_effect=prepare)
        module.render = Mock()
        module.report_source = Mock()
        module.verify = Mock(return_value=original_verifier(None, None, None, None, None, None))
        def admit(*args, prepared=None):
            self.assertIs(prepared, observed[0])
            self.assertTrue(prepared.output.is_dir())
            return original_verifier(*args)
        module.verify_publication = Mock(side_effect=admit)
        policy_calls = []
        def policy():
            self.assertEqual(module.render.call_count, 1)
            policy_calls.append('owning finite policy')
            if reject_policy:
                raise ValueError('controlled finite download policy refused')
            return shared / 'security/policy.json'
        modules = {
            'build_identity.py': self.base.identity,
            'publication.py': self.base.publication,
            'producer_authority.py': module,
            'csp.py': SimpleNamespace(apply=lambda *args: copy.deepcopy(f.records['csp'])),
            'redirects.py': SimpleNamespace(normalize_redirects=lambda *args, **kwargs: {'policy_inputs': f.records['csp']['policy_inputs']['redirects']}),
        }
        configuration = SimpleNamespace(site_url=f.url, strict=True)
        calls = []
        def external(argv, **kwargs):
            calls.append((argv, kwargs))
            (f.root / f.paths['verification']).write_text(json.dumps(f.records['verification'], indent=2) + '\n')
            if argv[0] == 'bash':
                self.assertEqual(kwargs['env']['DOCS_SOURCE_IDENTITY'], f.paths['source'])
                self.assertNotIn('BIJUX_DOCS_READER_OWNER', kwargs['env'])
                self.assertNotIn('BIJUX_DOCS_INTERACTIVE_REPORT_OWNER', kwargs['env'])
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(renderer, '__file__', str(shared / 'security/render_publication.py')), \
                patch.object(renderer, 'load', side_effect=lambda name, path: modules[path.name]), \
                patch.object(self.base.identity, 'begin', return_value=copy.deepcopy(f.records['build'])), \
                patch.object(self.base.identity, 'finish', side_effect=lambda root, value: value), \
                patch('mkdocs.config.load_config', return_value=configuration), \
                patch.object(renderer, 'subprocess', SimpleNamespace(run=external, CalledProcessError=subprocess.CalledProcessError)), \
                patch.dict(renderer.os.environ, {'BIJUX_DOCS_READER_OWNER': 'unselected.json'}):
            renderer.build_artifact(f.root, 'mkdocs.yml', 'artifacts/docs/site', site_url=f.url,
                                    source_identity=f.paths['source'], admission_policy=policy)
        self.assertEqual(module.prepare.call_count, 1)
        self.assertEqual(module.verify_publication.call_count, 1)
        self.assertEqual(len(policy_calls), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn('validate_site_routes.py', calls[0][0][1])
        self.assertEqual(calls[1][0], ['bash', str(shared / 'tooling/scripts/verify_bijux_docs_site.sh')])
        self.assertFalse(observed[0].output.exists())
        module.verify_publication = original_verifier
        return json.loads((f.root / 'artifacts/website-security/publication.json').read_text())

    def test_composed_build_prepares_once_and_preserves_the_entire_qualified_manifest(self):
        composed = self.compose()
        f = self.fixture
        standalone = self.base.publication.qualified_manifest(f.root, 'artifacts/docs/site', f.url, f.source_sha,
            f.policy, f.paths['source'], f.paths['build'], f.paths['verification'], f.paths['csp'])
        self.assertEqual(composed, standalone)

    def test_finite_policy_refusal_cannot_publish_a_composed_manifest(self):
        with self.assertRaisesRegex(ValueError, 'finite download policy refused'):
            self.compose(reject_policy=True)
        self.assertFalse((self.fixture.root / 'artifacts/website-security/publication.json').exists())


    def test_spoofed_canonical_module_cannot_supply_publication_authority(self):
        f = self.fixture
        module = ModuleType('forged_canonical_producer')
        module.__file__ = str(f.root / '.bijux/shared/bijux-docs/security/producer_authority.py')
        module.verify_publication = Mock(return_value={'forged': 'authority'})
        arguments = (f.root, 'artifacts/docs/site', f.url, f.source_sha, f.policy,
                     f.paths['source'], f.paths['build'], f.paths['verification'], f.paths['csp'])
        with self.assertRaisesRegex(TypeError, 'producer_module'):
            self.base.publication.qualified_manifest(*arguments, producer_module=module,
                                                    prepared_producer={'status': 'passed'})
        module.verify_publication.assert_not_called()
        # Without caller-selected code, this serialized object reaches the actual owner,
        # never its transported marker verifier. Real PreparedProducer type checks are above.
        with self.assertRaises(TypeError):
            self.base.publication.qualified_manifest(*arguments, prepared_producer={'status': 'passed'})


class CanonicalModuleTests(unittest.TestCase):
    def test_regular_source_bytes_select_the_module_and_invalidate_old_class_identity(self):
        publication = load('native_admission_module_owner', SHARED / 'security/publication.py')
        owner = ROOT / 'artifacts/native-publication-admission/module-tests'
        owner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=owner) as directory:
            root = Path(directory)
            path = root / 'security/producer_authority.py'
            path.parent.mkdir()
            path.write_text("class PreparedProducer: pass\nOWNER = 'first'\n")
            first = publication.producer_module(root)
            original = first.PreparedProducer()
            self.assertIs(publication.producer_module(root), first)
            path.write_text("class PreparedProducer: pass\nOWNER = 'changed'\n")
            second = publication.producer_module(root)
            self.assertIsNot(second, first)
            self.assertEqual(second.OWNER, 'changed')
            self.assertIsNot(type(original), second.PreparedProducer)
            path.unlink()
            target = root / 'other.py'
            target.write_text("OWNER = 'linked'\n")
            path.symlink_to(target)
            with self.assertRaises(ValueError):
                publication.producer_module(root)

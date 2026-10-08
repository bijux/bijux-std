"""Qualify owned repository navigation against the pinned native Material contract."""
from html.parser import HTMLParser
import importlib.metadata
import json
from pathlib import Path
import unittest

import jinja2
import material

ROOT = Path(__file__).resolve().parents[3]
OWNED = ROOT / 'shared/bijux-docs/partials/source.html'
MATERIAL = Path(material.__file__).resolve().parent / 'templates'


class Anchor(HTMLParser):
    def __init__(self):
        super().__init__(); self.attrs = None; self.parts = []; self.svg = 0
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.attrs = dict(attrs)
        if tag == 'svg': self.svg += 1
    def handle_data(self, data):
        if data.strip(): self.parts.append(data.strip())


class RepositoryFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.metadata.version('mkdocs-material') != '9.7.7':
            raise RuntimeError('Repository facts admission requires reviewed Material9.7.7 source')
        cls.environment = jinja2.Environment(loader=jinja2.FileSystemLoader(str(MATERIAL)))
        cls.owned = cls.environment.from_string(OWNED.read_text())
        cls.native = cls.environment.get_template('partials/source.html')
        source_map = next((MATERIAL / 'assets/javascripts').glob('bundle*.js.map'))
        parsed = json.loads(source_map.read_text())
        cls.source = dict(zip(parsed['sources'], parsed['sourcesContent']))

    def config(self, extra):
        return {'repo_url':'https://github.com/bijux/bijux-core','repo_name':'bijux/bijux-core', 'extra':extra,'theme':{'icon':{'repo':'fontawesome/brands/github'}}}

    def render(self, config, template=None):
        result=(template or self.owned).render(config=config,lang={'t':lambda key:'Go to repository'})
        parsed=Anchor(); parsed.feed(result)
        return result,parsed

    def test_default_preserves_native_destination_name_icon_and_title(self):
        config=self.config({'bijux':{}})
        _,actual=self.render(config)
        _,native=self.render(config,self.native)
        expected={key:value for key,value in native.attrs.items() if key!='data-md-component'}
        expected['aria-label']='Go to repository: bijux/bijux-core'
        self.assertEqual(actual.attrs,expected)
        self.assertEqual(actual.parts,native.parts)
        self.assertEqual(actual.svg,native.svg)
        self.assertGreater(actual.svg,0)

    def test_absent_extra_namespace_is_disabled_without_render_failure(self):
        for extra in [{},{'bijux':{}},None]:
            with self.subTest(extra=extra):
                _,actual=self.render(self.config(extra))
                self.assertNotIn('data-md-component',actual.attrs)
                self.assertEqual(actual.attrs['href'],'https://github.com/bijux/bijux-core')

    def test_only_explicit_boolean_true_activates_native_component(self):
        for value in [False,None,'false','true',0,1,[],{},'yes']:
            with self.subTest(value=value):
                _,actual=self.render(self.config({'bijux':{'repository_facts':value}}))
                self.assertNotIn('data-md-component',actual.attrs)
        _,enabled=self.render(self.config({'bijux':{'repository_facts':True}}))
        self.assertEqual(enabled.attrs['data-md-component'],'source')

    def test_explicit_true_preserves_all_native_navigation_markup(self):
        config=self.config({'bijux':{'repository_facts':True}})
        _,actual=self.render(config)
        _,native=self.render(config,self.native)
        expected={**native.attrs,'aria-label':'Go to repository: bijux/bijux-core'}
        self.assertEqual(actual.attrs,expected)
        self.assertEqual(actual.parts,native.parts)
        self.assertEqual(actual.svg,native.svg)

    def test_authored_repo_icon_and_name_are_preserved(self):
        config=self.config({'bijux':{}})
        config['repo_name']='Bijux scientific reports'
        config['theme']['icon']['repo']='material/git'
        _,actual=self.render(config)
        _,native=self.render(config,self.native)
        self.assertEqual(actual.parts,native.parts)
        self.assertEqual(actual.svg,native.svg)
        self.assertIn('Bijux scientific reports',actual.parts)

    def test_repository_identity_is_named_even_when_header_hides_text(self):
        config=self.config({'bijux':{}})
        config['repo_name']='Bijux scientific reports'
        _,actual=self.render(config)
        self.assertEqual(actual.attrs['aria-label'],'Go to repository: Bijux scientific reports')
        self.assertEqual(actual.attrs['title'],'Go to repository')

    def test_authored_repository_name_cannot_add_anchor_attributes(self):
        config=self.config({'bijux':{}})
        config['repo_name']='Reports" role="button'
        _,actual=self.render(config)
        self.assertEqual(actual.attrs['aria-label'],'Go to repository: Reports" role="button')
        self.assertNotIn('role',actual.attrs)

    def test_exact_native_selector_and_mount_contract_is_present(self):
        selector=self.source['src/templates/assets/javascripts/components/_/index.ts']
        initializer=self.source['src/templates/assets/javascripts/bundle.ts']
        self.assertIn('return getElements(`[data-md-component=${type}]`, node)',selector)
        self.assertIn('...getComponentElements("source")\n    .map(el => mountSource(el))',initializer)
        watcher=self.source['src/templates/assets/javascripts/components/source/_/index.ts']
        self.assertIn('fetchSourceFacts(el.href)',watcher)
        self.assertIn('__md_get<SourceFacts>("__source", sessionStorage)',watcher)
        self.assertIn('__md_set("__source", facts, sessionStorage)',watcher)


if __name__=='__main__':
    unittest.main()

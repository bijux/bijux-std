"""Keep authored navigation occurrence names without mutating shared Page objects."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]


def page(title, source):
    return SimpleNamespace(title=title, file=SimpleNamespace(src_uri=source),
                           children=[], url=source.removesuffix('.md')+'/',
                           active=False, is_page=True, is_link=False)


def section(title, children):
    return SimpleNamespace(title=title, children=children, active=False,
                           is_page=False, is_link=False)


class AuthoredNavigationLabelTests(unittest.TestCase):
    def setUp(self):
        env = Environment(loader=FileSystemLoader(ROOT/'shared/bijux-docs/partials'))
        env.filters['url'] = lambda value: value
        self.template = env.get_template('nav-item.html')

    def render(self, node, authored=None, repeated=True):
        # Retain a semantic before-source witness against the original renderer.
        def leaves(item):
            if item.children:
                return [leaf for child in item.children for leaf in leaves(child)]
            return [item] if item.is_page else []
        pages = leaves(node)
        macro = self.template.make_module({'nav':SimpleNamespace(pages=pages*(2 if repeated else 1))}).render
        args = [node, 'navigation-owned-node', 1]
        if 'authored' in macro.arguments:
            args.append(authored)
        if 'page_occurrences' in macro.arguments:
            counts = {}
            for entry in pages*(2 if repeated else 1):
                counts[entry.file.src_uri] = counts.get(entry.file.src_uri,0)+1
            args.append(counts)
        return str(macro(*args))

    def test_shared_page_retains_each_authored_occurrence_without_title_mutation(self):
        shared = page('Original content title', 'index.md')
        for name in ['Home', 'Overview', 'Reader entry']:
            with self.subTest(name=name):
                self.assertIn(f'>{name}</span>', self.render(shared, {name:'index.md'}))
        self.assertEqual(shared.title, 'Original content title')

    def test_equal_parent_index_keeps_explicit_overview_link(self):
        shared = page('Home', 'index.md')
        html = self.render(section('Parent', [shared]), {'Parent':[{'Overview':'index.md'}]})
        self.assertIn('<summary', html)
        self.assertIn('>Parent</summary>', html)
        self.assertIn('>Overview</span>', html)
        self.assertIn('href="index/"', html)
        self.assertEqual(shared.title, 'Home')

    def test_duplicate_labels_keep_distinct_leaf_destinations(self):
        for source in ['alpha/index.md', 'beta/index.md']:
            with self.subTest(source=source):
                html = self.render(page('Provider title', source), {'Overview':source})
                self.assertIn('>Overview</span>', html)
                self.assertIn('href="'+source.removesuffix('.md')+'/"', html)

    def test_provider_reordered_children_do_not_receive_another_pages_label(self):
        alpha, beta = page('Alpha provider', 'alpha.md'), page('Beta provider', 'beta.md')
        node = section('Parent', [beta, alpha])
        html = self.render(node, {'Parent':[{'Authored alpha':'alpha.md'}, {'Authored beta':'beta.md'}]})
        self.assertIn('>Alpha provider</span>', html)
        self.assertIn('>Beta provider</span>', html)
        self.assertNotIn('>Authored alpha</span>', html)
        self.assertNotIn('>Authored beta</span>', html)

    def test_mismatched_provider_parent_cannot_borrow_authored_child_names(self):
        html = self.render(section('Provider parent',[page('Provider page','alpha.md')]),
                           {'Different parent':[{'Wrong alias':'alpha.md'}]})
        self.assertIn('>Provider page</span>', html)
        self.assertNotIn('Wrong alias', html)

    def test_mapping_children_preserve_authored_overview(self):
        html = self.render(section('Parent',[page('Provider page','alpha.md')]),
                           {'Parent':{'Overview':'alpha.md'}})
        self.assertIn('>Overview</span>', html)

    def test_nested_mixed_tree_keeps_occurrence_names(self):
        node = section('Parent',[page('Provider overview','index.md'),
                                 section('Details',[page('Provider leaf','leaf.md')])])
        authored = {'Parent':[{'Overview':'index.md'},{'Details':[{'Leaf':'leaf.md'}]}]}
        html = self.render(node, authored)
        self.assertIn('>Overview</span>', html)
        self.assertIn('>Details</summary>', html)
        self.assertIn('>Leaf</span>', html)

    def test_automatic_and_malformed_authoring_fall_back_to_provider(self):
        for authored in [None,'index.md',{}, {'A':'index.md','B':'leaf.md'}]:
            with self.subTest(authored=authored):
                self.assertIn('>Provider</span>', self.render(page('Provider','index.md'),authored))

    def test_unmatched_source_does_not_override_name(self):
        html = self.render(page('Provider','index.md'), {'Wrong page':'different.md'})
        self.assertIn('>Provider</span>', html)
        self.assertNotIn('Wrong page', html)

    def test_supported_absolute_source_identity_remains_matched(self):
        self.assertIn('>Overview</span>', self.render(page('Provider','index.md'),{'Overview':'/index.md'}))

    def test_authored_alias_is_text_not_new_markup(self):
        html = self.render(page('Provider','index.md'), {'<Reader & overview>':'index.md'})
        self.assertIn('&lt;Reader &amp; overview&gt;', html)
        self.assertNotIn('<Reader', html)

    def test_single_page_provider_title_is_not_overwritten(self):
        html = self.render(page('Provider page','index.md'),{'Authored name':'index.md'},repeated=False)
        self.assertIn('>Provider page</span>', html)
        self.assertNotIn('Authored name', html)

    def test_provider_link_titles_remain_owned_by_provider(self):
        link = SimpleNamespace(title='Provider link',children=[],active=False,
                               is_page=False,is_link=True,url='https://example.invalid/reader')
        self.assertIn('>Provider link</span>', self.render(link, {'Reader':link.url}))
        self.assertIn('>Provider link</span>', self.render(link, {'Wrong':'https://different.invalid/'}))


if __name__ == '__main__':
    unittest.main()

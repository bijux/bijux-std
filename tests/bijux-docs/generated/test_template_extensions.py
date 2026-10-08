"""Render consumer head extensions through the actual admitted Material templates."""
from __future__ import annotations

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "shared/bijux-docs"
AUTHORED_ROOT = '''{% extends "base.html" %}

{% block extrahead %}
  {{ super() }}
  <link rel="icon" href="{{ 'favicon.ico' | url }}">
  <link rel="apple-touch-icon" href="{{ 'apple-touch-icon.png' | url }}">
  <link rel="apple-touch-icon-precomposed" href="{{ 'apple-touch-icon-precomposed.png' | url }}">
{% endblock %}
'''
HEAD_LINKS = ''.join(re.findall(r'^  <link[^\n]+>\n', AUTHORED_ROOT, re.MULTILINE))
EXTRACTED_ROOT = AUTHORED_ROOT.replace(HEAD_LINKS, '  {% include "partials/site-head.html" %}\n')
CONFIG = '''site_name: Consumer reading fixture
site_url: https://example.invalid/consumer/
docs_dir: docs
strict: true
exclude_docs: /overrides/
theme:
  name: material
  custom_dir: docs/overrides
  font: false
  features: [navigation.instant, search.highlight]
plugins: [search]
extra_javascript:
  - assets/javascripts/consumer-extra.js
  - path: assets/javascripts/consumer-extra.js
    type: module
    defer: true
nav:
  - Reader entry: index.md
  - Detailed document: deep/reading.md
'''


class HtmlTokens(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []

    def handle_starttag(self, tag, attrs):
        self.tokens.append(('open', tag, tuple(sorted(attrs))))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.tokens.append(('close', tag))

    def handle_data(self, data):
        text = ' '.join(data.split())
        if text:
            self.tokens.append(('text', text))


def normalized(html):
    parser = HtmlTokens()
    parser.feed(html)
    return parser.tokens


class TemplateExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = ROOT / 'artifacts/bijux-docs/template-extension-tests'
        parent.mkdir(parents=True, exist_ok=True)
        cls.directory = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls.directory.cleanup)
        cls.scratch = Path(cls.directory.name)
        cls.asset = json.loads((SHARED / 'tooling/material/runtime-provenance.json').read_text())['output_asset']
        cls.native_bundle = json.loads((SHARED / 'tooling/material/admission.json').read_text())['bundle']
        cls.canonical_root = (SHARED / 'partials/main.html').read_text()
        cls.renders = {}
        cls.commands = []
        for name, template, partial in (
            ('native', None, None),
            ('authored', AUTHORED_ROOT, None),
            ('extracted', EXTRACTED_ROOT, HEAD_LINKS),
            ('shared-custom', cls.canonical_root, HEAD_LINKS),
            ('shared-default', cls.canonical_root, None),
            ('shared-empty', cls.canonical_root, ''),
            ('shared-invalid', cls.canonical_root, '{% invalid_template_tag %}'),
        ):
            work = cls.scratch / name
            docs = work / 'docs'
            (docs / 'deep').mkdir(parents=True)
            (docs / 'index.md').write_text('# Reader entry\n\n[Detailed document](deep/reading.md)\n')
            (docs / 'deep/reading.md').write_text('# Detailed document\n\nRead the detailed document.\n')
            overrides = docs / 'overrides'
            overrides.mkdir()
            if template is not None:
                (overrides / 'main.html').write_text(template)
            if partial is not None:
                (overrides / 'partials').mkdir()
                (overrides / 'partials/site-head.html').write_text(partial)
            for icon in ('favicon.ico', 'apple-touch-icon.png', 'apple-touch-icon-precomposed.png'):
                shutil.copy2(SHARED / 'assets/site-icons' / icon, docs / icon)
            target = docs / cls.asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SHARED / cls.asset, target)
            (docs / 'assets/javascripts/consumer-extra.js').write_text('/* Consumer script fixture. */\n')
            (work / 'mkdocs.yml').write_text(CONFIG)
            argv = [sys.executable, '-m', 'mkdocs', 'build', '--strict', '--config-file', str(work / 'mkdocs.yml'), '--site-dir', str(work / 'site')]
            result = subprocess.run(argv, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', XDG_CACHE_HOME=str(cls.scratch / 'cache')), capture_output=True, text=True, timeout=30, check=False)
            cls.commands.append({'name': name, 'exit_code': result.returncode})
            log = parent / (name + '.log')
            log.write_text(result.stdout + result.stderr)
            if name == 'shared-invalid':
                cls.invalid_result = result
                continue
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.renders[name] = {rel: (work / 'site' / rel).read_text() for rel in ('index.html', 'deep/reading/index.html')}
        (parent / 'build-commands.json').write_text(json.dumps(cls.commands, indent=2) + '\n')

    def test_authored_extraction_retains_complete_render_on_root_and_deep_pages(self):
        for rel in self.renders['authored']:
            with self.subTest(page=rel):
                self.assertEqual(normalized(self.renders['authored'][rel]), normalized(self.renders['extracted'][rel]))

    def test_shared_extension_preserves_head_and_layout_replacing_only_admitted_runtime(self):
        for rel, authored in self.renders['authored'].items():
            with self.subTest(page=rel):
                shared = self.renders['shared-custom'][rel]
                self.assertEqual(normalized(authored), normalized(shared.replace(self.asset, self.native_bundle)))
                self.assertEqual(shared.count(self.asset), 1)
                self.assertNotIn(self.native_bundle, shared)
                self.assertEqual(shared.count('consumer-extra.js'), 2)
                links = lambda html: [tag for tag in re.findall(r'<link[^>]+>', html) if 'apple-touch-icon' in tag or re.search(r'href="(?:\.\./)*favicon.ico"', tag)]
                self.assertEqual(links(authored), links(shared))
                self.assertEqual(len(links(shared)), 3)

    def test_absent_or_empty_extension_adds_no_head_or_layout_content(self):
        for rel, native in self.renders['native'].items():
            for fixture in ('shared-default', 'shared-empty'):
                with self.subTest(page=rel, fixture=fixture):
                    self.assertEqual(normalized(native), normalized(self.renders[fixture][rel].replace(self.asset, self.native_bundle)))

    def test_invalid_authored_extension_fails_real_build(self):
        self.assertNotEqual(self.invalid_result.returncode, 0)
        self.assertIn('invalid_template_tag', self.invalid_result.stdout + self.invalid_result.stderr)

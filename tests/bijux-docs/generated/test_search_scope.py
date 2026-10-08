"""Qualify local search names while preserving the pinned native provider interface."""

from html.parser import HTMLParser
import hashlib
import importlib.metadata
from pathlib import Path
from types import SimpleNamespace
import unittest

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
PARTIAL = ROOT / "shared/bijux-docs/partials/search.html"
PROVIDER_SHA = "bfd556535abcddb99396ab2a7e3acc2ebcd3f36756007d3969396caa4126be30"


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.text = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.text.append(text)


class SearchScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = importlib.metadata.distribution("mkdocs-material")
        cls.provider = Path(
            cls.material.locate_file("material/templates/partials/search.html")
        )
        cls.environment = Environment(
            loader=ChoiceLoader(
                [
                    DictLoader(
                        {
                            ".icons/material/magnify.svg": "<svg></svg>",
                            ".icons/material/arrow-left.svg": "<svg></svg>",
                            ".icons/material/close.svg": "<svg></svg>",
                            ".icons/material/share-variant.svg": "<svg></svg>",
                        }
                    ),
                    FileSystemLoader(str(cls.provider.parents[1])),
                ]
            ),
            autoescape=False,
        )
        cls.template = cls.environment.from_string(PARTIAL.read_text())

    def render(self, site_name="Bijux Atlas", features=()):
        return self.template.render(
            config=SimpleNamespace(
                site_name=site_name,
                theme=SimpleNamespace(
                    icon=SimpleNamespace(
                        search=None, previous=None, close=None, share=None
                    )
                ),
            ),
            lang=SimpleNamespace(
                t=lambda key: "Search" if key == "search.placeholder" else key
            ),
            features=features,
        )

    def test_exact_pinned_provider_preimage(self):
        self.assertEqual(self.material.version, "9.7.7")
        self.assertEqual(
            hashlib.sha256(self.provider.read_bytes()).hexdigest(), PROVIDER_SHA
        )

    def test_only_native_presentation_interface_is_changed(self):
        original = self.provider.read_text()
        candidate = PARTIAL.read_text()
        candidate = candidate[candidate.index('<div class="md-search"') :]
        candidate = candidate.replace(
            'aria-label="{{ bijux_search_label | e }}" aria-describedby="bijux-search-scope" placeholder="{{ bijux_search_label | e }}"',
            "aria-label=\"{{ lang.t('search.placeholder') }}\" placeholder=\"{{ lang.t('search.placeholder') }}\"",
        )
        candidate = candidate.replace(
            '        <p class="bijux-search-scope" id="bijux-search-scope">Results from <strong>{{ bijux_search_name | e }}</strong> only.</p>\n',
            "",
        )
        self.assertEqual(
            candidate, original[original.index('<div class="md-search"') :]
        )

    def test_named_scope_and_accessible_description_for_product_sites(self):
        for site_name in [
            "Bijux",
            "Bijux Core",
            "Bijux Canon",
            "Bijux GNSS",
            "Bijux Proteomics",
            "Bijux Pollenomics",
            "Bijux Phylogenetics",
            "Bijux Atlas",
            "Bijux Masterclass",
        ]:
            with self.subTest(site_name=site_name):
                parsed = Elements(self.render(site_name))
                query = next(
                    attrs
                    for tag, attrs in parsed.elements
                    if attrs.get("data-md-component") == "search-query"
                )
                self.assertEqual(query["aria-label"], f"Search {site_name}")
                self.assertEqual(query["placeholder"], f"Search {site_name}")
                self.assertEqual(query["aria-describedby"], "bijux-search-scope")
                self.assertEqual(
                    sum(
                        attrs.get("id") == "bijux-search-scope"
                        for _, attrs in parsed.elements
                    ),
                    1,
                )
                self.assertIn(f"Results from {site_name} only.", "".join(parsed.text))

    def test_site_name_is_escaped_in_attribute_and_visible_content(self):
        site_name = 'Bijux "Field" & <img src=x onerror=alert(1)>'
        parsed = Elements(self.render(site_name))
        query = next(
            attrs
            for _, attrs in parsed.elements
            if attrs.get("data-md-component") == "search-query"
        )
        self.assertEqual(query["aria-label"], f"Search {site_name}")
        self.assertFalse(any(tag == "img" for tag, _ in parsed.elements))
        self.assertFalse(any("onerror" in attrs for _, attrs in parsed.elements))

    def test_scope_paragraph_is_not_native_dynamic_result_metadata(self):
        parsed = Elements(self.render())
        self.assertEqual(
            sum(
                attrs.get("class") == "md-search-result__meta"
                for _, attrs in parsed.elements
            ),
            1,
        )
        self.assertEqual(
            sum(
                attrs.get("data-md-component") == "search-result"
                for _, attrs in parsed.elements
            ),
            1,
        )
        scope = next(
            attrs
            for _, attrs in parsed.elements
            if attrs.get("id") == "bijux-search-scope"
        )
        self.assertNotIn("tabindex", scope)
        self.assertNotIn("role", scope)

    def test_native_optional_suggestion_and_share_interfaces_are_retained(self):
        parsed = Elements(self.render(features=("search.suggest", "search.share")))
        self.assertEqual(
            sum(
                attrs.get("data-md-component") == "search-suggest"
                for _, attrs in parsed.elements
            ),
            1,
        )
        self.assertEqual(
            sum(
                attrs.get("data-md-component") == "search-share"
                for _, attrs in parsed.elements
            ),
            1,
        )
        self.assertEqual(
            sum(
                tag == "button" and attrs.get("type") == "reset"
                for tag, attrs in parsed.elements
            ),
            1,
        )
        self.assertEqual(
            sum(
                tag == "form" and attrs.get("name") == "search"
                for tag, attrs in parsed.elements
            ),
            1,
        )

    def test_scope_does_not_claim_network_search_or_install_a_new_provider(self):
        rendered = self.render()
        self.assertNotIn("<script", rendered)
        self.assertNotIn("hub_links", PARTIAL.read_text())
        self.assertNotIn("all Bijux sites", rendered)
        self.assertIn("Results from <strong>Bijux Atlas</strong> only.", rendered)

    def test_native_license_notice_is_retained(self):
        self.assertIn("Copyright (c) 2016-2025 Martin Donath", PARTIAL.read_text())
        self.assertIn(
            "Permission is hereby granted, free of charge", PARTIAL.read_text()
        )
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', PARTIAL.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)

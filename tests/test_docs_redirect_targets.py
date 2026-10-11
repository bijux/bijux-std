"""Exact MkDocs root representations never broaden the redirect URL boundary."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bijux_redirect_target_controls', ROOT / 'shared/bijux-docs/security/redirects.py')
redirects = importlib.util.module_from_spec(spec)
spec.loader.exec_module(redirects)


class RedirectTargets(unittest.TestCase):
    def test_actual_mkdocs_root_representations_bind_only_root_destination(self):
        for representation in ('./', 'index.html'):
            self.assertEqual(redirects.destination_url(representation, 'index.html'), '')
        self.assertEqual(redirects.destination_url('index.html', 'other/index.html'), 'index.html')
        with self.assertRaises(ValueError): redirects.destination_url('./', 'other/index.html')

    def test_other_urls_keep_the_relative_product_boundary(self):
        for value in ('../', '../index.html', '/index.html', '//other.example/', 'https://other.example/',
                      './target/', 'target/../', '%2e%2e/index.html', 'target?x=1', 'target#x', 'target\\evil'):
            with self.subTest(value=value), self.assertRaises(ValueError): redirects.destination_url(value, 'index.html')
        for value in ('target/', 'science-%CE%BB.html', 'nested/index.html'):
            self.assertEqual(redirects.destination_url(value, 'target/index.html'), value)


if __name__ == '__main__': unittest.main()

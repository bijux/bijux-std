"""Keep actual redirect fixtures on a closed, unchanged MkDocs producer."""
import base64
import hashlib
import importlib.metadata as metadata
from pathlib import Path
import sys
import unittest

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[3]


class RendererFixtureDependencyTests(unittest.TestCase):
    def test_exact_lock_closes_declared_dependencies_on_supported_fixture_platforms(self):
        requirements = [Requirement(line) for line in (ROOT / 'tests/bijux-docs/generated/requirements.lock.txt').read_text().splitlines() if line and not line.startswith('#')]
        pins = {canonicalize_name(item.name): next(iter(item.specifier)).version for item in requirements}
        self.assertEqual(pins['mkdocs-redirects'], '1.2.3')
        self.assertEqual(pins['properdocs'], '1.6.7')
        for python, system in [('3.12', 'Linux'), ('3.14', 'Darwin')]:
            environment = {**default_environment(), 'python_version': python, 'python_full_version': python + '.0', 'platform_system': system, 'sys_platform': 'linux' if system == 'Linux' else 'darwin', 'extra': ''}
            for name, version in pins.items():
                distribution = metadata.distribution(name)
                self.assertEqual(distribution.version, version)
                for declaration in distribution.requires or []:
                    dependency = Requirement(declaration)
                    if dependency.marker and not dependency.marker.evaluate(environment):
                        continue
                    key = canonicalize_name(dependency.name)
                    with self.subTest(platform=system, package=name, dependency=key):
                        self.assertIn(key, pins)
                        self.assertIn(pins[key], dependency.specifier)

    def test_redirect_plugin_retains_mkdocs_namespace_and_executable_ownership(self):
        import mkdocs
        import mkdocs.plugins
        import mkdocs_redirects.plugin
        mkdocs_owner = metadata.distribution('mkdocs')
        properdocs_owner = metadata.distribution('properdocs')
        mkdocs_files = {str(item) for item in mkdocs_owner.files if '..' not in item.parts}
        properdocs_files = {str(item) for item in properdocs_owner.files if '..' not in item.parts}
        self.assertFalse(mkdocs_files & properdocs_files)
        self.assertFalse(any(item.startswith('mkdocs/') for item in properdocs_files))
        self.assertFalse(any(item.group.startswith('mkdocs') or item.name == 'mkdocs' for item in properdocs_owner.entry_points))
        self.assertEqual(Path(mkdocs.__file__).resolve(), Path(mkdocs_owner.locate_file('mkdocs/__init__.py')).resolve())
        self.assertIs(mkdocs_redirects.plugin.RedirectPlugin.__mro__[1], mkdocs.plugins.BasePlugin)
        executable = Path(sys.executable).parent / 'mkdocs'
        self.assertIn('from mkdocs.__main__ import cli', executable.read_text())

    def test_mkdocs_installed_payload_keeps_its_recorded_source_bytes(self):
        checked = 0
        for item in metadata.distribution('mkdocs').files:
            if '..' in item.parts or item.suffix == '.pyc' or item.hash is None:
                continue
            self.assertEqual(item.hash.mode, 'sha256')
            expected = base64.urlsafe_b64decode(item.hash.value + '=' * (-len(item.hash.value) % 4))
            self.assertEqual(hashlib.sha256(Path(metadata.distribution('mkdocs').locate_file(item)).read_bytes()).digest(), expected, str(item))
            checked += 1
        self.assertGreater(checked, 50)


if __name__ == '__main__':
    unittest.main()

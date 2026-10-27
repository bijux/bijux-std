"""Keep executable documentation recipes above reviewed security floors."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'shared/bijux-docs/security/runtime'
FLOORS = {'certifi': (2026, 10, 19), 'gitpython': (3, 2, 1), 'setuptools': (84, 1, 0)}


def pins(path):
    return {re.sub(r'[-_.]+', '-', name).lower(): version for name, version in
            re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)', path.read_text(), re.M)}


class DocumentationDependencySecurity(unittest.TestCase):
    def test_active_verification_and_publication_locks_meet_security_floors(self):
        locks = [ROOT / 'tests/bijux-docs/generated/requirements.lock.txt',
                 ROOT / 'tests/bijux-docs/catalogue/requirements.lock.txt',
                 RUNTIME / 'requirements.lock', RUNTIME / 'requirements-legacy.lock',
                 RUNTIME / 'requirements-media.lock']
        for lock in locks:
            packages = pins(lock)
            self.assertIn('certifi', packages)
            for name, minimum in FLOORS.items():
                if name in packages:
                    with self.subTest(lock=lock.relative_to(ROOT), package=name):
                        self.assertGreaterEqual(tuple(map(int, packages[name].split('.'))), minimum)

    def test_every_admitted_runtime_meets_the_same_security_floors(self):
        table = json.loads((RUNTIME.parent / 'renderer-producer-admission.json').read_text())
        for profile in table['profiles']:
            packages = {re.sub(r'[-_.]+', '-', p['name']).lower(): p['version']
                        for p in profile['environment']['packages']}
            for name, minimum in FLOORS.items():
                if name in packages:
                    with self.subTest(profile=profile['id'], package=name):
                        self.assertGreaterEqual(tuple(map(int, packages[name].split('.'))), minimum)
            if profile['usage'] == 'publication':
                lock = ROOT / 'shared/bijux-docs' / profile['qualification']['dependency_recipe']
                self.assertEqual(packages, pins(lock))

    def test_source_wheel_builder_meets_security_floor_and_matches_its_recipe(self):
        packages = pins(RUNTIME / 'build-requirements.lock')
        recipe = json.loads((RUNTIME / 'source-wheels.json').read_text())
        self.assertEqual(packages, recipe['builder_packages'])
        self.assertGreaterEqual(tuple(map(int, packages['setuptools'].split('.'))), FLOORS['setuptools'])


if __name__ == '__main__':
    unittest.main()

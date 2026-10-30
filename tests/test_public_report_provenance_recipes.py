"""Qualify legacy and data-owned display declarations without trusting callbacks."""
from pathlib import Path
import __future__
import builtins
import hashlib
import importlib.util
import json
import tempfile
import types
import typing
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capability = load('bijux_test_producer_capability', 'shared/bijux-docs/security/producer_capabilities.py')
projection = load('bijux_test_report_projection', 'shared/bijux-docs/security/report_provenance.py')


def forbidden_callback(*args, **kwargs):
    raise AssertionError('Callback return values must not grant independent authority')


class PublicReportDisplayRecipes(unittest.TestCase):
    def setUp(self):
        artifacts = ROOT / 'artifacts/qualification/public-report-provenance-recipes'
        artifacts.mkdir(parents=True, exist_ok=True)
        self.scratch = tempfile.TemporaryDirectory(dir=artifacts)
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    @staticmethod
    def sha(value):
        return hashlib.sha256(value).hexdigest()

    def write_case(self, fields=48, *, data_manifest=True):
        reports = []
        self.originals = {}
        self.expected = {}
        for index, name in enumerate(projection.REPORT_PATHS):
            count = fields - 12 if index == 0 else 1
            self.assertGreater(count, 0)
            values = [(f'path_{field}', f'/tmp/own-receipt-{index}/field-{field}') for field in range(count)]
            raw = ('{"negative_zero":-0.0,"small":1e-310,"precise":1.23456789012345678901234567890,'
                   '"flag":false,"missing":null,'
                   + ','.join(json.dumps(key) + ':' + json.dumps(value) for key, value in values)
                   + '}\n').encode()
            row = {
                'path': name,
                'source_sha256': self.sha(raw),
                'fields': [
                    {'pointer': '/' + key, 'value_sha256': self.sha(value.encode()),
                     'kind': 'artifact-path-display', 'display': f'retained/own-{index}/{key}'}
                    for key, value in values
                ],
            }
            # This golden uses unique invented strings, not either production pointer walker.
            text = raw.decode()
            for (_, value), field in zip(values, row['fields']):
                text = text.replace(json.dumps(value), json.dumps(field['display']))
            note = {'schema': 1, 'source_receipt_sha256': row['source_sha256'],
                    'display_fields': row['fields'], 'display_semantics': projection.SEMANTICS}
            text = text.rstrip()[:-1] + ',\n  "_public_provenance": ' + json.dumps(
                note, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n}\n'
            expected = text.encode()
            row['public_sha256'] = self.sha(expected)
            reports.append(row)
            target = self.root / 'docs' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            self.originals[name] = raw
            self.expected[name] = expected
        self.manifest = {'schema': 1, 'owner': 'bijux-pollenomics', 'reports': reports}
        manifest_bytes = self.write_manifest()
        source_path = self.root / 'configs/docs/report_provenance.py'
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b'# Own callback source fixture; never executed.\n')
        hook = types.ModuleType('own_public_receipt_hook')
        hook.__file__ = str(source_path)
        hook.__builtins__ = dict(vars(builtins))
        from pathlib import PurePosixPath
        from mkdocs.config.defaults import MkDocsConfig
        from mkdocs.structure.files import File, Files
        for name, value in {
            'File': File, 'Files': Files, 'MkDocsConfig': MkDocsConfig,
            'ROOT': self.root, 'MANIFEST': projection.MANIFEST,
            'REPORT_PATHS': projection.REPORT_PATHS, 'NOTE_KEY': projection.NOTE_KEY,
            'INTERNAL_PREFIXES': projection.INTERNAL_PREFIXES, 'Path': Path,
            'PurePosixPath': PurePosixPath, 'annotations': __future__.annotations,
            'hashlib': hashlib, 'json': json,
        }.items():
            setattr(hook, name, value)
        if data_manifest:
            hook.Any = typing.Any
        else:
            hook.MANIFEST_SHA256 = self.sha(manifest_bytes)
        for name in ('_digest', '_nonfinite', '_note', '_pairs', '_project_report',
                     '_read', '_require', '_string_fields', 'on_files', 'projected_reports'):
            setattr(hook, name, forbidden_callback)
        config = types.SimpleNamespace(
            docs_dir=str(self.root / 'docs'),
            repo_url='https://github.com/bijux/bijux-pollenomics',
            site_url='https://bijux.io/bijux-pollenomics/',
        )
        return hook, config, source_path

    def write_manifest(self):
        value = json.dumps(self.manifest, indent=2).encode() + b'\n'
        target = self.root / projection.MANIFEST
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        return value

    def admit(self, case, *, data_manifest=True):
        hook, config, source = case
        return projection.admit(hook, config, self.root, source,
                                source.read_bytes(), capability.regular,
                                data_manifest=data_manifest)

    def test_exact_registered_callback_sources_keep_distinct_recipes(self):
        self.assertEqual(capability.HOOKS['0e3cf71e68b4b3697b1ddd85f9bd9e45e5ec312105fcb1481e884ab6d293b256'],
                         'public-report-provenance')
        self.assertEqual(capability.HOOKS['9e66783e652ad350cb59ac36fedd49b88f06eb0633c43b6ce9e985a4a0b9c5de'],
                         'public-report-provenance-data-manifest')
        source = self.root / 'own-hook.py'
        source.write_bytes(b'def on_files(files, config):\n    return files\n')
        hook = types.ModuleType('unreviewed_own_hook')
        hook.__file__ = str(source)
        with self.assertRaisesRegex(capability.CapabilityError, 'reviewed source recipe'):
            capability.hooks(types.SimpleNamespace(hooks={'own': hook}), self.root)

    def test_data_manifest_48_and_other_valid_populations_preserve_all_numeric_lexemes(self):
        for count in (48, 49):
            with self.subTest(fields=count):
                case = self.write_case(count)
                result = self.admit(case)
                self.assertEqual(result['recipe'], 'public-report-provenance-data-manifest')
                self.assertEqual(len(result['inputs']), 14)
                self.assertEqual(len(result['outputs']), 13)
                for name, raw in self.originals.items():
                    expected = self.expected[name]
                    self.assertEqual(projection.project(raw, next(r for r in self.manifest['reports'] if r['path'] == name)), expected)
                    self.assertIn(b'"negative_zero":-0.0,"small":1e-310,"precise":1.23456789012345678901234567890', expected)
                    self.assertEqual(result['outputs'][name], self.sha(expected))

    def test_legacy_manifest_pin_and_32_field_population_remain_required(self):
        case = self.write_case(32, data_manifest=False)
        with mock.patch.object(projection, 'MANIFEST_SHA256', case[0].MANIFEST_SHA256):
            self.assertEqual(self.admit(case, data_manifest=False)['recipe'], 'public-report-provenance')
            target = self.root / projection.MANIFEST
            target.write_bytes(target.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'reviewed manifest differs'):
                self.admit(case, data_manifest=False)
        case = self.write_case(33, data_manifest=False)
        with mock.patch.object(projection, 'MANIFEST_SHA256', case[0].MANIFEST_SHA256):
            with self.assertRaisesRegex(ValueError, 'finite report population differs'):
                self.admit(case, data_manifest=False)

    def test_data_declarations_still_require_exact_13_path_population(self):
        for fault in ('missing', 'extra', 'reordered'):
            with self.subTest(fault=fault):
                case = self.write_case()
                self.admit(case)
                if fault == 'missing':
                    self.manifest['reports'].pop()
                elif fault == 'extra':
                    self.manifest['reports'].append(dict(self.manifest['reports'][0]))
                else:
                    self.manifest['reports'].reverse()
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, 'finite report population differs'):
                    self.admit(case)

    def test_source_receipt_identity_and_public_numeric_changes_refuse(self):
        for fault in ('source_bytes', 'numeric_projection'):
            with self.subTest(fault=fault):
                case = self.write_case()
                self.admit(case)
                row = self.manifest['reports'][0]
                if fault == 'source_bytes':
                    path = self.root / 'docs' / row['path']
                    path.write_bytes(path.read_bytes().replace(b'-0.0', b'0.0'))
                    expected = 'physical raw receipt differs'
                else:
                    row['public_sha256'] = self.sha(self.expected[row['path']].replace(b'1e-310', b'0.0'))
                    self.write_manifest()
                    expected = 'independent public bytes differ'
                with self.assertRaisesRegex(ValueError, expected):
                    self.admit(case)

    def test_declared_pointer_value_kind_and_portable_display_remain_strict(self):
        for fault in ('pointer', 'duplicate', 'value_hash', 'kind', 'display', 'extra_field'):
            with self.subTest(fault=fault):
                case = self.write_case()
                self.admit(case)
                fields = self.manifest['reports'][0]['fields']
                if fault == 'pointer':
                    fields[0]['pointer'] = '/negative_zero'
                elif fault == 'duplicate':
                    fields.append(dict(fields[0]))
                elif fault == 'value_hash':
                    fields[0]['value_sha256'] = '0' * 64
                elif fault == 'kind':
                    fields[0]['kind'] = 'execution-authority'
                elif fault == 'display':
                    fields[0]['display'] = '../unowned'
                else:
                    fields[0]['unexpected'] = True
                self.write_manifest()
                with self.assertRaises(ValueError):
                    self.admit(case)

    def test_unmapped_private_string_duplicate_and_nonfinite_sources_refuse(self):
        for fault in ('private', 'duplicate', 'nonfinite'):
            with self.subTest(fault=fault):
                case = self.write_case()
                self.admit(case)
                row = self.manifest['reports'][0]
                path = self.root / 'docs' / row['path']
                extra = {'private': ',"unmapped":"/tmp/own-unmapped"',
                         'duplicate': ',"flag":false', 'nonfinite': ',"invalid":NaN'}[fault]
                value = path.read_bytes().rstrip()[:-1] + extra.encode() + b'}\n'
                path.write_bytes(value)
                row['source_sha256'] = self.sha(value)
                self.write_manifest()
                with self.assertRaises(ValueError):
                    self.admit(case)

    def test_loaded_namespace_and_annotation_bindings_are_closed(self):
        for fault in ('extra', 'missing', 'annotation', 'builtin', 'default'):
            with self.subTest(fault=fault):
                case = self.write_case()
                self.admit(case)
                hook = case[0]
                if fault == 'extra':
                    hook.MANIFEST_SHA256 = '0' * 64
                elif fault == 'missing':
                    del hook.Any
                elif fault == 'annotation':
                    hook.Any = object
                elif fault == 'builtin':
                    hook.__builtins__ = {'len': len}
                else:
                    hook._read = lambda value=None: value
                with self.assertRaises(ValueError):
                    self.admit(case)

    def test_legacy_and_data_global_names_cannot_borrow_each_other(self):
        legacy = self.write_case(32, data_manifest=False)
        with self.assertRaisesRegex(ValueError, 'undeclared loaded global'):
            self.admit(legacy, data_manifest=True)
        current = self.write_case(48)
        with self.assertRaisesRegex(ValueError, 'undeclared loaded global'):
            self.admit(current, data_manifest=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)

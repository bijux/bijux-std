"""Qualify owned payload accounting against mismatched and unavailable evidence."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'shared/bijux-docs/tooling/quality'))
from performance import payloads

SHA = 'ab' * 20
VENDOR = 'assets/javascripts/vendor/mermaid-11.17.2.min.js'
SHARED = ROOT / 'shared/bijux-docs'


class OwnedPayloadTests(unittest.TestCase):
    def setUp(self):
        parent = Path(os.environ.get('BIJUX_PAYLOAD_TEST_ARTIFACTS', ROOT / 'artifacts/qualification/payload-accounting/controls'))
        parent.mkdir(parents=True, exist_ok=True)
        self.directory = tempfile.TemporaryDirectory(prefix='owned-payload-', dir=parent)
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name)
        self.site = self.repo / 'artifacts/site'
        self.standard = self.repo / 'standard'
        self.standard.mkdir()
        self.data = {name: (SHARED / name).read_bytes() for name in (
            payloads.PREFERRED_LOGO, payloads.COMPATIBILITY_LOGO, VENDOR,
            'assets/javascripts/vendor/THIRD-PARTY-LICENSES.txt', VENDOR + '.LEGAL.txt',
            'config/mkdocs-baseline.json', 'tooling/diagrams/provenance.json')}
        self.projection = {'schema': 1, 'source': {'mode': 'accepted-github', 'origin': payloads.ORIGIN, 'sha': SHA}, 'files': {}}
        for name in (payloads.PREFERRED_LOGO, payloads.COMPATIBILITY_LOGO, VENDOR,
                     'assets/javascripts/vendor/THIRD-PARTY-LICENSES.txt', VENDOR + '.LEGAL.txt'):
            self.write_owned(name, self.data[name])
        self.write_projection()
        self.git_mock = mock.patch.object(payloads, '_git', side_effect=self.git)
        self.git_mock.start()
        self.addCleanup(self.git_mock.stop)

    def git(self, root, *args):
        self.assertEqual(root, self.standard)
        if args == ('rev-parse', '--show-toplevel'): return str(self.standard).encode()
        if args == ('remote', 'get-url', 'origin'): return payloads.ORIGIN.encode()
        if args == ('rev-parse', SHA + '^{commit}'): return SHA.encode()
        if args == ('rev-parse', SHA + '^{tree}'): return ('4' * 40).encode()
        if args[0] == 'show' and args[1].startswith(SHA + ':shared/bijux-docs/'):
            name = args[1].split(':shared/bijux-docs/', 1)[1]
            if name in self.data: return self.data[name]
        raise ValueError('Controlled committed source unavailable')

    def write_owned(self, name, data):
        for path in (self.repo / 'docs' / name, self.site / name):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.projection['files']['docs/' + name] = {'source': 'bijux-docs/' + name, 'sha256': payloads.fingerprint(data)['sha256']}

    def write_projection(self):
        path = self.repo / '.bijux/docs-projection.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.projection))

    def qualify(self): return payloads.qualify(self.repo, self.site, self.standard, SHA)

    def changed_source(self, name, data):
        self.data[name] = data
        self.write_owned(name, data)
        self.write_projection()

    def test_exact_owned_source_projection_and_served_representations_pass(self):
        report = self.qualify()
        self.assertEqual(report['result'], 'pass')
        self.assertEqual(len(report['payloads']), 5)
        self.assertEqual(report['payloads'][0]['intrinsic_pixels'], [128, 128])
        for item in report['payloads']:
            self.assertEqual(item['source']['sha256'], item['projected']['sha256'])
            self.assertEqual(item['source']['sha256'], item['served']['sha256'])

    def test_static_size_never_certifies_unobserved_network_quantities(self):
        for item in self.qualify()['payloads']:
            quantities = item['quantities']
            self.assertEqual(quantities['raw_file_bytes']['value'], item['served']['bytes'])
            for name in ('decoded_body_bytes', 'encoded_body_bytes', 'transfer_bytes_including_headers'):
                self.assertIsNone(quantities[name]['value'])
                self.assertEqual(quantities[name]['availability'], 'unobserved')
            self.assertEqual(item['cache'], 'unobserved')
            self.assertEqual(item['content_encoding'], 'unobserved')

    def test_measured_zero_is_distinct_from_unknown(self):
        self.assertNotEqual(payloads.byte_quantity(0, 'actual observation'), payloads.byte_quantity(None, 'actual observation'))
        self.assertEqual(payloads.byte_quantity(0, 'actual observation')['availability'], 'observed')

    def test_invalid_byte_values_are_not_coerced(self):
        for value in (False, True, -1, 1.5, '0', [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError): payloads.byte_quantity(value, 'observation')

    def test_changed_served_source_cannot_reuse_matching_projection(self):
        for name in (payloads.PREFERRED_LOGO, payloads.COMPATIBILITY_LOGO, VENDOR):
            path = self.site / name
            original = path.read_bytes()
            path.write_bytes(original + b'changed served representation')
            with self.subTest(asset=name), self.assertRaisesRegex(ValueError, 'Served bytes differ'): self.qualify()
            path.write_bytes(original)

    def test_missing_served_asset_is_not_unknown_or_zero(self):
        path = self.site / VENDOR
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing owned file'): self.qualify()

    def test_retained_license_and_legal_notice_files_must_match_provenance(self):
        name = 'assets/javascripts/vendor/THIRD-PARTY-LICENSES.txt'
        self.changed_source(name, self.data[name] + b'changed license')
        with self.assertRaisesRegex(ValueError, 'license provenance'): self.qualify()

    def test_missing_legal_notice_cannot_qualify_a_matching_vendor(self):
        (self.site / (VENDOR + '.LEGAL.txt')).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing owned file'): self.qualify()

    def test_changed_projected_source_is_rejected_before_served_accounting(self):
        (self.repo / 'docs' / VENDOR).write_bytes(b'changed projection')
        with self.assertRaisesRegex(ValueError, 'Projected bytes differ'): self.qualify()

    def test_missing_projected_asset_refuses_qualification(self):
        (self.repo / 'docs' / payloads.PREFERRED_LOGO).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing owned file'): self.qualify()

    def test_stale_projection_source_cannot_reuse_identical_asset_bytes(self):
        self.projection['source']['sha'] = '5' * 40
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'stale or different'): self.qualify()

    def test_local_or_foreign_projection_cannot_claim_accepted_identity(self):
        original = copy.deepcopy(self.projection['source'])
        for field, value in [('mode', 'local-verification'), ('origin', 'https://example.invalid/bijux-std.git')]:
            self.projection['source'] = {**original, field: value}
            self.write_projection()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'stale or different'): self.qualify()

    def test_boolean_projection_schema_is_not_version_one(self):
        self.projection['schema'] = True
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'stale or different'): self.qualify()

    def test_projection_digest_drift_refuses_even_identical_physical_files(self):
        self.projection['files']['docs/' + VENDOR]['sha256'] = 'a' * 64
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'Projection digest differs'): self.qualify()

    def test_missing_or_duplicate_owned_projection_destination_refuses(self):
        entry = self.projection['files'].pop('docs/' + VENDOR)
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'one owned destination'): self.qualify()
        self.projection['files'].update({'docs/' + VENDOR: entry, 'other/' + VENDOR: entry})
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'one owned destination'): self.qualify()

    def test_duplicate_json_evidence_fields_refuse(self):
        (self.repo / '.bijux/docs-projection.json').write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, 'Duplicate evidence field'): self.qualify()

    def test_projection_traversal_never_reads_foreign_owned_bytes(self):
        entry = self.projection['files'].pop('docs/' + VENDOR)
        self.projection['files']['../' + VENDOR] = entry
        self.write_projection()
        with self.assertRaisesRegex(ValueError, 'inside their root'): self.qualify()

    def test_served_and_projected_symlinks_refuse(self):
        for path in (self.repo / 'docs' / VENDOR, self.site / VENDOR):
            original = path.read_bytes()
            target = self.repo / 'different-vendor.js'
            target.write_bytes(original)
            path.unlink()
            path.symlink_to(target)
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'symlink'): self.qualify()
            path.unlink()
            path.write_bytes(original)

    def test_preferred_logo_at_existing_ceiling_passes(self):
        data = self.data[payloads.PREFERRED_LOGO]
        self.changed_source(payloads.PREFERRED_LOGO, data + bytes(payloads.PREFERRED_LOGO_LIMIT - len(data)))
        self.assertEqual(self.qualify()['payloads'][0]['source']['bytes'], 32768)

    def test_preferred_logo_above_existing_ceiling_refuses_matching_source(self):
        data = self.data[payloads.PREFERRED_LOGO]
        self.changed_source(payloads.PREFERRED_LOGO, data + bytes(payloads.PREFERRED_LOGO_LIMIT + 1 - len(data)))
        with self.assertRaisesRegex(ValueError, '32 KiB'): self.qualify()

    def test_changed_intrinsic_dimensions_refuse_matching_digests(self):
        data = bytearray(self.data[payloads.PREFERRED_LOGO])
        data[16:24] = struct.pack('>II', 64, 64)
        data[29:33] = struct.pack('>I', zlib.crc32(data[12:29]))
        self.changed_source(payloads.PREFERRED_LOGO, bytes(data))
        with self.assertRaisesRegex(ValueError, '128x128'): self.qualify()

    def test_invalid_png_header_refuses_matching_projection(self):
        data = bytearray(self.data[payloads.PREFERRED_LOGO]); data[29] ^= 1
        self.changed_source(payloads.PREFERRED_LOGO, bytes(data))
        with self.assertRaisesRegex(ValueError, 'PNG IHDR'): self.qualify()

    def test_custom_logo_and_icon_fallback_remain_outside_owned_accounting(self):
        (self.repo / 'authored.yml').write_text('theme:\n  logo: assets/custom.svg\n  icon:\n    logo: material/book\n')
        (self.site / 'assets/custom.svg').write_bytes(b'authored custom branding')
        before = (self.repo / 'authored.yml').read_bytes()
        self.assertEqual(self.qualify()['result'], 'pass')
        self.assertEqual((self.repo / 'authored.yml').read_bytes(), before)
        self.assertEqual((self.site / 'assets/custom.svg').read_bytes(), b'authored custom branding')

    def test_stale_vendor_output_provenance_refuses_actual_owned_bytes(self):
        original = json.loads(self.data['tooling/diagrams/provenance.json'])
        for key, value in [('bytes', True), ('bytes', 0), ('sha256', 'f' * 64), ('integrity', 'sha384-stale')]:
            provenance = copy.deepcopy(original)
            next(item for item in provenance['output'] if item['name'] == Path(VENDOR).name)[key] = value
            self.data['tooling/diagrams/provenance.json'] = json.dumps(provenance).encode()
            with self.subTest(field=key, value=value), self.assertRaisesRegex(ValueError, 'provenance|integrity'): self.qualify()

    def test_exact_full_commit_selection_is_required(self):
        for sha in ('main', SHA[:12], SHA.upper(), '', True):
            with self.subTest(sha=sha), self.assertRaisesRegex(ValueError, 'full standard commit'): payloads.source_identity(self.standard, sha)

    def test_foreign_standard_origin_refuses(self):
        original = self.git
        def foreign(root, *args): return b'https://example.invalid/bijux-std.git' if args == ('remote', 'get-url', 'origin') else original(root, *args)
        with mock.patch.object(payloads, '_git', side_effect=foreign), self.assertRaisesRegex(ValueError, 'GitHub origin'): self.qualify()

    def test_selected_commit_must_equal_the_resolved_object(self):
        original = self.git
        def different(root, *args): return ('6' * 40).encode() if args == ('rev-parse', SHA + '^{commit}') else original(root, *args)
        with mock.patch.object(payloads, '_git', side_effect=different), self.assertRaisesRegex(ValueError, 'differs from the exact'): self.qualify()

    def test_site_outside_owning_artifacts_refuses(self):
        outside = self.repo / 'public'; outside.mkdir()
        with self.assertRaisesRegex(ValueError, 'owning artifacts'): payloads.qualify(self.repo, outside, self.standard, SHA)

    def cli(self, output):
        return mock.patch.object(sys, 'argv', ['payloads.py', '--repo-root', str(self.repo), '--site-dir', str(self.site),
                                              '--standard-root', str(self.standard), '--standard-sha', SHA, '--output', str(output)])

    def test_cli_pass_writes_explicit_unknown_network_quantities(self):
        output = self.repo / 'artifacts/report.json'
        with self.cli(output), mock.patch('builtins.print'): self.assertEqual(payloads.main(), 0)
        report = json.loads(output.read_text())
        self.assertEqual(report['result'], 'pass')
        self.assertIsNone(report['payloads'][0]['quantities']['transfer_bytes_including_headers']['value'])

    def test_cli_failure_writes_refusal_without_positive_payload_receipt(self):
        (self.site / VENDOR).write_bytes(b'wrong vendor')
        output = self.repo / 'artifacts/refusal.json'
        with self.cli(output), mock.patch('builtins.print'): self.assertEqual(payloads.main(), 1)
        report = json.loads(output.read_text())
        self.assertEqual(report['result'], 'fail')
        self.assertNotIn('payloads', report)
        self.assertIn('Served bytes differ', report['errors'][0])

    def test_cli_output_cannot_change_served_bundle_or_source(self):
        for output in (self.site / 'report.json', self.repo / 'source.json'):
            with self.subTest(output=output), self.cli(output), mock.patch('sys.stderr'), self.assertRaises(SystemExit) as raised:
                payloads.main()
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()

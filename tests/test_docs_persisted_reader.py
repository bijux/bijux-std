"""Reject missing native cache, forged entry identity and incomplete dedicated evidence."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('persisted_reader', ROOT / 'tests/bijux-docs/execution/persisted_reader.py')
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


def result(project='chromium-reader-narrow'):
    initial = {'href': 'http://127.0.0.1:4173/reader-diagrams/', 'entryKey': 'reader-entry',
               'timeOrigin': 123, 'sources': ['owned graph ' + str(n) for n in range(5)]}
    target = {'href': 'http://127.0.0.1:4173/reader-table/', 'entryKey': 'table-entry', 'timeOrigin': 456, 'sequence': 1}
    departure = {**initial, 'type': 'click', 'sequence': 2, 'trusted': True, 'disclosures': [True, False, False, False, False], 'top': 450}
    runtime = {'commandLine': {'arguments': ['/ms-playwright/chromium/chrome-linux/chrome', '--enable-automation']},
               'version': {'product': 'Chrome/145.0.0.0'}, 'executableSha256': 'a' * 64}
    cycles = [{'label': 'cached native cycle', 'cycle': cycle,
               'back': {**initial, 'type': 'pageshow', 'sequence': 4 + cycle * 2, 'trusted': True, 'persisted': True},
               'shown': {**target, 'type': 'pageshow', 'sequence': 3 + cycle * 2, 'trusted': True, 'persisted': True},
               'returned': {**initial, 'disclosures': departure['disclosures'], 'top': 450.09375},
               'forward': target, 'absoluteOffset': 0.09375} for cycle in range(2)]
    journey = {'departure': departure, 'initial': initial, 'target': target, 'records': cycles, 'external': []}
    return {'project': project, 'case_id': project + '-case', 'status': 'passed', 'retry': 0, 'errors': [],
            'annotations': [{'type': 'browser-version', 'description': '145.0.0.0'},
                            {'type': 'persisted-browser-runtime', 'description': json.dumps(runtime)},
                            {'type': 'persisted-cache-diagnostics', 'description': json.dumps({'rejections': [], 'lifecycle': [
                                {'frameId': 'reader-frame', 'loaderId': loader, 'name': 'load', 'timestamp': timestamp}
                                for loader, timestamp in [('reader-loader', 1), ('table-loader', 2)]]})},
                            {'type': 'persisted-native-journey', 'description': json.dumps(journey)}]}


def changed(name, value, change):
    item = next(annotation for annotation in value['annotations'] if annotation['type'] == name)
    body = json.loads(item['description'])
    change(body)
    item['description'] = json.dumps(body)
    return value


class NativeCacheAuthorityTests(unittest.TestCase):
    def test_missing_browser_load_observations_refuse_the_native_cache_claim(self):
        value = changed('persisted-cache-diagnostics', result(), lambda body: body.update(lifecycle=[]))
        with self.assertRaisesRegex(ValueError, 'Browser load observations'):
            READER.qualify_journey(value)

    def test_missing_diagnostics_refuses_the_native_cache_claim(self):
        value = result()
        value['annotations'] = [item for item in value['annotations'] if item['type'] != 'persisted-cache-diagnostics']
        with self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
            READER.qualify_journey(value)

    def test_browser_cache_rejection_refuses_otherwise_complete_cycles(self):
        value = changed('persisted-cache-diagnostics', result(), lambda body: body['rejections'].append(
            {'notRestoredExplanations': [{'reason': 'IgnoreEventAndEvict'}]}))
        with self.assertRaisesRegex(ValueError, 'browser cache rejection'):
            READER.qualify_journey(value)

    def test_malformed_protocol_lifecycle_refuses_the_native_cache_claim(self):
        value = changed('persisted-cache-diagnostics', result(), lambda body: body['lifecycle'].append(
            {'frameId': 'frame', 'loaderId': 'loader', 'name': 'load', 'timestamp': 'unknown'}))
        with self.assertRaisesRegex(ValueError, 'native cache diagnostics'):
            READER.qualify_journey(value)

    def test_actual_two_cached_cycles_qualify_only_chromium(self):
        qualified = READER.qualify_journey(result())
        self.assertEqual(qualified['cycles'], 2)
        self.assertEqual(qualified['project'], 'chromium-reader-narrow')

    def test_default_headless_shell_is_not_full_chromium_authority(self):
        value = changed('persisted-browser-runtime', result(), lambda body: body['commandLine'].update(arguments=['/ms-playwright/chromium_headless_shell/headless_shell']))
        with self.assertRaisesRegex(ValueError, 'Full Chromium'):
            READER.qualify_journey(value)

    def test_actual_cache_disabling_argument_refuses_the_native_job(self):
        value = changed('persisted-browser-runtime', result(), lambda body: body['commandLine']['arguments'].append('--disable-back-forward-cache'))
        with self.assertRaisesRegex(ValueError, 'cache was disabled'):
            READER.qualify_journey(value)

    def test_missing_physical_executable_digest_refuses_runtime_claim(self):
        value = changed('persisted-browser-runtime', result(), lambda body: body.update(executableSha256='unknown'))
        with self.assertRaisesRegex(ValueError, 'executable digest'):
            READER.qualify_journey(value)

    def test_other_protocol_product_is_not_chromium(self):
        value = changed('persisted-browser-runtime', result(), lambda body: body['version'].update(product='Firefox/146'))
        with self.assertRaisesRegex(ValueError, 'Chromium protocol'):
            READER.qualify_journey(value)

    def test_native_cache_false_or_synthetic_event_cannot_substitute_for_cache(self):
        for field in ('trusted', 'persisted'):
            with self.subTest(field=field):
                value = changed('persisted-native-journey', result(), lambda body: body['records'][0]['back'].update({field: False}))
                with self.assertRaisesRegex(ValueError, 'trusted persisted'):
                    READER.qualify_journey(value)

    def test_url_key_and_realm_change_refuse_retained_source_authority(self):
        for field in ('href', 'entryKey', 'timeOrigin'):
            with self.subTest(field=field):
                value = changed('persisted-native-journey', result(), lambda body: body['records'][0]['returned'].update({field: 'foreign'}))
                with self.assertRaisesRegex(ValueError, 'reader realm/entry/URL'):
                    READER.qualify_journey(value)

    def test_changed_actual_source_refuses_cached_inspection(self):
        value = changed('persisted-native-journey', result(), lambda body: body['records'][0]['returned'].update(sources=['different']))
        with self.assertRaisesRegex(ValueError, 'source or inspection'):
            READER.qualify_journey(value)

    def test_closed_cached_disclosure_refuses_even_when_offset_passes(self):
        value = changed('persisted-native-journey', result(), lambda body: body['records'][0]['returned'].update(disclosures=[False] * 5))
        with self.assertRaisesRegex(ValueError, 'source or inspection'):
            READER.qualify_journey(value)

    def test_original_one_pixel_limit_is_strict(self):
        value = changed('persisted-native-journey', result(), lambda body: body['records'][0]['returned'].update(top=451))
        with self.assertRaisesRegex(ValueError, 'one-pixel'):
            READER.qualify_journey(value)

    def test_missing_or_duplicate_cycle_is_not_complete_qualification(self):
        for change in (lambda body: body['records'].pop(), lambda body: body['records'][1].update(cycle=0)):
            with self.subTest(change=change):
                value = changed('persisted-native-journey', result(), change)
                with self.assertRaisesRegex(ValueError, 'Two unique'):
                    READER.qualify_journey(value)

    def test_replayed_true_pageshow_cannot_stand_in_for_the_next_cached_journey(self):
        value = changed('persisted-native-journey', result(), lambda body: body['records'][1]['back'].update(sequence=4))
        with self.assertRaisesRegex(ValueError, 'Replayed lifecycle'):
            READER.qualify_journey(value)

    def test_unexpected_provider_request_refuses_the_owned_local_fixture(self):
        value = changed('persisted-native-journey', result(), lambda body: body['external'].append('https://provider.invalid/tile'))
        with self.assertRaisesRegex(ValueError, 'provider requests'):
            READER.qualify_journey(value)

    def test_duplicate_or_missing_runtime_annotation_refuses_a_retained_claim(self):
        for duplicate in (False, True):
            value = result()
            if duplicate:
                value['annotations'].append(value['annotations'][1])
            else:
                value['annotations'].pop(1)
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, 'Missing or duplicate'):
                READER.qualify_journey(value)


class DedicatedReceiptTests(unittest.TestCase):
    def packet(self, root):
        output = root / 'persisted-reader'
        output.mkdir()
        cases = [{'id': name + '-case', 'project': name, 'title': 'native cached journey'} for name in READER.PROJECTS]
        source = READER.current_source_identity()
        inventory = {'qualification_scope': READER.SCOPE, 'source_identity': source,
                     'fixture_identity': {'kind': 'owned test fixture'},
                     'canonical_projects': [{'name': name, 'engine': 'chromium', 'count': 1} for name in READER.PROJECTS],
                     'cases': cases}
        results = [result(name) for name in READER.PROJECTS]
        xml = '<testsuites tests="3" failures="0" skipped="0" errors="0">' + ''.join(
            '<testsuite hostname="' + name + '" tests="1"><testcase name="native cached journey"/></testsuite>'
            for name in READER.PROJECTS) + '</testsuites>'
        (output / 'junit.xml').write_text(xml)
        report = {**inventory, 'status': 'passed', 'qualification_kind': 'assigned_engine_shard',
                  'assigned_project_names': list(READER.PROJECTS), 'expected_cases': cases,
                  'projects': {name: {'expected': 1, 'executed': 1, 'passed': 1, 'failed': 0, 'skipped': 0} for name in READER.PROJECTS},
                  'results': results,
                  'junit': {'path': 'junit.xml', 'sha256': hashlib.sha256(xml.encode()).hexdigest()}}
        (output / 'qualification.json').write_text(json.dumps(report))
        inventory_path = root / 'canonical.json'
        inventory_path.write_text(json.dumps(inventory))
        return output, inventory_path

    def test_physical_dedicated_packet_requires_exact_projects_and_terminal_junit(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            output, inventory = self.packet(Path(directory))
            actual = READER.derive(output, inventory)
            self.assertEqual(actual['executed_cases'], 3)
            self.assertEqual(actual['cached_native_cycles'], 6)
            self.assertEqual(actual['source_identity'], READER.current_source_identity())

    def test_foreign_source_identity_cannot_reuse_a_self_consistent_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            output, inventory = self.packet(Path(directory))
            report = json.loads((output / 'qualification.json').read_text())
            original = json.loads(inventory.read_text())
            report['source_identity']['head'] = 'f' * 40
            original['source_identity'] = report['source_identity']
            (output / 'qualification.json').write_text(json.dumps(report))
            inventory.write_text(json.dumps(original))
            with self.assertRaisesRegex(ValueError, 'actual source tree'):
                READER.derive(output, inventory)

    def test_missing_dedicated_case_refuses_complete_coverage(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            output, inventory = self.packet(Path(directory))
            report = json.loads((output / 'qualification.json').read_text())
            report['results'].pop()
            (output / 'qualification.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Missing or extra'):
                READER.derive(output, inventory)

    def test_changed_junit_bytes_are_not_hidden_by_a_passing_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            output, inventory = self.packet(Path(directory))
            (output / 'junit.xml').write_text('<testsuites tests="3" failures="1"/>')
            with self.assertRaisesRegex(ValueError, 'JUnit digest'):
                READER.derive(output, inventory)

    def test_changed_after_verification_receipt_is_rederived_from_its_owned_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'artifacts') as directory:
            root = Path(directory)
            output, inventory = self.packet(root)
            target = root / 'inventories' / (READER.SUITE + '.json')
            target.parent.mkdir()
            target.write_bytes(inventory.read_bytes())
            receipt = READER.derive(output, target)
            (output / 'receipt.json').write_text(json.dumps(receipt))
            with patch.object(READER, 'ARTIFACTS', root):
                self.assertEqual(READER.verify(output), receipt)
                receipt['cached_native_cycles'] = 7
                (output / 'receipt.json').write_text(json.dumps(receipt))
                with self.assertRaisesRegex(ValueError, 'physical source-bound'):
                    READER.verify(output)


if __name__ == '__main__':
    unittest.main()

"""Validate real compiler caches and reject typed constant or executable tampering."""
import importlib.util
import marshal
import math
from pathlib import Path
import py_compile
import struct
import sys
import sysconfig
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bijux_cache_profiles', ROOT / 'shared/bijux-docs/security/renderer_profiles.py')
profiles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(profiles)


class ExecutableCacheConstants(unittest.TestCase):
    def setUp(self):
        cache_prefix = patch.object(sys, 'pycache_prefix', None)
        cache_prefix.start()
        self.addCleanup(cache_prefix.stop)
        artifact = ROOT / 'artifacts/website-security/runtime-cache-tests'
        artifact.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(dir=artifact)
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)
        self.number = 0

    def compile_cache(self, text, optimize=2):
        self.number += 1
        source = self.root / ('owned_' + str(self.number) + '.py')
        source.write_text(text)
        cache = Path(importlib.util.cache_from_source(str(source), optimization=str(optimize) if optimize else ''))
        py_compile.compile(str(source), cfile=str(cache), doraise=True, optimize=optimize)
        return source, cache

    def corrupt(self, cache, transform):
        payload = cache.read_bytes()
        cache.write_bytes(payload[:16] + marshal.dumps(transform(marshal.loads(payload[16:]))))

    def changed_constants(self, code, change):
        return code.replace(co_consts=tuple(self.changed_constants(value, change) if isinstance(value, types.CodeType) else change(value) for value in code.co_consts))

    def reject(self, cache):
        with self.assertRaisesRegex(profiles.ProfileError, 'cached executable bytecode differs from owned source'):
            profiles.validate_bytecode(cache)

    def test_actual_compiler_nan_caches_remain_source_owned(self):
        for optimize in (0, 1, 2):
            for source in (
                'value = 1e309 - 1e309\n',
                'value = 1e309j / 1e309j\n',
                'value = (1e309 - 1e309, (1e309j / 1e309j, b"owned"))\n',
                'def nested():\n    return 1e309 - 1e309\n',
                'if 0 in {1e309 - 1e309, "owned"}:\n    pass\n',
                'if 0 in {1e309 - 1e309, 1e309 - 1e309}:\n    pass\n',
            ):
                with self.subTest(optimize=optimize, source=source):
                    _, cache = self.compile_cache(source, optimize)
                    profiles.validate_bytecode(cache)

    def test_removed_identical_nan_set_member_is_rejected(self):
        _, cache = self.compile_cache('if 0 in {1e309 - 1e309, 1e309 - 1e309}:\n    pass\n')
        def changed(value):
            if type(value) is frozenset:
                self.assertEqual(len(value), 2)
                return frozenset([next(iter(value))])
            return value
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        self.reject(cache)

    def test_removed_nested_nan_set_member_is_rejected(self):
        _, cache = self.compile_cache('def nested():\n    if 0 in {1e309 - 1e309, 1e309 - 1e309}:\n        pass\n')
        self.corrupt(cache, lambda code: self.changed_constants(code, lambda value: frozenset([next(iter(value))]) if type(value) is frozenset else value))
        self.reject(cache)

    def test_nan_alias_collapse_changes_ordinary_result_and_is_rejected(self):
        _, cache = self.compile_cache('values=(1e309-1e309,1e309-1e309)\nresult=len(set(values))\n')
        original = marshal.loads(cache.read_bytes()[16:])
        scope = {}
        exec(original, scope)
        self.assertEqual(scope['result'], 2)
        def changed(value):
            if type(value) is tuple and len(value) == 2 and all(type(item) is float and math.isnan(item) for item in value):
                self.assertIsNot(value[0], value[1])
                return (value[0], value[0])
            return value
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        scope = {}
        exec(marshal.loads(cache.read_bytes()[16:]), scope)
        self.assertEqual(scope['result'], 1)
        self.reject(cache)

    def test_nested_container_alias_collapse_is_rejected(self):
        _, cache = self.compile_cache('values=((1e309-1e309,), (1e309-1e309,))\nresult=values[0][0] is values[1][0]\n')
        def changed(value):
            if type(value) is tuple and len(value) == 2 and all(type(item) is tuple for item in value):
                return (value[0], value[0])
            return value
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        self.reject(cache)

    def test_nan_aliases_across_nested_code_objects_are_rejected(self):
        _, cache = self.compile_cache('def first():\n    return 1e309-1e309\ndef second():\n    return 1e309-1e309\nresult=first() is second()\n')
        shared = None
        def changed(value):
            nonlocal shared
            if type(value) is float and math.isnan(value):
                if shared is None:
                    shared = value
                return shared
            return value
        original = marshal.loads(cache.read_bytes()[16:])
        scope = {}
        exec(original, scope)
        self.assertFalse(scope['result'])
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        scope = {}
        exec(marshal.loads(cache.read_bytes()[16:]), scope)
        self.assertTrue(scope['result'])
        self.reject(cache)

    def graph_code(self, constants):
        return compile('pass', 'owned.py', 'exec', dont_inherit=True).replace(co_consts=constants)

    def test_unordered_alias_correspondence_backtracks_across_containers(self):
        # The two equal-payload sets share exactly one NaN. Their shared
        # member is observable through ordinary identity and set operations.
        left = [float('nan') for _ in range(3)]
        right = [float('nan') for _ in range(3)]
        expected = self.graph_code((frozenset(left[:2]), frozenset(left[1:]), None))
        actual = self.graph_code((frozenset(right[1:]), frozenset(right[:2]), None))
        self.assertTrue(profiles.cache_code_equal(actual, expected))
        disjoint = [float('nan') for _ in range(4)]
        changed = self.graph_code((frozenset(disjoint[:2]), frozenset(disjoint[2:]), None))
        self.assertFalse(profiles.cache_code_equal(changed, expected))

    def test_ordered_alias_anchors_and_unordered_members_match(self):
        left = [float('nan') for _ in range(2)]
        right = [float('nan') for _ in range(2)]
        expected = self.graph_code((frozenset(left), (left[0], left[1]), None))
        actual = self.graph_code((frozenset(right), (right[1], right[0]), None))
        self.assertTrue(profiles.cache_code_equal(actual, expected))
        changed = self.graph_code((frozenset(right), (right[0], right[0]), None))
        self.assertFalse(profiles.cache_code_equal(changed, expected))

    def test_alias_expansion_in_nested_constants_is_rejected(self):
        left = float('nan')
        right = [float('nan') for _ in range(2)]
        expected = self.graph_code(((left, (left,)), None))
        changed = self.graph_code(((right[0], (right[1],)), None))
        self.assertFalse(profiles.cache_code_equal(changed, expected))

    def test_complex_nan_reference_aliases_remain_distinct(self):
        left = [complex(1.0, float('nan')) for _ in range(2)]
        expected = self.graph_code((tuple(left), None))
        self.assertTrue(profiles.cache_code_equal(marshal.loads(marshal.dumps(expected)), expected))
        changed = self.graph_code(((left[0], left[0]), None))
        self.assertFalse(profiles.cache_code_equal(changed, expected))

    def test_interpreter_slice_constants_preserve_members_and_aliases(self):
        for optimize in (0, 1, 2):
            _, cache = self.compile_cache('value=b"owned"[1:4]\n', optimize)
            profiles.validate_bytecode(cache)
        original = self.graph_code((slice(1, 4, None), None))
        if sys.version_info < (3, 14):
            # Earlier interpreters do not admit slice objects in their marshal
            # format; ordinary source compilation above remains qualified.
            with self.assertRaises(ValueError):
                marshal.dumps(original)
            return
        self.assertTrue(profiles.cache_code_equal(marshal.loads(marshal.dumps(original)), original))
        changed = self.graph_code((slice(1, 5, None), None))
        self.assertFalse(profiles.cache_code_equal(changed, original))

    def test_graph_budget_exhaustion_is_fail_closed(self):
        code = self.graph_code((('owned', 1), None))
        with self.assertRaisesRegex(profiles.ProfileError, 'graph comparison budget exceeded'):
            profiles.cache_code_equal(code, code, search_limit=1)

    def test_independent_compiler_reflexive_interning_remains_valid(self):
        # The compiler and marshal reader can share equal reflexive frozensets
        # differently. Such sharing is not a reproducible source invariant.
        source = Path(sysconfig.get_path('stdlib')) / 'ftplib.py'
        self.assertTrue(source.is_file())
        for optimize in (0, 1, 2):
            _, cache = self.compile_cache(source.read_text(), optimize)
            profiles.validate_bytecode(cache)

    def test_changed_nan_payload_is_rejected(self):
        _, cache = self.compile_cache('value = 1e309 - 1e309\n')
        def changed(value):
            if type(value) is float and math.isnan(value):
                bits = int.from_bytes(struct.pack('>d', value), 'big') ^ 1
                return struct.unpack('>d', bits.to_bytes(8, 'big'))[0]
            return value
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        self.reject(cache)

    def test_changed_complex_nan_payload_is_rejected(self):
        _, cache = self.compile_cache('value = 1e309j / 1e309j\n')
        def changed(value):
            if type(value) is complex:
                bits = int.from_bytes(struct.pack('>d', value.imag), 'big') ^ 1
                return complex(value.real, struct.unpack('>d', bits.to_bytes(8, 'big'))[0])
            return value
        self.corrupt(cache, lambda code: self.changed_constants(code, changed))
        self.reject(cache)

    def test_changed_float_sign_is_rejected(self):
        _, cache = self.compile_cache('value = 0.0\n')
        self.corrupt(cache, lambda code: self.changed_constants(code, lambda value: -0.0 if type(value) is float else value))
        self.reject(cache)

    def test_changed_finite_value_is_rejected(self):
        _, cache = self.compile_cache('value = 1.25\n')
        self.corrupt(cache, lambda code: self.changed_constants(code, lambda value: 3.25 if type(value) is float else value))
        self.reject(cache)

    def test_scalar_type_substitution_is_rejected(self):
        _, cache = self.compile_cache('value = 1\n')
        self.corrupt(cache, lambda code: self.changed_constants(code, lambda value: True if type(value) is int else value))
        self.reject(cache)

    def test_bytes_container_substitution_is_rejected(self):
        _, cache = self.compile_cache('value = b"owned"\n')
        self.corrupt(cache, lambda code: self.changed_constants(code, lambda value: ('bytes', value) if type(value) is bytes else value))
        self.reject(cache)

    def test_executable_payload_substitution_is_rejected(self):
        _, cache = self.compile_cache('value = 1e309 - 1e309\n')
        self.corrupt(cache, lambda code: compile('raise RuntimeError("changed executable")', code.co_filename, 'exec', dont_inherit=True, optimize=2))
        self.reject(cache)

    def test_changed_executable_stack_field_is_rejected(self):
        _, cache = self.compile_cache('value = 1e309 - 1e309\n')
        self.corrupt(cache, lambda code: code.replace(co_stacksize=code.co_stacksize + 1))
        self.reject(cache)

    def test_changed_nested_code_location_is_rejected(self):
        _, cache = self.compile_cache('def nested():\n    return 1e309 - 1e309\n')
        self.corrupt(cache, lambda code: code.replace(co_consts=tuple(value.replace(co_firstlineno=value.co_firstlineno + 1) if isinstance(value, types.CodeType) else value for value in code.co_consts)))
        self.reject(cache)

    def test_changed_code_line_table_is_rejected(self):
        _, cache = self.compile_cache('value = 1e309 - 1e309\n')
        self.corrupt(cache, lambda code: code.replace(co_linetable=code.co_linetable + b'\x00'))
        self.reject(cache)

    def test_changed_source_remains_rejected(self):
        source, cache = self.compile_cache('value = 1.25\n')
        source.write_text('value = 3.25\n')
        self.reject(cache)


if __name__ == '__main__':
    unittest.main()

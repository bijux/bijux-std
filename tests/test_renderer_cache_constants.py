"""Validate real compiler caches and reject typed constant or executable tampering."""
import importlib.util
import marshal
import math
from pathlib import Path
import py_compile
import struct
import sys
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
            ):
                with self.subTest(optimize=optimize, source=source):
                    _, cache = self.compile_cache(source, optimize)
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

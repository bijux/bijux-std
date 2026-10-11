"""Refuse unsafe archives and unreviewed source-wheel publication identities."""
from __future__ import annotations

import copy
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    'bijux_source_wheel_builder',
    ROOT/'shared/bijux-docs/tooling/security/build_publication_wheels.py',
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def archive(entries):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as stream:
        for name, kind, content in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.mode = 0o644
            if kind == tarfile.REGTYPE:
                info.size = len(content)
                stream.addfile(info, io.BytesIO(content))
            else:
                info.linkname = 'outside'
                stream.addfile(info)
    return output.getvalue()


class SourceWheelInputs(unittest.TestCase):
    def setUp(self):
        self.prefix = 'jsmin-3.0.1'
        self.valid = [(self.prefix+'/setup.py', tarfile.REGTYPE, b'from setuptools import setup\n')]
        self.document = json.loads((builder.RUNTIME/'source-wheels.json').read_text())

    def test_bounded_native_setup_source_is_captured_without_execution(self):
        records = builder.archive_files(archive(self.valid), self.prefix)
        self.assertEqual(records[self.prefix+'/setup.py'][0], self.valid[0][2])

    def test_parent_traversal_member_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'escaping'):
            builder.archive_files(archive(self.valid+[(self.prefix+'/../outside.py',tarfile.REGTYPE,b'x')]), self.prefix)

    def test_absolute_member_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'escaping'):
            builder.archive_files(archive(self.valid+[('/outside.py',tarfile.REGTYPE,b'x')]), self.prefix)

    def test_backslash_member_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'escaping'):
            builder.archive_files(archive(self.valid+[(self.prefix+'/foreign\\path.py',tarfile.REGTYPE,b'x')]), self.prefix)

    def test_duplicate_member_cannot_replace_reviewed_source(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            builder.archive_files(archive(self.valid+self.valid), self.prefix)

    def test_symlink_hardlink_and_device_members_are_refused(self):
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.CHRTYPE,tarfile.FIFOTYPE):
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'nonregular'):
                builder.archive_files(archive(self.valid+[(self.prefix+'/foreign',kind,b'')]), self.prefix)

    def test_source_without_setup_entrypoint_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'entrypoint missing'):
            builder.archive_files(archive([(self.prefix+'/README.rst',tarfile.REGTYPE,b'text')]),self.prefix)

    def test_excessive_member_population_is_refused_before_extraction(self):
        members=self.valid+[(self.prefix+f'/source-{index}.py',tarfile.REGTYPE,b'x') for index in range(1024)]
        with self.assertRaisesRegex(ValueError,'member budget'):
            builder.archive_files(archive(members),self.prefix)

    def test_frozen_source_observation_is_explicitly_separate_from_admission(self):
        sources=builder.recipe(self.document,observation=True)
        self.assertEqual({source['name'] for source in sources},{'csscompressor','jsmin'})
        pending=copy.deepcopy(self.document)
        for row in pending['sources']:
            row.pop('wheel_filename',None)
            row.pop('wheel_sha256',None)
        with self.assertRaisesRegex(ValueError,'independently reviewed wheel fingerprint'):
            builder.recipe(pending)

    def test_replaced_source_hash_is_refused_even_for_observation(self):
        self.document['sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            builder.recipe(self.document,observation=True)

    def test_foreign_download_host_is_refused(self):
        self.document['sources'][0]['url']=self.document['sources'][0]['url'].replace('files.pythonhosted.org','example.invalid')
        with self.assertRaisesRegex(ValueError,'primary source identity'):
            builder.recipe(self.document,observation=True)

    def test_floating_builder_version_is_refused(self):
        self.document['builder_packages']['setuptools']='latest'
        with self.assertRaisesRegex(ValueError,'frozen builder recipe'):
            builder.recipe(self.document,observation=True)

    def test_duplicate_source_distribution_is_refused(self):
        self.document['sources'][1]=dict(self.document['sources'][0])
        with self.assertRaisesRegex(ValueError,'duplicate'):
            builder.recipe(self.document,observation=True)


class PureWheelOutputs(unittest.TestCase):
    def setUp(self):
        output=ROOT/'artifacts/qualification/source-wheel-builder'
        output.mkdir(parents=True,exist_ok=True)
        self.scratch=tempfile.TemporaryDirectory(dir=output)
        self.addCleanup(self.scratch.cleanup)
        self.root=Path(self.scratch.name)
        self.path=self.root/'jsmin-3.0.1-py3-none-any.whl'
        self.source={'name':'jsmin','version':'3.0.1'}

    def wheel(self,*,metadata=b'Name: jsmin\nVersion: 3.0.1\n',extra=None):
        with zipfile.ZipFile(self.path,'w') as wheel:
            wheel.writestr('jsmin-3.0.1.dist-info/METADATA',metadata)
            wheel.writestr('jsmin-3.0.1.dist-info/WHEEL',b'Root-Is-Purelib: true\nTag: py3-none-any\n')
            wheel.writestr('jsmin/__init__.py',b'__version__="3.0.1"\n')
            if extra is not None:wheel.writestr(extra,b'foreign')

    def test_actual_pure_wheel_metadata_binds_name_version_and_payload(self):
        self.wheel()
        record=builder.wheel_identity(self.path,self.source)
        self.assertEqual(record['sha256'],builder.digest(self.path.read_bytes()))

    def test_mismatched_package_metadata_is_refused(self):
        self.wheel(metadata=b'Name: substitute\nVersion: 3.0.1\n')
        with self.assertRaisesRegex(ValueError,'metadata differs'):
            builder.wheel_identity(self.path,self.source)

    def test_duplicate_wheel_member_is_refused(self):
        self.wheel(extra='jsmin/__init__.py')
        with self.assertRaisesRegex(ValueError,'unique wheel population'):
            builder.wheel_identity(self.path,self.source)

    def test_wheel_member_cannot_escape_output(self):
        self.wheel(extra='../foreign.py')
        with self.assertRaisesRegex(ValueError,'escaping'):
            builder.wheel_identity(self.path,self.source)

    def test_existing_output_is_never_overwritten(self):
        target=self.root/'artifacts/owned';target.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'fresh absent'):
            builder.output_directory(self.root,'artifacts/owned')

    def test_output_must_belong_to_repository_artifacts(self):
        for value in ('source/wheels','../artifacts/wheels','artifacts/../foreign','/artifacts/wheels'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError,'confined'):
                builder.output_directory(self.root,value)


if __name__=='__main__':
    unittest.main(verbosity=2)

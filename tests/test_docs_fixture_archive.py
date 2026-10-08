"""Require exact fixture reconstruction and reject malformed object transports."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fixture_archive", ROOT / "tests/bijux-docs/execution/fixture_archive.py"
)
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)


class FixtureArchiveTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(dir=ROOT / "artifacts")
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.source = self.root / "producer"
        self.archive = self.root / "browser-fixtures.tar.gz"
        self.output = self.root / "worker"
        self.roots = ["contrast-generated", "generated"]
        self.bytes = {}
        for root in self.roots:
            files = {
                "index.html": ("Authored " + root).encode(),
                "assets/native.js": b"/* immutable native search */" * 500,
                "guide/index.html": "Punctuation: API::call --help; café".encode(),
            }
            manifest = {
                "schema": 1,
                "source_sha": "a" * 40,
                "source_tree_dirty": False,
                "source_files": {"styles/03-header.css": ARCHIVE.digest(b"source")},
                "site_files": {
                    name: ARCHIVE.digest(data) for name, data in files.items()
                },
            }
            files = {"site/" + name: data for name, data in files.items()}
            files["manifest.json"] = json.dumps(manifest, indent=2).encode()
            for name, data in files.items():
                path = self.source / root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                self.bytes[root + "/" + name] = data
        self.receipt = ARCHIVE.pack(self.source, self.roots, self.archive)

    def members(self):
        with tarfile.open(self.archive) as stream:
            return [
                (member.name, stream.extractfile(member).read(), member.type)
                for member in stream
            ]

    def rewrite(self, members):
        with tarfile.open(self.archive, "w:gz", format=tarfile.USTAR_FORMAT) as stream:
            for name, data, kind in members:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = (
                    "../../outside"
                    if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE)
                    else ""
                )
                member.size = len(data) if kind == tarfile.REGTYPE else 0
                stream.addfile(member, io.BytesIO(data) if member.size else None)

    def change_index(self, function):
        members = self.members()
        index = json.loads(members[0][1])
        function(index)
        members[0] = ("index.json", json.dumps(index).encode(), tarfile.REGTYPE)
        return members

    def unpack(self, expected=None):
        return ARCHIVE.unpack(
            self.archive,
            self.output,
            self.roots,
            expected or ARCHIVE.digest(self.archive.read_bytes()),
        )

    def rejected(self, expression=None):
        if expression:
            context = self.assertRaisesRegex(ValueError, expression)
        else:
            context = self.assertRaises(
                (ValueError, OSError, EOFError, tarfile.TarError)
            )
        with context:
            self.unpack()
        self.assertFalse(any((self.output / root).exists() for root in self.roots))

    def test_reconstructs_every_exact_manifest_and_regular_site_file(self):
        receipt = self.unpack(self.receipt["archive_sha256"])
        actual = {
            str(path.relative_to(self.output)): path.read_bytes()
            for path in self.output.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual, self.bytes)
        self.assertEqual(receipt["file_count"], len(self.bytes))
        self.assertTrue(all(not path.is_symlink() for path in self.output.rglob("*")))
        native = [self.output / root / "site/assets/native.js" for root in self.roots]
        self.assertNotEqual(native[0].stat().st_ino, native[1].stat().st_ino)

    def test_transports_identical_content_once_and_is_deterministic(self):
        expected_objects = {
            hashlib.sha256(data).hexdigest() for data in self.bytes.values()
        }
        members = self.members()
        self.assertEqual(len(members), len(expected_objects) + 1)
        self.assertTrue(all(kind == tarfile.REGTYPE for _, _, kind in members))
        self.assertLess(
            self.receipt["unique_bytes"], self.receipt["reconstructed_bytes"]
        )
        previous = self.archive.read_bytes()
        ARCHIVE.pack(self.source, list(reversed(self.roots)), self.archive)
        self.assertEqual(previous, self.archive.read_bytes())

    def test_additional_owned_fixture_root_does_not_require_hardcoded_totals(self):
        extra = self.source / "extended-fixtures"
        import shutil

        shutil.copytree(self.source / "generated", extra)
        roots = self.roots + ["extended-fixtures"]
        receipt = ARCHIVE.pack(self.source, roots, self.archive)
        ARCHIVE.unpack(self.archive, self.output, roots, receipt["archive_sha256"])
        self.assertEqual(
            (self.output / "extended-fixtures/site/index.html").read_bytes(),
            self.bytes["generated/site/index.html"],
        )

    def test_archive_digest_corruption_rejects_before_destination(self):
        with self.archive.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.unpack(self.receipt["archive_sha256"])
        self.assertFalse(self.output.exists())

    def test_object_corruption_rejects_even_with_recomputed_archive_digest(self):
        members = self.members()
        name, data, kind = members[1]
        members[1] = (name, bytes([data[0] ^ 1]) + data[1:], kind)
        self.rewrite(members)
        self.rejected("object digest mismatch")

    def test_duplicate_member_rejects(self):
        members = self.members()
        self.rewrite(members + [members[1]])
        self.rejected("Duplicate fixture archive member")

    def test_missing_object_rejects(self):
        members = self.members()
        self.rewrite(members[:-1])
        self.rejected("Incomplete fixture object inventory")

    def test_undeclared_object_rejects(self):
        self.rewrite(
            self.members()
            + [("objects/" + ARCHIVE.digest(b"orphan"), b"orphan", tarfile.REGTYPE)]
        )
        self.rejected("Unexpected fixture object")

    def test_incomplete_file_map_rejects_against_original_manifest(self):
        members = self.change_index(
            lambda index: index["files"].pop("generated/site/guide/index.html")
        )
        self.rewrite(members)
        self.rejected("output is missing")

    def test_nonmanifest_file_rejects(self):
        def change(index):
            index["files"]["generated/site/fabricated.html"] = dict(
                index["files"]["generated/site/guide/index.html"]
            )

        self.rewrite(self.change_index(change))
        self.rejected("outside manifest")

    def test_file_path_escape_and_aliases_reject(self):
        for name in [
            "generated/site/../../outside",
            "/outside",
            "generated/site//index.html",
            "generated/site/./index.html",
            "generated/site/C:\\outside",
            "generated/site/\x00outside",
            "generated/site/C:outside",
        ]:
            with self.subTest(path=name):
                previous = self.archive.read_bytes()
                self.rewrite(
                    self.change_index(
                        lambda index: index["files"].update(
                            {name: dict(index["files"]["generated/site/index.html"])}
                        )
                    )
                )
                self.rejected("fixture path")
                self.archive.write_bytes(previous)

    def test_unexpected_tar_path_rejects(self):
        self.rewrite(self.members() + [("../outside", b"outside", tarfile.REGTYPE)])
        self.rejected("Unexpected fixture archive member")

    def test_links_and_special_files_reject(self):
        for kind in [
            tarfile.SYMTYPE,
            tarfile.LNKTYPE,
            tarfile.DIRTYPE,
            tarfile.FIFOTYPE,
            tarfile.CHRTYPE,
            tarfile.XHDTYPE,
        ]:
            with self.subTest(kind=kind):
                previous = self.archive.read_bytes()
                members = self.members()
                members[1] = (members[1][0], b"", kind)
                self.rewrite(members)
                self.rejected("nonregular")
                self.archive.write_bytes(previous)

    def test_duplicate_json_key_rejects(self):
        members = self.members()
        members[0] = (
            "index.json",
            members[0][1].replace(b'"schema":1', b'"schema":1,"schema":1'),
            tarfile.REGTYPE,
        )
        self.rewrite(members)
        self.rejected("Duplicate JSON key")

    def test_root_ownership_mismatch_rejects(self):
        with self.assertRaisesRegex(ValueError, "root ownership mismatch"):
            ARCHIVE.unpack(
                self.archive, self.output, ["generated"], self.receipt["archive_sha256"]
            )
        self.assertFalse(self.output.exists())

    def test_conflicting_object_sizes_and_invalid_scalar_types_reject(self):
        for size in [True, -1, ARCHIVE.MAX_FILE_BYTES + 1]:
            with self.subTest(size=size):
                previous = self.archive.read_bytes()
                self.rewrite(
                    self.change_index(
                        lambda index: index["files"][
                            "generated/site/index.html"
                        ].update(size=size)
                    )
                )
                self.rejected("identity or size")
                self.archive.write_bytes(previous)
        self.rewrite(
            self.change_index(
                lambda index: index["files"]["generated/site/assets/native.js"].update(
                    size=1
                )
            )
        )
        self.rejected("Conflicting fixture object sizes")

    def test_unique_content_and_member_limits_reject(self):
        with patch.object(ARCHIVE, "MAX_UNIQUE_BYTES", 1):
            self.rejected("unique byte limit")
        with patch.object(ARCHIVE, "MAX_RECONSTRUCTED_BYTES", 1):
            self.rejected("reconstructed byte limit")
        with patch.object(ARCHIVE, "MAX_FILES", 1):
            self.rejected("file inventory")

    def test_oversized_header_rejects_without_reading_declared_body(self):
        index = self.members()[0]
        entry = tarfile.TarInfo(index[0])
        entry.size = len(index[1])
        oversized = tarfile.TarInfo("objects/" + "a" * 64)
        oversized.size = ARCHIVE.MAX_FILE_BYTES + 1
        encoded = (
            entry.tobuf(tarfile.USTAR_FORMAT)
            + index[1]
            + bytes((-len(index[1])) % tarfile.BLOCKSIZE)
            + oversized.tobuf(tarfile.USTAR_FORMAT)
            + bytes(tarfile.BLOCKSIZE * 2)
        )
        self.archive.write_bytes(gzip.compress(encoded))
        self.rejected("member exceeds byte limit")

    def test_truncation_and_gzip_crc_reject(self):
        previous = self.archive.read_bytes()
        for data in [
            previous[:-6],
            previous[:-8] + bytes([previous[-8] ^ 1]) + previous[-7:],
        ]:
            with self.subTest(length=len(data)):
                self.archive.write_bytes(data)
                self.rejected()
        self.archive.write_bytes(previous)

    def test_member_after_tar_terminator_rejects(self):
        data = gzip.decompress(self.archive.read_bytes())
        self.archive.write_bytes(gzip.compress(data + b"undeclared payload"))
        self.rejected("trailing data")

    def test_preserves_existing_destination_and_rejects_directory_links(self):
        owned = self.output / "generated/site"
        owned.mkdir(parents=True)
        sentinel = owned / "reader.html"
        sentinel.write_bytes(b"user work")
        with self.assertRaisesRegex(ValueError, "Preserve existing"):
            self.unpack()
        self.assertEqual(sentinel.read_bytes(), b"user work")
        other = self.root / "elsewhere"
        other.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(other, target_is_directory=True)
        with self.assertRaises(OSError):
            ARCHIVE.unpack(
                self.archive, alias, self.roots, self.receipt["archive_sha256"]
            )
        self.assertEqual(list(other.iterdir()), [])

    def test_existing_downloaded_build_logs_are_preserved(self):
        logs = {}
        for root in self.roots:
            path = self.output / root / "build-product.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"exact failed or passing producer diagnostic")
            logs[path] = path.read_bytes()
        self.unpack()
        for path, expected in logs.items():
            self.assertEqual(path.read_bytes(), expected)
        for name, expected in self.bytes.items():
            self.assertEqual((self.output / name).read_bytes(), expected)

    def test_producer_rejects_missing_extra_corrupt_and_nonregular_outputs(self):
        target = self.source / "generated/site/guide/index.html"
        previous = target.read_bytes()
        target.unlink()
        with self.assertRaisesRegex(ValueError, "output is missing"):
            ARCHIVE.pack(self.source, self.roots, self.archive)
        target.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "differs from manifest"):
            ARCHIVE.pack(self.source, self.roots, self.archive)
        target.write_bytes(previous)
        extra = target.parent / "extra.html"
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "outside manifest"):
            ARCHIVE.pack(self.source, self.roots, self.archive)
        extra.unlink()
        target.unlink()
        target.symlink_to(self.source / "generated/site/index.html")
        with self.assertRaisesRegex(ValueError, "nonregular"):
            ARCHIVE.pack(self.source, self.roots, self.archive)
        target.unlink()
        os.mkfifo(target)
        with self.assertRaisesRegex(ValueError, "nonregular"):
            ARCHIVE.pack(self.source, self.roots, self.archive)

    def test_producer_rejects_source_directory_link(self):
        alias = self.root / "producer-alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(OSError):
            ARCHIVE.pack(alias, self.roots, self.archive)


if __name__ == "__main__":
    unittest.main()

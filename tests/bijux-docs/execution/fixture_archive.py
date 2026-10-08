"""Transport exact rendered fixtures without repeating identical asset bytes."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tarfile
import tempfile

FORMAT = "bijux-rendered-fixture-objects"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_UNIQUE_BYTES = 512 * 1024 * 1024
MAX_INDEX_BYTES = 16 * 1024 * 1024
MAX_RECONSTRUCTED_BYTES = 2 * 1024 * 1024 * 1024
MAX_FILES = 100_000
MAX_ROOTS = 128
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def path_name(name: str) -> str:
    require(
        isinstance(name, str) and bool(name) and len(name) <= 4096,
        "Invalid fixture path",
    )
    require(
        "\\" not in name
        and ":" not in name
        and not PureWindowsPath(name).drive
        and all(ord(char) >= 32 and ord(char) != 127 for char in name),
        "Invalid fixture path",
    )
    require(
        len(name.split("/")) <= 128
        and all(
            part not in ("", ".", "..") and len(part) <= 255 for part in name.split("/")
        ),
        "Invalid fixture path",
    )
    return name


def root_names(names: list[str]) -> list[str]:
    require(
        isinstance(names, list) and bool(names) and len(names) <= MAX_ROOTS,
        "Fixture roots are required",
    )
    for name in names:
        require("/" not in path_name(name), "Fixture root must be a single directory")
    require(len(set(names)) == len(names), "Duplicate fixture root")
    return sorted(names)


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def decode_json(data: bytes) -> dict:
    try:
        value = json.loads(data, object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid fixture JSON") from error
    require(isinstance(value, dict), "Fixture JSON must be an object")
    return value


def open_directory(path: Path, parent: int | None = None) -> int:
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)


def read_file(name: str, parent: int, maximum: int = MAX_FILE_BYTES) -> bytes:
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(before.st_mode) and before.st_size <= maximum,
            "Fixture input must be a bounded regular file",
        )
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        require(
            len(data) == before.st_size
            and len(data) <= maximum
            and (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "Fixture input changed while reading",
        )
        return data


def site_files(directory: int, prefix: str = ""):
    with os.scandir(directory) as entries:
        names = sorted(entry.name for entry in entries)
    for name in names:
        relative = path_name(prefix + name)
        info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = open_directory(Path(name), directory)
            try:
                yield from site_files(child, relative + "/")
            finally:
                os.close(child)
        else:
            require(
                stat.S_ISREG(info.st_mode), "Fixture site contains a nonregular file"
            )
            yield relative, read_file(name, directory)


def scenario_configurations(scenarios: list[dict]) -> dict[str, dict]:
    require(isinstance(scenarios, list) and bool(scenarios), "Fixture scenario configurations are required")
    require(len(scenarios) <= MAX_FILES, "Fixture scenario configuration limit exceeded")
    records = {}
    routes = set()
    for scenario in scenarios:
        require(isinstance(scenario, dict), "Invalid fixture scenario")
        route = scenario.get("route")
        require(isinstance(route, str) and route.startswith("/") and route.endswith("/"),
                "Invalid fixture scenario route")
        require(route not in routes, "Duplicate fixture scenario route")
        routes.add(route)
        if route != "/":
            path_name(route.strip("/"))
        label = "hub" if route == "/" else route.strip("/").replace("/", "-")
        expected = "inputs/" + label + "/mkdocs.yml"
        path_name(expected)
        config = scenario.get("configuration")
        require(isinstance(config, dict) and set(config) == {"path", "sha256", "bytes"},
                "Fixture scenario configuration identity is required")
        require(config["path"] == expected, "Fixture configuration path differs from scenario")
        require(isinstance(config["sha256"], str) and SHA256.fullmatch(config["sha256"]),
                "Invalid fixture configuration digest")
        require(type(config["bytes"]) is int and 0 < config["bytes"] <= MAX_FILE_BYTES,
                "Invalid fixture configuration byte count")
        require(expected not in records, "Duplicate fixture configuration path")
        records[expected] = {"bytes": config["bytes"], "sha256": config["sha256"]}
    return records


def configurations_digest(scenarios: list[dict]) -> str:
    records = scenario_configurations(scenarios)
    # Config paths are portable metadata; exact rendered YAML bytes stay producer-owned.
    return digest(json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def validate_configurations(manifest: dict) -> str:
    expected = manifest.get("configurations_sha256")
    require(isinstance(expected, str) and SHA256.fullmatch(expected),
            "Fixture configuration aggregate digest is required")
    actual = configurations_digest(manifest.get("scenarios"))
    require(actual == expected, "Fixture configuration aggregate differs")
    return actual


def manifest_sites(data: bytes) -> dict[str, str]:
    manifest = decode_json(data)
    validate_configurations(manifest)
    outputs = manifest.get("site_files")
    sources = manifest.get("source_files")
    require(
        isinstance(outputs, dict)
        and bool(outputs)
        and isinstance(sources, dict)
        and bool(sources),
        "Fixture manifest source and output inventories are required",
    )
    for mapping in (outputs, sources):
        require(len(mapping) <= MAX_FILES, "Fixture manifest exceeds file limit")
        for name, expected in mapping.items():
            path_name(name)
            require(
                isinstance(expected, str) and SHA256.fullmatch(expected),
                "Invalid manifest digest",
            )
    return outputs


def index_objects(index: dict) -> dict[str, int]:
    require(
        set(index) == {"schema", "format", "roots", "files"}
        and type(index["schema"]) is int
        and index["schema"] == 1
        and index["format"] == FORMAT,
        "Unsupported fixture archive format",
    )
    roots = root_names(index["roots"])
    require(index["roots"] == roots, "Fixture roots must be canonical")
    files = index["files"]
    require(
        isinstance(files, dict) and bool(files) and len(files) <= MAX_FILES,
        "Invalid fixture file inventory",
    )
    objects = {}
    for name, record in files.items():
        path_name(name)
        parts = name.split("/")
        require(
            parts[0] in roots
            and (
                parts[1:] == ["manifest.json"] or len(parts) >= 3 and parts[1] == "site"
            ),
            "Unexpected fixture output path",
        )
        require(
            isinstance(record, dict) and set(record) == {"sha256", "size"},
            "Invalid fixture object reference",
        )
        key, size = record["sha256"], record["size"]
        require(
            isinstance(key, str)
            and SHA256.fullmatch(key)
            and type(size) is int
            and 0 <= size <= MAX_FILE_BYTES,
            "Invalid fixture object identity or size",
        )
        require(
            key not in objects or objects[key] == size,
            "Conflicting fixture object sizes",
        )
        objects[key] = size
    require(
        sum(objects.values()) <= MAX_UNIQUE_BYTES,
        "Fixture archive exceeds unique byte limit",
    )
    require(
        sum(record["size"] for record in files.values()) <= MAX_RECONSTRUCTED_BYTES,
        "Fixture archive exceeds reconstructed byte limit",
    )
    return objects


def validate_maps(index: dict, objects: dict[str, bytes]) -> None:
    require(
        set(objects) == set(index_objects(index)), "Incomplete fixture object inventory"
    )
    expected = {}
    for root in index["roots"]:
        name = root + "/manifest.json"
        require(name in index["files"], "Fixture manifest is missing")
        record = index["files"][name]
        expected[name] = record
        for relative, key in manifest_sites(objects[record["sha256"]]).items():
            name = root + "/site/" + relative
            require(name in index["files"], "Fixture output is missing from archive")
            require(
                index["files"][name]["sha256"] == key,
                "Fixture output differs from manifest",
            )
            expected[name] = index["files"][name]
    require(expected == index["files"], "Archive contains output outside manifest")


def add_member(bundle: tarfile.TarFile, name: str, data: bytes) -> None:
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    entry.mode = 0o644
    entry.mtime = 0
    bundle.addfile(entry, io.BytesIO(data))


def pack(directory: Path, roots: list[str], archive: Path) -> dict:
    """Create a deterministic gzip tar containing regular objects and an index."""
    roots = root_names(roots)
    index = {"schema": 1, "format": FORMAT, "roots": roots, "files": {}}
    objects = {}
    unique_bytes = 0
    reconstructed_bytes = 0

    def collect(name: str, data: bytes) -> None:
        nonlocal unique_bytes, reconstructed_bytes
        require(len(index["files"]) < MAX_FILES, "Fixture archive exceeds file limit")
        reconstructed_bytes += len(data)
        require(
            reconstructed_bytes <= MAX_RECONSTRUCTED_BYTES,
            "Fixture archive exceeds reconstructed byte limit",
        )
        key = digest(data)
        require(
            key not in objects or objects[key] == data,
            "Conflicting bytes for fixture digest",
        )
        if key not in objects:
            unique_bytes += len(data)
            objects[key] = data
        require(
            unique_bytes <= MAX_UNIQUE_BYTES,
            "Fixture archive exceeds unique byte limit",
        )
        index["files"][name] = {"sha256": key, "size": len(data)}

    parent = open_directory(directory)
    try:
        for root in roots:
            folder = open_directory(Path(root), parent)
            try:
                manifest = read_file("manifest.json", folder, MAX_INDEX_BYTES)
                manifest_sites(manifest)
                collect(root + "/manifest.json", manifest)
                site = open_directory(Path("site"), folder)
                try:
                    for name, data in site_files(site):
                        collect(root + "/site/" + name, data)
                finally:
                    os.close(site)
            finally:
                os.close(folder)
    finally:
        os.close(parent)
    validate_maps(index, objects)
    encoded = json.dumps(
        index, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    require(len(encoded) <= MAX_INDEX_BYTES, "Fixture index exceeds byte limit")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=archive.parent, prefix="fixture-archive-", delete=False
    ) as stream:
        pending = Path(stream.name)
        try:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=stream, compresslevel=1, mtime=0
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed, mode="w|", format=tarfile.USTAR_FORMAT
                ) as bundle:
                    add_member(bundle, "index.json", encoded)
                    for key, data in sorted(objects.items()):
                        add_member(bundle, "objects/" + key, data)
            stream.flush()
            os.replace(pending, archive)
        finally:
            if pending.exists():
                pending.unlink()
    return {
        "format": FORMAT,
        "archive_sha256": digest(archive.read_bytes()),
        "archive_bytes": archive.stat().st_size,
        "file_count": len(index["files"]),
        "object_count": len(objects),
        "reconstructed_bytes": sum(
            record["size"] for record in index["files"].values()
        ),
        "unique_bytes": sum(map(len, objects.values())),
        "roots": roots,
    }


def regular_members(stream):
    """Read our regular-member tar dialect, including its exact EOF boundary."""
    count = 0
    while True:
        header = stream.read(tarfile.BLOCKSIZE)
        require(len(header) == tarfile.BLOCKSIZE, "Truncated fixture archive header")
        if not any(header):
            require(
                stream.read(tarfile.BLOCKSIZE) == bytes(tarfile.BLOCKSIZE),
                "Invalid fixture archive terminator",
            )
            trailing = 0
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                trailing += len(block)
                require(
                    trailing <= tarfile.RECORDSIZE and not any(block),
                    "Unexpected archive trailing data",
                )
            return
        member = tarfile.TarInfo.frombuf(header, "utf-8", "strict")
        require(member.type == tarfile.REGTYPE, "Unexpected nonregular archive member")
        maximum = MAX_INDEX_BYTES if member.name == "index.json" else MAX_FILE_BYTES
        require(
            0 <= member.size <= maximum, "Fixture archive member exceeds byte limit"
        )
        count += 1
        require(count <= MAX_FILES + 1, "Fixture archive exceeds member limit")
        data = stream.read(member.size)
        require(len(data) == member.size, "Truncated fixture archive member")
        padding = stream.read((-member.size) % tarfile.BLOCKSIZE)
        require(
            len(padding) == (-member.size) % tarfile.BLOCKSIZE and not any(padding),
            "Invalid fixture archive padding",
        )
        yield member, data


def write_output(root: int, parts: list[str], data: bytes) -> None:
    directories = []
    parent = root
    try:
        for name in parts[:-1]:
            try:
                os.mkdir(name, mode=0o755, dir_fd=parent)
            except FileExistsError:
                pass
            parent = open_directory(Path(name), parent)
            directories.append(parent)
        descriptor = os.open(
            parts[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=parent,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
    finally:
        for directory in reversed(directories):
            os.close(directory)


def decode_and_reconstruct(
    archive: Path, directory: Path, roots: list[str], expected_sha256: str
) -> dict:
    """Validate the entire transport before creating exact regular output files."""
    roots = root_names(roots)
    require(
        isinstance(expected_sha256, str) and SHA256.fullmatch(expected_sha256),
        "Invalid fixture archive digest",
    )
    descriptor = os.open(archive, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    objects = {}
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(
            stat.S_ISREG(before.st_mode)
            and before.st_size <= MAX_UNIQUE_BYTES + MAX_INDEX_BYTES + MAX_FILES * 1024,
            "Fixture archive must be a bounded regular file",
        )
        actual = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            actual.update(block)
        require(
            actual.hexdigest() == expected_sha256, "Fixture archive digest mismatch"
        )
        stream.seek(0)
        index = None
        with gzip.GzipFile(fileobj=stream, mode="rb") as compressed:
            for member, data in regular_members(compressed):
                if index is None:
                    require(
                        member.name == "index.json", "Unexpected fixture archive index"
                    )
                    index = decode_json(data)
                    require(
                        index.get("roots") == roots,
                        "Fixture archive root ownership mismatch",
                    )
                    expected = index_objects(index)
                    continue
                require(
                    member.name.startswith("objects/"),
                    "Unexpected fixture archive member",
                )
                key = member.name.removeprefix("objects/")
                require(
                    key in expected and member.name == "objects/" + key,
                    "Unexpected fixture object",
                )
                require(key not in objects, "Duplicate fixture archive member")
                require(member.size == expected[key], "Fixture object size mismatch")
                require(digest(data) == key, "Fixture object digest mismatch")
                objects[key] = data
        require(index is not None, "Fixture archive index is missing")
        after = os.fstat(stream.fileno())
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "Fixture archive changed while reading",
        )
    validate_maps(index, objects)
    directory.mkdir(parents=True, exist_ok=True)
    parent = open_directory(directory)
    folders = {}
    try:
        # Hosted artifact downloads also retain build logs in each fixture root.
        # Preserve those files while reserving only the manifest and served tree.
        for root in roots:
            try:
                folder = open_directory(Path(root), parent)
            except FileNotFoundError:
                folders[root] = None
                continue
            folders[root] = folder
            for name in ("manifest.json", "site"):
                try:
                    os.stat(name, dir_fd=folder, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise ValueError("Preserve existing fixture destination")
        for root in roots:
            if folders[root] is None:
                os.mkdir(root, mode=0o755, dir_fd=parent)
                folders[root] = open_directory(Path(root), parent)
        # Every object and both complete maps have passed validation before any
        # output creation. Exclusive leaves and directory descriptors prevent
        # overwriting existing files or following namespace links while writing.
        for name, record in sorted(
            index["files"].items(), key=lambda item: item[0].endswith("/manifest.json")
        ):
            parts = name.split("/")
            write_output(folders[parts[0]], parts[1:], objects[record["sha256"]])
    finally:
        for folder in folders.values():
            if folder is not None:
                os.close(folder)
        os.close(parent)
    return {
        "format": FORMAT,
        "archive_sha256": expected_sha256,
        "roots": roots,
        "file_count": len(index["files"]),
        "object_count": len(objects),
        "reconstructed_bytes": sum(
            record["size"] for record in index["files"].values()
        ),
    }


def unpack(
    archive: Path, directory: Path, roots: list[str], expected_sha256: str
) -> dict:
    try:
        return decode_and_reconstruct(archive, directory, roots, expected_sha256)
    except (EOFError, tarfile.TarError) as error:
        raise ValueError("Invalid fixture archive encoding") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("pack", "unpack"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--root", required=True, action="append")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    try:
        if args.operation == "pack":
            receipt = pack(args.directory, args.root, args.archive)
        else:
            receipt = unpack(args.archive, args.directory, args.root, args.sha256)
    except (ValueError, OSError, EOFError, tarfile.TarError) as error:
        print(f"Fixture archive failed: {error}")
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

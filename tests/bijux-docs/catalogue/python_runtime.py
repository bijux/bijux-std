"""Install an isolated CPython recipe for catalogue verification, not publication."""

from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[3]
VERSION = "3.14.4"
UV_VERSION = "0.11.17"
REQUEST = "cpython-" + VERSION


def require(condition, message):
    if not condition:
        raise ValueError(message)


def destination(value):
    path = value.absolute()
    require(
        path.resolve().is_relative_to((ROOT / "artifacts").resolve()),
        "Catalogue interpreter must remain under repository artifacts",
    )
    require(
        not any(parent.is_symlink() for parent in (path, *path.parents)),
        "Catalogue interpreter destination must use ordinary directories",
    )
    require(
        not path.exists() or (path.is_dir() and not any(path.iterdir())),
        "Preserve existing interpreter contents; select a fresh artifact path",
    )
    return path


def observe(python, directory):
    executable = Path(python).resolve(strict=True)
    require(
        executable.is_relative_to(directory.resolve()),
        "Selected catalogue interpreter escaped its installed recipe",
    )
    code = (
        "import json,sys; print(json.dumps(dict(version=list(sys.version_info[:3]), "
        "implementation=sys.implementation.name, prefix=sys.prefix, "
        "base_prefix=sys.base_prefix, executable=sys.executable)))"
    )
    result = subprocess.run(
        [str(executable), "-B", "-I", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    require(
        actual["version"] == [3, 14, 4] and actual["implementation"] == "cpython",
        "Catalogue interpreter must be exact CPython 3.14.4",
    )
    require(
        Path(actual["prefix"]).resolve() == Path(actual["base_prefix"]).resolve()
        and Path(actual["base_prefix"]).resolve().is_relative_to(directory.resolve())
        and Path(actual["executable"]).resolve() == executable,
        "Catalogue interpreter must belong to the selected standalone recipe",
    )
    actual["executable_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    actual["verification_only"] = True
    actual["publication_approval"] = False
    return actual


def install(value, uv):
    directory = destination(value)
    require(
        not any(
            name in os.environ
            for name in ("UV_PYTHON_DOWNLOADS_JSON_URL", "UV_PYTHON_INSTALL_MIRROR")
        ),
        "Catalogue interpreter recipe rejects alternative download authorities",
    )
    result = subprocess.run(
        [uv, "--version"], capture_output=True, text=True, check=True
    )
    require(
        result.stdout.split()[:2] == ["uv", UV_VERSION],
        "Catalogue interpreter requires exact uv 0.11.17",
    )
    cache = ROOT / "artifacts/bijux-docs/catalogue/interpreter-cache"
    scratch = ROOT / "artifacts/bijux-docs/catalogue/interpreter-scratch"
    for path in (cache, scratch):
        require(
            not any(parent.is_symlink() for parent in (path, *path.parents)),
            "Catalogue interpreter installer storage must use ordinary paths",
        )
        path.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "UV_PYTHON_INSTALL_DIR": str(directory),
        "UV_CACHE_DIR": str(cache),
        "TMPDIR": str(scratch),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    subprocess.run(
        [
            uv,
            "--no-config",
            "python",
            "install",
            "--no-bin",
            "--no-registry",
            "--install-dir",
            str(directory),
            REQUEST,
        ],
        env=env,
        check=True,
    )
    selected = subprocess.run(
        [
            uv,
            "--no-config",
            "python",
            "find",
            "--no-project",
            "--system",
            "--managed-python",
            "--no-python-downloads",
            "--resolve-links",
            REQUEST,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    actual = observe(selected.stdout.strip(), directory)
    actual["uv_version"] = UV_VERSION
    actual["request"] = REQUEST
    actual["recipe_source_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    (directory / "python-path.txt").write_text(
        str(Path(actual["executable"]).resolve()) + "\n"
    )
    (directory / "recipe.json").write_text(json.dumps(actual, indent=2) + "\n")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--uv", default="uv")
    options = parser.parse_args()
    print(json.dumps(install(options.root, options.uv), sort_keys=True))


if __name__ == "__main__":
    main()

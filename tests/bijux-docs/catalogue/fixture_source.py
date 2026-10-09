"""Create owned source fixtures from immutable reviewed catalogue inputs."""

from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import textwrap


def create_fixture(repository, root):
    RECIPE_FIXTURES = Path(__file__).resolve().parent / "fixtures/committed-catalogue"
    assert not root.exists()
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    SHARED = root / ".bijux/shared/bijux-docs"
    shutil.copytree(repository / "shared/bijux-docs", SHARED)
    recipe_spec = importlib.util.spec_from_file_location(
        "bijux_fixture_recipe", SHARED / "security/catalogue_recipe.py"
    )
    recipe = importlib.util.module_from_spec(recipe_spec)
    recipe_spec.loader.exec_module(recipe)
    for name in recipe.GENERATOR:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RECIPE_FIXTURES / name, path)
    (root / "mkdocs.shared.yml").write_bytes(
        (RECIPE_FIXTURES / "mkdocs.shared.yml").read_bytes()
    )
    (root / "mkdocs.yml").write_text(
        textwrap.dedent("""
    INHERIT: mkdocs.shared.yml
    site_name: Source-backed catalogue verification
    site_url: !ENV [SITE_URL, https://bijux.io/bijux-masterclass/]
    repo_name: bijux/bijux-masterclass
    repo_url: https://github.com/bijux/bijux-masterclass
    nav:
      - Home: index.md
      - Python: python-programming/index.md
    exclude_docs: |
      /overrides/
      /hooks/
    """)
    )
    for name, content in {
        "programs/README.md": "# Catalogue\n\n[Python](python-programming/index.md)\n",
        "programs/python-programming/README.md": "# Python\n\n[Course](course/index.md)\n",
        "programs/python-programming/course/mkdocs.yml": "site_name: Source course\nnav:\n  - Home: index.md\n  - Lesson: lesson.md\n",
        "programs/python-programming/course/course-book/index.md": "# Source course\n\n[Lesson](lesson.md)\n",
        "programs/python-programming/course/course-book/lesson.md": "# Source lesson\n\nLiteral original text.\n",
        "stock.yml": "site_name: Tracked configuration control\nsite_url: https://bijux.io/bijux-masterclass/\ndocs_dir: reader\ntheme:\n  name: material\n  custom_dir: docs/overrides\n  font: false\nplugins:\n  - search\n",
        "reader/index.md": "# Tracked reader\n",
        ".gitignore": "artifacts/\n/docs/index.md\n/docs/python-programming/\n__pycache__/\n",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "docs/hooks").mkdir(parents=True)
    shutil.copy2(
        RECIPE_FIXTURES / "docs/hooks/publish_site_assets.py",
        root / "docs/hooks/publish_site_assets.py",
    )
    subprocess.run(
        [
            sys.executable,
            str(SHARED / "tooling/scripts/project_bijux_docs.py"),
            str(root),
            str(SHARED),
        ],
        check=True,
        env={
            **os.environ,
            "BIJUX_DOCS_SOURCE_MODE": "local-verification",
            "BIJUX_STD_LOCAL_VERIFY": "1",
        },
    )
    # The stock control is a separate tracked docs source and uses identical admitted
    # native assets; it must not become an unplanned catalogue document.
    shutil.copytree(root / "docs/assets", root / "reader/assets")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("config", "user.name", "Bijux verification")
    git("config", "user.email", "verification@bijux.invalid")
    git(
        "add",
        ".gitignore",
        ".bijux",
        "mkdocs.yml",
        "mkdocs.shared.yml",
        "stock.yml",
        "programs",
        "scripts",
        "docs",
        "reader",
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "commit",
            "-qm",
            "test(docs): bind synthetic catalogue originals",
        ],
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_DATE": "2020-01-02T03:04:05+00:00",
            "GIT_COMMITTER_DATE": "2021-02-03T04:05:06+00:00",
        },
    )
    producer = recipe.shared_module(SHARED / "security/producer_authority.py")
    inputs = producer.repository_files(root)
    generator = recipe.captured_generator(
        root,
        {
            k: v
            for k, v in inputs.items()
            if k in recipe.GENERATOR
            or k in {"mkdocs.yml", "mkdocs.shared.yml"}
            or k.startswith("programs/")
        },
    )
    plan = generator.build_plan(
        {
            k: v
            for k, v in inputs.items()
            if k in recipe.GENERATOR
            or k in {"mkdocs.yml", "mkdocs.shared.yml"}
            or k.startswith("programs/")
        },
        environment={},
    )
    for name, data in plan.output_bytes().items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    context = recipe.derive(root, SHARED, recipe.RECIPE)
    return root

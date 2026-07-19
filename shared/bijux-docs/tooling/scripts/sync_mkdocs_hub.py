#!/usr/bin/env python3
"""Synchronize the canonical Bijux hub into an inherited MkDocs config."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def load_hub_links(shared_root: Path) -> list[dict[str, str]]:
    path = shared_root / "config/hub-links.json"
    links = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(links, list) or not links:
        raise RuntimeError(f"{path}: expected a non-empty list")

    keys: set[str] = set()
    for index, link in enumerate(links, start=1):
        if not isinstance(link, dict):
            raise RuntimeError(f"{path}: entry {index} must be an object")
        if set(link) != {"key", "label", "url"}:
            raise RuntimeError(f"{path}: entry {index} must contain key, label, and url")
        if not all(isinstance(link[field], str) and link[field] for field in link):
            raise RuntimeError(f"{path}: entry {index} contains an empty value")
        if link["key"] in keys:
            raise RuntimeError(f"{path}: duplicate key {link['key']}")
        if not link["url"].startswith("https://"):
            raise RuntimeError(f"{path}: entry {index} URL must use https")
        keys.add(link["key"])
    return links


def render_hub_links(links: list[dict[str, str]]) -> list[str]:
    rendered = ["    hub_links:\n"]
    for link in links:
        rendered.extend(
            (
                f"      - key: {link['key']}\n",
                f"        label: {link['label']}\n",
                f"        url: {link['url']}\n",
            )
        )
    return rendered


def leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def synchronize_shared_config(config_path: Path, links: list[dict[str, str]]) -> bool:
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)

    extra_index = next((index for index, line in enumerate(lines) if line == "extra:\n"), None)
    if extra_index is None:
        raise RuntimeError(f"{config_path}: missing top-level extra mapping")

    extra_end = next(
        (
            index
            for index in range(extra_index + 1, len(lines))
            if lines[index].strip() and leading_spaces(lines[index]) == 0
        ),
        len(lines),
    )
    bijux_index = next(
        (
            index
            for index in range(extra_index + 1, extra_end)
            if lines[index] == "  bijux:\n"
        ),
        None,
    )
    if bijux_index is None:
        raise RuntimeError(f"{config_path}: missing extra.bijux mapping")

    bijux_end = next(
        (
            index
            for index in range(bijux_index + 1, extra_end)
            if lines[index].strip() and leading_spaces(lines[index]) <= 2
        ),
        extra_end,
    )
    hub_index = next(
        (
            index
            for index in range(bijux_index + 1, bijux_end)
            if lines[index] == "    hub_links:\n"
        ),
        None,
    )

    replacement = render_hub_links(links)
    if hub_index is None:
        insert_index = next(
            (
                index + 1
                for index in range(bijux_index + 1, bijux_end)
                if lines[index].startswith("    theme_key:")
            ),
            bijux_end,
        )
        updated = lines[:insert_index] + replacement + lines[insert_index:]
    else:
        hub_end = next(
            (
                index
                for index in range(hub_index + 1, bijux_end)
                if lines[index].strip() and leading_spaces(lines[index]) <= 4
            ),
            bijux_end,
        )
        updated = lines[:hub_index] + replacement + lines[hub_end:]

    content = "".join(updated)
    original = "".join(lines)
    if content == original:
        return False

    config_path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    repo_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    if len(sys.argv) > 2:
        shared_root = Path(sys.argv[2]).resolve()
    elif (repo_root / "shared/bijux-docs").is_dir():
        shared_root = repo_root / "shared/bijux-docs"
    else:
        shared_root = repo_root / ".bijux/shared/bijux-docs"

    config_path = repo_root / "mkdocs.shared.yml"
    links = load_hub_links(shared_root)
    changed = synchronize_shared_config(config_path, links)
    status = "updated" if changed else "current"
    print(f"Bijux MkDocs hub {status}: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

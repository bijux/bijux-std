#!/usr/bin/env python3
"""Build real Material documents from canonical shared inputs for browser tests."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import material.extensions.emoji
import pymdownx.superfences
import yaml

from fixtures.diagram_trust import authored_sources as diagram_trust_authored_sources
from fixtures.diagram_trust import pages as diagram_trust_pages

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "artifacts/bijux-docs"
MERMAID_SHA256 = "3a93016a73dc82ba890d919f9bbb176f3da9d98341650c0b517f2595cc68fef8"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.6.0/dist/mermaid.min.js"
READER_CODE = (
    'def inspect_checkpoint(reader):\n    descriptor = "'
    + "boundary-" * 6
    + 'input"\n    return reader(descriptor)\n'
)
READER_HEADERS = ["Platform", "Compiler", "Data", "Owner", "Boundary", "Final column"]
READER_ROWS = [["Linux", "Clang", "Owned input", "Reader", "Local surface", "TARGET_FINAL_COLUMN"], ["Darwin", "LLVM", "Source bytes", "Author", "Native region", "Checkpoint preserved"]]



def digest_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def vendor(shared: Path, baseline: dict) -> Path:
    contract = baseline.get("diagram", {})
    expected = contract.get("sha256", MERMAID_SHA256)
    canonical = shared / "assets" / contract.get("vendor", "assets/javascripts/vendor/mermaid-11.6.0.min.js").removeprefix("assets/")
    if contract and not canonical.is_file():
        raise ValueError("Missing baseline-owned Mermaid asset; legacy CDN fallback is not admitted")
    target = canonical if canonical.exists() else ARTIFACTS / "cache/mermaid-11.6.0.min.js"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with urllib.request.urlopen(MERMAID_URL, timeout=60) as response:
            target.write_bytes(response.read())
    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        raise ValueError("Mermaid asset differs from the admitted baseline digest")
    return target


def write_page(docs: Path, relative: str, title: str, body: str = "") -> None:
    path = docs / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{body or 'Production shell reading and navigation fixture.'}\n")


def content(docs: Path, scenario: str) -> list[dict]:
    diagram_trust_pages(docs)
    write_page(docs, "index.md", "Bijux reference" if scenario in {"hub", "rtl"} else "Product overview")
    if scenario == "empty":
        return [{"Home": "index.md"}]
    nav = [{"Home": "index.md"}]
    write_page(docs, "links.md", "Authored link intent", '''<p><a id="link-ordinary" href="https://outside.example/ordinary" rel="external nofollow" referrerpolicy="no-referrer">Ordinary external reader</a></p>
<p><a id="link-new-tab" href="https://outside.example/new-tab" target="_blank" rel="sponsored opener">Authored new tab</a></p>
<p><a id="link-explicit-self" href="https://outside.example/self" target="_self">Authored same window</a></p>
<p><a id="link-named" href="https://outside.example/named" target="research-window">Named research window</a></p>
<p><a id="link-download" href="../reader-report.txt" download="authored-report.txt">Reader report</a></p>
<p><a id="link-privacy" href="https://outside.example/privacy" target="_blank" rel="noreferrer nofollow" referrerpolicy="strict-origin">Private authored tab</a></p>
<p><a id="link-described" href="https://outside.example/described" target="_blank" aria-label="Authored accessible name" aria-describedby="authored-link-description">Named resource</a><span id="authored-link-description">Authored resource context</span></p>
<p><a id="link-internal" href="../platform/start/">Internal document</a></p>
<p><a id="link-hash" href="#authored-heading">Local heading</a></p>
<p><a id="link-mail" href="mailto:reader@example.invalid">Email reader</a></p>
<p><a id="link-phone" href="tel:+441234567890">Call reader</a></p>

## Authored heading

Return through history without rewriting the native destination.
''')
    (docs / "reader-report.txt").write_text("Authored reader report bytes.\n")
    nav.append({"Links": "links.md"})
    names = ["Platform", "Projects", "Handbook", "Knowledge", "Repository"]
    for label in names:
        section = label.lower()
        write_page(docs, f"{section}/index.md", f"{label} overview", "[Getting started](start.md)\n\n[Details overview](details/index.md)")
        write_page(docs, f"{section}/start.md", f"{label} getting started")
        write_page(docs, f"{section}/details/index.md", f"{label} details overview")
        write_page(docs, f"{section}/details/leaf.md", f"{label} leaf destination", "Known-answer fixture search phrase: resilient navigation.\n\n## Detailed heading\n\nReturn to this topic through a direct deep link.")
        nav.append({label: [{"Overview": f"{section}/index.md"}, {"Getting started": f"{section}/start.md"}, {"Details": [{"Overview": f"{section}/details/index.md"}, {"Leaf destination": f"{section}/details/leaf.md"}]}]})
    write_page(docs, "reading.md", "Rich reading reference", '''## Code and tabs

=== "Python"

    ```python
    print("resilient navigation")
    ```

=== "Rust"

    ```rust
    println!("resilient navigation");
    ```

??? note "Reader disclosure"

    Important nested reading content remains available.

## Scientific table

| Sample | Measurement | Units |
| --- | ---: | --- |
| Control | 42 | reads |

## Diagram

```mermaid
flowchart LR
  accTitle: Reader navigation
  accDescr: A reader follows the overview to a detailed document.
  Overview --> Detail
```

## Long content

AnIdentifierThatIsIntentionallyLongToExerciseReadableScientificContentAcrossSmallScreensAndEnlargedTextWithoutLosingTheMeaningfulEnding.
''')
    write_page(docs, "diagram-safety.md", "Diagram trust boundaries", r'''These inputs preserve their authored source when the renderer cannot admit them.

```mermaid
flowchart LR
  A["<img src='https://diagram-resource.invalid/pixel' />"] --> B
```

```mermaid
flowchart LR
  A --> B
  style A fill:\75rl(https://diagram-resource.invalid/style)
```

```mermaid
%%{init: {"securityLevel": "loose", "themeCSS": "@import url(https://diagram-resource.invalid/theme)"}}%%
flowchart LR
  A --> B
```

```mermaid
flowchart LR
  A["Local<br/>label"] --> B["Reader"]
  classDef emphasis fill:#ffffff,stroke:#123456,stroke-width:2px
  class A emphasis
```
''')
    nav.append({"Reading reference": "reading.md"})
    write_page(docs, "reader-code.md", "Code boundary reference", "A reader can inspect the final token without moving the entire document sideways.\n\n## Boundary example\n\n```python linenums=\"1\"\n" + READER_CODE + "```\n")
    table = "| " + " | ".join(READER_HEADERS) + " |\n| " + " | ".join(["---"] * len(READER_HEADERS)) + " |\n"
    table += "\n".join("| " + " | ".join(row) + " |" for row in READER_ROWS)
    write_page(docs, "reader-table.md", "Table boundary reference", "Each checkpoint keeps its original row, column and header relationships.\n\n## Checkpoint matrix\n\n" + table)
    nav.extend([{"Code boundary reference": "reader-code.md"}, {"Table boundary reference": "reader-table.md"}])
    return nav


def config(baseline: dict, registry: list[dict], identity: str, docs: Path, site: Path, base_url: str, route: str, scenario: str) -> dict:
    theme = baseline["theme"]
    extensions = []
    for extension in baseline["required_markdown_extensions"]:
        settings = {
            "toc": {"permalink": True},
            "pymdownx.superfences": {"custom_fences": [{"name": "mermaid", "class": baseline.get("diagram", {}).get("fence_class", "mermaid"), "format": pymdownx.superfences.fence_code_format}]},
            "pymdownx.tabbed": {"alternate_style": True},
            "pymdownx.highlight": {"anchor_linenums": True},
            "pymdownx.tasklist": {"custom_checkbox": True},
            "pymdownx.emoji": {"emoji_index": material.extensions.emoji.twemoji, "emoji_generator": material.extensions.emoji.to_svg},
        }.get(extension)
        extensions.append({extension: settings} if settings else extension)
    return {
        "site_name": "Bijux" if identity == "bijux" else identity,
        "site_url": base_url.rstrip("/") + route,
        "repo_url": "https://github.com/bijux/bijux.github.io" if identity == "bijux" else f"https://github.com/bijux/{identity}",
        "repo_name": "bijux/bijux.github.io" if identity == "bijux" else f"bijux/{identity}",
        "docs_dir": str(docs), "site_dir": str(site), "strict": baseline["strict"],
        "exclude_docs": "/overrides/",
        "use_directory_urls": baseline["use_directory_urls"],
        "theme": {"name": theme["name"], "language": theme["language"], "custom_dir": str(docs / "overrides"), "logo": theme["logo"], "favicon": theme["favicon"], "font": theme["font"], "icon": {"repo": theme["repository_icon"]}, "features": theme["required_features"], "palette": [
            {"media": "(prefers-color-scheme)", "primary": "teal", "accent": "cyan", "toggle": {"icon": "material/theme-light-dark", "name": "Switch to light mode"}},
            {"media": "(prefers-color-scheme: light)", "scheme": "default", "primary": "teal", "accent": "cyan", "toggle": {"icon": "material/moon-waning-crescent", "name": "Switch to dark mode"}},
            {"media": "(prefers-color-scheme: dark)", "scheme": "slate", "primary": "teal", "accent": "cyan", "toggle": {"icon": "material/white-balance-sunny", "name": "Switch to system mode"}},
        ]},
        "plugins": baseline["required_plugins"], "markdown_extensions": extensions,
        "extra_css": baseline["extra_css"], "extra_javascript": baseline["extra_javascript"],
        "copyright": baseline["copyright"],
        "extra": {"homepage": base_url.rstrip("/") + route, "bijux": {"repository": identity, "nav_mode": "default", "theme_key": "bijux:theme", "hub_links": registry}},
        "nav": content(docs, scenario),
    }


def build(shared: Path, output: Path, base_url: str) -> None:
    diagram_sources = diagram_trust_authored_sources()
    original = digest_tree(shared)
    compiler = shared / "tooling/material/build_runtime.py"
    subprocess.run([sys.executable, "-B", str(compiler), "--shared-root", str(shared), "--check"], check=True, stdout=subprocess.DEVNULL)
    baseline = json.loads((shared / "config/mkdocs-baseline.json").read_text())
    raw_registry = json.loads((shared / "config/hub-links.json").read_text())
    entries = raw_registry if isinstance(raw_registry, list) else raw_registry["hub_links"]
    registry = [{**entry, "url": base_url.rstrip("/") + ("/" if entry["key"] == "bijux" else f"/{entry['key']}/")} for entry in entries]
    scenarios = [(entry["key"], "/" if entry["key"] == "bijux" else f"/{entry['key']}/", "hub" if entry["key"] == "bijux" else "project") for entry in entries]
    scenarios += [("bijux-core", "/fixtures/empty/", "empty"), ("bijux-core", "/fixtures/long-registry/", "long"), ("bijux-core", "/fixtures/native-header/", "native-header"), ("bijux", "/fixtures/rtl/", "rtl")]
    output.mkdir(parents=True, exist_ok=True)
    site_root = output / "site"
    if site_root.exists():
        shutil.rmtree(site_root)
    site_root.mkdir()
    vendor_file = vendor(shared, baseline)
    for identity, route, scenario in scenarios:
        label = "hub" if route == "/" else route.strip("/").replace("/", "-")
        work = output / "inputs" / label
        if work.exists():
            shutil.rmtree(work)
        docs = work / "docs"
        (docs / "assets").mkdir(parents=True)
        shutil.copytree(shared / "assets", docs / "assets", dirs_exist_ok=True)
        shutil.copytree(shared / "partials", docs / "overrides/partials", ignore=shutil.ignore_patterns("main.html"))
        shutil.copy2(shared / "partials/main.html", docs / "overrides/main.html")
        if scenario == "native-header":
            # Exercise the installed Material header, not a fabricated control surrogate.
            (docs / "overrides/partials/header.html").unlink()
        shutil.copytree(shared / "styles", docs / "assets/styles", ignore=shutil.ignore_patterns("README.md"))
        shutil.copytree(shared / "scripts", docs / "assets/javascripts/shell", ignore=shutil.ignore_patterns("README.md", "external-links.js"))
        shutil.copy2(shared / "scripts/nav-sync.js", docs / "assets/javascripts/navigation-sync.js")
        shutil.copy2(shared / "scripts/mermaid-init.js", docs / "assets/javascripts/mermaid-init.js")
        (docs / "assets/javascripts/vendor").mkdir(parents=True, exist_ok=True)
        vendor_destination = docs / baseline.get("diagram", {}).get("vendor", "assets/javascripts/vendor/mermaid-11.6.0.min.js")
        if vendor_file.resolve() != vendor_destination.resolve():
            shutil.copy2(vendor_file, vendor_destination)
        shutil.copy2(shared / "scripts/external-links.js", docs / "assets/javascripts/external-links.js")
        scenario_registry = registry
        if scenario == "long":
            scenario_registry = [{**entry, "label": entry["label"] + " scientific platform"} for entry in registry] + [{"key": "bijux-reference", "label": "Reference extension", "url": base_url + "/fixtures/empty/"}, {"key": "bijux-research", "label": "Research extension", "url": base_url + "/reading/"}]
        cfg = config(baseline, scenario_registry, identity, docs, work / "site", base_url, route, scenario)
        if scenario == "rtl":
            cfg["theme"]["direction"] = "rtl"
        cfg_path = work / "mkdocs.yml"
        cfg_path.write_text(yaml.dump(cfg, sort_keys=False))
        log_path = output / f"build-{label}.log"
        with log_path.open("w") as log:
            subprocess.run([str(Path(__import__('sys').executable)), "-m", "mkdocs", "build", "--strict", "--clean", "--config-file", str(cfg_path)], stdout=log, stderr=subprocess.STDOUT, check=True)
        destination = site_root / route.strip("/")
        shutil.copytree(work / "site", destination, dirs_exist_ok=True)
    if original != digest_tree(shared):
        raise RuntimeError("Canonical source changed while fixture rendering; rebuild a coherent candidate")
    git_root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, text=True).strip())
    owns_source = git_root == ROOT and shared.is_relative_to(ROOT)
    if owns_source:
        source_path = str(shared.relative_to(ROOT))
        owns_source = bool(subprocess.check_output(["git", "ls-files", "--", source_path], cwd=ROOT, text=True).strip())
    manifest = {
        "schema": 1, "source_root": str(shared), "source_files": original,
        "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() if owns_source else None,
        "source_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--", source_path], cwd=ROOT, text=True).strip()) if owns_source else None,
        "source_identity": "tracked repository source" if owns_source else "untracked artifact source; file digests are authoritative",
        "toolchain": {name: importlib.metadata.version(name) for name in ["mkdocs", "mkdocs-material", "mkdocs-autorefs", "pymdown-extensions"]},
        "vendor": {"url": None if baseline.get("diagram") else MERMAID_URL, "sha256": baseline.get("diagram", {}).get("sha256", MERMAID_SHA256), "source": str(vendor_file)},
        "base_url": base_url, "scenarios": [{"identity": identity, "route": route, "kind": scenario} for identity, route, scenario in scenarios],
        "registry_adaptation": "Canonical keys/order; URLs point to generated local consumers. Long-registry scenario expands labels and adds two entries.",
        "diagram_fixture": {"authored_sources": diagram_sources},
        "reader_fixture": {"code": READER_CODE, "code_sha256": hashlib.sha256(READER_CODE.encode()).hexdigest(), "table_headers": READER_HEADERS, "table_rows": READER_ROWS},
        "site_files": digest_tree(site_root),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Strict generated fixtures: {len(scenarios)} scenarios, {len(manifest['site_files'])} output files, {site_root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "shared/bijux-docs")
    parser.add_argument("--output", type=Path, default=ARTIFACTS / "generated")
    parser.add_argument("--base-url", default="http://127.0.0.1:4173")
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve(), args.base_url.rstrip("/"))

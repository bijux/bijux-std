"""Keep the ordinary navigation oracle bound to the authored fixture graph."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
GENERATED = ROOT / "tests/bijux-docs/generated"
sys.path.insert(0, str(GENERATED))
spec = importlib.util.spec_from_file_location("navigation_fixture_builder", GENERATED / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class NavigationDestinationsTests(unittest.TestCase):
    def test_expected_destinations_match_every_authored_branch_and_heading(self):
        parent = ROOT / "artifacts/bijux-docs/navigation-graph-tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            docs = Path(directory)
            navigation = builder.content(docs, "hub")
            actual = []

            def visit(items, ancestors=()):
                for item in items:
                    for label, value in item.items():
                        if isinstance(value, list):
                            visit(value, (*ancestors, label))
                            continue
                        route = "/" if value == "index.md" else "/" + value.removesuffix(".md").removesuffix("/index") + "/"
                        actual.append({"label": label, "ancestors": list(ancestors), "route": route,
                                       "heading": (docs / value).read_text().splitlines()[0].removeprefix("# ")})

            visit(navigation)
            helper = (ROOT / "tests/bijux-docs/ui/generated-specs/navigation/destinations.js").read_text()
            literal = helper.split("const destinations = ", 1)[1].split(";\nconst escaped", 1)[0]
            expected = json.loads(literal)
            self.assertEqual(expected, actual)
            self.assertEqual(len({item["route"] for item in actual}), len(actual))


if __name__ == "__main__":
    unittest.main()

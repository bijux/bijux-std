"""Keep the ordinary navigation oracle bound to the authored fixture graph."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
GENERATED = ROOT / "tests/bijux-docs/generated"
sys.path.insert(0, str(GENERATED))
spec = importlib.util.spec_from_file_location("navigation_fixture_builder", GENERATED / "build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def expected_destinations():
    helper = (ROOT / "tests/bijux-docs/ui/generated-specs/navigation/destinations.js").read_text()
    return json.loads(helper.split("const destinations = ", 1)[1].split(";\nconst escaped", 1)[0])


def partition(destinations, owners=None):
    module = ROOT / "tests/bijux-docs/ui/generated-specs/navigation/destination-partitions.js"
    script = "const {partitionDestinations}=require(process.argv[1]);console.log(JSON.stringify(partitionDestinations(JSON.parse(process.argv[2]),process.argv[3]===undefined?undefined:JSON.parse(process.argv[3]))));"
    command = ["node", "-e", script, str(module), json.dumps(destinations)]
    if owners is not None:
        command.append(json.dumps(owners))
    return subprocess.run(command, capture_output=True, text=True)


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
            expected = expected_destinations()
            self.assertEqual(expected, actual)
            self.assertEqual(len({item["route"] for item in actual}), len(actual))

    def test_bounded_owners_cover_every_authored_destination_exactly_once(self):
        graph = expected_destinations()
        result = partition(graph)
        self.assertEqual(result.returncode, 0, result.stderr)
        groups = json.loads(result.stdout)
        self.assertEqual([group["name"] for group in groups],
                         ["root documents", "section destinations", "nested destinations"])
        claimed = [destination for group in groups for destination in group["destinations"]]
        self.assertCountEqual(claimed, graph)
        self.assertEqual(len({item["route"] for item in claimed}), len(graph))
        for group in groups:
            self.assertLessEqual(len(group["destinations"]), 10)
            self.assertTrue(all(len(item["ancestors"]) == group["depth"] for item in group["destinations"]))

    def test_missing_duplicate_or_moved_ownership_cannot_qualify_graph(self):
        graph = expected_destinations()
        for owners in (
                [{"name": "root documents", "depth": 0}, {"name": "section destinations", "depth": 1}],
                [{"name": "root documents", "depth": 0}, {"name": "root documents", "depth": 1}, {"name": "nested destinations", "depth": 2}],
                [{"name": "root documents", "depth": 0}, {"name": "section destinations", "depth": 0}, {"name": "nested destinations", "depth": 2}],
                [{"name": "root documents", "depth": 0}, {"name": "section destinations", "depth": 1}, {"name": "nested destinations", "depth": 3}]):
            with self.subTest(owners=owners):
                self.assertNotEqual(partition(graph, owners).returncode, 0)

    def test_duplicate_unknown_or_unbounded_graph_requires_new_ownership(self):
        graph = expected_destinations()
        for changed in (
                [*graph, graph[0]],
                [*graph, {"route": "/unknown/", "ancestors": ["A", "B", "C"]}],
                [*graph, *({"route": f"/article-{index}/", "ancestors": []} for index in range(4))]):
            with self.subTest(graph=changed):
                self.assertNotEqual(partition(changed).returncode, 0)


if __name__ == "__main__":
    unittest.main()

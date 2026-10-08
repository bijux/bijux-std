"""Qualify complete browser coverage from explicitly assigned shard receipts."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def aggregate(inventories: list[dict], reports: list[dict]) -> dict:
    require(bool(inventories) and bool(reports), "Inventory and shard evidence are required")
    scopes = {item["qualification_scope"]: item for item in inventories}
    require(len(scopes) == len(inventories), "Duplicate inventory scope")
    source = inventories[0]["source_identity"]
    require(all(item["source_identity"] == source for item in inventories), "Inventory source mismatch")
    seen: set[tuple[str, str]] = set()
    projects_seen: set[tuple[str, str]] = set()
    versions: dict[str, str] = {}
    for report in reports:
        scope = report["qualification_scope"]
        require(scope in scopes, "Unexpected qualification scope")
        inventory = scopes[scope]
        require(report["status"] == "passed" and report["qualification_kind"] == "assigned_engine_shard", "Failed or non-shard evidence")
        require(report["source_identity"] == source, "Shard source mismatch")
        require(report["fixture_identity"] == inventory["fixture_identity"], "Shard bundle mismatch")
        require(report["canonical_projects"] == inventory["canonical_projects"], "Canonical project contract mismatch")
        names = report["assigned_project_names"]
        require(bool(names) and len(set(names)) == len(names), "Invalid assigned projects")
        canonical = {project["name"]: project for project in inventory["canonical_projects"]}
        require(set(names) <= set(canonical), "Unknown assigned project")
        expected = [case for case in inventory["cases"] if case["project"] in names]
        require(report["expected_cases"] == expected, "Shard case inventory mismatch")
        require(len(report["results"]) == len(expected) > 0, "Missing or extra executions")
        cases = {case["id"]: case for case in expected}
        require(len(cases) == len(expected), "Duplicate canonical case ID")
        for name in names:
            require((scope, name) not in projects_seen, "Duplicate project shard")
            projects_seen.add((scope, name))
            count = canonical[name]["count"]
            require(sum(case["project"] == name for case in expected) == count, "Canonical count mismatch")
            require(report["projects"].get(name) == {"expected": count, "executed": count, "passed": count, "failed": 0, "skipped": 0}, "Project execution count mismatch")
        require(set(report["projects"]) == set(names), "Unexpected project execution")
        for result in report["results"]:
            identity = result["case_id"]
            require(identity in cases and result["project"] == cases[identity]["project"], "Unknown case execution")
            require((scope, identity) not in seen, "Duplicate case execution")
            seen.add((scope, identity))
            require(result["status"] == "passed" and result["retry"] == 0 and not result["errors"], "Failed, skipped or retried case")
            values = [entry["description"] for entry in result["annotations"] if entry["type"] == "browser-version"]
            require(len(values) == 1 and bool(values[0]), "Missing or ambiguous engine version")
            engine = canonical[result["project"]]["engine"]
            require(engine not in versions or versions[engine] == values[0], "Engine version mismatch")
            versions[engine] = values[0]
        junit = report["junit"]
        data = Path(junit["path"]).read_bytes()
        require(hashlib.sha256(data).hexdigest() == junit["sha256"], "JUnit digest mismatch")
        xml = ET.fromstring(data)
        require(xml.tag == "testsuites", "Unexpected JUnit root")
        require(int(xml.get("tests", "-1")) == len(expected), "JUnit total mismatch")
        require(all(int(xml.get(key, "-1")) == 0 for key in ("failures", "skipped", "errors")), "JUnit failure or incomplete status")
        require(len(xml.findall(".//testcase")) == len(expected) and not xml.findall(".//failure") and not xml.findall(".//skipped") and not xml.findall(".//error"), "JUnit case status mismatch")
        xml_cases: list[tuple[str, str]] = []
        for suite in xml.findall("testsuite"):
            project = suite.get("hostname")
            require(project in names and int(suite.get("tests", "-1")) == len(suite.findall("testcase")), "JUnit project count mismatch")
            xml_cases.extend((project, case.get("name")) for case in suite.findall("testcase"))
        require(sorted(xml_cases) == sorted((case["project"], case["title"]) for case in expected), "JUnit case identity mismatch")
    expected_all = {(scope, case["id"]) for scope, inventory in scopes.items() for case in inventory["cases"]}
    expected_projects = {(scope, project["name"]) for scope, inventory in scopes.items() for project in inventory["canonical_projects"]}
    require(seen == expected_all and projects_seen == expected_projects, "Coverage is incomplete")
    return {"schema": 1, "status": "passed", "qualification_kind": "complete_engine_matrix", "source_identity": source,
            "scopes": {scope: {"case_count": len(item["cases"]), "project_count": len(item["canonical_projects"]), "fixture_identity": item["fixture_identity"]} for scope, item in scopes.items()},
            "executed_cases": len(seen), "engine_versions": versions,
            "limits": ["Headless engines do not establish physical mobile, actual zoom or human assistive review."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", action="append", required=True, type=Path)
    parser.add_argument("--report", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    inputs = args.inventory + args.report
    try:
        reports = []
        for path in args.report:
            report = json.loads(path.read_text())
            if "junit" in report:
                report["junit"]["path"] = str((path.parent / report["junit"]["path"]).resolve())
            reports.append(report)
        receipt = aggregate([json.loads(path.read_text()) for path in args.inventory], reports)
    except (ValueError, KeyError, TypeError, OSError, ET.ParseError) as error:
        receipt = {"schema": 1, "status": "failed", "error": str(error)}
    receipt["inputs"] = [{"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in inputs if path.exists()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Browser aggregate: {receipt['status']}: {receipt.get('executed_cases', receipt.get('error'))}")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

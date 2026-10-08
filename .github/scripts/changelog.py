#!/usr/bin/env python3
"""Validate and project repository-owned pull request change records offline."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import subprocess
import sys

TYPES = {"feat", "fix", "perf", "docs", "ci", "build", "test", "refactor", "chore", "revert"}
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
TITLE = re.compile(r"([a-z]+)\(([a-z][a-z0-9]*(?:-[a-z0-9]+)*)\)(!)?: (\S.*)\Z")
DISPOSABLE = re.compile(r"(?:^|-)(?:iteration|phase|task|step|goal|draft|tmp|temp|wip|misc)(?:[0-9]+)?(?:-|$)")
FIELDS = {"schema", "pr", "title", "type", "scope", "summary", "details", "status", "merged_at", "breaking"}
START = "<!-- bijux:pr-history:start -->"
END = "<!-- bijux:pr-history:end -->"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict:
    require(not path.is_symlink() and path.is_file(), f"Expected ordinary file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    require(isinstance(value, dict), f"Expected JSON object: {path}")
    return value


def line(value: object, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"Empty or invalid {field}")
    require(value == value.strip() and not any(ord(char) < 32 for char in value), f"{field} must be one trimmed text line")
    return value


def positive(value: object) -> bool:
    return type(value) is int and value > 0


def configuration(root: Path) -> dict:
    directory = root / "changelog"
    require(not directory.is_symlink(), "Changelog directory cannot be a symlink")
    config = read_json(directory / "config.json")
    require(set(config) == {"schema", "repository", "mode"}, "Unknown or missing changelog configuration keys")
    require(type(config["schema"]) is int and config["schema"] == 1, "Unsupported changelog schema")
    require(isinstance(config["repository"], str) and bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"])), "Invalid GitHub repository identity")
    require(config["mode"] in {"pr-history", "append"}, "Changelog mode must be pr-history or append")
    return config


def validate_record(record: dict, relative: Path, draft: bool = False) -> None:
    require(set(record) == FIELDS, f"Unknown or missing record keys: {relative}")
    require(type(record["schema"]) is int and record["schema"] == 1, "Unsupported record schema")
    require(positive(record["pr"]) or (draft and record["pr"] is None), "Record needs an actual positive PR number; only explicit draft validation admits null")
    require(record["type"] in TYPES, "Unknown Conventional Commit type")
    require(isinstance(record["scope"], str) and bool(SLUG.fullmatch(record["scope"])), "Invalid record scope")
    require(len(relative.parts) == 2 and relative.parts[0] == record["scope"] and relative.suffix == ".json" and bool(SLUG.fullmatch(relative.stem)) and not DISPOSABLE.search(relative.stem), "Fragment path must be <scope>/<durable-intent>.json")
    for field in ("title", "summary"):
        line(record[field], field)
    require(isinstance(record["details"], list) and bool(record["details"]), "Details need at least one meaningful text line")
    for detail in record["details"]:
        line(detail, "detail")
    require(record["status"] in {"pending", "merged"}, "Status must be pending or merged")
    require(type(record["breaking"]) is bool, "Breaking must be a JSON boolean")
    stamp = record["merged_at"]
    if record["status"] == "pending":
        require(stamp is None, "Pending review cannot claim a merge timestamp")
        parsed = TITLE.fullmatch(record["title"])
        require(bool(parsed), "Pending PR title must be type(scope): subject")
        require(parsed.group(1) == record["type"] and parsed.group(2) == record["scope"], "Pending title type/scope must match the record")
        require(bool(parsed.group(3)) == record["breaking"], "Pending title breaking marker must match the record")
    elif stamp is not None:
        require(isinstance(stamp, str) and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp)), "Merge timestamp must be verified UTC YYYY-MM-DDTHH:MM:SSZ")
        observed = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        require(observed <= datetime.now(timezone.utc), "Merged history cannot claim a future merge timestamp")
    require(record["pr"] is not None or record["status"] == "pending", "Merged records cannot have unknown PR identity")


def records(root: Path, draft: bool = False) -> list[tuple[Path, dict]]:
    configuration(root)
    directory = root / "changelog/fragments"
    require(directory.is_dir() and not directory.is_symlink(), "Missing ordinary changelog/fragments directory")
    result, numbers = [], set()
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), f"Fragment paths cannot be symlinks: {path}")
        if path.is_dir():
            continue
        relative = path.relative_to(directory)
        require(path.suffix == ".json", f"Unexpected fragment file: {relative}")
        record = read_json(path)
        validate_record(record, relative, draft)
        number = record["pr"]
        require(number is None or number not in numbers, f"Duplicate PR record: {number}")
        if number is not None:
            numbers.add(number)
        result.append((path, record))
    return result


def markdown(text: str) -> str:
    # Authored records contain plain text, not active HTML or arbitrary destinations.
    escaped = html.escape(text, quote=False)
    return re.sub(r"([\\`*{}\[\]()_#!|])", r"\\\1", escaped)


def project(root: Path) -> str:
    config = configuration(root)
    values = [record for _, record in records(root)]
    pending = sorted((r for r in values if r["status"] == "pending"), key=lambda r: r["pr"], reverse=True)
    dated = sorted((r for r in values if r["status"] == "merged" and r["merged_at"] is not None), key=lambda r: (r["merged_at"], r["pr"]), reverse=True)
    undated = sorted((r for r in values if r["status"] == "merged" and r["merged_at"] is None), key=lambda r: r["pr"], reverse=True)
    lines = ["## Pull request history", "", "Records describe reviewed repository changes. Pending review is not a merged or published release.", ""]
    foundation = root / "changelog/FOUNDATION.md"
    if foundation.exists() or foundation.is_symlink():
        require(foundation.is_file() and not foundation.is_symlink(), "Foundation notes must be an ordinary repository-owned file")
        lines += ["Audited legacy material and source distinctions are retained in [foundation notes](changelog/FOUNDATION.md).", ""]
    for heading, group in (("Pending review", pending), ("Merged pull requests", dated), ("Merged pull requests with unverified dates", undated)):
        if not group:
            continue
        lines += [f"### {heading}", ""]
        if heading.endswith("unverified dates"):
            lines += ["Ordered by PR identity; no verified merge chronology is claimed.", ""]
        for record in group:
            prefix = record["merged_at"] + " — " if record["merged_at"] else ""
            url = f"https://github.com/{config['repository']}/pull/{record['pr']}"
            lines += [f"#### {prefix}[#{record['pr']}]({url}) — {markdown(record['title'])}", "", markdown(record["summary"]), ""]
            if record["breaking"]:
                lines += ["**Breaking change.**", ""]
            lines += ["- " + markdown(detail) for detail in record["details"]] + [""]
    if not values:
        lines += ["No pull request records are present.", ""]
    body = "\n".join(lines)
    if config["mode"] == "pr-history":
        return "# Changelog\n\nRepository change history for `" + config["repository"] + "`, projected from authoritative `changelog/fragments/` records.\n\n" + body
    path = root / "CHANGELOG.md"
    require(not path.is_symlink() and path.is_file(), "Append mode requires an ordinary existing CHANGELOG.md")
    original = path.read_text(encoding="utf-8")
    require(original.count(START) == 1 and original.count(END) == 1 and original.index(START) < original.index(END), "Append mode needs one correctly ordered PR history marker pair")
    before, rest = original.split(START)
    _, after = rest.split(END)
    return before + START + "\n\n" + body + END + after


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def check_pr(root: Path, number: int, base: str, title: str | None = None) -> None:
    require(positive(number), "Current PR number must be positive")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", base)), "PR base must be the actual full commit SHA")
    require(git(root, "cat-file", "-t", base) == "commit", "PR base is not an available commit")
    inventory = records(root)
    current = [(path, record) for path, record in inventory if record["pr"] == number]
    require(len(current) == 1, f"Missing exact current PR record: {number}")
    path, record = current[0]
    require(record["status"] == "pending", "Current review record must remain pending")
    require(title is None or record["title"] == title, "Record title does not match the actual PR title")
    changed = set(git(root, "diff", "--name-only", "--diff-filter=AM", base, "--", "changelog/fragments").splitlines())
    require(path.relative_to(root).as_posix() in changed, "Current PR must add or modify its own tracked fragment against the actual base")
    retained = {record["pr"] for _, record in inventory}
    for old_path in git(root, "ls-tree", "-r", "--name-only", base, "--", "changelog/fragments").splitlines():
        old = json.loads(git(root, "show", f"{base}:{old_path}"), object_pairs_hook=unique_object)
        require(positive(old.get("pr")) and old["pr"] in retained, "An existing PR record was removed or reassigned")


def check_event(root: Path, event_path: Path, event_name: str, repository: str) -> str:
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)), "Missing actual workflow repository")
    config_path = root / "changelog/config.json"
    if not config_path.exists() and not config_path.is_symlink() and not (root / "changelog").is_symlink():
        require(repository != "bijux/bijux-std", "bijux-std requires its changelog contract")
        return "Not adopted: no repository-owned changelog/config.json; no PR-history qualification claimed"
    config = configuration(root)
    require(config["repository"] == repository, "Changelog repository differs from the workflow repository")
    records(root)
    if event_name == "pull_request":
        event = read_json(event_path)
        pr = event.get("pull_request")
        require(isinstance(pr, dict), "Missing pull_request event payload")
        require(positive(event.get("number")) and event["number"] == pr.get("number") and positive(pr.get("number")), "Ambiguous event PR identity")
        line(pr.get("title"), "actual PR title")
        check_pr(root, pr["number"], pr.get("base", {}).get("sha", ""), pr.get("title"))
    else:
        require(event_name in {"push", "merge_group", "workflow_dispatch"}, "Unsupported workflow event")
    require((root / "CHANGELOG.md").is_file() and not (root / "CHANGELOG.md").is_symlink() and (root / "CHANGELOG.md").read_text(encoding="utf-8") == project(root), "CHANGELOG projection differs; reconcile fragments then render --write")
    return "Changelog records, exact review identity where applicable, and projection passed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--draft", action="store_true", help="Admit unknown PR identity only before opening review")
    render = commands.add_parser("render")
    destination = render.add_mutually_exclusive_group()
    destination.add_argument("--write", action="store_true", help="Write the governed CHANGELOG.md projection")
    destination.add_argument("--check", action="store_true")
    destination.add_argument("--output", type=Path)
    assign = commands.add_parser("assign")
    assign.add_argument("--fragment", type=Path, required=True)
    assign.add_argument("--pr", type=int, required=True)
    review = commands.add_parser("check-pr")
    review.add_argument("--number", type=int, required=True)
    review.add_argument("--base", required=True)
    review.add_argument("--title")
    event = commands.add_parser("check-event")
    event.add_argument("--event-file", type=Path, required=True)
    event.add_argument("--event-name", required=True)
    event.add_argument("--repository", required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "validate":
            count = len(records(root, args.draft))
            print(f"Validated {count} PR change records" + (" (draft identity permitted; not merge qualification)" if args.draft else ""))
        elif args.command == "assign":
            require(positive(args.pr), "Actual PR number must be positive")
            path = root / args.fragment
            inventory = records(root, True)
            require(any(p == path for p, _ in inventory), "Assignment must name an existing ordinary fragment inside this repository")
            require(all(r["pr"] != args.pr for _, r in inventory), "PR number already assigned")
            record = read_json(path)
            require(record["pr"] is None and record["status"] == "pending", "Only an unassigned pending record can be bound")
            record["pr"] = args.pr
            validate_record(record, path.relative_to(root / "changelog/fragments"))
            path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        elif args.command == "check-pr":
            check_pr(root, args.number, args.base, args.title)
        elif args.command == "check-event":
            print(check_event(root, args.event_file, args.event_name, args.repository))
        else:
            text = project(root)
            if args.check:
                path = root / "CHANGELOG.md"
                require(not path.is_symlink() and path.is_file() and path.read_text(encoding="utf-8") == text, "CHANGELOG projection differs; render --write")
            else:
                path = root / "CHANGELOG.md" if args.write else root / (args.output or Path("artifacts/changelog/CHANGELOG.md"))
                require(not path.is_symlink(), "Projection destination cannot be a symlink")
                if not args.write:
                    require(path.resolve().is_relative_to(root / "artifacts"), "Preview output must stay inside repository artifacts/")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                print(f"Projected changelog: {path}")
        return 0
    except (ValueError, TypeError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

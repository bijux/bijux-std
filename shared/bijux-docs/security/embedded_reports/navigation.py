"""Preserve full-document navigation across source-owned CSP partitions."""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, unquote
from .contract import AdmissionError, canonical, digest


def partitions(records):
    return {
        record["path"]: digest(canonical(record["capability"])) for record in records
    }


def normalize(content, path, base, ownership):
    current = ownership.get(path, "ordinary")
    lines = [0]
    for index, char in enumerate(content):
        if char == "\n":
            lines.append(index + 1)
    changes = []
    root = urlsplit(base)

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            values = dict(attrs)
            if len(values) != len(attrs):
                raise AdmissionError(
                    "Ambiguous anchor attributes at CSP partition boundary"
                )
            href = values.get("href")
            if not href or values.get("target"):
                return
            target = urlsplit(urljoin(base + path, href))
            if (target.scheme, target.netloc) != (
                root.scheme,
                root.netloc,
            ) or not target.path.startswith(root.path):
                return
            name = unquote(target.path[len(root.path) :])
            if "\\" in name or any(part in {".", ".."} for part in name.split("/")):
                raise AdmissionError("Ambiguous capability navigation route")
            name = name + "index.html" if not name or name.endswith("/") else name
            destination = ownership.get(name, "ordinary")
            if current == destination:
                return
            start = lines[self.getpos()[0] - 1] + self.getpos()[1]
            original = self.get_starttag_text()
            # Material 9.7.7 handle() excludes any truthy target. _self keeps
            # native same-window, keyboard, history and no-script navigation.
            if "target" in values:
                raise AdmissionError(
                    "Empty target attribute must be reviewed before normalization"
                )
            replacement = original[:-1] + ' target="_self">'
            changes.append(
                {
                    "offset": start,
                    "original": original,
                    "replacement": replacement,
                    "destination": name,
                    "source_partition": current,
                    "destination_partition": destination,
                }
            )

    parser = Links(convert_charrefs=True)
    parser.feed(content)
    result = content
    for change in reversed(changes):
        start = change["offset"]
        result = (
            result[:start]
            + change["replacement"]
            + result[start + len(change["original"]) :]
        )
    return {
        "path": path,
        "input_sha256": digest(content.encode()),
        "normalized_sha256": digest(result.encode()),
        "changes": changes,
        "normalized_html": result,
    }


def restore(content, record, base, ownership):
    if digest(content.encode()) != record["normalized_sha256"]:
        raise AdmissionError("Normalized capability anchor output differs")
    result = content
    shift = sum(len(c["replacement"]) - len(c["original"]) for c in record["changes"])
    for change in reversed(record["changes"]):
        shift -= len(change["replacement"]) - len(change["original"])
        start = change["offset"] + shift
        if result[start : start + len(change["replacement"])] != change["replacement"]:
            raise AdmissionError("Capability link position/content differs")
        result = (
            result[:start]
            + change["original"]
            + result[start + len(change["replacement"]) :]
        )
    expected = normalize(result, record["path"], base, ownership)
    if {
        k: v for k, v in expected.items() if k != "normalized_html"
    } != record or digest(result.encode()) != record["input_sha256"]:
        raise AdmissionError(
            "Capability link normalization lacks exact route-derived attribution"
        )
    return result

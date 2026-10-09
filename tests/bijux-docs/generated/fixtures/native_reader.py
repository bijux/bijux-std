"""Authored native and instant reader links share an asynchronously rendered corpus."""
from pathlib import Path


def pages(docs: Path) -> list[dict[str, str]]:
    sections = []
    for number, title in enumerate(("Reader entry", "Source inspection", "Document selection", "History return", "Context recovery")):
        lines = ["flowchart LR", f"  accTitle: {title}", "  accDescr: Reader checkpoints retain their original source and destination."]
        for index in range(20):
            lines.append(f'  N{index}["Checkpoint {index + 1}"] --> N{index + 1}["Checkpoint {index + 2}"]')
        sections.append(f"## {title}\n\n```mermaid\n" + "\n".join(lines) + "\n```\n")
    paragraphs = "\n\n".join(
        f"Reader context {index + 1} keeps the authored document, diagram source and destination together. "
        "Returning through browser history preserves the reader's visible departure point."
        for index in range(12)
    )
    body = "# Native diagram history reference\n\n" + "\n".join(sections) + "\n## Departure context\n\n" + paragraphs
    body += '\n\n<p><a id="reader-native-next" href="../reader-table/" target="_self">Native checkpoint reference</a></p>\n'
    body += '<p><a id="reader-instant-next" href="../reader-table/">Instant checkpoint reference</a></p>\n'
    (docs / "reader-diagrams.md").write_text(body)
    return [{"Native diagram history reference": "reader-diagrams.md"}]

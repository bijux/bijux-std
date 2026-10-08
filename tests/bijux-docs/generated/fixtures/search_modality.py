"""Authored editable reference surfaces rendered by the shared production shell."""
from pathlib import Path


def pages(docs: Path) -> list[dict]:
    (docs / "search-modality.md").write_text("""# Editable reading reference

Character input belongs to the focused authored field.

<label for="reader-notes">Reader notes</label>
<textarea id="reader-notes" rows="3"></textarea>

<div role="textbox" aria-label="Editable reader notes" contenteditable="true" tabindex="0"></div>

[Ordinary reading destination](reading.md)
""")
    return [{"Editable reading reference": "search-modality.md"}]

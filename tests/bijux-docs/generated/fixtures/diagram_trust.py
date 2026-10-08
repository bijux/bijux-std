"""Authored diagram inputs exercising scientific meaning and renderer isolation."""

from pathlib import Path


def fence(source: str) -> str:
    return f"```mermaid\n{source}\n```\n"


def pages(docs: Path) -> None:
    scientific = [
        ('Comparison meaning', 'flowchart LR\n  accTitle: Scientific comparison\n  accDescr: Compare x with y and probability alpha with beta.\n  A["Comparison x < y; probability α ≤ β"] --> B["Scientific result"]'),
        ('Nested scientific labels', 'flowchart LR\n  accTitle: Nested scientific reading\n  accDescr: A cohort contains control and treatment with a labelled comparison.\n  subgraph Cohort["Nested cohort α ≤ β"]\n    A["Control x < y"] --> B["Treatment"]\n  end\n  classDef scientific fill:#ffffff,stroke:#123456,stroke-width:2px;\n  class A scientific;'),
        ('State meaning', 'stateDiagram-v2\n  accTitle: Scientific review states\n  accDescr: A sample moves from measured to reviewed.\n  [*] --> Measured\n  Measured --> Reviewed: α ≤ β\n  Reviewed --> [*]'),
    ]
    resources = [
        ('Structured renderer configuration', '---\nconfig:\n  securityLevel: loose\n  themeCSS: "@import url(https://diagram.example.invalid/theme.css);"\n---\nflowchart LR\n  A --> B'),
        ('Resource nested in mathematical markup', 'flowchart LR\n  A["<math><mtext><img src=\'https://diagram.example.invalid/math.png\' onerror=\'window.diagramAttack=true\'></mtext></math>"] --> B'),
        ('Image shape resource', 'flowchart LR\n  A@{ img: "https://diagram.example.invalid/image.png" } --> B'),
    ]
    healthy = 'flowchart LR\n  accTitle: Healthy isolation checkpoint\n  accDescr: A valid diagram remains readable after a rejected input.\n  A["Healthy checkpoint"] --> B["Reader continues"]'
    excessive_text = 'flowchart LR\n  A["' + 'bounded-authored-text-' * 2400 + '"] --> B'
    excessive_edges = 'flowchart LR\n' + '\n'.join(f'  n{i} --> n{i + 1}' for i in range(501))
    limits = [
        ('Malformed diagram', 'flowchart LR\n  A["Malformed input" -->'),
        ('Healthy after malformed input', healthy),
        ('Text exceeding the 50000 character budget', excessive_text),
        ('Healthy after excessive text', healthy),
        ('Edges exceeding the 500 edge budget', excessive_edges),
        ('Healthy after excessive edges', healthy),
    ]
    for name, title, examples in [
        ('diagram-scientific.md', 'Scientific diagram meaning', scientific),
        ('diagram-resources.md', 'Diagram resource boundaries', resources),
        ('diagram-limits.md', 'Diagram failure isolation', limits),
    ]:
        body = f'# {title}\n\nEach example retains its exact authored source for reader inspection.\n\n'
        body += '\n'.join(f'## {heading}\n\n{fence(source)}' for heading, source in examples)
        (docs / name).write_text(body)

"""Render a Markdown document to PDF via headless Edge.

There is no pandoc or LaTeX on this machine, so the route is
Markdown -> styled HTML -> Edge's --print-to-pdf. Run it with uv so the
`markdown` package does not have to be installed globally:

    uv run --with markdown python scripts/md2pdf.py docs/tp/informe.md

The stylesheet targets an academic submission: A4, serif body, visible table
rules, and page breaks before top-level sections.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }

html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }

body {
  font-family: "Georgia", "Cambria", "Times New Roman", serif;
  font-size: 10.5pt;
  line-height: 1.5;
  color: #1a1a1a;
  margin: 0;
}

h1 {
  font-size: 19pt;
  line-height: 1.25;
  margin: 0 0 2mm 0;
  padding-bottom: 3mm;
  border-bottom: 2px solid #1a1a1a;
}

h2 {
  font-size: 13.5pt;
  margin: 9mm 0 3mm 0;
  padding-bottom: 1.5mm;
  border-bottom: 1px solid #b0b0b0;
  page-break-after: avoid;
}

h3 {
  font-size: 11.5pt;
  margin: 6mm 0 2mm 0;
  page-break-after: avoid;
}

h2 + h3 { margin-top: 4mm; }

p { margin: 0 0 3mm 0; orphans: 3; widows: 3; }

strong { font-weight: 700; }

hr {
  border: 0;
  border-top: 1px solid #d0d0d0;
  margin: 7mm 0;
}

table {
  border-collapse: collapse;
  width: 100%;
  margin: 3mm 0 5mm 0;
  font-size: 9.5pt;
  page-break-inside: avoid;
}

th, td {
  border: 1px solid #999;
  padding: 1.6mm 2.4mm;
  text-align: left;
  vertical-align: top;
}

th { background: #ececec; font-weight: 700; }

tbody tr:nth-child(even) { background: #f8f8f8; }

code {
  font-family: "Consolas", "Courier New", monospace;
  font-size: 9pt;
  background: #f1f1f1;
  padding: 0.3mm 1mm;
  border-radius: 2px;
}

pre {
  background: #f6f6f6;
  border: 1px solid #ddd;
  border-left: 3px solid #888;
  padding: 3mm;
  font-size: 9pt;
  overflow-x: auto;
  page-break-inside: avoid;
}

pre code { background: none; padding: 0; }

blockquote {
  margin: 3mm 0;
  padding: 2mm 4mm;
  border-left: 3px solid #999;
  background: #fafafa;
  font-size: 10pt;
}

blockquote p:last-child { margin-bottom: 0; }

ul, ol { margin: 0 0 3mm 0; padding-left: 7mm; }
li { margin-bottom: 1.2mm; }

a { color: #1a1a1a; text-decoration: none; }

/* Each numbered section starts on a fresh page, but not the first one. */
h2 { page-break-before: auto; }
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def find_browser() -> str:
    """Return the first Chromium-family browser found, or exit with a message."""
    for candidate in EDGE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("msedge", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("No Edge or Chrome found — cannot print to PDF.")


def render(source: Path, output: Path) -> None:
    """Convert ``source`` Markdown to a PDF at ``output``."""
    text = source.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list", "nl2br"],
        output_format="html5",
    )
    html = TEMPLATE.format(title=source.stem, css=CSS, body=body)

    # Edge needs a real file on disk and an absolute file:// URL.
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "doc.html"
        html_path.write_text(html, encoding="utf-8")
        browser = find_browser()
        output.parent.mkdir(parents=True, exist_ok=True)

        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output.resolve()}",
            html_path.resolve().as_uri(),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if not output.exists():
            sys.exit(
                f"Browser did not produce a PDF.\n"
                f"exit={result.returncode}\nstderr={result.stderr[:800]}"
            )

    size_kb = output.stat().st_size / 1024
    print(f"wrote {output}  ({size_kb:,.0f} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Markdown file to convert")
    parser.add_argument("-o", "--output", type=Path, help="output PDF path")
    args = parser.parse_args()

    if not args.source.exists():
        sys.exit(f"not found: {args.source}")
    output = args.output or args.source.with_suffix(".pdf")
    render(args.source, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

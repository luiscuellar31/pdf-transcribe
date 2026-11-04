# Working in this repository

A local tool that turns PDFs into Markdown next to each file, so agents read text instead of page images. One person uses it, on macOS 26 or later, where OCR is Apple Vision, and on Linux, where it is Tesseract. [README.md](README.md) explains what it does, how to install and use it, and its limits, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) how a PDF becomes Markdown; update them in the same commit whenever any of that changes.

## Code

- `pdf_transcribe.py` decides which pages use their own text, which go through OCR, and which are marked as having images, and writes the Markdown. On Linux it calls Tesseract; `vision_ocr.swift` only reads images with Vision on macOS.
- Python with its standard library, poppler, and Swift on macOS or Tesseract on Linux. Ask before adding a third-party package.
- Prefer readable code consistent with the code around it, even when it takes more lines. Comments explain why, not what.
- Everything in the repository is in English: code, identifiers, comments, commit messages, the tool's messages, the generated Markdown, and the docs. The PDFs it reads can be in Spanish or English, or in any language Vision detects.
- The tool never overwrites a `.md` it did not write.

## Checks

Before calling a change done, run the tests (`python3 -I -m unittest`) and transcribe a PDF with text and a scanned one. Use copies in a temporary folder, because the tool writes next to the PDF. If the change touches OCR on Linux, test it on Linux, for example in a Debian container with `poppler-utils`, `tesseract-ocr`, and `tesseract-ocr-spa`.

## Commits

Write commit messages in English using Conventional Commits:

```text
type(scope): imperative summary
type: imperative summary
```

Use a scope when the change belongs to one part of the tool: `ocr` for reading scanned pages, `images` for marking pages with images, or `markdown` for what the tool writes. Leave it out for a change across the tool or to the repository. Common types here are `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, and `chore`. Keep each commit about one logical change. Examples:

```text
feat: transcribe PDFs to Markdown next to each file
fix(markdown): keep the columns of a table apart
docs: explain how to install and use pdf-transcribe
```

Choose the type by who notices the change:

- `feat`, `fix`, and `perf` are for changes that the person using the tool notices: a new capability, corrected behavior, or faster work.
- Changes to tests, docs, and the repository's tooling use `test`, `docs`, `build`, `refactor`, or `chore`, even when they fix something.

Write the subject as the effect, not the mechanism, starting in lowercase and without a final period: `fix(ocr): read small print on scanned pages` rather than `fix(ocr): render pages at 200 dpi`.

After a blank line, the body explains the change in plain sentences, wrapped at 72 columns: first what happened before and why it was a problem, then what happens now and, when it is not obvious, how. Put commands, files, options, and values in backticks. A change whose subject says it all needs no body. For example:

```text
fix(images): stop marking every page for a template's logo

A logo drawn on every page of a template marked them all "with
images", so the mark no longer told the reader which pages to check
in the PDF.

An image drawn on at least three pages and on more than half of them
now counts as part of the template and marks none of them.
```

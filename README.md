# pdf-transcribe

Turns a PDF into Markdown and saves it next to the file: `report.pdf` → `report.md`. An agent can then read and search the text instead of opening each page as an image, which costs more tokens.

- Pages use the text the PDF carries.
- Pages with little text, such as scans or handwriting, also go through Apple Vision's OCR. Its reading is used only when it finds clearly more text than the PDF.
- Pages with large images are marked, so you can check them in the PDF when needed.
- If the Markdown already exists and is newer than the PDF, it is not made again.
- It never overwrites a `.md` the tool did not write.

## Requirements

Python 3.9 or later, with its standard library and no third-party packages. Also:

- macOS 26 or later, for Vision's document reader.
- poppler: `brew install poppler`.
- Swift, which comes with Xcode or its Command Line Tools. The first time it runs OCR, it builds `vision_ocr.swift` into `build/`.

## Installation

From the repository folder:

```bash
ln -s "$PWD/pdf_transcribe.py" ~/.local/bin/pdf-transcribe
```

`~/.local/bin` must be on the `PATH`.

## Usage

```bash
pdf-transcribe report.pdf [other.pdf ...]
```

It prints the path of each Markdown and how many pages went through OCR or have images. To redo one, delete the `.md` and run it again.

OCR takes under a second per page, although the first time Vision is used on a Mac it can take about a minute to load.

## The Markdown

```markdown
# report

Transcription of `report.pdf` made with pdf-transcribe: …

## Page 1

…

## Page 2 · with images

…

## Page 3 · OCR

…
```

"Page N" is the page of the PDF, not the printed one. To save tokens, the text loses the spaces that only line up columns: columns are left two spaces apart.

## Limits

- A page with at least 200 letters or digits does not go through OCR. If it also carries an image with text, that text is not read, but the page is marked "with images".
- Images under 2 square inches do not mark a page, nor do those repeated on more than half of the pages, such as logos and template backgrounds. Large decorative images, such as the shadow of a title on a slide, do mark it.
- Figures drawn as vectors, not as images, are not marked.
- A page that went through OCR is not marked "with images". Tables are read cell by cell, without their structure.
- Handwriting is read with errors, and handwritten formulas are barely understood.
- If the PDF is inside a repository, the `.md` sits next to it and can end up in a commit.

## Tests

```bash
python3 -I -m unittest
```

Also transcribe copies of a PDF with text and of a scanned one in a temporary folder, and compare the Markdown with the PDF.

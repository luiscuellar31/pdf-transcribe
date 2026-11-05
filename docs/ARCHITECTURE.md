# How pdf-transcribe works

pdf-transcribe is one Python script, [`pdf_transcribe.py`](../pdf_transcribe.py),
that runs poppler's command-line tools and an OCR engine: Apple Vision on
macOS, through the small Swift program [`vision_ocr.swift`](../vision_ocr.swift),
and Tesseract on Linux and Windows. It uses only Python's standard library.

On Windows, [`pdf-transcribe.cmd`](../pdf-transcribe.cmd) runs the script with
the `py` launcher, and the script expands wildcards such as `*.pdf` itself,
because cmd and PowerShell pass them on as typed.

## From PDF to Markdown

For each PDF, `transcribe()`:

1. Finds where its Markdown goes, and stops early when that Markdown is up to
   date (see [Writing safely](#writing-safely)).
2. Reads each page's own text with `pdftotext -layout`, which keeps columns and
   indents apart.
3. Sends pages with fewer than 200 letters or digits to OCR, since they may
   hold their content as an image or as strokes: a scan, handwriting.
   `pdftoppm` renders them in gray, at 200 dpi for Vision and 300 dpi for
   Tesseract, where each reads best. The OCR reading replaces the page's text
   only when it has more than twice its letters, so a page keeps real text of
   its own, and a typed header does not hide the handwriting under it.
4. Marks the pages that have images, from the table of `pdfimages -list`. An
   image counts when it covers at least 2 square inches of the page, unless it
   appears on three pages or more and on more than half of them, as a
   template's logo or background does. A page read by OCR is not marked, since
   its images were read with it.
5. Writes the Markdown: a title, a note on how it was made, and a section per
   page. Runs of three or more spaces become two, because `-layout` lines up
   columns with spaces that cost tokens and say nothing.

`vision_ocr.swift` reads every PNG in a folder with Vision's document reader,
which keeps the reading order of columns and boxes, and writes a `.txt` beside
each. It is built into `build/` on first use, and again whenever its source
changes. On Linux and Windows, Tesseract reads Spanish and English when both are
installed, else English alone.

## Where the Markdown goes

`markdown_path()` places it by `-o`, or by `PDF_TRANSCRIBE_OUTPUT` when `-o` is
not given:

- `beside`, the default: next to the PDF, with the PDF's name.
- `cache`: in the system's cache folder, `~/Library/Caches/pdf-transcribe` on
  macOS, `$XDG_CACHE_HOME/pdf-transcribe` on Linux, by default
  `~/.cache/pdf-transcribe`, or `%LOCALAPPDATA%\pdf-transcribe\Cache` on
  Windows, under the PDF's own folder path, with its drive on Windows, so PDFs
  with the same name never meet there.
- Anything else is a folder, created when missing, that holds the Markdown
  under the PDF's name.

Next to its PDF, the Markdown's note names the PDF alone. Anywhere else it names
the PDF's full path, so a reader can find the PDF, and so the tool can tell
which PDF a Markdown belongs to.

## Writing safely

- The note at the top of each Markdown says `made with pdf-transcribe`. A `.md`
  without it was not made by the tool, and is never overwritten.
- A Markdown whose note names another PDF, as when two PDFs with the same name
  go to one folder, is never overwritten either.
- A Markdown newer than its PDF is left as is.
- The Markdown is written to a `.partial` file first and then renamed, so an
  interrupted run never leaves half a Markdown that looks finished.

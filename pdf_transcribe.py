#!/usr/bin/env -S python3 -I
"""Transcribes PDFs to Markdown next to each file, so an agent reads text instead of page images.

    pdf-transcribe report.pdf [other.pdf ...]       writes report.md next to report.pdf

Pages keep the PDF's own text; pages with little of it, such as scans or handwriting, also go
through OCR: Apple Vision on macOS (vision_ocr.swift, built on first use), Tesseract elsewhere.
Pages with large images are marked, so a reader knows when to look at the page itself. A Markdown
newer than its PDF is left as is, and a .md this tool did not write is never overwritten. Needs
poppler (pdfinfo, pdftotext, pdfimages, pdftoppm), plus Swift on macOS or Tesseract elsewhere.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Apple Vision on macOS; elsewhere Tesseract, which reads worse.
VISION = sys.platform == "darwin"
OCR_ENGINE = "Apple Vision" if VISION else "Tesseract"
# Vision reads small print well at 200 dpi; Tesseract works best from 300 dpi up.
OCR_DPI = 200 if VISION else 300
MARK = "made with pdf-transcribe"
NOTE = (
    "Transcription of `{name}` " + MARK + ": the PDF's own text and, on pages with almost none, "
    "such as scans or handwriting, OCR by " + OCR_ENGINE + '. "Page N" is page N of the PDF, '
    'not the printed one. A page marked "OCR" may contain errors, and one marked "with images" has '
    "figures this text does not describe: to quote exactly or see a figure, check that page in the PDF."
)
# A page with fewer letters or digits than this may hold its content as an image or as drawn
# strokes (a scan, handwriting), so it also goes through OCR.
FEW_LETTERS = 200
# Smaller images, in square inches on the page, are icons or logos.
MIN_IMAGE_AREA = 2


def main():
    parser = argparse.ArgumentParser(description="Transcribe PDFs to Markdown next to each file.")
    parser.add_argument("pdfs", nargs="+", type=Path, metavar="pdf")
    failed = False
    for pdf in parser.parse_args().pdfs:
        try:
            print(transcribe(pdf))
        except subprocess.CalledProcessError as error:
            # The tool already printed why.
            print(f"{pdf}: {Path(error.cmd[0]).name} failed", file=sys.stderr)
            failed = True
        except (OSError, ValueError) as error:
            print(f"{pdf}: {error}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


def transcribe(pdf: Path) -> str:
    if not pdf.is_file():
        raise ValueError("does not exist")
    out = pdf.with_suffix(".md")
    if out.exists():
        if MARK not in out.read_text(encoding="utf-8", errors="replace")[:1000]:
            raise ValueError(f"{out.name} already exists and was not made by pdf-transcribe; left untouched")
        if out.stat().st_mtime >= pdf.stat().st_mtime:
            return f"{out} (already up to date)"

    texts = page_texts(pdf)
    short = {n for n, text in enumerate(texts, 1) if letters(text) < FEW_LETTERS}
    ocr_pages = set()
    for n, read in ocr(pdf, short).items():
        if ocr_wins(texts[n - 1], read):
            texts[n - 1] = read
            ocr_pages.add(n)
    images = pages_with_images(run(["pdfimages", "-list", str(pdf)]), len(texts)) - ocr_pages

    # Written aside and then moved, so an interrupted run never leaves a half Markdown that looks done.
    partial = out.with_name(out.name + ".partial")
    partial.write_text(markdown(pdf, texts, ocr_pages, images), encoding="utf-8")
    partial.replace(out)
    return f"{out}: {count_pages(len(texts))}, {len(ocr_pages)} with OCR, {len(images)} with images"


def count_pages(count: int) -> str:
    return f"{count} page" + ("s" if count != 1 else "")


def page_texts(pdf: Path) -> list[str]:
    """Each page's own text. -layout keeps columns and indents apart."""
    pages = int(re.search(r"^Pages:\s+(\d+)", run(["pdfinfo", str(pdf)]), re.MULTILINE)[1])
    # pdftotext ends each page with a form feed.
    texts = run(["pdftotext", "-layout", str(pdf), "-"]).split("\f")[:pages]
    return texts + [""] * (pages - len(texts))


def letters(text: str) -> int:
    return sum(char.isalnum() for char in text)


def ocr_wins(own: str, read: str) -> bool:
    """Whether the OCR reading replaces the page's own text: only when it finds clearly more."""
    return letters(read) > 2 * letters(own)


def ocr(pdf: Path, pages: set[int]) -> dict[int, str]:
    """The OCR reading of the given pages, by page number."""
    if not pages:
        return {}
    print(f"{pdf.name}: OCR of {count_pages(len(pages))} with little text…", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="pdf-transcribe-") as work:
        # shortcut: renders every page before reading them (2 to 5 MB each); read in batches if books of hundreds of scanned pages fill the disk.
        for n in pages:
            # In gray, the images stay light.
            run(["pdftoppm", "-r", str(OCR_DPI), "-gray", "-png", "-singlefile", "-f", str(n), "-l", str(n), str(pdf), f"{work}/{n}"])
        if VISION:
            run([str(vision_ocr()), work])
            return {n: Path(work, f"{n}.txt").read_text(encoding="utf-8") for n in pages}
        languages = tesseract_languages(run(["tesseract", "--list-langs"]))
        # debug_file drops notices such as "Detected 27 diacritics"; errors still show.
        options = ["-l", languages, "--dpi", str(OCR_DPI), "-c", "debug_file=/dev/null"]
        return {n: run(["tesseract", f"{work}/{n}.png", "stdout", *options]) for n in pages}


def tesseract_languages(listing: str) -> str:
    """Spanish and English for `tesseract -l`, from those `tesseract --list-langs` reports."""
    installed = set(listing.splitlines()[1:])
    # shortcut: reads Spanish and English only; add a language here when documents in it show up.
    return "+".join(language for language in ("spa", "eng") if language in installed) or "eng"


def vision_ocr() -> Path:
    """The OCR program, built again when its source changes."""
    source, program = HERE / "vision_ocr.swift", HERE / "build" / "vision-ocr"
    if not program.exists() or program.stat().st_mtime < source.stat().st_mtime:
        program.parent.mkdir(exist_ok=True)
        run(["swiftc", "-O", str(source), "-o", str(program)])
    return program


def pages_with_images(listing: str, page_count: int) -> set[int]:
    """Pages with an image large enough to carry content, from the table of `pdfimages -list`."""
    pages_of = defaultdict(set)  # image object → pages that draw it
    for row in listing.splitlines()[2:]:
        # page num type width height color comp bpc enc interp object ID x-ppi y-ppi size ratio
        fields = row.split()
        if len(fields) < 14 or fields[2] != "image":
            continue
        x_ppi, y_ppi = float(fields[12]), float(fields[13])
        if x_ppi and y_ppi and int(fields[3]) / x_ppi * int(fields[4]) / y_ppi >= MIN_IMAGE_AREA:
            pages_of[fields[10]].add(int(fields[0]))

    content = set()
    for pages in pages_of.values():
        # An image on most pages is a template's logo or background, not content.
        if len(pages) < 3 or len(pages) <= page_count / 2:
            content |= pages
    return content


def markdown(pdf: Path, texts: list[str], ocr_pages: set[int], images: set[int]) -> str:
    parts = [f"# {pdf.stem}", "", NOTE.format(name=pdf.name), ""]
    for n, text in enumerate(texts, 1):
        mark = " · OCR" if n in ocr_pages else " · with images" if n in images else ""
        parts += [f"## Page {n}{mark}", "", tidy(text) or "(no text)", ""]
    return "\n".join(parts)


def tidy(text: str) -> str:
    """The text without the padding -layout adds to line up columns: it costs tokens and says nothing."""
    lines = (re.sub(" {3,}", "  ", line.rstrip()) for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def run(command: list[str]) -> str:
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="replace").stdout


if __name__ == "__main__":
    main()

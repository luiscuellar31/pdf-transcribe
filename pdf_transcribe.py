#!/usr/bin/env -S python3 -I
"""Transcribes PDFs to Markdown, so an agent reads text instead of page images.

    pdf-transcribe report.pdf [other.pdf ...]       writes report.md next to report.pdf
    pdf-transcribe -o cache report.pdf              writes it in the cache; -o also takes a folder

Pages keep the PDF's own text; pages with little of it, such as scans or handwriting, also go
through OCR: Apple Vision on macOS (vision_ocr.swift, built on first use), Tesseract elsewhere.
Pages with large images are marked, so a reader knows when to look at the page itself. A Markdown
newer than its PDF is left as is, and a .md this tool did not write is never overwritten. Needs
poppler (pdfinfo, pdftotext, pdfimages, pdftoppm), plus Swift on macOS or Tesseract elsewhere.
"""

import argparse
import glob
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path, PurePath

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
    parser = argparse.ArgumentParser(description="Transcribe PDFs to Markdown.")
    parser.add_argument("pdfs", nargs="+", type=Path, metavar="pdf")
    parser.add_argument(
        "-o", "--output", metavar="WHERE", default=os.environ.get("PDF_TRANSCRIBE_OUTPUT") or "beside",
        help='where each Markdown goes: "beside" its PDF, "cache", or a folder; '
        "PDF_TRANSCRIBE_OUTPUT sets the default (beside)",
    )
    args = parser.parse_args()
    # cmd and PowerShell pass a wildcard such as *.pdf on as typed, where the shells of macOS and Linux expand it.
    pdfs = expand_wildcards(args.pdfs) if sys.platform == "win32" else args.pdfs
    failed = False
    for pdf in pdfs:
        try:
            print(transcribe(pdf, args.output))
        except subprocess.CalledProcessError as error:
            # The tool already printed why.
            print(f"{pdf}: {Path(error.cmd[0]).name} failed", file=sys.stderr)
            failed = True
        except (OSError, ValueError) as error:
            print(f"{pdf}: {error}", file=sys.stderr)
            failed = True
    sys.exit(1 if failed else 0)


def expand_wildcards(names: list[Path]) -> list[Path]:
    """The files each name matches, or the name itself when it holds no wildcard or matches nothing."""
    pdfs = []
    for name in map(str, names):
        # Windows file names cannot hold * or ?, so either one is a wildcard.
        matches = sorted(glob.glob(name)) if "*" in name or "?" in name else []
        pdfs += [Path(match) for match in matches or [name]]
    return pdfs


def transcribe(pdf: Path, output: str = "beside") -> str:
    if not pdf.is_file():
        raise ValueError("does not exist")
    out = markdown_path(pdf, output)
    # Away from its PDF, the Markdown names the PDF's full path, so a reader can still find it.
    source = Path(pdf.name) if out.parent.resolve() == pdf.parent.resolve() else pdf.resolve()
    if out.exists():
        head = out.read_text(encoding="utf-8", errors="replace")[:1000]
        if MARK not in head:
            raise ValueError(f"{out} already exists and was not made by pdf-transcribe; left untouched")
        # Two PDFs with the same name sent to one folder would otherwise share a Markdown.
        if f"`{source}` {MARK}" not in head:
            raise ValueError(f"{out} already exists for another PDF; left untouched")
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
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    partial.write_text(markdown(source, texts, ocr_pages, images), encoding="utf-8")
    partial.replace(out)
    return f"{out}: {count_pages(len(texts))}, {len(ocr_pages)} with OCR, {len(images)} with images"


def markdown_path(pdf: Path, output: str) -> Path:
    """Where the Markdown of a PDF goes: "beside" it, in the "cache", or in a folder."""
    if output == "beside":
        return pdf.with_suffix(".md")
    if output == "cache":
        # Under the PDF's own folder path, so PDFs with the same name never meet.
        return cache_folder() / without_anchor(pdf.resolve().with_suffix(".md"))
    return Path(output).expanduser() / pdf.with_suffix(".md").name


def without_anchor(path: PurePath) -> PurePath:
    r"""An absolute path made relative, keeping a Windows drive or network share as folders: C:\docs becomes C\docs."""
    return type(path)(path.anchor.strip("/\\:"), path.relative_to(path.anchor))


def cache_folder() -> Path:
    """This tool's folder in the system's cache, which the system may clear: the Markdown is made again then."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "pdf-transcribe"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "pdf-transcribe" / "Cache"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "pdf-transcribe"


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
        options = ["-l", languages, "--dpi", str(OCR_DPI), "-c", f"debug_file={os.devnull}"]
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


def markdown(source: Path, texts: list[str], ocr_pages: set[int], images: set[int]) -> str:
    parts = [f"# {source.stem}", "", NOTE.format(name=source), ""]
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

import os
import tempfile
import unittest
from pathlib import Path

import pdf_transcribe as tool

# A logo and a photo with its soft mask on page 1, and one image drawn on pages 2 to 4.
LISTING = """\
page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
--------------------------------------------------------------------------------------------
   1     0 image     111    36  rgb     3   8  jpeg   no         9  0   103   103 2.1K 18%
   1     1 image    1200   900  rgb     3   8  jpeg   no        12  0   150   150  80K 3.2%
   1     2 smask    1200   900  gray    1   8  image  no        12  0   150   150  10K 1.0%
   2     3 image     800   600  rgb     3   8  jpeg   no        30  0   200   200  20K 1.0%
   3     4 image     800   600  rgb     3   8  jpeg   no        30  0   200   200  20K 1.0%
   4     5 image     800   600  rgb     3   8  jpeg   no        30  0   200   200  20K 1.0%
"""


class PagesTest(unittest.TestCase):
    def test_ocr_replaces_the_text_only_when_it_finds_clearly_more(self):
        self.assertTrue(tool.ocr_wins("", "Plain language"))
        # A handwritten page under a typed header.
        self.assertTrue(tool.ocr_wins("Quiz, February 16", "Quiz, February 16\nLet A be a set with n elements"))
        self.assertFalse(tool.ocr_wins("Chapter 2", "Chapter 2"))
        self.assertFalse(tool.ocr_wins("", ""))

    def test_small_and_repeated_images_do_not_mark_a_page(self):
        self.assertEqual(tool.pages_with_images(LISTING, page_count=4), {1})
        # On 3 pages of 10 the image is content, not part of the template.
        self.assertEqual(tool.pages_with_images(LISTING, page_count=10), {1, 2, 3, 4})

    def test_tesseract_reads_spanish_and_english_when_installed(self):
        header = 'List of available languages in "/usr/share/tesseract-ocr/5/tessdata/" (3):\n'
        self.assertEqual(tool.tesseract_languages(header + "eng\nosd\nspa\n"), "spa+eng")
        self.assertEqual(tool.tesseract_languages(header + "eng\nosd\n"), "eng")

    def test_tidy_drops_padding_and_extra_blank_lines(self):
        self.assertEqual(tool.tidy("  Name        Age   \n\n\n\n  Ana         31"), "Name  Age\n\n  Ana  31")

    def test_markdown_marks_each_page(self):
        text = tool.markdown(Path("report.pdf"), ["one", "two", ""], ocr_pages={1}, images={2})
        self.assertIn(tool.MARK, text)
        self.assertIn("## Page 1 · OCR\n\none", text)
        self.assertIn("## Page 2 · with images\n\ntwo", text)
        self.assertIn("## Page 3\n\n(no text)", text)


class GuardsTest(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.folder = Path(work.name)
        self.pdf = self.folder / "report.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n")
        self.md = self.folder / "report.md"

    def test_never_overwrites_a_markdown_it_did_not_write(self):
        self.md.write_text("My notes", encoding="utf-8")
        with self.assertRaises(ValueError):
            tool.transcribe(self.pdf)
        self.assertEqual(self.md.read_text(encoding="utf-8"), "My notes")

    def test_skips_a_markdown_newer_than_its_pdf(self):
        os.utime(self.pdf, (0, 0))
        self.md.write_text(tool.NOTE.format(name=self.pdf.name), encoding="utf-8")
        self.assertTrue(tool.transcribe(self.pdf).endswith("(already up to date)"))

    def test_puts_the_markdown_beside_the_pdf_in_a_folder_or_in_the_cache(self):
        pdf = Path("/docs/report.pdf")
        self.assertEqual(tool.markdown_path(pdf, "beside"), Path("/docs/report.md"))
        self.assertEqual(tool.markdown_path(pdf, "/notes"), Path("/notes/report.md"))
        # The PDF's folder path keeps PDFs with the same name apart.
        self.assertEqual(tool.markdown_path(pdf, "cache"), tool.cache_folder() / "docs/report.md")

    def test_skips_a_markdown_in_a_folder_newer_than_its_pdf(self):
        os.utime(self.pdf, (0, 0))
        notes = self.folder / "notes"
        notes.mkdir()
        (notes / "report.md").write_text(tool.NOTE.format(name=self.pdf.resolve()), encoding="utf-8")
        self.assertTrue(tool.transcribe(self.pdf, str(notes)).endswith("(already up to date)"))

    def test_never_shares_a_markdown_between_pdfs_with_the_same_name(self):
        notes = self.folder / "notes"
        notes.mkdir()
        other = tool.NOTE.format(name="/elsewhere/report.pdf")
        (notes / "report.md").write_text(other, encoding="utf-8")
        with self.assertRaises(ValueError):
            tool.transcribe(self.pdf, str(notes))
        self.assertEqual((notes / "report.md").read_text(encoding="utf-8"), other)

    def test_rejects_a_missing_pdf(self):
        with self.assertRaises(ValueError):
            tool.transcribe(self.folder / "other.pdf")


if __name__ == "__main__":
    unittest.main()

<div align="center">
  <h1>pdf-transcribe</h1>

  <p><strong>Convert PDFs to clean, token-efficient Markdown for AI agents, with OCR for scanned pages.</strong></p>
</div>

pdf-transcribe turns a PDF into Markdown once, so an AI agent can read and
search its text instead of opening each page as an image, which costs far more
tokens. It is a single Python script for macOS and Linux.

## Features

- Uses the text the PDF already has, and runs OCR only on pages with almost
  none, such as scans or handwriting: Apple Vision on macOS, Tesseract on
  Linux.
- Marks pages with large images, so you know when to look at the PDF itself.
- Skips PDFs whose Markdown is up to date, and never overwrites a `.md` it did
  not write.

## Limitations

A page with enough text of its own skips OCR, so the text inside its images is
not transcribed. Tables come out as plain text, without their structure, and
figures drawn as vectors are not marked. Handwriting comes out with errors, and
handwritten formulas are barely readable. Vision detects the language, while
Tesseract reads only Spanish and English, and handwriting much worse. The
Markdown goes next to its PDF, so in a Git repository it can end up in a
commit.

## Install

You need Python 3.9 or later, with no extra Python packages.

**macOS:** macOS 26 or later, with poppler and Swift, which comes with Xcode or
its Command Line Tools:

```sh
brew install poppler
xcode-select --install   # only if Swift is missing
```

**Linux:** Debian 12, Ubuntu 24.04, or later, with poppler and Tesseract,
including its Spanish data:

```sh
sudo apt install poppler-utils tesseract-ocr tesseract-ocr-spa
```

Then get the code and put the command on your `PATH`:

```sh
git clone https://github.com/luiscuellar31/pdf-transcribe.git
cd pdf-transcribe
ln -s "$PWD/pdf_transcribe.py" ~/.local/bin/pdf-transcribe
```

## Usage

```sh
pdf-transcribe report.pdf   # writes report.md next to report.pdf
pdf-transcribe *.pdf        # several at once
```

It prints where each Markdown went and how many of its pages needed OCR or
have images. To redo one, delete its `.md` and run the command again.

OCR takes under a second per page with Vision, though its first use on a Mac
can take about a minute to load, and a few seconds per page with Tesseract.

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

"Page N" is the page's place in the PDF, not the number printed on it. A page
marked **OCR** may have reading errors, and one marked **with images** has
figures the text does not describe.

## Documentation

- [How it works](docs/ARCHITECTURE.md)
- [Working on pdf-transcribe](AGENTS.md): checks and commit messages

## License

pdf-transcribe is available under the [MIT License](LICENSE).

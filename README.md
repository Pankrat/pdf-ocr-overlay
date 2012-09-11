pdf-ocr-overlay
===============

Simple way to make scanned PDFs searchable based on Tesseract.

$ ./ocr.py scanned.pdf output.pdf

Adds an overlay to scanned PDF so that your document archive can be indexed and
text can be found easier in large documents.

Dependencies
------------

 * python
 * tesseract-ocr (tesseract)
 * exactimage (hocr2pdf)
 * poppler-utils (pdfimages)
 * ghostscript (gs)

Alternatives
------------

[OCRFeeder](https://live.gnome.org/OCRFeeder) lets you rebuild documents from
scanned images and documents. It has layout analysis, frontend-editing,
spell-checking and much more. If you want to modify the extracted texts then
this is the way to go. Exported PDFs with an overlay tend to be very large and
it takes some time to process a bunch of documents.

[Google Docs](https://docs.google.com) does OCR for uploaded documents. I've
not tested this extensively but it's probably good and will probably get better
over time. If you want to upload your documents to Google anyway, go for that.

[pdfocr](https://github.com/gkovacs/pdfocr) by Geza Kovacs is quite similar to
this project also I haven't used it yet. It's based on cuneiform and
implemented in Ruby.

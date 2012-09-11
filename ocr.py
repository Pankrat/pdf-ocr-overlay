#!/usr/bin/python
#
# Copyright (c) 2012 Ludwig Haehne
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


from argparse import ArgumentParser
from glob import glob
import os
from shutil import rmtree
from subprocess import check_call
from tempfile import mkdtemp
import time


class Timer:
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start


def extract_images(pdf, output):
    check_call(["pdfimages", pdf, output])
    images = []
    for filetype in ('*.ppm', '*.pbm', '*.jpg'):
        images.extend(glob(os.path.join(output, filetype)))
    images.sort()
    return images


def ocr_page(image, lang='eng'):
    base = os.path.splitext(image)[0]
    png = base + '.png'
    hocr = base + '.html'
    pdf = base + '.pdf'
    check_call(["convert", image, png])
    check_call(["tesseract", png, base, '-l', lang, 'hocr'])
    html = os.open(hocr, os.O_RDONLY)
    check_call(['hocr2pdf', '-i', png, '-o', pdf], stdin=html)
    os.close(html)
    return pdf


def merge_pdf(pages, output_filename):
    check_call(['gs',
                '-q',
                '-dNOPAUSE',
                '-dBATCH',
                '-sDEVICE=pdfwrite',
                '-sOutputFile={}'.format(output_filename)] +
               pages,
               )


def process(input_file, output_file, lang='eng'):
    tmp = os.path.join(mkdtemp(), '')
    try:
        print ("Extract pages ...")
        images = extract_images(input_file, tmp)
        pages = []
        for idx, image in enumerate(images, start=1):
            print ("[{:>2}/{:>2}] Run OCR on {}".format(idx, len(images), image))
            with Timer() as t:
                page = ocr_page(image, lang=lang)
            print ("Recognition of page {} took {:.2f}s".format(idx, t.interval))
            pages.append(page)
        print ("\nOCR complete. Merging into '{}'".format(output_file))
        merge_pdf(pages, output_file)
        check_call(['ls', '-lh', input_file, output_file])
    finally:
        rmtree(tmp)


if __name__ == '__main__':
    parser = ArgumentParser(description="Add OCR to overlay to scanned PDF")
    parser.add_argument('input', nargs=1, help='Scanned PDF')
    parser.add_argument('output', nargs=1, help='Output PDF')
    parser.add_argument('-l', '--lang', default='eng',
                        help='3-digit tesseract language code (default "eng")')
    args = parser.parse_args()
    process(args.input[0], args.output[0], lang=args.lang)

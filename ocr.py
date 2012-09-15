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
import logging
import os
from Queue import Queue
from shutil import rmtree
from subprocess import check_call, check_output, Popen, PIPE
from tempfile import mkdtemp
from threading import Thread
import time


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    datefmt='%H:%M:%S',
                    )


class Timer:
    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.interval = self.end - self.start


def system_info():
    deps = []

    pdfimages = Popen(['pdfimages', '-v'], stderr=PIPE).communicate()[1]
    deps.append(('pdfimages', pdfimages.split('\n')[0]))

    tesseract = Popen(['tesseract', '-v'], stderr=PIPE).communicate()[1]
    deps.append(('tesseract', tesseract.split('\n')[0]))

    # hocr2pdf doesn't support a --version flag but prints the version to
    # stderr if called without arguments
    hocr2pdf = Popen(['hocr2pdf', '--help'], stdout=PIPE, stderr=PIPE)
    hocr2pdf = hocr2pdf.communicate()[1]
    hocr2pdf = [line for line in hocr2pdf if 'version' in line]
    if hocr2pdf:
        deps.append(('hocr2pdf', hocr2pdf))

    gs = check_output(['gs', '--version']).split('\n')[0]
    deps.append(('gs', gs))

    identify = check_output(['identify', '--version']).split('\n')[0]
    deps.append(('identify', identify))

    convert = check_output(['convert', '--version']).split('\n')[0]
    deps.append(('convert', convert))

    return deps


def extract_images(pdf, output):
    check_call(["pdfimages", pdf, output])
    images = []
    for filetype in ('*.ppm', '*.pbm', '*.jpg'):
        images.extend(glob(os.path.join(output, filetype)))
    images.sort()
    return images


def compute_dpi(pdf_w, pdf_h, image_w, image_h):
    """
    Deduce scan resolution from PDF and image size.
    http://stackoverflow.com/a/576816/63392
    """
    dpi_w = int(round(image_w*72./pdf_w))
    dpi_h = int(round(image_h*72./pdf_h))
    return dpi_w, dpi_h


def get_resolution(filename):
    """
    Return resolution per page.
    """
    pages = check_output(["identify", "-format", "%w,%h;", filename])
    pages = [page.split(',') for page in pages.split(';') if page.strip()]
    pages = [(int(x), int(y)) for x, y in pages]
    return pages


PAPER_SIZES = {
    (841, 1189): 'A0',
    (594, 841): 'A1',
    (420, 594): 'A2',
    (297, 420): 'A3',
    (210, 297): 'A4',
    (148, 210): 'A5',
    (105, 148): 'A6',
    ( 74, 105): 'A7',
    ( 52,  74): 'A8',
    (250, 353): 'B4',
    (176, 250): 'B5',
    (125, 176): 'B6',
    (215, 279): 'US Letter',
    }


def get_paper_type(wdots, hdots):
    w_mm = int(wdots / 7.2 * 2.54)
    h_mm = int(hdots / 7.2 * 2.54)
    if (w_mm, h_mm) in PAPER_SIZES:
        return PAPER_SIZES[(w_mm, h_mm)]
    elif (h_mm, w_mm) in PAPER_SIZES:
        return PAPER_SIZES[(h_mm, w_mm)] + ', landscape'
    else:
        return ''


def ocr_page(image, lang='eng', width=-1, height=-1):
    base = os.path.splitext(image)[0]
    png = base + '.png'
    hocr = base + '.html'
    pdf = base + '.pdf'
    w, h = get_resolution(image)[0]
    dpi_w, dpi_h = compute_dpi(width, height, w, h)
    logging.debug("Page={}x{} Image={}x{} DPI={}x{}".format(
                  width, height, w, h, dpi_w, dpi_h))
    check_call(["convert", image, png])
    devnull = open('/dev/null', 'w')
    check_call(["tesseract", png, base, '-l', lang, 'hocr'],
               stdout=devnull)
    # Reduce resolution of images to 1/2 that have 600dpi or more.
    if dpi_w >= 600:
        check_call(["mogrify", "-resize", "50%", png])
        dpi_w = dpi_w / 2
    html = os.open(hocr, os.O_RDONLY)
    check_call(['hocr2pdf', '-r', str(dpi_w), '-i', png, '-o', pdf],
               stdin=html)
    os.close(html)
    return pdf


def process_page(index, queue, lang, resolution):
    """
    Pull page from the queue and perform OCR. Make sure to acknowledge the
    message in the queue even if there is an exception so that the main thread
    does not block on a queue that will never be empty.
    """
    while True:
        page, image = queue.get()
        try:
            logging.info("Page {:>2}: Run OCR ...".format(page))
            width, height = resolution[page-1]
            with Timer() as t:
                ocr_page(image, lang=lang, width=width, height=height)
            logging.info("Page {:>2}: OCR took {:.2f}s".format(page, t.interval))
        finally:
            queue.task_done()


def merge_pdf(pages, output_filename):
    check_call(['gs',
                '-q',
                '-dNOPAUSE',
                '-dBATCH',
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.4',
                '-sOutputFile={}'.format(output_filename)] +
               pages,
               )


def start_workers(num_workers, queue, lang, resolution):
    for tid in range(num_workers):
        args = (tid, queue, lang, resolution)
        worker = Thread(target=process_page, args=args)
        worker.daemon = True
        worker.start()


def process(input_file, output_file, lang='eng', jobs=4):
    tmp = os.path.join(mkdtemp(), '')
    try:
        resolution = get_resolution(input_file)
        w, h = resolution[0]
        logging.info("{} pages, {}mm*{}mm {}".format(len(resolution),
                                                     int(w / 7.2 * 2.54),
                                                     int(h / 7.2 * 2.54),
                                                     get_paper_type(w, h)))
        logging.info("Extract pages from {}".format(input_file))
        images = extract_images(input_file, tmp)
        num_workers = min(len(images), jobs)
        queue = Queue()
        start_workers(num_workers, queue, lang, resolution)
        logging.info("Process {} pages with {} threads".format(len(images),
                                                                   num_workers))
        for idx, image in enumerate(images, start=1):
            queue.put((idx, image))
        queue.join()
        pages = sorted(glob(os.path.join(tmp, '*.pdf')))
        logging.info("OCR complete. Merge pages into '{}'".format(output_file))
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
    parser.add_argument('-j', '--jobs', default=4, type=int,
                        help='Specifies the number of pages to process simultaneously')
    args = parser.parse_args()
    for name, version in system_info():
        logging.info('{:<12}: {}'.format(name, version))
    process(args.input[0], args.output[0], lang=args.lang, jobs=args.jobs)

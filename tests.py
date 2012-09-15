
from ocr import compute_dpi, get_paper_type
import unittest


class ResolutionTests(unittest.TestCase):

    def test_compute_dpi(self):
        self.assertEqual(compute_dpi(611, 792, 2544, 3300), (300, 300))

    def test_paper_type(self):
        self.assertEqual(get_paper_type(611, 792), 'US Letter')
        self.assertEqual(get_paper_type(792, 611), 'US Letter, landscape')
        self.assertEqual(get_paper_type(598, 842), 'A4')


if __name__ == '__main__':
    unittest.main()

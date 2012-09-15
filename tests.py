
from ocr import compute_dpi
import unittest


class ResolutionTests(unittest.TestCase):
    def test_compute_dpi(self):
        self.assertEqual(compute_dpi(611, 792, 2544, 3300), (300, 300))


if __name__ == '__main__':
    unittest.main()

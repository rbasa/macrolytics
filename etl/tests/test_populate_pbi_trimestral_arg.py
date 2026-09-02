import unittest
from datetime import date

from etl.populate_pbi_trimestral_arg import quarter_period, release_suffixes


class QuarterlyGDPTest(unittest.TestCase):
  def test_quarter_period(self):
    self.assertEqual(quarter_period(2026, "I"), date(2026, 1, 1))
    self.assertEqual(quarter_period(2026, "IV"), date(2026, 10, 1))

  def test_release_suffixes_are_newest_first(self):
    self.assertEqual(
      release_suffixes(date(2026, 8, 1))[:4],
      ["06_26", "03_26", "12_25", "09_25"],
    )
    self.assertEqual(release_suffixes(date(2026, 9, 2))[0], "06_26")
    self.assertEqual(release_suffixes(date(2026, 9, 20))[0], "09_26")


if __name__ == "__main__":
  unittest.main()

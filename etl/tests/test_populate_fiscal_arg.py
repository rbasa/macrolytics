import unittest

from etl.populate_fiscal_arg import AIFPageParser


class AIFPageParserTest(unittest.TestCase):
    def test_month_after_links(self):
        parser = AIFPageParser()
        parser.feed(
            """
            <h2>CUENTA AIF SEC. PÚBLICO NACIONAL- BASE CAJA</h2>
            <a href="Jan26.pdf"></a>
            <a href="Jan26.xlsx"></a>Enero
            <a href="2dotrim26.pdf"></a>
            <a href="2dotrim26.xlsx"></a>Marzo
            <h2>EJECUCIÓN DIVISAS</h2>
            """
        )

        self.assertEqual(
            parser.links,
            {
                1: "Jan26.xlsx",
                3: "2dotrim26.xlsx",
            },
        )

    def test_month_before_links(self):
        parser = AIFPageParser()
        parser.feed(
            """
            <h2>CUENTA AIF SEC. PÚBLICO NACIONAL- BASE CAJA</h2>
            Junio
            <a href="Jun26.pdf"></a>
            <a href="Jun26.xlsx"></a>
            <h2>EJECUCIÓN DIVISAS</h2>
            """
        )

        self.assertEqual(
            parser.links,
            {6: "Jun26.xlsx"},
        )


if __name__ == "__main__":
    unittest.main()

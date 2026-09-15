from __future__ import annotations

import unittest

from agente_telegram.bot import parse_model_selection


class ModelCommandTests(unittest.TestCase):
    def test_accepts_equals_syntax(self) -> None:
        self.assertEqual(parse_model_selection("/modelo=sol"), "sol")

    def test_accepts_standard_telegram_syntax(self) -> None:
        self.assertEqual(parse_model_selection("/modelo terra"), "terra")

    def test_accepts_full_model_identifier(self) -> None:
        self.assertEqual(
            parse_model_selection("/modelo=gpt-5.6-luna"),
            "luna",
        )

    def test_empty_selection_requests_status(self) -> None:
        self.assertEqual(parse_model_selection("/modelo"), "")


if __name__ == "__main__":
    unittest.main()

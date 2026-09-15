from __future__ import annotations

import unittest

from agente_ia.map_service import is_molina_hiking_map_request


class MapRequestTests(unittest.TestCase):
    def test_detects_requested_molina_map(self) -> None:
        prompt = (
            "dibuja sobre un mapa de los alrededores de Molina de Aragon "
            "con líneas punteadas 3 rutas de senderismo de 5 - 10 Km"
        )

        self.assertTrue(is_molina_hiking_map_request(prompt))

    def test_does_not_intercept_general_question(self) -> None:
        self.assertFalse(is_molina_hiking_map_request("¿Qué es el senderismo?"))

    def test_requires_molina_for_current_cartographic_template(self) -> None:
        self.assertFalse(
            is_molina_hiking_map_request(
                "Dibuja un mapa con rutas de senderismo en Cuenca"
            )
        )


if __name__ == "__main__":
    unittest.main()

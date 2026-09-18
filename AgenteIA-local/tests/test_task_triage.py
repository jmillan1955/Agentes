from __future__ import annotations

import unittest

from agente_ia.task_workflow import (
    AdaptiveClarificationAnalyzer,
    IntentKind,
    TaskIntentClassifier,
)


class TaskIntentClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = TaskIntentClassifier()

    def test_direct_action_verbs_are_tasks(self) -> None:
        requests = (
            "Construye una API de salud",
            "Escribe las pruebas del modulo de usuarios",
            "Planifica la migracion de la base de datos",
            "Crea un comando de diagnostico",
            "Implementa autenticacion OAuth",
            "Modifica el formulario de acceso",
            "Corrige el error al guardar",
        )

        for request in requests:
            with self.subTest(request=request):
                decision = self.classifier.classify(request)
                self.assertEqual(decision.kind, IntentKind.TASK)
                self.assertGreaterEqual(decision.confidence, 0.9)

    def test_indirect_action_request_is_a_task(self) -> None:
        for request in (
            "Necesito que implementes el inicio de sesion",
            "Quiero crear un servicio de avisos",
            "Podrias corregir el fallo del bot",
            "Encargate de preparar las pruebas de integracion",
            "Vamos a actualizar la API",
        ):
            with self.subTest(request=request):
                self.assertEqual(self.classifier.classify(request).kind, IntentKind.TASK)

    def test_action_after_project_context_is_still_a_task(self) -> None:
        decision = self.classifier.classify(
            "En AgenteIA-local, implementa el triaje de tareas"
        )

        self.assertEqual(decision.kind, IntentKind.TASK)
        self.assertEqual(decision.project, "AgenteIA-local")

    def test_conceptual_questions_are_not_tasks(self) -> None:
        requests = (
            "Como se crea una API REST?",
            "Explicame como implementar OAuth",
            "Quiero saber como corregir conflictos de Git",
            "Que significa planificar una migracion?",
        )

        for request in requests:
            with self.subTest(request=request):
                self.assertEqual(self.classifier.classify(request).kind, IntentKind.QUERY)

    def test_action_verbs_inside_quotes_do_not_create_a_task(self) -> None:
        request = 'Analiza la frase "crea, implementa y corrige el modulo"'

        decision = self.classifier.classify(request)

        self.assertEqual(decision.kind, IntentKind.QUERY)

    def test_description_of_existing_behavior_is_not_a_task(self) -> None:
        decision = self.classifier.classify("El comando crea un archivo temporal")

        self.assertEqual(decision.kind, IntentKind.QUERY)

    def test_spanish_auxiliary_ha_is_not_home_assistant_alias(self) -> None:
        decision = self.classifier.classify("Se ha corregido el error")

        self.assertIsNone(decision.project)

    def test_extracts_known_project_and_explicit_path(self) -> None:
        request = r"Implementa el triaje en AgenteIA-local, C:\Desarrollo\Proyectos\AgenteIA-local"

        decision = self.classifier.classify(request)

        self.assertEqual(decision.kind, IntentKind.TASK)
        self.assertEqual(decision.project, "AgenteIA-local")
        self.assertEqual(decision.context, r"C:\Desarrollo\Proyectos\AgenteIA-local")

    def test_ambiguous_action_requests_clarification(self) -> None:
        decision = self.classifier.classify("Seria posible crear algo parecido?")

        self.assertEqual(decision.kind, IntentKind.CLARIFICATION)
        self.assertLess(decision.confidence, 0.7)

    def test_command_bypasses_task_detection(self) -> None:
        decision = self.classifier.classify("/compra casa crea y leche")

        self.assertEqual(decision.kind, IntentKind.COMMAND)

    def test_pending_context_can_classify_plain_answer_as_clarification(self) -> None:
        decision = self.classifier.classify(
            "En el repositorio de Home Assistant", has_pending_task=True
        )

        self.assertEqual(decision.kind, IntentKind.CLARIFICATION)


class AdaptiveClarificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = TaskIntentClassifier()
        self.analyzer = AdaptiveClarificationAnalyzer()

    def test_clear_request_does_not_trigger_unnecessary_questions(self) -> None:
        request = "Implementa OAuth en AgenteIA-local con Python y pruebas unitarias"
        decision = self.classifier.classify(request)

        self.assertEqual(self.analyzer.questions_for(request, decision), ())

    def test_vague_software_request_asks_only_material_questions(self) -> None:
        request = "Corrige este bug"
        decision = self.classifier.classify(request)

        questions = self.analyzer.questions_for(request, decision)

        self.assertIn("¿Qué componente o comportamiento concreto debo cambiar?", questions)
        self.assertIn("¿En qué proyecto o ruta debo realizar el trabajo?", questions)

    def test_greenfield_app_requires_platform_and_destination(self) -> None:
        request = "Crea una app de inventario"
        decision = self.classifier.classify(request)

        questions = self.analyzer.questions_for(request, decision)

        self.assertEqual(len(questions), 2)


if __name__ == "__main__":
    unittest.main()

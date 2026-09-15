from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agente_ia.conversation_store import ConversationStore


class ConversationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = ConversationStore(Path(self.temporary.name) / "conversations.db")
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_user(self, telegram_id: int) -> int:
        return self.store.get_or_create_user(
            telegram_id,
            username=f"usuario{telegram_id}",
            first_name="Nombre",
            last_name=None,
        )

    def test_keeps_users_and_conversations_separate(self) -> None:
        first_user = self.create_user(101)
        second_user = self.create_user(202)
        first = self.store.get_or_create_active_conversation(first_user, 101)
        second = self.store.get_or_create_active_conversation(second_user, 202)

        self.store.save_message(
            first.id,
            101,
            telegram_message_id=1,
            direction="incoming",
            content_type="text",
            text="Secreto del primer usuario",
        )
        self.store.save_message(
            second.id,
            202,
            telegram_message_id=1,
            direction="incoming",
            content_type="text",
            text="Pregunta del segundo usuario",
        )

        self.assertIn("Secreto del primer", self.store.context_text(first.id))
        self.assertNotIn("Secreto del primer", self.store.context_text(second.id))
        self.assertIn("Pregunta del segundo", self.store.context_text(second.id))

    def test_new_conversation_archives_previous_one(self) -> None:
        user = self.create_user(101)
        first = self.store.get_or_create_active_conversation(user, 101)
        second = self.store.start_new_conversation(user, 101)

        conversations = self.store.list_conversations(user)
        by_id = {conversation.id: conversation for conversation in conversations}
        self.assertEqual(by_id[first.id].status, "archived")
        self.assertEqual(by_id[second.id].status, "active")

    def test_new_conversation_keeps_explicit_name(self) -> None:
        user = self.create_user(101)

        conversation = self.store.start_new_conversation(
            user,
            101,
            title="  Reforma   del jardín  ",
        )

        self.assertEqual(conversation.title, "Reforma del jardín")

    def test_rejects_conversation_name_longer_than_70_characters(self) -> None:
        user = self.create_user(101)

        with self.assertRaises(ValueError):
            self.store.start_new_conversation(user, 101, title="x" * 71)

    def test_can_reopen_only_own_conversation(self) -> None:
        first_user = self.create_user(101)
        second_user = self.create_user(202)
        first = self.store.get_or_create_active_conversation(first_user, 101)
        other = self.store.get_or_create_active_conversation(second_user, 202)

        self.assertIsNone(
            self.store.activate_conversation(first_user, 101, other.id)
        )
        self.assertIsNotNone(
            self.store.activate_conversation(first_user, 101, first.id)
        )

    def test_first_message_becomes_title(self) -> None:
        user = self.create_user(101)
        conversation = self.store.get_or_create_active_conversation(user, 101)
        self.store.save_message(
            conversation.id,
            101,
            telegram_message_id=8,
            direction="incoming",
            content_type="text",
            text="Quiero preparar una aplicación para controlar la calefacción",
        )

        updated = self.store.list_conversations(user)[0]
        self.assertEqual(
            updated.title,
            "Quiero preparar una aplicación para controlar la calefacción",
        )

    def test_rejects_duplicate_update_but_allows_same_id_in_another_chat(self) -> None:
        first_user = self.create_user(101)
        second_user = self.create_user(202)
        first = self.store.get_or_create_active_conversation(first_user, 101)
        second = self.store.get_or_create_active_conversation(second_user, 202)

        first_insert = self.store.save_message(
            first.id,
            101,
            telegram_message_id=25,
            direction="incoming",
            content_type="text",
            text="Primero",
        )
        duplicate = self.store.save_message(
            first.id,
            101,
            telegram_message_id=25,
            direction="incoming",
            content_type="text",
            text="Duplicado",
        )
        other_chat = self.store.save_message(
            second.id,
            202,
            telegram_message_id=25,
            direction="incoming",
            content_type="text",
            text="Otro chat",
        )

        self.assertTrue(first_insert)
        self.assertFalse(duplicate)
        self.assertTrue(other_chat)


if __name__ == "__main__":
    unittest.main()

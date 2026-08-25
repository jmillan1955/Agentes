from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskClarificationResponse:
    id: int
    task_id: int
    response_message_id: str
    questions: tuple[str, ...]
    answer: str
    created_at: str

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(
                "id debe ser mayor que cero"
            )

        if self.task_id <= 0:
            raise ValueError(
                "task_id debe ser "
                "mayor que cero"
            )

        response_message_id = (
            self.response_message_id.strip()
        )
        answer = self.answer.strip()

        questions = tuple(
            question.strip()
            for question in self.questions
            if question.strip()
        )

        if not response_message_id:
            raise ValueError(
                "response_message_id no puede "
                "estar vacío"
            )

        if not questions:
            raise ValueError(
                "questions no puede estar vacío"
            )

        if not answer:
            raise ValueError(
                "answer no puede estar vacío"
            )

        object.__setattr__(
            self,
            "response_message_id",
            response_message_id,
        )
        object.__setattr__(
            self,
            "questions",
            questions,
        )
        object.__setattr__(
            self,
            "answer",
            answer,
        )
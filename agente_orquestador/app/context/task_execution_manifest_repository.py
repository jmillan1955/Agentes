from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
from collections.abc import Iterable

from app.context.database import (
    ContextDatabase,
)
from app.execution.actions import (
    ExecutionAction,
    ExecutionActionType,
)
from app.execution.manifest_models import (
    ExecutionManifest,
    ExecutionManifestAction,
    ExecutionManifestStatus,
)


class TaskExecutionManifestRepository:
    def __init__(
        self,
        database: ContextDatabase,
    ) -> None:
        self._database = database

    def get_by_id(
        self,
        manifest_id: int,
    ) -> ExecutionManifest | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                version,
                status,
                manifest_hash,
                action_count,
                destructive_action_count,
                created_at,
                confirmed_at,
                confirmed_by_user_id,
                confirmation_message_id,
                confirmation_channel
            FROM task_execution_manifests
            WHERE id = ?
            """,
            (manifest_id,),
        ).fetchone()

        return self._to_manifest(row)

    def get_latest(
        self,
        execution_id: int,
    ) -> ExecutionManifest | None:
        row = self._database.connection.execute(
            """
            SELECT
                id,
                execution_id,
                version,
                status,
                manifest_hash,
                action_count,
                destructive_action_count,
                created_at,
                confirmed_at,
                confirmed_by_user_id,
                confirmation_message_id,
                confirmation_channel
            FROM task_execution_manifests
            WHERE execution_id = ?
            ORDER BY version DESC
            LIMIT 1
            """,
            (execution_id,),
        ).fetchone()

        return self._to_manifest(row)

    def list_actions(
        self,
        manifest_id: int,
    ) -> tuple[
        ExecutionManifestAction,
        ...,
    ]:
        rows = self._database.connection.execute(
            """
            SELECT
                id,
                manifest_id,
                step_number,
                name,
                action_type,
                relative_path,
                content_text,
                content_sha256,
                destructive,
                created_at
            FROM task_execution_manifest_actions
            WHERE manifest_id = ?
            ORDER BY step_number
            """,
            (manifest_id,),
        ).fetchall()

        return tuple(
            self._to_action(row)
            for row in rows
        )

    def create(
        self,
        execution_id: int,
        actions: Iterable[
            ExecutionAction
        ],
    ) -> ExecutionManifest:
        if execution_id <= 0:
            raise ValueError(
                "execution_id debe ser "
                "mayor que cero"
            )

        action_values = tuple(actions)

        self._validate_actions(
            action_values
        )

        prepared_actions = tuple(
            self._prepare_action(action)
            for action in action_values
        )

        manifest_hash = (
            self._calculate_manifest_hash(
                prepared_actions
            )
        )

        destructive_count = sum(
            1
            for action in prepared_actions
            if action["destructive"]
        )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            execution_row = connection.execute(
                """
                SELECT status
                FROM task_executions
                WHERE id = ?
                """,
                (execution_id,),
            ).fetchone()

            if execution_row is None:
                raise ValueError(
                    "No existe la ejecucion"
                )

            if (
                execution_row["status"]
                != "prepared"
            ):
                raise ValueError(
                    "Solo se puede crear el "
                    "manifiesto de una ejecucion "
                    "preparada"
                )

            version_row = connection.execute(
                """
                SELECT COALESCE(
                    MAX(version),
                    0
                ) AS latest_version
                FROM task_execution_manifests
                WHERE execution_id = ?
                """,
                (execution_id,),
            ).fetchone()

            version = (
                int(
                    version_row[
                        "latest_version"
                    ]
                )
                + 1
            )

            connection.execute(
                """
                UPDATE task_execution_manifests
                SET status = 'superseded'
                WHERE execution_id = ?
                  AND status != 'superseded'
                """,
                (execution_id,),
            )

            cursor = connection.execute(
                """
                INSERT INTO
                    task_execution_manifests (
                        execution_id,
                        version,
                        status,
                        manifest_hash,
                        action_count,
                        destructive_action_count
                    )
                VALUES (
                    ?,
                    ?,
                    'pending_confirmation',
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    execution_id,
                    version,
                    manifest_hash,
                    len(prepared_actions),
                    destructive_count,
                ),
            )

            manifest_id = int(
                cursor.lastrowid
            )

            for action in prepared_actions:
                connection.execute(
                    """
                    INSERT INTO
                        task_execution_manifest_actions (
                            manifest_id,
                            step_number,
                            name,
                            action_type,
                            relative_path,
                            content_text,
                            content_sha256,
                            destructive
                        )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        manifest_id,
                        action["step_number"],
                        action["name"],
                        action["action_type"],
                        action["relative_path"],
                        action["content_text"],
                        action["content_sha256"],
                        int(
                            action[
                                "destructive"
                            ]
                        ),
                    ),
                )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        created = self.get_by_id(
            manifest_id
        )

        if created is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el manifiesto creado"
            )

        return created

    def confirm(
        self,
        manifest_id: int,
        expected_manifest_hash: str,
        confirmed_by_user_id: str,
        confirmation_message_id: str,
        confirmation_channel: str,
    ) -> ExecutionManifest:
        expected_manifest_hash = (
            expected_manifest_hash
            .strip()
            .lower()
        )
        confirmed_by_user_id = (
            confirmed_by_user_id.strip()
        )
        confirmation_message_id = (
            confirmation_message_id.strip()
        )
        confirmation_channel = (
            confirmation_channel.strip()
        )

        if manifest_id <= 0:
            raise ValueError(
                "manifest_id debe ser "
                "mayor que cero"
            )

        if not confirmed_by_user_id:
            raise ValueError(
                "confirmed_by_user_id no "
                "puede estar vacio"
            )

        if not confirmation_message_id:
            raise ValueError(
                "confirmation_message_id no "
                "puede estar vacio"
            )

        if not confirmation_channel:
            raise ValueError(
                "confirmation_channel no "
                "puede estar vacio"
            )

        connection = self._database.connection

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            manifest = self.get_by_id(
                manifest_id
            )

            if manifest is None:
                raise ValueError(
                    "No existe el manifiesto"
                )

            if (
                manifest.manifest_hash
                != expected_manifest_hash
            ):
                raise ValueError(
                    "El hash del manifiesto "
                    "no coincide"
                )

            if manifest.is_confirmed:
                if (
                    manifest
                    .confirmed_by_user_id
                    == confirmed_by_user_id
                    and manifest
                    .confirmation_message_id
                    == confirmation_message_id
                    and manifest
                    .confirmation_channel
                    == confirmation_channel
                ):
                    connection.rollback()
                    return manifest

                raise ValueError(
                    "El manifiesto ya esta "
                    "confirmado"
                )

            if (
                manifest.status
                != ExecutionManifestStatus
                .PENDING_CONFIRMATION
            ):
                raise ValueError(
                    "El manifiesto no esta "
                    "pendiente de confirmacion"
                )

            latest = self.get_latest(
                manifest.execution_id
            )

            if (
                latest is None
                or latest.id != manifest.id
            ):
                raise ValueError(
                    "Solo puede confirmarse "
                    "el ultimo manifiesto"
                )

            cursor = connection.execute(
                """
                UPDATE task_execution_manifests
                SET
                    status = 'confirmed',
                    confirmed_at = strftime(
                        '%Y-%m-%dT%H:%M:%fZ',
                        'now'
                    ),
                    confirmed_by_user_id = ?,
                    confirmation_message_id = ?,
                    confirmation_channel = ?
                WHERE id = ?
                  AND status =
                      'pending_confirmation'
                  AND manifest_hash = ?
                """,
                (
                    confirmed_by_user_id,
                    confirmation_message_id,
                    confirmation_channel,
                    manifest_id,
                    expected_manifest_hash,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "No se pudo confirmar "
                    "el manifiesto"
                )

            connection.commit()

        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise ValueError(
                "El mensaje de confirmacion "
                "ya fue utilizado"
            ) from error

        except Exception:
            connection.rollback()
            raise

        confirmed = self.get_by_id(
            manifest_id
        )

        if confirmed is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el manifiesto confirmado"
            )

        return confirmed

    def load_confirmed_actions(
        self,
        execution_id: int,
    ) -> tuple[
        ExecutionAction,
        ...,
    ]:
        row = self._database.connection.execute(
            """
            SELECT id
            FROM task_execution_manifests
            WHERE execution_id = ?
              AND status = 'confirmed'
            ORDER BY version DESC
            LIMIT 1
            """,
            (execution_id,),
        ).fetchone()

        if row is None:
            raise ValueError(
                "El manifiesto no esta "
                "confirmado"
            )

        manifest = self.get_by_id(
            row["id"]
        )

        if manifest is None:
            raise RuntimeError(
                "No se pudo recuperar "
                "el manifiesto"
            )

        records = self.list_actions(
            manifest.id
        )

        if len(records) != manifest.action_count:
            raise RuntimeError(
                "El numero de acciones no "
                "coincide con el manifiesto"
            )

        prepared_actions = tuple(
            {
                "step_number": (
                    record.step_number
                ),
                "name": record.name,
                "action_type": (
                    record.action_type
                ),
                "relative_path": (
                    record.relative_path
                ),
                "content_text": (
                    record.content_text
                ),
                "content_sha256": (
                    record.content_sha256
                ),
                "destructive": (
                    record.destructive
                ),
            }
            for record in records
        )

        for action in prepared_actions:
            content = action[
                "content_text"
            ]
            stored_hash = action[
                "content_sha256"
            ]

            calculated_hash = (
                sha256(
                    content.encode("utf-8")
                ).hexdigest()
                if content is not None
                else None
            )

            if calculated_hash != stored_hash:
                raise RuntimeError(
                    "El contenido de una accion "
                    "no coincide con su hash"
                )

        calculated_manifest_hash = (
            self._calculate_manifest_hash(
                prepared_actions
            )
        )

        if (
            calculated_manifest_hash
            != manifest.manifest_hash
        ):
            raise RuntimeError(
                "Las acciones no coinciden "
                "con el hash del manifiesto"
            )

        return tuple(
            ExecutionAction(
                step_number=(
                    action["step_number"]
                ),
                name=action["name"],
                action_type=(
                    ExecutionActionType(
                        action["action_type"]
                    )
                ),
                relative_path=(
                    action["relative_path"]
                ),
                content=(
                    action["content_text"]
                ),
            )
            for action in prepared_actions
        )

    @staticmethod
    def _validate_actions(
        actions: tuple[
            ExecutionAction,
            ...,
        ],
    ) -> None:
        if not actions:
            raise ValueError(
                "El manifiesto debe contener "
                "acciones"
            )

        expected_numbers = tuple(
            range(
                1,
                len(actions) + 1,
            )
        )

        actual_numbers = tuple(
            action.step_number
            for action in actions
        )

        if actual_numbers != expected_numbers:
            raise ValueError(
                "Las acciones deben estar "
                "ordenadas y numeradas desde 1"
            )

    @staticmethod
    def _prepare_action(
        action: ExecutionAction,
    ) -> dict[str, object]:
        content_hash = (
            sha256(
                action.content.encode(
                    "utf-8"
                )
            ).hexdigest()
            if action.content is not None
            else None
        )

        destructive = (
            action.action_type
            == ExecutionActionType
            .WRITE_TEXT_FILE
        )

        return {
            "step_number": action.step_number,
            "name": action.name,
            "action_type": (
                action.action_type.value
            ),
            "relative_path": (
                action.relative_path
            ),
            "content_text": action.content,
            "content_sha256": content_hash,
            "destructive": destructive,
        }

    @staticmethod
    def _calculate_manifest_hash(
        actions: tuple[
            dict[str, object],
            ...,
        ],
    ) -> str:
        canonical_actions = tuple(
            {
                "step_number": (
                    action["step_number"]
                ),
                "name": action["name"],
                "action_type": (
                    action["action_type"]
                ),
                "relative_path": (
                    action["relative_path"]
                ),
                "content_sha256": (
                    action["content_sha256"]
                ),
                "destructive": (
                    action["destructive"]
                ),
            }
            for action in actions
        )

        canonical_json = json.dumps(
            canonical_actions,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return sha256(
            canonical_json.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _to_manifest(
        row: sqlite3.Row | None,
    ) -> ExecutionManifest | None:
        if row is None:
            return None

        return ExecutionManifest(
            id=row["id"],
            execution_id=row["execution_id"],
            version=row["version"],
            status=ExecutionManifestStatus(
                row["status"]
            ),
            manifest_hash=(
                row["manifest_hash"]
            ),
            action_count=row["action_count"],
            destructive_action_count=(
                row[
                    "destructive_action_count"
                ]
            ),
            created_at=row["created_at"],
            confirmed_at=row["confirmed_at"],
            confirmed_by_user_id=(
                row["confirmed_by_user_id"]
            ),
            confirmation_message_id=(
                row[
                    "confirmation_message_id"
                ]
            ),
            confirmation_channel=(
                row["confirmation_channel"]
            ),
        )

    @staticmethod
    def _to_action(
        row: sqlite3.Row,
    ) -> ExecutionManifestAction:
        return ExecutionManifestAction(
            id=row["id"],
            manifest_id=row["manifest_id"],
            step_number=row["step_number"],
            name=row["name"],
            action_type=row["action_type"],
            relative_path=row["relative_path"],
            content_text=row["content_text"],
            content_sha256=(
                row["content_sha256"]
            ),
            destructive=bool(
                row["destructive"]
            ),
            created_at=row["created_at"],
        )
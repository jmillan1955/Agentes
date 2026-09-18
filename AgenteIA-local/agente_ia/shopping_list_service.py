from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

import httpx


class ShoppingListServiceError(RuntimeError):
    """Error al gestionar una lista de la compra mediante Home Assistant."""


ShoppingOperation = Literal["list", "add", "complete", "remove", "clear_completed"]


@dataclass(frozen=True, slots=True)
class ShoppingListRequest:
    operation: ShoppingOperation
    list_key: str
    items: tuple[str, ...] = ()

    @property
    def needs_confirmation(self) -> bool:
        return self.operation in {"remove", "clear_completed"}


@dataclass(frozen=True, slots=True)
class ShoppingListItem:
    summary: str
    uid: str
    status: str


LIST_NAMES = {"casa": "Casa", "casa_jessi": "Casa Jessi"}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _list_key(text: str) -> str:
    normalized = _normalize(text)
    return "casa_jessi" if re.search(r"\b(?:casa\s+jessi|jessi)\b", normalized) else "casa"


def _clean_item_text(text: str) -> str:
    value = text.strip(" \t,.;:!?¿¡")
    value = re.sub(r"^(?:el|la|los|las)\s+", "", value, flags=re.IGNORECASE)
    return " ".join(value.split())


def _split_items(text: str) -> tuple[str, ...]:
    parts = re.split(r"\s*(?:,|;|\by\b|\be\b)\s*", text, flags=re.IGNORECASE)
    return tuple(item for part in parts if (item := _clean_item_text(part)))


def _without_list_suffix(text: str) -> str:
    patterns = (
        r"\s+(?:a|en|de)\s+(?:la\s+)?lista(?:\s+de\s+la\s+compra)?"
        r"(?:\s+de)?\s+(?:casa\s+jessi|jessi|casa)\s*[.?!]*$",
        r"\s+(?:a|en|de)\s+(?:casa\s+jessi|jessi|casa)\s*[.?!]*$",
        r"\s+(?:a|en|de)\s+(?:la\s+)?lista(?:\s+de\s+la\s+compra)?\s*[.?!]*$",
    )
    for pattern in patterns:
        updated = re.sub(pattern, "", text, flags=re.IGNORECASE)
        if updated != text:
            return updated
    return text


def parse_shopping_list_request(text: str) -> ShoppingListRequest | None:
    original = " ".join(text.strip().split())
    normalized = _normalize(original).strip(" .?!¿¡")
    if not normalized:
        return None

    if normalized.startswith("/lista"):
        return ShoppingListRequest("list", _list_key(normalized))

    if normalized.startswith("/compra"):
        argument = re.sub(r"^/compra\b", "", original, flags=re.IGNORECASE).strip()
        if not argument or _normalize(argument) in {"casa", "jessi", "casa jessi"}:
            return ShoppingListRequest("list", _list_key(argument))
        list_key = _list_key(argument)
        argument = re.sub(
            r"^(?:casa\s+jessi|jessi|casa)\s*[:,-]?\s*", "", argument, flags=re.IGNORECASE
        )
        items = _split_items(_without_list_suffix(argument))
        return ShoppingListRequest("add", list_key, items) if items else None

    has_list_context = bool(
        re.search(r"\b(?:lista|comprar|compra|comprad[oa]s?|jessi)\b", normalized)
    )
    if not has_list_context:
        return None
    list_key = _list_key(normalized)

    if re.search(
        r"\b(?:vacia|limpia|borra|elimina|quita)\b.*\b(?:comprados|compradas|completados|completadas)\b",
        normalized,
    ):
        return ShoppingListRequest("clear_completed", list_key)

    complete = re.match(
        r"^(?:marca|pon)\s+(.+?)\s+como\s+(?:comprado|comprada|comprados|compradas|hecho|hecha|completado|completada)\b",
        original,
        flags=re.IGNORECASE,
    )
    if complete:
        items = _split_items(_without_list_suffix(complete.group(1)))
        return ShoppingListRequest("complete", list_key, items) if items else None

    remove = re.match(r"^(?:borra|elimina|quita)\s+(.+)$", original, flags=re.IGNORECASE)
    if remove:
        items = _split_items(_without_list_suffix(remove.group(1)))
        return ShoppingListRequest("remove", list_key, items) if items else None

    add = re.match(
        r"^(?:anade|añade|agrega|apunta|pon)\s+(.+)$", original, flags=re.IGNORECASE
    )
    if add:
        items = _split_items(_without_list_suffix(add.group(1)))
        return ShoppingListRequest("add", list_key, items) if items else None

    is_list_query = "lista" in normalized and re.search(
        r"\b(?:que|dime|muestra|ver|consulta|hay|falta|faltan)\b", normalized
    )
    is_missing_query = re.search(
        r"\b(?:falta|faltan)\b.*\bcomprar\b", normalized
    )
    if is_list_query or is_missing_query:
        return ShoppingListRequest("list", list_key)
    return None


class HomeAssistantShoppingListService:
    def __init__(
        self,
        base_url: str,
        token: str,
        entities: dict[str, str],
        *,
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.token = token.strip()
        self.entities = {key: value.strip() for key, value in entities.items()}
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def display_name(self, list_key: str) -> str:
        return LIST_NAMES.get(list_key, list_key)

    def _entity_id(self, list_key: str) -> str:
        entity_id = self.entities.get(list_key, "")
        if not self.base_url or not self.token or not entity_id:
            raise ShoppingListServiceError(
                f"La lista {self.display_name(list_key)} todavía no está configurada."
            )
        return entity_id

    async def items(
        self, list_key: str, *, status: str = "needs_action"
    ) -> list[ShoppingListItem]:
        entity_id = self._entity_id(list_key)
        response = await self._call(
            "get_items", {"entity_id": entity_id, "status": status}, return_response=True
        )
        try:
            raw_items = response["service_response"][entity_id]["items"]
        except (KeyError, TypeError) as exc:
            raise ShoppingListServiceError(
                "Home Assistant ha devuelto una respuesta de lista no válida."
            ) from exc
        if not isinstance(raw_items, list):
            raise ShoppingListServiceError(
                "Home Assistant ha devuelto una respuesta de lista no válida."
            )
        return [self._parse_item(item) for item in raw_items if isinstance(item, dict)]

    async def add_items(self, list_key: str, items: tuple[str, ...]) -> None:
        entity_id = self._entity_id(list_key)
        for item in items:
            await self._call("add_item", {"entity_id": entity_id, "item": item})

    async def complete_items(self, list_key: str, names: tuple[str, ...]) -> None:
        await self._update_named_items(list_key, names, "completed")

    async def remove_items(self, list_key: str, names: tuple[str, ...]) -> None:
        entity_id = self._entity_id(list_key)
        current = await self.items(list_key)
        for name in names:
            item = self._find_item(current, name)
            await self._call("remove_item", {"entity_id": entity_id, "item": item.uid})

    async def clear_completed(self, list_key: str) -> None:
        entity_id = self._entity_id(list_key)
        await self._call("remove_completed_items", {"entity_id": entity_id})

    async def _update_named_items(
        self, list_key: str, names: tuple[str, ...], status: str
    ) -> None:
        entity_id = self._entity_id(list_key)
        current = await self.items(list_key)
        for name in names:
            item = self._find_item(current, name)
            await self._call(
                "update_item", {"entity_id": entity_id, "item": item.uid, "status": status}
            )

    async def _call(
        self, action: str, payload: dict[str, Any], *, return_response: bool = False
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        suffix = "?return_response" if return_response else ""
        url = f"{self.base_url}/api/services/todo/{action}{suffix}"
        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as exc:
            raise ShoppingListServiceError(
                "Home Assistant no ha podido gestionar la lista de la compra."
            ) from exc

    @staticmethod
    def _parse_item(item: dict[str, Any]) -> ShoppingListItem:
        summary = str(item.get("summary") or "").strip()
        uid = str(item.get("uid") or "").strip()
        if not summary or not uid:
            raise ShoppingListServiceError("Hay un artículo de lista no válido.")
        return ShoppingListItem(summary, uid, str(item.get("status") or "needs_action"))

    @staticmethod
    def _find_item(items: list[ShoppingListItem], requested_name: str) -> ShoppingListItem:
        normalized = _normalize(requested_name)
        matches = [item for item in items if _normalize(item.summary) == normalized]
        if not matches:
            raise ShoppingListServiceError(
                f"No encuentro «{requested_name}» entre los productos pendientes."
            )
        if len(matches) > 1:
            raise ShoppingListServiceError(
                f"Hay más de un producto llamado «{requested_name}»."
            )
        return matches[0]


def format_shopping_list(name: str, items: list[ShoppingListItem]) -> str:
    if not items:
        return f"La lista {name} está vacía."
    return "\n".join(
        [f"Lista de la compra — {name}:", *(f"• {item.summary}" for item in items)]
    )


def format_shopping_confirmation(request: ShoppingListRequest) -> str:
    name = LIST_NAMES[request.list_key]
    if request.operation == "clear_completed":
        return f"¿Quieres borrar definitivamente los productos comprados de {name}?"
    products = "\n".join(f"• {item}" for item in request.items)
    return f"Vas a borrar de {name}:\n\n{products}\n\n¿Quieres continuar?"

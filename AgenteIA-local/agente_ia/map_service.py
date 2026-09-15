from __future__ import annotations

import asyncio
import io
import math
import re
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from PIL import Image, ImageDraw, ImageFont


BROUTER_URL = "https://brouter.de/brouter"
OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "AgenteIA-local/0.1 (mapa solicitado por el usuario)"
TILE_CACHE_MAX_AGE = timedelta(days=7)
START = (-1.88508, 40.84339)
ROUTE_WAYPOINTS = (
    (
        "Ruta norte",
        "-1.88508,40.84339;-1.872,40.855;-1.892,40.858;-1.88508,40.84339",
        "#d62728",
    ),
    (
        "Ruta sur",
        "-1.88508,40.84339;-1.870,40.830;-1.895,40.828;-1.88508,40.84339",
        "#1f77b4",
    ),
    (
        "Ruta oeste",
        "-1.88508,40.84339;-1.900,40.844;-1.900,40.852;-1.88508,40.84339",
        "#2ca02c",
    ),
)


class MapServiceError(RuntimeError):
    """Error controlado al crear una salida cartográfica."""


@dataclass(frozen=True, slots=True)
class MapResult:
    image_path: Path
    caption: str
    elapsed_seconds: float


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def is_molina_hiking_map_request(prompt: str) -> bool:
    text = _plain(prompt)
    return (
        "molina de aragon" in text
        and "mapa" in text
        and bool(re.search(r"\bruta(?:s)?\b", text))
        and ("senderismo" in text or "senderista" in text)
    )


def _lon_to_world_x(lon: float, zoom: int) -> float:
    return (lon + 180.0) / 360.0 * (2**zoom) * 256


def _lat_to_world_y(lat: float, zoom: int) -> float:
    limited = min(max(lat, -85.05112878), 85.05112878)
    radians = math.radians(limited)
    return (
        1.0
        - math.asinh(math.tan(radians)) / math.pi
    ) / 2.0 * (2**zoom) * 256


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    *,
    fill: str,
    width: int = 7,
    dash: float = 14,
    gap: float = 9,
) -> None:
    for start, end in zip(points, points[1:]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        position = 0.0
        while position < length:
            finish = min(position + dash, length)
            p1 = (start[0] + dx * position / length, start[1] + dy * position / length)
            p2 = (start[0] + dx * finish / length, start[1] + dy * finish / length)
            draw.line((p1, p2), fill=fill, width=width)
            position += dash + gap


class HikingMapService:
    """Genera un PNG verificable a partir de rutas calculadas sobre caminos OSM."""

    def __init__(self, *, zoom: int = 14, client_factory=httpx.AsyncClient) -> None:
        self.zoom = zoom
        self._client_factory = client_factory

    def supports(self, prompt: str) -> bool:
        return is_molina_hiking_map_request(prompt)

    async def create(self, prompt: str) -> MapResult:
        if not self.supports(prompt):
            raise MapServiceError("La petición cartográfica todavía no está soportada.")
        started = perf_counter()
        headers = {"User-Agent": USER_AGENT}
        async with self._client_factory(headers=headers, timeout=60.0) as client:
            routes = await asyncio.gather(
                *(self._fetch_route(client, name, points, color) for name, points, color in ROUTE_WAYPOINTS)
            )
            image = await self._render_map(client, routes)

        output_dir = Path(tempfile.gettempdir()) / "agenteia_mapas"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"molina_de_aragon_senderismo-{uuid4().hex}.png"
        image.save(output_path, format="PNG", optimize=True)
        distances = ", ".join(f"{route[0]}: {route[2]:.1f} km" for route in routes)
        return MapResult(
            image_path=output_path,
            caption=(
                "Tres propuestas circulares alrededor de Molina de Aragón.\n"
                f"{distances}.\n\n"
                "Rutas calculadas sobre caminos cartografiados. Verifica el terreno, "
                "la señalización y las condiciones antes de salir."
            ),
            elapsed_seconds=perf_counter() - started,
        )

    async def _fetch_route(
        self,
        client: httpx.AsyncClient,
        name: str,
        lonlats: str,
        color: str,
    ) -> tuple[str, list[tuple[float, float]], float, str]:
        response = await client.get(
            BROUTER_URL,
            params={
                "lonlats": lonlats,
                "profile": "trekking",
                "alternativeidx": "0",
                "format": "geojson",
            },
        )
        response.raise_for_status()
        feature = response.json()["features"][0]
        coordinates = [tuple(point[:2]) for point in feature["geometry"]["coordinates"]]
        distance_km = float(feature["properties"]["track-length"]) / 1000
        if not 5 <= distance_km <= 10:
            raise MapServiceError(f"{name} queda fuera de 5–10 km ({distance_km:.1f} km).")
        return name, coordinates, distance_km, color

    async def _render_map(
        self,
        client: httpx.AsyncClient,
        routes: list[tuple[str, list[tuple[float, float]], float, str]],
    ) -> Image.Image:
        all_points = [point for _, points, _, _ in routes for point in points]
        world_x = [_lon_to_world_x(lon, self.zoom) for lon, _ in all_points]
        world_y = [_lat_to_world_y(lat, self.zoom) for _, lat in all_points]
        min_tile_x = math.floor(min(world_x) / 256) - 1
        max_tile_x = math.floor(max(world_x) / 256) + 1
        min_tile_y = math.floor(min(world_y) / 256) - 1
        max_tile_y = math.floor(max(world_y) / 256) + 1
        width = (max_tile_x - min_tile_x + 1) * 256
        height = (max_tile_y - min_tile_y + 1) * 256
        canvas = Image.new("RGB", (width, height), "white")
        tile_cache = Path(tempfile.gettempdir()) / "agenteia_mapas" / "tiles"
        tile_cache.mkdir(parents=True, exist_ok=True)
        semaphore = asyncio.Semaphore(4)

        async def fetch_tile(x: int, y: int) -> tuple[int, int, Image.Image]:
            cached = tile_cache / str(self.zoom) / str(x) / f"{y}.png"
            if cached.is_file():
                modified = datetime.fromtimestamp(cached.stat().st_mtime, timezone.utc)
                if datetime.now(timezone.utc) - modified <= TILE_CACHE_MAX_AGE:
                    return x, y, Image.open(cached).convert("RGB")
            async with semaphore:
                response = await client.get(OSM_TILE_URL.format(z=self.zoom, x=x, y=y))
                response.raise_for_status()
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(response.content)
            tile = Image.open(io.BytesIO(response.content)).convert("RGB")
            return x, y, tile

        tiles = await asyncio.gather(
            *(fetch_tile(x, y) for x in range(min_tile_x, max_tile_x + 1) for y in range(min_tile_y, max_tile_y + 1))
        )
        for x, y, tile in tiles:
            canvas.paste(tile, ((x - min_tile_x) * 256, (y - min_tile_y) * 256))

        draw = ImageDraw.Draw(canvas)
        origin_x = min_tile_x * 256
        origin_y = min_tile_y * 256
        for name, points, distance_km, color in routes:
            pixels = [
                (_lon_to_world_x(lon, self.zoom) - origin_x, _lat_to_world_y(lat, self.zoom) - origin_y)
                for lon, lat in points
            ]
            _draw_dashed_line(draw, pixels, fill="white", width=11)
            _draw_dashed_line(draw, pixels, fill=color, width=7)

        start_x = _lon_to_world_x(START[0], self.zoom) - origin_x
        start_y = _lat_to_world_y(START[1], self.zoom) - origin_y
        draw.ellipse((start_x - 10, start_y - 10, start_x + 10, start_y + 10), fill="white", outline="black", width=3)

        font = ImageFont.load_default(size=18)
        legend_height = 42 + len(routes) * 29
        draw.rounded_rectangle((14, 14, 310, 14 + legend_height), radius=10, fill=(255, 255, 255), outline="#555555", width=2)
        draw.text((28, 25), "Rutas de senderismo", fill="black", font=font)
        for index, (name, _, distance_km, color) in enumerate(routes):
            y = 58 + index * 29
            _draw_dashed_line(draw, [(28, y + 8), (80, y + 8)], fill=color, width=6, dash=9, gap=6)
            draw.text((92, y), f"{name}: {distance_km:.1f} km", fill="black", font=font)
        attribution = "© OpenStreetMap contributors · rutas: BRouter"
        box = draw.textbbox((0, 0), attribution, font=font)
        text_width = box[2] - box[0]
        draw.rectangle((width - text_width - 22, height - 31, width, height), fill=(255, 255, 255))
        draw.text((width - text_width - 12, height - 27), attribution, fill="black", font=font)
        return canvas

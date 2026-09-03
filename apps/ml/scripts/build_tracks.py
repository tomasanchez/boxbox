"""Convierte la geometría real de los circuitos a paths SVG para el frontend.

Fuente: `bacinger/f1-circuits`, GeoJSON derivado de OpenStreetMap (ODbL). La
longitud que declara para Zandvoort — 4.259 m — coincide con la del concepto de
diseño, así que es el mismo origen.

Proyección: equirectangular local centrada en la latitud del circuito. A escala
de circuito (unos pocos kilómetros) la distorsión es despreciable frente al
grosor del trazo, y evita depender de una librería de proyecciones.

    uv run --with requests python scripts/build_tracks.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import requests

SOURCE = "https://raw.githubusercontent.com/bacinger/f1-circuits/master/f1-circuits.geojson"

#: id del dataset -> clave usada en el frontend
WANTED = {
    "nl-1948": "zandvoort",
    "hu-1986": "hungaroring",
    "it-1922": "monza",
}

OUT = Path(__file__).resolve().parents[2] / "web" / "src" / "tracks.ts"

HEADER = """/**
 * Geometría real de los circuitos.
 *
 * Fuente: bacinger/f1-circuits (GeoJSON, derivado de OpenStreetMap, ODbL).
 * Proyección equirectangular local centrada en la latitud del circuito y
 * normalizada a un lienzo de 100x100 — a escala de circuito la distorsión es
 * despreciable y evita arrastrar una librería de proyecciones.
 *
 * Regenerar con `apps/ml/scripts/build_tracks.py`.
 */

export interface Track {
  name: string
  location: string
  /** Longitud oficial de la vuelta, en metros. */
  lengthM: number
  /** Path SVG cerrado en un viewBox 0 0 100 100. */
  path: string
}

export const TRACKS: Record<string, Track> = {"""


def to_svg_path(coordinates: list[list[float]]) -> str:
    """Proyecta [lon, lat] a un path SVG cerrado, centrado en 100x100."""
    mean_lat = sum(c[1] for c in coordinates) / len(coordinates)
    k = math.cos(math.radians(mean_lat))

    xs = [c[0] * k for c in coordinates]
    ys = [c[1] for c in coordinates]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width, height = max_x - min_x, max_y - min_y
    scale = 100.0 / max(width, height)

    offset_x = (100 - width * scale) / 2
    offset_y = (100 - height * scale) / 2

    points = [
        (
            round((x - min_x) * scale + offset_x, 2),
            # La y del SVG crece hacia abajo, al revés que la latitud.
            round((max_y - y) * scale + offset_y, 2),
        )
        for x, y in zip(xs, ys, strict=True)
    ]
    return "M " + " L ".join(f"{x} {y}" for x, y in points) + " Z"


def main() -> int:
    data = requests.get(SOURCE, timeout=60).json()

    blocks: list[str] = []
    for feature in data["features"]:
        properties = feature["properties"]
        key = WANTED.get(properties.get("id"))
        if key is None:
            continue
        path = to_svg_path(feature["geometry"]["coordinates"])
        blocks.append(
            f"  {key}: {{\n"
            f"    name: {json.dumps(properties['Name'], ensure_ascii=False)},\n"
            f"    location: {json.dumps(properties['Location'], ensure_ascii=False)},\n"
            f"    lengthM: {properties['length']},\n"
            f"    path:\n      {json.dumps(path)},\n"
            f"  }},"
        )
        print(f"  {key:<12} {properties['Name']:<28} {properties['length']} m")

    if len(blocks) != len(WANTED):
        raise SystemExit(f"esperaba {len(WANTED)} circuitos, encontré {len(blocks)}")

    OUT.write_text("\n".join([HEADER, *blocks, "}", ""]), encoding="utf-8")
    print(f"\nescrito {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

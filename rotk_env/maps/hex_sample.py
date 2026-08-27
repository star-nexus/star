"""Sample a source image through the game hex grid and emit an ASCII map.

Drop a Dynasty Warriors Red Cliff screenshot/map at a path, then:

    uv run python -m rotk_env.maps.hex_sample path/to/chibi_source.png \\
        --out rotk_env/maps/chibi.json --overlay /tmp/chibi_hex_overlay.png

Each hex is classified by the majority of pixels inside it.
Edit the ASCII afterwards if a few cells are wrong.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

from rotk_env.maps.ascii_map import CHAR_FOR, dump_ascii_map
from rotk_env.maps.map_file import MapDocument, dump_map, load_map
from rotk_env.prefabs.config import GameConfig, TerrainType
from rotk_env.utils.hex_utils import HexConverter


def _terrain_from_rgb(r: int, g: int, b: int) -> TerrainType:
    """Heuristic: water is blue, forest is dark green, hills/mountains darker."""
    mx = max(r, g, b)
    mn = min(r, g, b)
    sat = 0 if mx == 0 else (mx - mn) / mx
    if b > r + 25 and b > g + 10:
        return TerrainType.WATER
    if g > r + 15 and g > b + 15 and g < 140:
        return TerrainType.FOREST
    if mx < 70:
        return TerrainType.MOUNTAIN
    if 80 < r < 180 and 60 < g < 140 and b < g and sat > 0.2:
        return TerrainType.HILL
    if mx > 160 and sat < 0.25:
        return TerrainType.URBAN
    return TerrainType.PLAIN


def _point_in_hex(px: float, py: float, corners: list[tuple[float, float]]) -> bool:
    inside = False
    n = len(corners)
    j = n - 1
    for i in range(n):
        xi, yi = corners[i]
        xj, yj = corners[j]
        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def sample_image(
    image: Image.Image,
    margin: float = 0.04,
) -> dict[tuple[int, int], TerrainType]:
    conv = HexConverter()
    half_w = GameConfig.MAP_WIDTH // 2
    half_h = GameConfig.MAP_HEIGHT // 2
    cells = [
        (col, row)
        for col in range(-half_w, half_w + 1)
        for row in range(-half_h, half_h + 1)
    ]
    xs, ys = zip(*(conv.hex_to_pixel(c, r) for c, r in cells))
    min_x, max_x = min(xs) - conv.size, max(xs) + conv.size
    min_y, max_y = min(ys) - conv.size, max(ys) + conv.size
    img_w, img_h = image.size
    pad_x = img_w * margin
    pad_y = img_h * margin
    usable_w = img_w - 2 * pad_x
    usable_h = img_h - 2 * pad_y
    scale = min(usable_w / (max_x - min_x), usable_h / (max_y - min_y))

    def world_to_img(x: float, y: float) -> tuple[float, float]:
        # hex y increases up; image y increases down
        ix = pad_x + (x - min_x) * scale
        iy = pad_y + (max_y - y) * scale
        return ix, iy

    rgb = image.convert("RGB")
    pixels = rgb.load()
    terrain = {}
    step = max(2, int(conv.size * scale / 6))
    for col, row in cells:
        corners = [world_to_img(x, y) for x, y in conv.get_hex_corners(col, row)]
        xs_c = [p[0] for p in corners]
        ys_c = [p[1] for p in corners]
        votes: Counter[TerrainType] = Counter()
        for ix in range(int(min(xs_c)), int(max(xs_c)) + 1, step):
            for iy in range(int(min(ys_c)), int(max(ys_c)) + 1, step):
                if ix < 0 or iy < 0 or ix >= img_w or iy >= img_h:
                    continue
                if not _point_in_hex(ix + 0.5, iy + 0.5, corners):
                    continue
                votes[_terrain_from_rgb(*pixels[ix, iy])] += 1
        terrain[(col, row)] = votes.most_common(1)[0][0] if votes else TerrainType.PLAIN
    return terrain


def draw_overlay(
    image: Image.Image,
    terrain: dict[tuple[int, int], TerrainType],
    out_path: Path,
) -> None:
    conv = HexConverter()
    half_w = GameConfig.MAP_WIDTH // 2
    half_h = GameConfig.MAP_HEIGHT // 2
    cells = [
        (col, row)
        for col in range(-half_w, half_w + 1)
        for row in range(-half_h, half_h + 1)
    ]
    xs, ys = zip(*(conv.hex_to_pixel(c, r) for c, r in cells))
    min_x, max_x = min(xs) - conv.size, max(xs) + conv.size
    min_y, max_y = min(ys) - conv.size, max(ys) + conv.size
    img_w, img_h = image.size
    margin = 0.04
    pad_x = img_w * margin
    pad_y = img_h * margin
    scale = min(
        (img_w - 2 * pad_x) / (max_x - min_x),
        (img_h - 2 * pad_y) / (max_y - min_y),
    )

    def world_to_img(x: float, y: float) -> tuple[float, float]:
        ix = pad_x + (x - min_x) * scale
        iy = pad_y + (max_y - y) * scale
        return ix, iy

    overlay = image.convert("RGBA").copy()
    draw = ImageDraw.Draw(overlay)
    colors = {
        TerrainType.PLAIN: (240, 220, 160, 80),
        TerrainType.WATER: (40, 90, 200, 110),
        TerrainType.FOREST: (30, 120, 50, 100),
        TerrainType.HILL: (160, 110, 50, 100),
        TerrainType.MOUNTAIN: (90, 90, 90, 110),
        TerrainType.URBAN: (200, 200, 200, 110),
    }
    for col, row in cells:
        corners = [world_to_img(x, y) for x, y in conv.get_hex_corners(col, row)]
        draw.polygon(corners, fill=colors[terrain[(col, row)]], outline=(20, 20, 20, 200))
    overlay.save(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Source Red Cliff / Chibi map image")
    parser.add_argument(
        "--out",
        type=Path,
        default=MAPS_DIR_CHIBI,
        help="Map file to write (.json keeps formations if the file already exists)",
    )
    parser.add_argument(
        "--overlay",
        type=Path,
        default=None,
        help="Optional PNG of the hex net over the source image",
    )
    args = parser.parse_args()
    image = Image.open(args.image)
    terrain = sample_image(image)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.suffix == ".json":
        formations = {}
        name = args.out.stem
        if args.out.exists():
            existing = load_map(args.out)
            formations = existing.formations
            name = existing.name
        doc = MapDocument(
            id=args.out.stem,
            name=name,
            width=GameConfig.MAP_WIDTH,
            height=GameConfig.MAP_HEIGHT,
            terrain=terrain,
            formations=formations,
        )
        args.out.write_text(dump_map(doc), encoding="utf-8")
    else:
        header = (
            "# Generated by rotk_env.maps.hex_sample. Edit cells that look wrong.\n"
            "# . plain  ~ water  F forest  H hill  M mountain  C urban\n"
        )
        args.out.write_text(header + dump_ascii_map(terrain), encoding="utf-8")
    print(f"Wrote {args.out}")
    if args.overlay:
        draw_overlay(image, terrain, args.overlay)
        print(f"Wrote overlay {args.overlay}")


MAPS_DIR_CHIBI = Path(__file__).resolve().parent / "chibi.json"


if __name__ == "__main__":
    main()

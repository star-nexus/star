# STAR Map Editor v2.0

A dependency-free browser map editor for STAR / StarBench.

## v2.0 changes

- Large maps: odd width / height from **5 to 101** (v1.5 stopped at 51).
- Typed unit painting: paint **Infantry / Archer / Cavalry** directly into Wei / Shu / Wu formations.
- Native typed export: formation slots are exported as `[col, row, type]`, which is accepted by `rotk_env.maps.map_file`.
- Legacy map compatibility: untyped `[col, row]` slots are inferred from `unit_mix` exactly like the runtime loader; without a mix they become Infantry.
- Faction colors are explicitly aligned to STAR: **Wei blue, Shu red, Wu green**.
- Real map zoom and pan: wheel / trackpad to zoom, Space+drag or middle-drag to pan, plus Fit / +/- controls.
- Resize preserves terrain and unit slots that remain inside the new bounds.
- Large-map coordinate labels are automatically suppressed while zoomed out when the map has more than 3000 cells.

## Run

Open `index.html` directly in a modern browser, or serve this directory with any static server:

```bash
python -m http.server 8080 --directory tools/map-editor
```

Then visit `http://localhost:8080`.

## Core workflow

1. Choose an odd map width / height up to 101 and click **Create / Resize**.
2. Paint terrain.
3. Under **Units / Formation**, choose a faction and unit type.
4. Click + drag to paint typed spawn units. Use **Erase Unit** to remove them.
5. Pan / zoom to work on large maps.
6. Run validation.
7. Export JSON and place it in `rotk_env/maps/`.

## Export format

v2 writes explicit unit types:

```json
{
  "formations": {
    "wei": [[-9, 15, "infantry"], [-8, 15, "archer"]],
    "shu": [[-15, -10, "cavalry"]],
    "wu": [[8, -10, "infantry"]]
  }
}
```

Supported unit types are `infantry`, `archer`, and `cavalry`.

The editor preserves an imported `unit_mix` field for round trips, but explicit v2 slot types are authoritative.

## Terrain legend

| Character | Terrain |
|---|---|
| `.` | plain |
| `~` | water |
| `F` | forest |
| `H` | hill |
| `M` | mountain |
| `C` | urban |

The editor exports STAR's native map schema instead of defining an editor-only format.

## Image → Map workflow

1. Create the target map size.
2. Click **Import PNG / JPG**.
3. Adjust reference opacity if useful.
4. Click **Generate Terrain**.
5. Manually correct terrain and typed formations.
6. Run validation.
7. Export JSON.

Image classification is heuristic. Treat generated terrain as a starting point, not final gameplay topology.

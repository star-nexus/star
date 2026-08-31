# STAR Map Editor v1.5

A dependency-free browser map editor for STAR / StarBench.

## Run

Open `index.html` directly in a modern browser, or serve this directory with any static server:

```bash
python -m http.server 8080 --directory tools/map-editor
```

Then visit `http://localhost:8080`.

## Features

- Paint STAR terrain on a centered flat-top hex grid.
- Place Wei / Shu / Wu formation cells.
- Exact STAR `(col,row)` coordinates.
- Undo / redo.
- Edit and preview modes.
- Import existing STAR JSON maps.
- Export native `rotk_env/maps/*.json` format.
- Local browser save/load.
- Validation for spawn legality, overlaps, and cross-faction land connectivity.
- Import a PNG/JPG reference image.
- Generate terrain from an image using the same RGB heuristics as `rotk_env.maps.hex_sample`.

## Terrain legend

| Character | Terrain |
|---|---|
| `.` | plain |
| `~` | water |
| `F` | forest |
| `H` | hill |
| `M` | mountain |
| `C` | urban |

The editor intentionally exports STAR's native map schema instead of defining an editor-only format.

## Image → Map workflow

1. Create the target map size.
2. Click **Import PNG / JPG**.
3. Adjust reference opacity if useful.
4. Click **Generate Terrain**.
5. Manually correct terrain and formations.
6. Run validation.
7. Export JSON and place it in `rotk_env/maps/`.

Image classification is heuristic. Treat generated terrain as a starting point, not final gameplay topology.

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EDITOR_DIR = ROOT / "tools" / "map-editor"


def _read(name: str) -> str:
    return (EDITOR_DIR / name).read_text(encoding="utf-8")


def test_map_editor_v2_entrypoint_and_large_map_limit():
    html = _read("index.html")
    js = _read("editor-v2.js")

    assert "STAR Map Editor <span>v2.0</span>" in html
    assert 'src="editor-v2.js"' in html
    assert 'href="style-v2.css"' in html
    assert html.count('max="201"') >= 2
    assert html.count('step="1"') >= 2
    assert "const MAX_MAP_SIZE = 201;" in js
    assert "n % 2 === 1" not in js
    assert "Number.isInteger(n) && n >= 5 && n <= MAX_MAP_SIZE" in js
    assert "Scan bounds incrementally so 120x120+ maps" in js
    assert "minX: Math.min(...xs) - margin" not in js
    assert "maxY: Math.max(...ys) + margin" not in js


def test_map_editor_v2_exposes_typed_unit_painting():
    html = _read("index.html")
    js = _read("editor-v2.js")

    for unit_type in ("infantry", "archer", "cavalry"):
        assert f'data-unit-type="{unit_type}"' in html
        assert unit_type in js

    assert 'state.tool = { kind: "unit" }' in js
    assert "state.formations[state.selectedFaction].push([col, row, state.selectedUnitType]);" in js
    assert 'cells.map(([col, row, type = "infantry"]) => [col, row, type])' in js


def test_map_editor_v2_uses_star_faction_colors_and_navigation_controls():
    css = _read("style-v2.css")
    color_fix = _read("faction-colors-v2.js")
    html = _read("index.html")

    assert 'src="faction-colors-v2.js"' in html
    assert 'Wei: "#4f79ff"' in color_fix
    assert 'Shu: "#ff5f5f"' in color_fix
    assert 'Wu: "#46c878"' in color_fix
    assert ".dot.wei { background: #4f79ff; }" in css
    assert ".dot.shu { background: #ff5f5f; }" in css
    assert ".dot.wu { background: #46c878; }" in css

    for control in ("zoomOutBtn", "zoomFitBtn", "zoomInBtn"):
        assert f'id="{control}"' in html
    assert 'els.svg.addEventListener("wheel"' in _read("editor-v2.js")
    assert "state.spaceDown" in _read("editor-v2.js")

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
    assert html.count('max="101"') >= 2
    assert "const MAX_MAP_SIZE = 101;" in js


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
    js = _read("editor-v2.js")
    css = _read("style-v2.css")
    html = _read("index.html")

    assert 'wei: { label: "Wei", color: "#4f79ff" }' in js
    assert 'shu: { label: "Shu", color: "#46c878" }' in js
    assert 'wu: { label: "Wu", color: "#ff5f5f" }' in js
    assert ".dot.wei { background: #4f79ff; }" in css
    assert ".dot.shu { background: #46c878; }" in css
    assert ".dot.wu { background: #ff5f5f; }" in css

    for control in ("zoomOutBtn", "zoomFitBtn", "zoomInBtn"):
        assert f'id="{control}"' in html
    assert 'els.svg.addEventListener("wheel"' in js
    assert "state.spaceDown" in js

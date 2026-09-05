"""Structural checks for the Phase-4 synthetic scale-map generator."""

from __future__ import annotations

import json

import pytest

from rotk_env.maps.map_file import load_map
from tools.generate_scale_map import build_scale_payload, generate_formations


def test_generated_scale_map_is_deterministic_unique_and_loadable(tmp_path):
    payload_a = build_scale_payload(size=9, total_units=50, seed=42)
    payload_b = build_scale_payload(size=9, total_units=50, seed=42)
    assert payload_a == payload_b

    formations = payload_a["formations"]
    cells = [tuple(cell[:2]) for faction_cells in formations.values() for cell in faction_cells]
    assert len(cells) == 50
    assert len(set(cells)) == 50
    assert sum(len(group) for group in formations.values()) == 50
    assert max(len(group) for group in formations.values()) - min(
        len(group) for group in formations.values()
    ) <= 1

    assert payload_a["width"] == 9
    assert payload_a["height"] == 9
    assert payload_a["unit_mix"] == [1, 3, 1]
    assert payload_a["scale_profile"]["terrain"] == "all_plain"
    assert payload_a["terrain"] == ["." * 9 for _ in range(9)]

    path = tmp_path / "scale.json"
    path.write_text(json.dumps(payload_a), encoding="utf-8")
    doc = load_map(path)
    assert doc.width == 9
    assert doc.height == 9
    assert len(doc.terrain) == 81
    assert sum(len(group) for group in doc.formations.values()) == 50


def test_generated_scale_map_rejects_even_size_and_over_capacity():
    with pytest.raises(ValueError, match="size must be odd"):
        generate_formations(size=10, total_units=10, seed=42)
    with pytest.raises(ValueError, match="has only 81 cells"):
        generate_formations(size=9, total_units=82, seed=42)

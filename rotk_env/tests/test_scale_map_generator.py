from rotk_env.maps.map_file import MapDocument
from rotk_env.prefabs.config import TerrainType
from tools.generate_scale_map import generate_scale_formations


def _doc(width=9, height=9):
    half_w = width // 2
    half_h = height // 2
    terrain = {
        (col, row): TerrainType.PLAIN
        for col in range(-half_w, width - half_w)
        for row in range(half_h - height + 1, half_h + 1)
    }
    return MapDocument(
        id="scale-fixture",
        name="Scale Fixture",
        width=width,
        height=height,
        terrain=terrain,
        formations={
            "wei": [(-3, 3), (-2, 3)],
            "shu": [(-3, -3), (-2, -3)],
            "wu": [(3, 0), (2, 0)],
        },
    )


def test_scale_formations_are_deterministic_balanced_and_non_overlapping():
    doc = _doc()
    first = generate_scale_formations(
        doc,
        total_units=50,
        factions=["wei", "shu", "wu"],
        seed=42,
    )
    second = generate_scale_formations(
        doc,
        total_units=50,
        factions=["wei", "shu", "wu"],
        seed=42,
    )

    assert first == second
    counts = [len(first[name]) for name in ("wei", "shu", "wu")]
    assert sum(counts) == 50
    assert max(counts) - min(counts) <= 1

    all_cells = [cell for cells in first.values() for cell in cells]
    assert len(all_cells) == len(set(all_cells))
    assert all(doc.terrain[cell] is not TerrainType.WATER for cell in all_cells)


def test_scale_formations_reject_more_units_than_passable_cells():
    doc = _doc(width=5, height=5)
    doc.terrain[(0, 0)] = TerrainType.WATER

    try:
        generate_scale_formations(
            doc,
            total_units=25,
            factions=["wei", "shu", "wu"],
            seed=1,
        )
    except ValueError as exc:
        assert "passable cells" in str(exc)
    else:
        raise AssertionError("expected capacity error")

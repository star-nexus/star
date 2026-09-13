"""Apply owned native display deltas to a Python presentation World.

The supplied World is prepared once with the scene's map, sprites and UI. Its
simulation systems must not run after native handoff. This consumer has no native
handle, advances no timers, and invokes no gameplay or command handlers. Rendering
can mutate these derived objects without changing the native world.
"""

from copy import deepcopy
from rotk_env import components as c
from rotk_env.prefabs.config import Faction, GameMode, UnitType, UnitState
from rotk_env.utils.unit_spatial_index import (
    rebuild_unit_spatial_index,
    update_unit_spatial_index,
    remove_unit_from_spatial_index,
)
from rotk_env.utils.fog_visibility_journal import publish_fog_visibility_delta
from .visual_projection import VisualProjection

_UNIT_COLUMNS = {
    "position": c.HexPosition,
    "unit": c.Unit,
    "count": c.UnitCount,
    "movement": c.MovementAnimation,
    "movement_points": c.MovementPoints,
    "action_points": c.ActionPoints,
    "status": c.UnitStatus,
    "skill_points": c.SkillPoints,
    "construction_points": c.ConstructionPoints,
}
_STATE_TYPES = {
    cls.__name__: cls
    for cls in (c.GameTime, c.GameState, c.GameModeComponent, c.TurnManager)
}
_ENUM_FIELDS = {
    c.Unit: dict(unit_type=UnitType, faction=Faction),
    c.TerritoryControl: dict(controlling_faction=Faction),
    c.GameTime: dict(current_mode=GameMode),
    c.GameState: dict(current_player=Faction, game_mode=GameMode, winner=Faction),
    c.GameModeComponent: dict(mode=GameMode),
}


def _component(cls, state):
    values = deepcopy(state)
    for key, enum in _ENUM_FIELDS.get(cls, {}).items():
        if values.get(key) is not None:
            values[key] = enum(values[key])
    if cls is c.UnitStatus and values.pop("current_status_is_enum", False):
        values["current_status"] = UnitState(values["current_status"])
    if cls is c.MovementAnimation:
        values["path"] = [tuple(cell) for cell in values["path"]]
        for key in ("start_pixel_pos", "target_pixel_pos"):
            if values[key] is not None:
                values[key] = tuple(values[key])
    return cls(**values)


class WorldPresentation:
    """O(changed rows + active visuals) application; one initial spatial rebuild.

    Recreate this consumer and the prepared display World on a scene reset. An
    epoch mismatch or an older revision is rejected before any display mutation.
    Events are returned to the application for explicit presentation dispatch.
    """

    def __init__(self, world):
        self.world = world
        self.visuals = VisualProjection()
        self.epoch = None
        self.revision = -1
        rebuild_unit_spatial_index(world)

    def apply(self, delta):
        if self.epoch is not None and delta["epoch"] != self.epoch:
            raise ValueError("Presentation epoch changed; prepare a new display World")
        if delta["revision"] < self.revision:
            raise ValueError("Stale presentation delta")
        if self.epoch is None and not delta["fog"]["full"]:
            raise ValueError("First presentation delta must contain a full baseline")
        self.epoch = delta["epoch"]
        self.revision = delta["revision"]
        world = self.world
        for uid in delta["removed"]:
            remove_unit_from_spatial_index(world, uid)
            world.destroy_entity(uid)
            ui = world.get_singleton_component(c.UIState)
            if ui is not None and ui.selected_unit == uid:
                ui.selected_unit = None
        for row in delta["units"]:
            uid = world.ensure_entity(row["id"])
            for key, cls in _UNIT_COLUMNS.items():
                state = row[key]
                if state is None:
                    world.remove_component(uid, cls)
                else:
                    world.add_component(uid, _component(cls, state))
            update_unit_spatial_index(world, uid)
        for row in delta["tiles"]:
            uid = world.ensure_entity(row["id"])
            world.add_component(uid, _component(c.TerritoryControl, row["control"]))
        for name, state in delta["state"].items():
            world.add_singleton_component(_component(_STATE_TYPES[name], state))
        self._apply_fog(delta["fog"])
        camera = world.get_singleton_component(c.Camera)
        self.visuals.apply(delta["visuals"], zoom=camera.zoom if camera else 1.0)
        for uid in delta["visuals"]["removed"]:
            world.destroy_entity(uid)
        visual_types = (
            c.AttackAnimation,
            c.DamageNumber,
            c.EffectAnimation,
            c.ProjectileAnimation,
        )
        for row in delta["visuals"]["rows"]:
            uid = row["id"]
            components = self.visuals.entities.get(uid, {})
            if components:
                world.ensure_entity(uid)
            for cls in visual_types:
                if cls in components:
                    world.add_component(uid, components[cls])
                else:
                    world.remove_component(uid, cls)
        world.bump_revision()
        return deepcopy(delta["events"])

    def update_camera(self):
        """Zoom affects current floating text even while the world is paused."""
        camera = self.world.get_singleton_component(c.Camera)
        self.visuals.set_zoom(camera.zoom if camera else 1.0)

    def _apply_fog(self, delta):
        world = self.world
        if delta["enabled"] is None:
            world.remove_singleton_component(c.FogOfWar)
            return
        fog = world.get_singleton_component(c.FogOfWar)
        if fog is None:
            fog = c.FogOfWar()
            world.add_singleton_component(fog)
        changes = {}
        if delta["full"]:
            for faction, cells in fog.faction_vision.items():
                changes.setdefault(faction, set()).update(cells)
            for faction, cells in fog.explored_tiles.items():
                changes.setdefault(faction, set()).update(cells)
            fog.faction_vision.clear()
            fog.explored_tiles.clear()
        fog.enabled = delta["enabled"]
        for entry in delta["factions"]:
            faction = Faction(entry["faction"])
            visible = fog.faction_vision.setdefault(faction, set())
            explored = fog.explored_tiles.setdefault(faction, set())
            dirty = changes.setdefault(faction, set())
            for cell in entry["cells"]:
                pos = (cell["col"], cell["row"])
                dirty.add(pos)
                for cells, flag in ((visible, "visible"), (explored, "explored")):
                    if cell[flag]:
                        cells.add(pos)
                    else:
                        cells.discard(pos)
        publish_fog_visibility_delta(world, changes)

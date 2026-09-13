//! Territory commands and capture tasks. Only unfinished capture IDs join a tick.
use crate::{
    codec::{action_integer, scalar_display},
    components::{
        ActionPoints, CaptureAction, ConstructionPoints, Position, TerritoryControl, UnitInfo,
    },
    hex::{self, Hex},
    observation::error,
    runtime::{InitialComponents, Runtime},
};
use bevy_ecs::entity::Entity;
use serde_json::{Value, json};

fn target(params: &Value) -> Result<(Option<Hex>, String), Value> {
    let p = &params["position"];
    if p.as_object().is_none_or(|p| p.is_empty()) {
        return Err(error("position must be object with col/row"));
    }
    let (Some(c), Some(r)) = (action_integer(&p["col"]), action_integer(&p["row"])) else {
        return Err(error("position col/row must be integers"));
    };
    // Imported maps are i32 bounded. Retain large parameter text without overflow
    // when deciding that the target is outside that map / too far away.
    let cell = i32::try_from(c)
        .ok()
        .zip(i32::try_from(r).ok())
        .map(|(c, r)| (i64::from(c), i64::from(r)));
    Ok((
        cell,
        format!(
            "({}, {})",
            scalar_display(&p["col"]),
            scalar_display(&p["row"])
        ),
    ))
}
fn success(message: String) -> Value {
    json!({"success":true,"result":true,"message":message,"details":message})
}
impl Runtime {
    fn mark_territory_visual(&mut self, tile: Entity) {
        if let Some(id) = self.world.ecs.get::<star_core::world::ExternalId>(tile) {
            self.presentation_tiles.insert(id.0);
        }
    }
    pub(crate) fn territory_entity(&self, cell: Hex) -> Option<Entity> {
        // All Python territory lookups deliberately treat external tile ID 0 as absent.
        let id = self.spatial.tiles.get(&cell)?.entity;
        if id == 0 {
            return None;
        }
        let entity = self.world.entity(id)?;
        self.world
            .ecs
            .get::<TerritoryControl>(entity)
            .map(|_| entity)
    }
    fn territory_turn_mode(&self) -> bool {
        self.singletons
            .get("GameModeComponent")
            .is_none_or(|g| g["mode"] == "turn_based")
    }
    fn set_territory_owner(&mut self, tile: Entity, uid: u64) {
        let Some(unit) = self.component::<UnitInfo>(uid) else {
            return;
        };
        let faction = unit.faction.clone();
        self.mark_territory_visual(tile);
        let mut control = self.world.ecs.get_mut::<TerritoryControl>(tile).unwrap();
        control.controlling_faction = Some(faction);
        control.being_captured = false;
        control.capturing_unit = None;
        control.capture_progress = 1.;
        control.captured_time = self.clock.elapsed;
    }
    fn cancel_capture(&mut self, cell: Hex) {
        if let Some(tile) = self.territory_entity(cell) {
            self.mark_territory_visual(tile);
            let mut control = self.world.ecs.get_mut::<TerritoryControl>(tile).unwrap();
            control.being_captured = false;
            control.capturing_unit = None;
            control.capture_progress = 0.;
        }
    }
    pub(crate) fn handle_territory(&mut self, action: &str, params: &Value) -> Value {
        let raw = &params["unit_id"];
        let Some(integer) = action_integer(raw) else {
            return error("unit_id must be integer");
        };
        let (cell, repr) = match target(params) {
            Ok(p) => p,
            Err(e) => return e,
        };
        let uid = u64::try_from(integer).ok();
        let Some((uid, unit)) = uid.and_then(|id| self.component::<UnitInfo>(id).map(|u| (id, u)))
        else {
            return error(&format!("Unit {} not found", scalar_display(raw)));
        };
        let faction = unit.faction.clone();
        if let Some(e) = self.turn_permission(uid, action) {
            return e;
        }
        let ap = self
            .component::<ActionPoints>(uid)
            .map_or(0, |p| p.current_ap);
        if action == "occupy" {
            let Some(pos) = self.component::<Position>(uid).map(Position::hex) else {
                return error("Unit missing position component");
            };
            if ap < 1 {
                return error(&format!(
                    "Insufficient action points for occupy: need 1, have {ap}"
                ));
            }
            if cell.is_none_or(|p| hex::distance(pos, p) > 1) {
                return error(&format!(
                    "Cannot occupy position {repr}: too far from unit position {}. Can only occupy current or adjacent positions.",
                    hex::repr(pos)
                ));
            }
            if !self.config.systems.contains_key("TerritorySystem") {
                return error("Territory system not available");
            }
            let Some(tile) = cell.and_then(|p| self.territory_entity(p)) else {
                return error(&format!(
                    "Failed to occupy position {repr}. Position may be contested or invalid."
                ));
            };
            if self
                .world
                .ecs
                .get::<TerritoryControl>(tile)
                .unwrap()
                .controlling_faction
                .as_deref()
                == Some(&faction)
            {
                return error(&format!(
                    "Position {repr} already controlled by faction {faction}"
                ));
            }
            // Immediate Agent occupy is distinct from the window's timed start_capture.
            self.set_territory_owner(tile, uid);
            self.world
                .ecs
                .get_mut::<ActionPoints>(self.world.entity(uid).unwrap())
                .unwrap()
                .current_ap -= 1;
            self.mark_ap_spent(uid);
            return success(format!(
                "Unit {} occupied territory at {repr}",
                scalar_display(raw)
            ));
        }
        if ap < 1 {
            return error(&format!(
                "Insufficient action points for fortify: need 1, have {ap}"
            ));
        }
        let cp = self
            .component::<ConstructionPoints>(uid)
            .map_or(0, |p| p.current_cp);
        if cp < 1 {
            return error(&format!(
                "Insufficient construction points for fortify: need 1, have {cp}"
            ));
        }
        let terrain = cell.map_or("plains", |p| self.action_terrain(p));
        let max = match terrain {
            "forest" | "hill" | "mountain" => 2,
            "city" | "urban" => 3,
            "water" => 0,
            _ => 1,
        };
        let tile = cell.and_then(|p| self.territory_entity(p));
        let control = tile.and_then(|t| self.world.ecs.get::<TerritoryControl>(t));
        let current = control
            .filter(|t| t.fortified)
            .map_or(0, |t| t.fortification_level);
        if current >= max {
            return error(&format!(
                "Fortification already at max level for terrain {terrain}: {current}/{max}"
            ));
        }
        if !self.config.systems.contains_key("TerritorySystem") {
            return error("Territory system not available");
        }
        if control.is_none_or(|t| t.controlling_faction.as_deref() != Some(&faction) || t.fortified)
        {
            return error("Cannot build fortification at this position");
        }
        let unit = self.world.entity(uid).unwrap();
        // Legacy realtime build checks resources in the handler but spends none.
        if self.territory_turn_mode() {
            self.world
                .ecs
                .get_mut::<ActionPoints>(unit)
                .unwrap()
                .current_ap -= 1;
            self.mark_ap_spent(uid);
            self.world
                .ecs
                .get_mut::<ConstructionPoints>(unit)
                .unwrap()
                .current_cp -= 1;
        }
        self.mark_territory_visual(tile.unwrap());
        let mut control = self
            .world
            .ecs
            .get_mut::<TerritoryControl>(tile.unwrap())
            .unwrap();
        control.fortified = true;
        control.fortification_level = 1;
        let mut result = success(format!(
            "Unit {} built fortification at {repr}, increasing level to {}/{max}",
            scalar_display(raw),
            current + 1
        ));
        // Preserve the handler's extra subtraction in the response, not the state.
        result["remaining_action_points"] =
            json!(self.component::<ActionPoints>(uid).unwrap().current_ap - 1);
        result
    }
    /// Framework input command. The Agent wire action `occupy` uses immediate capture.
    pub fn start_capture(&mut self, uid: u64, cell: Hex, wall_time: f64) -> Result<bool, String> {
        self.set_wall_metadata(wall_time)?;
        if !self.config.systems.contains_key("TerritorySystem") {
            return Err("Territory system not available".into());
        }
        let Some(unit) = self.component::<UnitInfo>(uid) else {
            return Ok(false);
        };
        let Some(pos) = self.component::<Position>(uid) else {
            return Ok(false);
        };
        if pos.hex() != cell {
            return Ok(false);
        }
        let Some(tile) = self.territory_entity(cell) else {
            return Ok(false);
        };
        let control = self.world.ecs.get::<TerritoryControl>(tile).unwrap();
        if control.controlling_faction.as_deref() == Some(&unit.faction) || control.being_captured {
            return Ok(false);
        }
        let turn = self.territory_turn_mode();
        if turn
            && self
                .component::<ActionPoints>(uid)
                .is_none_or(|p| p.current_ap < 1)
        {
            return Ok(false);
        }
        let cost = if control.is_city { 2 } else { 1 };
        let revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        let (id, entity) = self.world.spawn()?;
        self.world.ecs.entity_mut(entity).insert((
            InitialComponents(Default::default()),
            CaptureAction {
                capturing_unit: uid,
                target_position: cell,
                start_time: 0.,
                uses_action_points: turn,
                action_points_cost: cost,
                completed: false,
            },
        ));
        self.capturing.insert(id);
        self.mark_territory_visual(tile);
        let mut control = self.world.ecs.get_mut::<TerritoryControl>(tile).unwrap();
        control.being_captured = true;
        control.capturing_unit = Some(uid);
        control.capture_progress = 0.;
        if turn {
            self.world
                .ecs
                .get_mut::<ActionPoints>(self.world.entity(uid).unwrap())
                .unwrap()
                .current_ap -= 1;
            self.mark_ap_spent(uid);
        }
        self.revision = revision;
        Ok(true)
    }
    pub(crate) fn advance_captures(&mut self) -> Result<(), String> {
        if self
            .config
            .systems
            .get("TerritorySystem")
            .is_none_or(|s| s["enabled"] != true)
        {
            return Ok(());
        }
        // Stable external-ID order, O(active); a scene reset rebuilds this set once.
        let mut remove = vec![];
        for id in self.capturing.iter().copied().collect::<Vec<_>>() {
            let Some(capture) = self.component::<CaptureAction>(id).cloned() else {
                remove.push(id);
                continue;
            };
            let cell = capture.target_position;
            if self.world.entity(capture.capturing_unit).is_none() {
                remove.push(id);
                continue;
            }
            if self
                .component::<Position>(capture.capturing_unit)
                .is_none_or(|p| p.hex() != cell)
            {
                self.cancel_capture(cell);
                remove.push(id);
                continue;
            }
            let Some(tile) = self.territory_entity(cell) else {
                remove.push(id);
                continue;
            };
            if self.territory_turn_mode() {
                if capture.uses_action_points {
                    self.set_territory_owner(tile, capture.capturing_unit);
                    remove.push(id);
                }
            } else {
                let start = if capture.start_time == 0. {
                    self.clock.elapsed
                } else {
                    capture.start_time
                };
                self.world
                    .ecs
                    .get_mut::<CaptureAction>(self.world.entity(id).unwrap())
                    .unwrap()
                    .start_time = start;
                self.mark_territory_visual(tile);
                let mut control = self.world.ecs.get_mut::<TerritoryControl>(tile).unwrap();
                if control.capture_time_required == 0. {
                    return Err("float division by zero".into());
                }
                control.capture_progress =
                    ((self.clock.elapsed - start) / control.capture_time_required).min(1.);
                if control.capture_progress >= 1. {
                    self.set_territory_owner(tile, capture.capturing_unit);
                    remove.push(id);
                }
            }
        }
        for id in remove {
            self.capturing.remove(&id);
            self.world.remove(id);
        }
        Ok(())
    }
}

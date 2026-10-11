//! Trusted Framework commands, separate from authenticated Agent requests.
//! Preserve the local UI's low-level rules and return values; no fake Agent join.
use crate::{components::ActionPoints, hex::Hex, runtime::Runtime, vision::Fog};
use serde::Deserialize;
use serde_json::{Value, json};

#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ControlCommand {
    Move { unit_id: u64, position: Hex },
    Attack { unit_id: u64, target_id: u64 },
    Wait { unit_id: u64 },
    Garrison { unit_id: u64 },
    Fortify { unit_id: u64, position: Hex },
    SetFog { enabled: bool },
    ToolbarEndTurn,
}

impl Runtime {
    pub fn execute_control(
        &mut self,
        command: ControlCommand,
        wall_time: f64,
    ) -> Result<Value, String> {
        self.set_wall_metadata(wall_time)?;
        // Even a rejected command ends a read context. No query can reuse a
        // cached pre-input state when a control partially mutated the world.
        self.revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        match command {
            ControlCommand::Move { unit_id, position } => {
                if self.config.interface["movement_system"] != true {
                    return Err("Movement system not available".into());
                }
                Ok(self.move_unit(unit_id, position))
            }
            ControlCommand::Attack { unit_id, target_id } => {
                if self.config.interface["combat_system"] != true {
                    return Err("Combat system not available".into());
                }
                if !self.can_attack(unit_id, Some(target_id)) {
                    return Ok(json!(false));
                }
                // The historical human attack returns whether the hit succeeded,
                // unlike the Agent method which returns a detailed action result.
                let result = self.execute_attack(unit_id, target_id)?;
                Ok(json!(
                    result["success"] == true && result["battle_result"]["hit_success"] == true
                ))
            }
            ControlCommand::Wait { unit_id } | ControlCommand::Garrison { unit_id } => {
                if let Some(entity) = self.world.entity(unit_id)
                    && let Some(mut ap) = self.world.ecs.get_mut::<ActionPoints>(entity)
                    && ap.current_ap >= 1
                {
                    ap.current_ap -= 1;
                    self.mark_ap_spent(unit_id);
                }
                // UI wait/garrison only spend one AP. They do not call Agent rest.
                Ok(Value::Null)
            }
            ControlCommand::Fortify { unit_id, position } => {
                if !self.config.systems.contains_key("TerritorySystem") {
                    return Err("Territory system not available".into());
                }
                Ok(json!(self.build_fortification(unit_id, position)))
            }
            ControlCommand::SetFog { enabled } => {
                if self.fog.is_none() {
                    self.fog = Some(Fog::default());
                    self.presentation_fog_full = true;
                }
                self.fog.as_mut().unwrap().enabled = enabled;
                Ok(Value::Null)
            }
            ControlCommand::ToolbarEndTurn => {
                // UIButtonSystem rotates its explicit TurnManager list. Unlike
                // keyboard end-turn, it performs no round reset or game-over
                // check, and emits no statistics or TurnStartEvent.
                if !self.singletons.contains_key("GameState") {
                    return Ok(Value::Null);
                }
                let Some(manager) = self.singletons.get_mut("TurnManager") else {
                    return Ok(Value::Null);
                };
                let players = manager["players"]
                    .as_array()
                    .ok_or("invalid turn players")?;
                let previous = manager["current_player_index"]
                    .as_i64()
                    .ok_or("invalid turn index")?;
                let index = if players.is_empty() {
                    previous
                } else {
                    ((i128::from(previous) + 1).rem_euclid(players.len() as i128)) as i64
                };
                let id = usize::try_from(index)
                    .ok()
                    .and_then(|i| players.get(i))
                    .and_then(Value::as_u64);
                manager["current_player_index"] = json!(index);
                let state = self.singletons.get_mut("GameState").unwrap();
                if index == 0 {
                    state["turn_number"] = json!(state["turn_number"].as_i64().unwrap_or(1) + 1);
                }
                if let Some((_, faction)) = self
                    .players
                    .iter()
                    .find(|(pid, _)| Some(*pid) == id && *pid != 0)
                {
                    state["current_player"] = json!(faction);
                }
                Ok(Value::Null)
            }
        }
    }
}

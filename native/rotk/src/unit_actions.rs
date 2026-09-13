//! Existing move/attack validation order and external result formatting.
use crate::{
    codec::{action_integer, scalar_display},
    components::{ActionPoints, CombatStats, Headcount, MovePoints, Position, Status, UnitInfo},
    hex,
    observation::error,
    runtime::Runtime,
};
use serde_json::{Value, json};

fn extra(message: &str, data: Value) -> Value {
    let mut result = error(message);
    result
        .as_object_mut()
        .unwrap()
        .extend(data.as_object().unwrap().clone());
    result
}
fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
        Value::Number(n) => {
            if n.is_f64() {
                "float"
            } else {
                "int"
            }
        }
    }
}
fn id(v: &Value) -> Option<u64> {
    action_integer(v).and_then(|v| u64::try_from(v).ok())
}
impl Runtime {
    pub(crate) fn handle_rest(&mut self, params: &Value) -> Value {
        let raw = &params["unit_id"];
        if action_integer(raw).is_none() {
            return error("unit_id must be integer");
        }
        let uid = id(raw);
        let Some(entity) = uid
            .and_then(|uid| self.world.entity(uid))
            .filter(|&e| self.world.ecs.get::<UnitInfo>(e).is_some())
        else {
            return error(&format!("Unit {} not found", scalar_display(raw)));
        };
        let uid = uid.unwrap();
        if let Some(error) = self.turn_permission(uid, "rest") {
            return error;
        }
        let Some(mut status) = self.world.ecs.get_mut::<Status>(entity) else {
            return error(&format!("Unit {} has no status", scalar_display(raw)));
        };
        self.presentation_dirty.insert(uid);
        status.wait_turns += 1;
        if status.wait_turns >= 2
            && status.current_status_is_enum
            && status.current_status == "confusion"
        {
            status.current_status = "normal".into();
            status.status_duration = 0;
        }
        let ap = self
            .world
            .ecs
            .get::<ActionPoints>(entity)
            .map_or(0, |p| p.current_ap);
        let message = format!("Unit {} is resting and recovering", scalar_display(raw));
        json!({"success":true,"result":true,"message":message,"details":message,"remaining_action_points":ap})
    }
    pub(crate) fn turn_permission(&self, uid: u64, action: &str) -> Option<Value> {
        let unit = self.component::<UnitInfo>(uid)?;
        if self
            .singletons
            .get("GameModeComponent")
            .is_some_and(|m| m["mode"].as_str() == Some("real_time"))
        {
            return None;
        }
        let Some(faction) = self.current_player_faction() else {
            return Some(extra(
                "Unable to determine current player",
                json!({"unit_id":uid,"action":action}),
            ));
        };
        if unit.faction != faction {
            return Some(extra(
                &format!(
                    "Not {}'s turn to act. Current turn: {faction}",
                    unit.faction
                ),
                json!({"unit_id":uid,"unit_faction":unit.faction,"current_turn_faction":faction,"action":action,
                "suggestion":format!("Wait for {}'s turn or switch to a {faction} unit",unit.faction)}),
            ));
        }
        None
    }
    pub fn handle_move(&mut self, params: &Value) -> Value {
        let raw = &params["unit_id"];
        let target = &params["target_position"];
        if action_integer(raw).is_none() {
            return extra(
                &format!("Invalid unit_id type: expected int, got {}", type_name(raw)),
                json!({"received_unit_id":raw,"expected_type":"int","valid_example":{"unit_id":123}}),
            );
        }
        if !target.is_object() || target.as_object().unwrap().is_empty() {
            return extra(
                &format!(
                    "Invalid target_position: expected dict with col/row, got {}",
                    type_name(target)
                ),
                json!({"received_target_position":target,"expected_format":{"col":"int","row":"int"},"valid_example":{"target_position":{"col":5,"row":8}}}),
            );
        }
        let col = &target["col"];
        let row = &target["row"];
        let (Some(c), Some(r)) = (action_integer(col), action_integer(row)) else {
            return extra(
                "Invalid coordinate types: col must be int, row must be int",
                json!({"received_col":col,"received_row":row,"received_col_type":type_name(col),"received_row_type":type_name(row),"expected_types":{"col":"int","row":"int"},"valid_example":{"target_position":{"col":5,"row":8}}}),
            );
        };
        let cell = i64::try_from(c).ok().zip(i64::try_from(r).ok());
        if cell.is_none_or(|p| !self.spatial.tiles.contains_key(&p)) {
            return extra(
                &format!(
                    "Target position ({}, {}) is outside map boundaries",
                    scalar_display(col),
                    scalar_display(row)
                ),
                json!({"target_position":{"col":col,"row":row},"on_board":false,"tile_count":self.spatial.tiles.len()}),
            );
        }
        let uid = id(raw);
        if uid
            .and_then(|uid| self.component::<UnitInfo>(uid))
            .is_none()
        {
            return extra(
                &format!("Unit {} not found in world", scalar_display(raw)),
                json!({"requested_unit_id":raw,"suggestion":"Use get_faction_state action to see all units for a faction"}),
            );
        }
        let uid = uid.unwrap();
        if let Some(error) = self.turn_permission(uid, "move") {
            return error;
        }
        let missing: Vec<_> = [
            ("HexPosition", self.component::<Position>(uid).is_none()),
            (
                "MovementPoints",
                self.component::<MovePoints>(uid).is_none(),
            ),
            ("UnitCount", self.component::<Headcount>(uid).is_none()),
        ]
        .into_iter()
        .filter_map(|(name, missing)| missing.then_some(name))
        .collect();
        if !missing.is_empty() {
            return extra(
                &format!(
                    "Unit {uid} missing required components: {}",
                    missing.join(", ")
                ),
                json!({"unit_id":uid,"missing_components":missing,"required_components":["HexPosition","MovementPoints","UnitCount"],"suggestion":"This unit may not be properly initialized"}),
            );
        }
        if self.config.interface["movement_system"] != true {
            return extra(
                "Movement system not available",
                json!({"unit_id":uid,"system_error":"MovementSystem not found","suggestion":"This is a game engine error - contact administrator"}),
            );
        }
        let mut result = self.move_unit(uid, cell.unwrap());
        if result["success"] != true {
            let message = result["message"]
                .as_str()
                .unwrap_or("Move failed")
                .to_string();
            result.as_object_mut().unwrap().remove("success");
            result.as_object_mut().unwrap().remove("message");
            return extra(&message, result);
        }
        let start: hex::Hex = serde_json::from_value(result["from"].clone()).unwrap();
        let goal: hex::Hex = serde_json::from_value(result["to"].clone()).unwrap();
        let length = result["path"].as_array().unwrap().len().saturating_sub(1);
        let mp = self.component::<MovePoints>(uid).unwrap();
        let message = format!(
            "Unit {uid} has moved from {} to {}.",
            hex::repr(start),
            hex::repr(goal)
        );
        json!({"success":true,"result":true,"message":message,"details":message,"action_status":"in_progress",
            "movement_descriptions":{"start_position":{"col":start.0,"row":start.1},"target_position":{"col":goal.0,"row":goal.1},"path":result["path"],"path_length":length},
            "estimated_duration_seconds":length as f64/2.,"remaining_movement_points":format!("{}/{}",mp.current_mp,mp.max_mp)})
    }
    pub(crate) fn action_terrain(&self, cell: hex::Hex) -> &str {
        self.spatial
            .tiles
            .get(&cell)
            .filter(|t| t.entity != 0 && t.has_terrain)
            .map_or("plains", |t| t.terrain.as_str())
    }
    pub fn handle_attack(&mut self, params: &Value) -> Result<Value, String> {
        let raw_a = &params["unit_id"];
        let raw_t = &params["target_id"];
        if action_integer(raw_a).is_none() || action_integer(raw_t).is_none() {
            return Ok(extra(
                "unit_id and target_id must be integers",
                json!({"received_unit_id":raw_a,"received_target_id":raw_t,"expected_types":{"unit_id":"int","target_id":"int"},"valid_example":{"unit_id":123,"target_id":456}}),
            ));
        }
        let (a, t) = (id(raw_a), id(raw_t));
        let Some(attacker) = a.and_then(|a| self.component::<UnitInfo>(a)).cloned() else {
            return Ok(extra(
                &format!("Attacker unit {} not found", scalar_display(raw_a)),
                json!({"unit_id":raw_a,"suggestion":"Use get_faction_state action to see all available units"}),
            ));
        };
        let Some(target) = t.and_then(|t| self.component::<UnitInfo>(t)).cloned() else {
            return Ok(extra(
                &format!("Target unit {} not found", scalar_display(raw_t)),
                json!({"target_id":raw_t,"suggestion":"Use observation action to see visible enemy units"}),
            ));
        };
        let (a, t) = (a.unwrap(), t.unwrap());
        if let Some(error) = self.turn_permission(a, "attack") {
            return Ok(error);
        }
        if attacker.faction == target.faction {
            return Ok(extra(
                "Cannot attack units of same faction",
                json!({"attacker_faction":attacker.faction,"target_faction":target.faction,"suggestion":"Select an enemy unit from a different faction"}),
            ));
        }
        let missing: Vec<_> = [
            ("HexPosition", self.component::<Position>(a).is_none()),
            ("Combat", self.component::<CombatStats>(a).is_none()),
            ("ActionPoints", self.component::<ActionPoints>(a).is_none()),
            ("UnitCount", self.component::<Headcount>(a).is_none()),
        ]
        .into_iter()
        .filter_map(|(name, missing)| missing.then_some(name))
        .collect();
        if !missing.is_empty() {
            return Ok(extra(
                &format!(
                    "Attacker unit {a} missing required components: {}",
                    missing.join(", ")
                ),
                json!({"unit_id":a,"missing_components":missing,"required_components":["HexPosition","Combat","ActionPoints","UnitCount"],"suggestion":"This unit may not be properly initialized"}),
            ));
        }
        let missing: Vec<_> = [
            ("HexPosition", self.component::<Position>(t).is_none()),
            ("UnitCount", self.component::<Headcount>(t).is_none()),
        ]
        .into_iter()
        .filter_map(|(name, missing)| missing.then_some(name))
        .collect();
        if !missing.is_empty() {
            return Ok(extra(
                &format!(
                    "Target unit {t} missing required components: {}",
                    missing.join(", ")
                ),
                json!({"target_id":t,"missing_components":missing,"required_components":["HexPosition","UnitCount"],"suggestion":"Target unit may not be properly initialized"}),
            ));
        }
        let ap = self.component::<ActionPoints>(a).unwrap().current_ap;
        if ap < 1 {
            return Ok(extra(
                &format!("Insufficient action points for attack: need 1, have {ap}"),
                json!({"unit_id":a,"required_action_points":1,"current_action_points":ap,"deficit":1-ap,"suggestion":"Wait for action points to recover or use rest action"}),
            ));
        }
        let before = self.component::<Headcount>(t).unwrap().clone();
        if before.current_count <= 0 {
            return Ok(extra(
                &format!("Target unit {t} is already destroyed"),
                json!({"target_id":t,"current_count":before.current_count,"suggestion":"Select a living enemy unit"}),
            ));
        }
        let p = self.component::<Position>(a).unwrap().hex();
        let q = self.component::<Position>(t).unwrap().hex();
        let distance = hex::distance(p, q);
        let range = self.component::<CombatStats>(a).unwrap().attack_range;
        if distance > range {
            return Ok(extra(
                &format!("Target out of attack range: distance {distance}, range {range}"),
                json!({"unit_id":a,"target_id":t,"attacker_position":p,"target_position":q,"distance":distance,"attack_range":range,"range_deficit":distance-range,"unit_type":attacker.unit_type,"suggestion":format!("Move {} hexes closer or select a target within {range} hexes",distance-range)}),
            ));
        }
        if self.config.interface["combat_system"] != true {
            return Ok(extra(
                "Combat system not available",
                json!({"system_error":"CombatSystem not found","suggestion":"This is a game engine error - contact administrator"}),
            ));
        }
        let result = self.execute_attack(a, t)?;
        if result["success"] != true {
            return Ok(extra(result["message"].as_str().unwrap_or("Attack execution failed"),result.get("details").cloned().unwrap_or(json!({"unit_id":a,"target_id":t,"suggestion":"Attack validation passed but execution failed - possible game state conflict"}))));
        }
        let battle = &result["battle_result"];
        // Removed target components are no longer accessible; the battle record retains the post-state.
        let remaining = battle["post_battle_state"]["target_count"]
            .as_i64()
            .ok_or("missing battle post-state")?;
        let post_ap = self.component::<ActionPoints>(a).unwrap().current_ap;
        let casualties = before.current_count - remaining;
        let strength = if before.max_count > 0 {
            format!("{:.1}", (remaining as f64 / before.max_count as f64) * 100.)
                .parse::<f64>()
                .unwrap()
        } else {
            0.
        };
        let message = format!("Unit {a} attacked unit {t} successfully");
        Ok(
            json!({"success":true,"result":true,"message":message,"details":message,
            "battle_summary":{"attacker_info":{"unit_id":a,"unit_type":attacker.unit_type,"faction":attacker.faction,"position":p,"terrain":self.action_terrain(p)},
                "target_info":{"unit_id":t,"unit_type":target.unit_type,"faction":target.faction,"position":q,"terrain":self.action_terrain(q)},
                "battle_result":battle,"casualties_inflicted":casualties,"target_destroyed":remaining<=0,"distance":distance},
            "resource_consumption":{"action_points_used":ap-post_ap},"remaining_resources":{"action_points":post_ap},
            "tactical_info":{"attack_was_effective":casualties>0,"target_remaining_strength":format!("{remaining}/{}",before.max_count),"target_strength_percentage":strength}}),
        )
    }
}

//! Compatibility with the current terrain-skill handler (including its result-key mismatch).
use crate::{
    codec::{action_integer, scalar_display},
    components::{ActionPoints, Position, SkillPoints, UnitInfo},
    observation::error,
    runtime::{InitialComponents, Runtime},
};
use serde_json::Value;
impl Runtime {
    pub(crate) fn handle_skill(&self, params: &Value) -> Value {
        let raw = &params["unit_id"];
        let Some(uid) = action_integer(raw) else {
            return error("unit_id must be integer");
        };
        let Some(name) = params["skill_name"].as_str() else {
            return error("skill_name must be string");
        };
        let Some((uid, entity)) = u64::try_from(uid)
            .ok()
            .and_then(|uid| self.world.entity(uid).map(|e| (uid, e)))
            .filter(|(_, e)| self.world.ecs.get::<UnitInfo>(*e).is_some())
        else {
            return error(&format!("Unit {} not found", scalar_display(raw)));
        };
        if let Some(e) = self.turn_permission(uid, "skill") {
            return e;
        }
        let Some(skills) = self
            .world
            .ecs
            .get::<InitialComponents>(entity)
            .and_then(|c| c.0.get("UnitSkills"))
        else {
            return error("Unit has no skills");
        };
        let Some(sp) = self.component::<SkillPoints>(uid) else {
            return error("Unit has no skill points");
        };
        if skills["available_skills"]["$set"]
            .as_array()
            .is_none_or(|v| !v.iter().any(|s| s.as_str() == Some(name)))
        {
            return error(&format!("Skill {name} not available"));
        }
        let cooldown = skills["skill_cooldowns"]
            .get(name)
            .cloned()
            .unwrap_or(Value::from(0));
        if cooldown.as_f64().is_some_and(|v| v > 0.) {
            return error(&format!(
                "Skill {name} on cooldown: {} turns",
                scalar_display(&cooldown)
            ));
        }
        if sp.current_sp < 1 || sp.skill_cooldowns.get(name).is_some_and(|&v| v > 0) {
            return error(&format!(
                "Insufficient skill points: need 1, have {}",
                sp.current_sp
            ));
        }
        let ap = self
            .component::<ActionPoints>(uid)
            .map_or(0, |p| p.current_ap);
        if ap < 1 {
            return error(&format!(
                "Insufficient action points for skill: need 2, have {ap}"
            ));
        }
        let Some(pos) = self.component::<Position>(uid) else {
            return error("Unit position not found");
        };
        let terrain = self.action_terrain(pos.hex());
        let valid = match name {
            "hide" => matches!(terrain, "forest" | "mountain" | "hill"),
            "rockslide" => terrain == "mountain",
            "arrow_evasion" => terrain == "hill",
            _ => return error(&format!("Unknown skill: {name}")),
        };
        if !valid {
            return error(&format!("Skill {name} cannot be used on terrain {terrain}"));
        }
        // _execute_terrain_skill emits `success`, while handle_skill_action reads
        // `result`: even legal terrain returns this failure without AP/SP/CD writes.
        // Changing gameplay belongs in a separately versioned rules change.
        error("Skill execution failed")
    }
}

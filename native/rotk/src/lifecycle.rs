//! World lifecycle: simulation-time timeout and deterministic game-over event.
use crate::{
    components::{Headcount, Position, UnitInfo},
    runtime::Runtime,
};
use serde_json::json;
use star_core::world::OrderedWorld;
use std::collections::BTreeMap;

/// Derived once on import and maintained when liveness changes. Positionless
/// units count in the base policy, but not in the window spatial index.
#[derive(Default)]
pub(crate) struct LivingFactions {
    pub(crate) all: BTreeMap<String, usize>,
    positioned: BTreeMap<String, usize>,
}
impl LivingFactions {
    pub fn build(world: &OrderedWorld) -> Self {
        let mut counts = Self::default();
        for (_, e) in world.ordered() {
            let (Some(unit), Some(count)) =
                (world.ecs.get::<UnitInfo>(e), world.ecs.get::<Headcount>(e))
            else {
                continue;
            };
            if count.current_count > 0 {
                *counts.all.entry(unit.faction.clone()).or_default() += 1;
                if world.ecs.get::<Position>(e).is_some() {
                    *counts.positioned.entry(unit.faction.clone()).or_default() += 1;
                }
            }
        }
        counts
    }
    pub fn died(&mut self, faction: &str, had_position: bool) {
        for counts in [&mut self.all, &mut self.positioned]
            .into_iter()
            .take(if had_position { 2 } else { 1 })
        {
            let count = counts.get_mut(faction).expect("living faction ledger");
            *count -= 1;
            if *count == 0 {
                counts.remove(faction);
            }
        }
    }
}

impl Runtime {
    pub(crate) fn sync_turn_clock(&mut self) {
        if self.clock.realtime || !self.config.systems.contains_key("GameTimeSystem") {
            return;
        }
        let Some(turn) = self
            .singletons
            .get("GameState")
            .and_then(|s| s["turn_number"].as_i64())
        else {
            return;
        };
        let clock = self
            .singletons
            .get_mut("GameTime")
            .expect("validated clock");
        if turn > clock["current_turn"].as_i64().unwrap_or(1) {
            clock["current_turn"] = json!(turn);
            clock["turn_start_time"] = clock["last_update_time"].clone();
        }
    }

    pub(crate) fn advance_lifecycle(&mut self) {
        let mode = self
            .singletons
            .get("GameModeComponent")
            .and_then(|m| m["mode"].as_str());
        let name = match mode {
            Some("real_time") => "RealtimeSystem",
            Some("turn_based") => "TurnSystem",
            _ => return,
        };
        let Some(system) = self.config.systems.get(name) else {
            return;
        };
        if system["enabled"] != true {
            return;
        }
        self.check_game_over();
    }

    pub(crate) fn check_game_over(&mut self) -> bool {
        let Some(state) = self.singletons.get("GameState") else {
            return false;
        };
        if state["game_over"] == true {
            return true;
        }
        let indexed = self
            .config
            .systems
            .get("RealtimeSystem")
            .is_some_and(|s| s["indexed"] == true)
            && self
                .singletons
                .get("GameModeComponent")
                .is_some_and(|m| m["mode"] == "real_time");
        let living = if indexed {
            &self.living.positioned
        } else {
            &self.living.all
        };
        let mode = self
            .singletons
            .get("GameModeComponent")
            .map(|m| &m["mode"])
            .unwrap_or(&state["game_mode"]);
        let timed_out = if mode == "turn_based" {
            let limit = state["max_turns"]
                .as_i64()
                .filter(|v| *v != 0)
                .unwrap_or_else(|| self.config.rules["max_turns"].as_i64().unwrap_or(100));
            state["turn_number"].as_i64().unwrap_or(1) > limit
        } else if mode == "real_time" {
            self.clock.elapsed
                >= self.config.rules["max_realtime_seconds"]
                    .as_f64()
                    .unwrap_or(3600.)
        } else {
            false
        };
        // Annihilation takes precedence over timeout on the same simulation tick.
        let (winner, reason) = match living.len() {
            0 => (None, "mutual_annihilation"),
            1 => (living.keys().next().cloned(), "annihilation"),
            _ if timed_out => (None, "timeout"),
            _ => return false,
        };
        let state = self.singletons.get_mut("GameState").unwrap();
        state["game_over"] = json!(true);
        state["winner"] = json!(winner);
        state["end_reason"] = json!(reason);
        self.events
            .push(json!({"type":"GameOverEvent", "fields":{"winner":winner}}));
        true
    }
}

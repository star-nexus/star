//! Existing faction rotation and round reset, with submission-order events.
use crate::{
    codec::{scalar_display, truthy},
    components::{ActionPoints, Headcount, MovePoints, Status},
    observation::error,
    runtime::Runtime,
};
use serde_json::{Value, json};

impl Runtime {
    pub(crate) fn current_player_faction(&self) -> Option<&str> {
        let current = self.singletons.get("GameState")?["current_player"].as_str()?;
        self.players
            .iter()
            .find(|(_, faction)| faction == current)
            .map(|(_, faction)| faction.as_str())
    }
    fn reset_round_actions(&mut self) {
        let mut query = self.world.ecs.query::<(
            &star_core::world::ExternalId,
            &mut MovePoints,
            Option<&Headcount>,
            Option<&mut ActionPoints>,
        )>();
        // Disjoint rows: no RNG, events or shared state is touched during reset.
        for (id, mut mp, count, ap) in query.iter_mut(&mut self.world.ecs) {
            self.presentation_dirty.insert(id.0);
            mp.current_mp = count.map_or(mp.max_mp, |count| mp.effective(count));
            mp.has_moved = false;
            if let Some(mut ap) = ap {
                ap.current_ap = ap.max_ap;
            }
        }
        let mut query = self
            .world
            .ecs
            .query::<(&star_core::world::ExternalId, &mut Status)>();
        for (id, mut status) in query.iter_mut(&mut self.world.ecs) {
            self.presentation_dirty.insert(id.0);
            if status.status_duration > 0 {
                status.status_duration -= 1;
                if status.status_duration <= 0 {
                    status.current_status = "normal".into();
                    status.current_status_is_enum = true;
                }
            }
            if status.wait_turns > 0 {
                status.current_status = "high_morale".into();
                status.current_status_is_enum = true;
                status.status_duration = 1;
                status.wait_turns = 0;
            }
        }
    }
    fn switch_faction(&mut self, round_reset: bool) {
        if self.players.is_empty() {
            return;
        }
        let previous = self.singletons["GameState"]["current_player"]
            .as_str()
            .map(String::from);
        let index = self
            .players
            .iter()
            .position(|(_, f)| Some(f.as_str()) == previous.as_deref())
            .map_or(0, |i| (i + 1) % self.players.len());
        let next = self.players[index].1.clone();
        self.singletons.get_mut("GameState").unwrap()["current_player"] = json!(next);
        self.record_turn_change_native(previous.as_deref(), &next);
        if index == 0 {
            let state = self.singletons.get_mut("GameState").unwrap();
            state["turn_number"] = json!(state["turn_number"].as_i64().unwrap_or(1) + 1);
            if round_reset {
                self.reset_round_actions();
            }
        }
        self.config.systems.get_mut("TurnSystem").unwrap()["turn_timer"] = json!(0.);
        self.events
            .push(json!({"type":"TurnStartEvent", "fields":{"faction":next}}));
    }
    /// Human end-turn resets before victory checking, unlike Agent handoff.
    pub fn finish_human_turn(&mut self, wall_time: f64) -> Result<(), String> {
        if !self.config.systems.contains_key("TurnSystem") {
            return Err("Turn system not available".into());
        }
        if !self.singletons.contains_key("GameState") {
            return Err("Game not initialized".into());
        }
        self.set_wall_metadata(wall_time)?;
        self.revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        self.reset_round_actions();
        if !self.check_game_over() {
            self.switch_faction(false);
        }
        Ok(())
    }
    pub(crate) fn handle_end_turn(&mut self, params: &Value) -> Value {
        let requested = &params["faction"];
        if !truthy(requested) {
            return error("faction parameter required");
        }
        let faction = match requested.as_str() {
            Some(f @ ("wei" | "shu" | "wu")) => f,
            _ => return error(&format!("Invalid faction: {}", scalar_display(requested))),
        };
        let Some(state) = self.singletons.get("GameState") else {
            return error("Game not initialized");
        };
        if state["game_over"] == true {
            return error("Game is already over");
        }
        if !self.config.systems.contains_key("TurnSystem") {
            return error("Turn system not available");
        }
        let current = self.current_player_faction();
        if current != Some(faction) {
            return error(&format!(
                "Not {faction}'s turn. Current turn: {}",
                current.unwrap_or("unknown")
            ));
        }
        if !self.check_game_over() {
            self.switch_faction(true);
        }
        let next = self.current_player_faction().unwrap_or("unknown");
        let state = &self.singletons["GameState"];
        let message = format!("Turn ended for faction {faction}");
        json!({"success":true,"result":true,"details":message,"message":message,
            "turn_summary":{"ended_faction":faction,"next_faction":next,"turn_number":state["turn_number"],
                "forced":params.get("force").cloned().unwrap_or(json!(false))},
            "game_status":{"game_running":state["game_over"]!=true,"current_turn":state["turn_number"],"current_player":next}})
    }
}

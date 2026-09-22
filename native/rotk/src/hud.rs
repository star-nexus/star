//! Small HUD tables and append-only battle-log transport, independent of history size.
use crate::runtime::Runtime;
use serde_json::{Value, json};

impl Runtime {
    pub(crate) fn hud_presentation(&mut self) -> Value {
        // Rendered counters have faction cardinality, not Unit/Agent cardinality.
        // Full battle/observation/LLM histories belong to explicit final reports.
        let stats = self.singletons.get("GameStats").map(|stats| {
            json!({"faction_stats":stats["faction_stats"], "total_game_time":stats["total_game_time"]})
        });
        let full = std::mem::take(&mut self.presentation_log_full);
        let pending = std::mem::take(&mut self.presentation_log_entries);
        let log = self.singletons.get("BattleLog").map(|log| {
            if full {
                json!({"full":true,"baseline":log,"entries":[]})
            } else {
                json!({"full":false,"entries":pending})
            }
        });
        json!({"stats":stats,"battle_log":log})
    }
}

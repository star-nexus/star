//! Small authority boundary for Python transport and lifecycle orchestration.
//! No socket, retry timer, display state or Python callback belongs here.
use crate::runtime::Runtime;
use num_bigint::BigInt;
use serde_json::{Value, json};

fn increment(table: &mut Value, key: &str) -> Result<(), String> {
    let value = table.get(key).cloned().unwrap_or(json!(0));
    let count: BigInt = value
        .to_string()
        .parse()
        .map_err(|_| "invalid message counter")?;
    table[key] =
        serde_json::from_str(&(count + BigInt::from(1)).to_string()).expect("integer JSON");
    Ok(())
}

impl Runtime {
    /// Constant-size status, independent of Units, Agents and battle history.
    pub fn host_status(&self) -> Value {
        let state = self.singletons.get("GameState");
        json!({
            "game_over": state.is_some_and(|s| s["game_over"] == true),
            "current_player": state.map(|s| &s["current_player"]),
            "turn_number": state.map(|s| &s["turn_number"]),
            "winner": state.map(|s| &s["winner"]),
        })
    }

    /// Call at the legacy message-counting point (single: after execution;
    /// batch: before execution). This counts messages, not individual actions.
    /// Preserve the legacy partial count on an unregistered sender before error.
    pub fn record_message(&mut self, agent: Option<&str>) -> Result<(), String> {
        self.ensure_action_stats()?;
        let stats = self
            .singletons
            .get_mut("GameStats")
            .expect("prepared stats");
        if let Some(agent) = agent.filter(|id| !id.is_empty()) {
            increment(&mut stats["interaction_counts_by_agent"], agent)?;
            let faction = stats["agent_id_to_faction"][agent]
                .as_str()
                .map(String::from);
            if let Some(faction) = faction {
                increment(&mut stats["interaction_counts_by_faction"], &faction)?;
            } else {
                return Err(format!(
                    "[LLMSystem. _record_message] Record Agent -> ENV message error: [LLMSystem. _record_message] Missing faction mapping for agent {agent}. Agents must register before sending messages."
                ));
            }
        }
        Ok(())
    }

    /// Authority facts after a successful Agent end_turn, including its legacy
    /// game-over edge. Not a per-tick poll or an automatic human-turn broadcast.
    /// Keep registry-then-stats insertion candidates, including duplicates: the
    /// Python transport must retain its original set insertion/filtering order.
    pub fn turn_start_context(&self, wall_time: f64) -> Result<Value, String> {
        if !wall_time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        let Some(state) = self.singletons.get("GameState") else {
            return Ok(Value::Null);
        };
        let Some(faction) = state["current_player"].as_str() else {
            return Ok(Value::Null);
        };
        let mut candidates = Vec::new();
        if let Some(registry) = self.singletons.get("AgentInfoRegistry")
            && let Some(infos) = registry["agents"][faction].as_array()
        {
            for info in infos {
                if let Some(id) = info["agent_id"].as_str().filter(|s| !s.is_empty()) {
                    candidates.push(id);
                }
            }
        }
        if let Some(stats) = self.singletons.get("GameStats")
            && let Some(mapping) = stats["agent_id_to_faction"].as_object()
        {
            for (id, mapped) in mapping {
                if mapped.as_str() == Some(faction) {
                    candidates.push(id.as_str());
                }
            }
        }
        Ok(json!({"candidates":candidates, "notification":{
            "type":"turn_start", "faction":faction, "turn_number":state["turn_number"],
            "timestamp":wall_time, "message":"Your turn starts."
        }}))
    }
}

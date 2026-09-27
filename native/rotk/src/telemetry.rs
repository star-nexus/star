//! System actions feeding settlement statistics. Wall time is ingress metadata.
use crate::{codec::truthy, named_observation::py_display, runtime::Runtime};
use num_bigint::BigInt;
use serde_json::{Value, json};

const ADD_KEYS: &[&str] = &[
    "total_calls",
    "successful_calls",
    "failed_calls",
    "toolcall_error_total",
    "http_error_total",
    "spatial_awareness_error",
    "prompt_tokens",
    "completion_tokens",
    "prompt_cache_hit_tokens",
    "prompt_cache_miss_tokens",
    "reasoning_tokens",
];
fn failure(message: &str) -> Value {
    json!({"success":false,"message":message})
}
fn faction(params: &Value) -> Result<&str, Value> {
    let value = &params["faction"];
    if !truthy(value) {
        return Err(failure("Missing faction"));
    }
    value
        .as_str()
        .filter(|f| ["wei", "shu", "wu"].contains(f))
        .ok_or_else(|| failure(&format!("Invalid faction: {}", py_display(value))))
}
fn default(value: &Value, key: &str, fallback: Value) -> Value {
    value.get(key).cloned().unwrap_or(fallback)
}
// Decimal formatting rounds the original binary f64, unlike multiply/round/divide
// which can move a near-halfway value onto a different side of the tie.
fn rounded(value: f64, digits: usize) -> f64 {
    format!("{value:.digits$}")
        .parse()
        .expect("formatted finite number")
}
fn remove_digit_separators(text: &str) -> Option<String> {
    let chars: Vec<_> = text
        .trim()
        .chars()
        .map(crate::unicode_decimal::decimal_ascii)
        .collect();
    for (i, c) in chars.iter().enumerate() {
        if *c == '_'
            && (i == 0
                || i + 1 == chars.len()
                || !chars[i - 1].is_ascii_digit()
                || !chars[i + 1].is_ascii_digit())
        {
            return None;
        }
    }
    Some(chars.into_iter().filter(|c| *c != '_').collect())
}
fn number(value: &Value) -> Option<f64> {
    value
        .as_f64()
        .or_else(|| value.as_bool().map(|v| f64::from(u8::from(v))))
        .or_else(|| {
            value
                .as_str()
                .and_then(remove_digit_separators)?
                .parse()
                .ok()
        })
}
fn counter(value: &Value, integer_string_limit: usize) -> BigInt {
    if let Some(v) = crate::codec::action_integer(value) {
        return v.into();
    }
    if let Some(v) = value.as_str() {
        return remove_digit_separators(v)
            // CPython counts decimal digits, including leading zeroes, but not
            // signs, whitespace or separators. Zero disables the host limit.
            .filter(|s| {
                integer_string_limit == 0
                    || s.bytes().filter(u8::is_ascii_digit).count() <= integer_string_limit
            })
            .and_then(|s| s.parse().ok())
            .unwrap_or_default();
    }
    if let Value::Number(n) = value
        && let Ok(integer) = n.to_string().parse()
    {
        return integer;
    }
    value
        .as_f64()
        .filter(|f| f.is_finite())
        .and_then(|f| format!("{:.0}", f.trunc()).parse().ok())
        .unwrap_or_default()
}
fn label(previous: &Value, incoming: &Value) -> String {
    let mut parts = Vec::new();
    for v in [previous, incoming] {
        if !truthy(v) || v == "unknown" {
            continue;
        }
        let text = py_display(v);
        if !parts.contains(&text) {
            parts.push(text);
        }
    }
    if parts.is_empty() {
        "unknown".into()
    } else {
        parts.join(" + ")
    }
}

fn percent(numerator: &Value, denominator: &Value) -> Result<Value, &'static str> {
    // CPython integer true division rounds the ratio, not its operands. Keep
    // large token counters exact and avoid inf/inf or double-rounding them.
    let a = counter(numerator, 0);
    let b = counter(denominator, 0);
    if b == BigInt::from(0) {
        return Ok(json!(0.));
    }
    let negative = a.sign() != b.sign();
    let (n, d) = (a.magnitude(), b.magnitude());
    if n.bits() == 0 {
        return Ok(json!(0.));
    }
    let mut exponent = n.bits() as i64 - d.bits() as i64;
    if if exponent >= 0 {
        n < &(d << exponent as usize)
    } else {
        &(n << -exponent as usize) < d
    } {
        exponent -= 1;
    }
    if exponent > 1023 {
        return Err("integer division result too large for a float");
    }
    if exponent < -1075 {
        return Ok(json!(if negative { -0. } else { 0. }));
    }
    let shift = if exponent < -1022 {
        1074
    } else {
        52 - exponent
    };
    let (n, d) = if shift >= 0 {
        (n << shift as usize, d.clone())
    } else {
        (n.clone(), d << -shift as usize)
    };
    let mut q = &n / &d;
    let twice_remainder = (&n % &d) << 1;
    if twice_remainder > d || (twice_remainder == d && q.bit(0)) {
        q += 1u8;
    }
    let q: u64 = q.try_into().expect("53-bit quotient");
    let scale = if shift == 1074 {
        f64::from_bits(1)
    } else {
        2_f64.powi(-shift as i32)
    };
    let value = q as f64 * scale * if negative { -1. } else { 1. };
    if !value.is_finite() {
        return Err("integer division result too large for a float");
    }
    let result = rounded(value * 100., 2);
    Ok(if result.is_finite() {
        json!(result)
    } else {
        json!({"$float":if result.is_sign_negative() { "-inf" } else { "inf" }})
    })
}

impl Runtime {
    /// The owner host calls once when it observes game over, then handles delivery.
    /// No transport or retry loop runs inside the kernel. Input order is preserved.
    pub fn prepare_game_end(
        &mut self,
        connected: &[String],
        wall_time: f64,
    ) -> Result<Value, String> {
        if !wall_time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        let unique: std::collections::BTreeSet<_> = connected.iter().collect();
        if unique.len() != connected.len() {
            return Err("duplicate connected agent ID".into());
        }
        let state = self
            .singletons
            .get("GameState")
            .ok_or("game state missing")?;
        if state["game_over"] != true {
            return Err("game has not ended".into());
        }
        let notification = json!({"type":"game_end_notification", "winner":state["winner"],
            "reason":"game_completed", "timestamp":wall_time,
            "message":"Game has ended. Please report your LLM statistics."});
        let mut targets = Vec::new();
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            let registered = stats["registered_factions"]["$set"]
                .as_array()
                .cloned()
                .unwrap_or_default();
            let expected = if registered.is_empty() {
                connected.len()
            } else {
                registered.len()
            };
            stats["expected_llm_stats_count"] = json!(expected);
            stats["received_llm_stats_count"] = json!(if registered.is_empty() {
                0
            } else {
                stats["received_llm_stats_factions"]["$set"]
                    .as_array()
                    .map_or(0, Vec::len)
            });
            if expected == 0 {
                stats["can_generate_settlement_report"] = json!(true);
            } else {
                for agent in connected {
                    if registered.contains(&stats["agent_id_to_faction"][agent]) {
                        targets.push(agent);
                    }
                }
            }
        }
        Ok(json!({"notification":notification, "targets":targets}))
    }

    pub(crate) fn strategy_ping(&mut self, params: &Value) -> Value {
        let faction = match faction(params) {
            Ok(f) => f,
            Err(e) => return e,
        };
        let raw = default(params, "score", json!(0.5));
        let Some(score) = number(&raw) else {
            return failure("Invalid score");
        };
        if !(0.0 < score && score <= 1.0) {
            return failure("Score out of range (0, 1]");
        }
        let stats = self
            .singletons
            .get_mut("GameStats")
            .expect("request prepared stats");
        let last = stats["last_strategy_ping_ts"][faction].as_f64();
        if last.is_some_and(|last| self.wall_time - last < 2.) {
            return failure("Strategy ping throttled");
        }
        let count = stats["strategy_ping_count_by_faction"][faction]
            .as_u64()
            .unwrap_or(0);
        if count >= 6 && last.is_some_and(|last| last != 0. && self.wall_time - last < 60.) {
            return failure("Per-minute cap reached");
        }
        let score = rounded(
            stats["strategy_scores_by_faction"][faction]
                .as_f64()
                .unwrap_or(0.)
                + score,
            4,
        );
        stats["strategy_scores_by_faction"][faction] = json!(score);
        stats["strategy_ping_count_by_faction"][faction] = json!(count + 1);
        stats["last_strategy_ping_ts"][faction] = json!(self.wall_time);
        if truthy(&params["evidence"]) {
            let text = py_display(&params["evidence"]);
            let text = if text.chars().count() > 120 {
                text.chars().take(117).collect::<String>() + "..."
            } else {
                text
            };
            let table = stats["strategy_evidence"]
                .as_object_mut()
                .expect("strategy evidence map");
            let entries = table
                .entry(faction)
                .or_insert(json!([]))
                .as_array_mut()
                .expect("evidence list");
            entries.push(json!(text));
            if entries.len() > 10 {
                entries.drain(..entries.len() - 10);
            }
        }
        json!({"success":true,"message":"Strategy score accepted","new_score":score,"pings":count+1})
    }

    pub(crate) fn report_llm_stats(
        &mut self,
        params: &Value,
        integer_string_limit: usize,
    ) -> Value {
        let faction = match faction(params) {
            Ok(f) => f,
            Err(e) => return e,
        };
        let api = default(params, "api_stats", json!({}));
        if !api.is_object() {
            return failure("Invalid api_stats format");
        }
        if !self
            .singletons
            .get("AgentInfoRegistry")
            .is_some_and(|r| truthy(&r["agents"][faction]))
        {
            return failure("Agent not registered. Please register before reporting LLM stats.");
        }
        let mut incoming = json!({});
        for key in ADD_KEYS {
            let source = if [
                "toolcall_error_total",
                "http_error_total",
                "spatial_awareness_error",
            ]
            .contains(key)
            {
                params
            } else {
                &api
            };
            incoming[*key] = default(source, key, json!(0));
        }
        for key in ["success_rate", "cache_hit_rate"] {
            incoming[key] = default(&api, key, json!(0.0));
        }
        for key in ["provider", "model_id"] {
            incoming[key] = default(params, key, json!("unknown"));
        }
        incoming["timestamp"] = json!(self.wall_time);
        let stats = self
            .singletons
            .get_mut("GameStats")
            .expect("request prepared stats");
        let previous = &stats["llm_api_stats"][faction];
        if previous.is_object() && truthy(previous) {
            for key in ADD_KEYS {
                let value = counter(&previous[*key], integer_string_limit)
                    + counter(&incoming[*key], integer_string_limit);
                incoming[*key] = serde_json::from_str(&value.to_string()).expect("integer JSON");
            }
            for (rate, numerator, denominator) in [
                ("success_rate", "successful_calls", "total_calls"),
                ("cache_hit_rate", "prompt_cache_hit_tokens", "prompt_tokens"),
            ] {
                match percent(&incoming[numerator], &incoming[denominator]) {
                    Ok(value) => incoming[rate] = value,
                    Err(message) => return failure(&format!("Report LLM stats failed: {message}")),
                }
            }
            for key in ["provider", "model_id"] {
                incoming[key] = json!(label(&previous[key], &incoming[key]));
            }
        }
        stats["llm_api_stats"][faction] = incoming;
        let received = stats["received_llm_stats_factions"]["$set"]
            .as_array_mut()
            .expect("received faction set");
        if !received.iter().any(|v| v == faction) {
            received.push(json!(faction));
            received.sort_by(|a, b| a.as_str().cmp(&b.as_str()));
        }
        let received_count = received.len();
        let registered_count = stats["registered_factions"]["$set"]
            .as_array()
            .expect("registered factions")
            .len();
        if received_count >= registered_count && registered_count > 0 {
            stats["can_generate_settlement_report"] = json!(true);
        }
        stats["received_llm_stats_count"] = json!(received_count);
        stats["expected_llm_stats_count"] = json!(registered_count);
        let mut result =
            json!({"success":true,"message":"LLM stats received","faction":faction,"stats":api});
        for key in [
            "toolcall_error_total",
            "http_error_total",
            "spatial_awareness_error",
        ] {
            result[key] = default(params, key, json!(0));
        }
        result
    }

    pub(crate) fn retrieve_game_status(&self, connected_agents: u64) -> Value {
        let state = self.singletons.get("GameState");
        let registered = self
            .singletons
            .get("GameStats")
            .map(|s| s["registered_factions"]["$set"].clone())
            .unwrap_or(json!([]));
        json!({"success":true,"message":"Game status reported","data":{
            "turn":state.map(|s| &s["turn_number"]),"current_player":state.map(|s| &s["current_player"]),
            "registered_factions":registered,"connected_agents":connected_agents,"timestamp":self.wall_time}})
    }
}

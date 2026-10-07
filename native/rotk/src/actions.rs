//! Trusted local request boundary. Transport identity is supplied separately from parameters.
use crate::{
    codec::{action_integer, scalar_display, string_repr, truthy},
    components::UnitInfo,
    observation::{ObservationBatch, ReadSegmentCache, Response, error},
    runtime::Runtime,
    team::Team,
};
use serde::Deserialize;
use serde_json::{Value, json};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub agent_id: Option<String>,
    pub action: Option<String>,
    pub parameters: Value,
    pub wall_time: f64,
    /// Captured in Python at ingress, never a clock advancing simulation.
    #[serde(default)]
    pub registration_time: String,
    /// Python URL parsing is transport metadata preparation, not a hot-loop callback.
    #[serde(default)]
    pub sanitized_base_url: String,
    /// Trusted transport snapshot, never inferred from Agent-provided parameters.
    #[serde(default)]
    pub connected_agents: u64,
    /// Trusted Python interpreter setting captured at admission, not Agent input.
    #[serde(default = "default_integer_string_limit")]
    pub integer_string_limit: usize,
}
fn default_integer_string_limit() -> usize {
    4300 // CPython oracle default for legacy raw native envelopes.
}

#[derive(serde::Serialize)]
pub struct BatchReport {
    pub results: Vec<Response>,
    pub observation_segments: Vec<Value>,
}

impl Request {
    fn normalize_identity(&mut self) {
        if [
            "register_agent_info",
            "claim_units",
            "release_units",
            "list_team",
            "broadcast_to_team",
            "read_team_messages",
            "get_faction_state",
            "get_faction_state_vlm",
        ]
        .contains(&self.action.as_deref().unwrap_or(""))
            && let (Some(agent), Some(params)) = (
                self.agent_id.as_deref().filter(|a| !a.is_empty()),
                self.parameters.as_object_mut(),
            )
        {
            params.insert("agent_id".into(), json!(agent));
        }
    }
}

impl Runtime {
    fn release_request(&mut self, params: &Value) -> Result<Value, String> {
        let agent = params["agent_id"]
            .as_str()
            .filter(|a| !a.is_empty())
            .ok_or("release_units requires agent_id")?;
        let team = self.team.get_or_insert_with(Team::default);
        let selected = &params["unit_ids"];
        if selected.is_null() {
            return Ok(team.release(agent, None));
        }
        let mut released = vec![];
        if let Some(values) = selected.as_array() {
            for raw in values {
                if raw.is_array() {
                    return Err("unhashable type: 'list'".into());
                }
                if raw.is_object() {
                    return Err("unhashable type: 'dict'".into());
                }
                let id = action_integer(raw)
                    .and_then(|v| u64::try_from(v).ok())
                    .or_else(|| {
                        raw.as_f64()
                            .filter(|v| {
                                v.is_finite()
                                    && *v >= 0.
                                    && *v < 18446744073709551616.
                                    && v.fract() == 0.
                            })
                            .map(|v| v as u64)
                    });
                if let Some(id) = id {
                    let result = team.release(agent, Some(&[id]));
                    if !result["released"].as_array().unwrap().is_empty() {
                        released.push(raw.clone());
                    }
                }
            }
        } else if !selected.is_string() && !selected.is_object() {
            let kind = if selected.is_boolean() {
                "bool"
            } else if selected.is_f64() {
                "float"
            } else {
                "int"
            };
            return Err(format!("'{kind}' object is not iterable"));
        }
        Ok(
            json!({"success":true,"released":released,"message":format!("Released {} units.",released.len())}),
        )
    }
    fn team_action(&mut self, action: &str, params: &Value) -> Value {
        let agent = params["agent_id"].as_str().filter(|a| !a.is_empty());
        let Some(agent) = agent else {
            return json!({"success":false,"message":format!("{action} requires agent_id.")});
        };
        let faction = self.agent_faction(Some(agent));
        match action {
            "claim_units" => {
                let empty = json!([]);
                let selected = if truthy(&params["unit_ids"]) {
                    &params["unit_ids"]
                } else {
                    &empty
                };
                let Some(ids) = selected
                    .as_array()
                    .filter(|ids| ids.iter().all(|v| action_integer(v).is_some()))
                else {
                    return json!({"success":false,"message":"claim_units requires agent_id and unit_ids: list[int]."});
                };
                let Some(faction) = faction else {
                    return json!({"success":false,"message":"Agent must call register_agent_info before claiming units."});
                };
                let mut accepted = vec![];
                for raw in ids {
                    let uid = action_integer(raw).and_then(|v| u64::try_from(v).ok());
                    let Some(unit) = uid
                        .and_then(|id| self.world.entity(id))
                        .and_then(|e| self.world.ecs.get::<UnitInfo>(e))
                    else {
                        return json!({"success":false,"message":format!("Unit {} does not exist.",scalar_display(raw))});
                    };
                    if unit.faction != faction {
                        return json!({"success":false,"message":format!("Unit {} belongs to {}, not the requesting agent's faction ({faction}).",scalar_display(raw),unit.faction)});
                    }
                    accepted.push(uid.unwrap());
                }
                let exclusive = params.get("exclusive").is_none_or(truthy);
                let mut result = self
                    .team
                    .get_or_insert_with(Team::default)
                    .claim(agent, &accepted, exclusive);
                if result["success"] == true {
                    result["claimed"] = selected.clone();
                }
                result
            }
            "list_team" => {
                let Some(faction) = faction else {
                    return json!({"success":false,"message":"Agent must register_agent_info before listing the team."});
                };
                let teammates = self
                    .team
                    .get_or_insert_with(Team::default)
                    .teammates(&faction, Some(agent));
                json!({"success":true,"faction":faction,"team_size":teammates.len()+1,"teammates":teammates})
            }
            "broadcast_to_team" => {
                let Some(text) = params["text"].as_str().filter(|s| !s.is_empty()) else {
                    return json!({"success":false,"message":"broadcast_to_team requires agent_id and a non-empty text."});
                };
                let Some(faction) = faction else {
                    return json!({"success":false,"message":"Agent must register_agent_info before broadcasting."});
                };
                let metadata = params.get("metadata").cloned().unwrap_or(json!({}));
                self.team.get_or_insert_with(Team::default).broadcast(
                    agent,
                    &faction,
                    text,
                    metadata,
                    self.wall_time,
                )
            }
            "read_team_messages" => {
                let messages = self.team.get_or_insert_with(Team::default).drain(agent);
                json!({"success":true,"count":messages.as_array().unwrap().len(),"messages":messages})
            }
            _ => unreachable!("team verb list"),
        }
    }
    fn system_error(&self, action: &str, message: &str, code: i64) -> Value {
        self.system_error_at(action, message, code, self.wall_time)
    }
    fn system_error_at(&self, action: &str, message: &str, code: i64, wall_time: f64) -> Value {
        let code_key = code.to_string();
        let description = self.config.interface["system_errors"][&code_key]
            .as_str()
            .unwrap_or("Unknown system error");
        json!({"success":false,"error":description,"error_code":code,"message":format!("Action {action} failed: {message}"),
            "api_version":"v1.0","metadata":{"action":action,"timestamp":wall_time}})
    }
    pub(crate) fn allowed_actions(&self) -> Vec<String> {
        let specs = &self.config.interface["action_specs"];
        if let Some(names) = self
            .singletons
            .get("MatchRules")
            .and_then(|r| r["game_actions"].as_array())
        {
            let names: Vec<_> = names
                .iter()
                .filter_map(|n| n.as_str())
                .filter(|n| !specs[*n].is_null())
                .map(String::from)
                .collect();
            if !names.is_empty() {
                return names;
            }
        }
        let mut names = vec!["move".into(), "attack".into(), "get_faction_state".into()];
        if self
            .singletons
            .get("GameModeComponent")
            .is_some_and(|m| m["mode"].as_str() == Some("turn_based"))
        {
            names.push("end_turn".into());
        }
        names
    }
    fn action_docs(&self) -> Value {
        let names = self.allowed_actions();
        let docs: serde_json::Map<_, _> = names
            .iter()
            .map(|n| (n.clone(), self.config.interface["action_specs"][n].clone()))
            .collect();
        json!({"names":names,"docs":docs})
    }
    fn agent_faction(&self, agent: Option<&str>) -> Option<String> {
        agent.filter(|a| !a.is_empty()).and_then(|a| {
            self.singletons
                .get("GameStats")
                .and_then(|s| s["agent_id_to_faction"][a].as_str())
                .map(String::from)
        })
    }
    pub(crate) fn ensure_action_stats(&mut self) -> Result<(), String> {
        if !self.singletons.contains_key("GameStats") {
            let defaults = self.config.interface["game_stats_defaults"].clone();
            if !defaults.is_object() {
                return Err("missing native action bootstrap metadata".into());
            }
            self.singletons.insert("GameStats".into(), defaults);
        }
        let stats = self
            .singletons
            .get_mut("GameStats")
            .unwrap()
            .as_object_mut()
            .ok_or("invalid GameStats")?;
        stats.entry("agent_id_to_faction").or_insert(json!({}));
        stats
            .entry("registered_factions")
            .or_insert(json!({"$set":[]}));
        Ok(())
    }
    fn register_faction(&mut self, faction: &str) {
        if !["wei", "shu", "wu"].contains(&faction) {
            return;
        }
        let values = self.singletons.get_mut("GameStats").unwrap()["registered_factions"]["$set"]
            .as_array_mut()
            .unwrap();
        if !values.iter().any(|v| v.as_str() == Some(faction)) {
            values.push(json!(faction));
            values.sort_by(|a, b| a.as_str().cmp(&b.as_str()));
        }
    }
    fn register_agent(&mut self, request: &Request, params: &Value) -> Value {
        for name in ["faction", "provider", "model_id", "base_url"] {
            if params.get(name).is_none() {
                return error(&format!("Missing required parameter: {name}"));
            }
        }
        let faction = params["faction"].as_str().unwrap_or("");
        let agent = params["agent_id"].as_str().filter(|a| !a.is_empty());
        let success = ["wei", "shu", "wu"].contains(&faction);
        let registry = self
            .singletons
            .entry("AgentInfoRegistry".into())
            .or_insert(json!({"agents":{}}));
        if success {
            let info = json!({"provider":params["provider"],"model_id":params["model_id"],"base_url":request.sanitized_base_url,
                "agent_id":params["agent_id"],"version":params["version"],"note":params["note"],
                "registration_time":request.registration_time,"enable_thinking":params.get("enable_thinking").cloned().unwrap_or(json!(false))});
            let bucket = registry["agents"]
                .as_object_mut()
                .unwrap()
                .entry(faction)
                .or_insert(json!([]))
                .as_array_mut()
                .unwrap();
            if let Some(index) = agent.and_then(|a| {
                bucket
                    .iter()
                    .position(|i| i["agent_id"].as_str() == Some(a))
            }) {
                bucket[index] = info;
            } else {
                bucket.push(info);
            }
        }
        self.register_faction(faction);
        if let Some(agent) = agent {
            self.team
                .get_or_insert_with(Team::default)
                .register_member(faction, agent);
        }
        if !success {
            return error("Failed to register agent info");
        }
        let message = format!("Agent info registered for faction: {faction}");
        json!({"success":true,"result":true,"details":message,"message":message,
            "registered_info":{"faction":faction,"provider":params["provider"],"model_id":params["model_id"],
                "base_url_sanitized":request.sanitized_base_url,"enable_thinking":params.get("enable_thinking").cloned().unwrap_or(json!(false))},
            "map":self.config.interface["map_briefing"],"game_actions":self.action_docs()})
    }
    fn authorize_request(&self, request: &Request) -> Option<Value> {
        let action = request.action.as_deref().unwrap_or("");
        let agent = request.agent_id.as_deref().filter(|a| !a.is_empty());
        let params = &request.parameters;
        if !["register_agent_info", "get_action_list"].contains(&action) {
            let Some(faction) = self.agent_faction(agent) else {
                return Some(self.system_error_at(
                    action,
                    "Agent not registered. Please call register_agent_info first.",
                    2005,
                    request.wall_time,
                ));
            };
            if let Some(reported) = params["faction"].as_str()
                && ["wei", "shu", "wu"].contains(&reported)
                && faction != reported
            {
                return Some(self.system_error_at(action,&format!("Agent {} is registered to {faction} faction, but action specifies {reported}. Please use your registered faction or re-register.",agent.unwrap()),2005, request.wall_time));
            }
            if ["move", "attack", "rest", "occupy", "fortify", "skill"].contains(&action)
                && let Some(id) =
                    action_integer(&params["unit_id"]).and_then(|id| u64::try_from(id).ok())
            {
                if let Some(unit) = self
                    .world
                    .entity(id)
                    .and_then(|e| self.world.ecs.get::<UnitInfo>(e))
                    && unit.faction != faction
                {
                    return Some(self.system_error_at(
                        action,
                        &format!(
                            "Unit {id} belongs to {}; this agent is registered to {faction}.",
                            unit.faction
                        ),
                        2005,
                        request.wall_time,
                    ));
                }
                if let Some(owner) = self.team.as_ref().and_then(|t| t.owner(id))
                    && Some(owner) != agent
                {
                    return Some(self.system_error_at("unit_ownership",&format!("Unit {id} is claimed by teammate {}; agent {} is not authorized to act on it. Use claim_units / release_units to negotiate.",string_repr(owner),string_repr(agent.unwrap())),2005, request.wall_time));
                }
            }
        }
        None
    }
    fn record_action_result<T: From<Value>>(&mut self, request: &Request, mut result: T) -> T {
        let action = request.action.as_deref().unwrap_or("");
        let agent = request.agent_id.as_deref().filter(|a| !a.is_empty());
        if let Some(agent) = agent {
            let faction = self.agent_faction(Some(agent));
            let stats = self.singletons.get_mut("GameStats").unwrap();
            stats["action_counts_by_agent"][agent] =
                json!(stats["action_counts_by_agent"][agent].as_u64().unwrap_or(0) + 1);
            if let Some(faction) = faction {
                stats["action_counts_by_faction"][&faction] = json!(
                    stats["action_counts_by_faction"][&faction]
                        .as_u64()
                        .unwrap_or(0)
                        + 1
                );
            } else {
                result=self.system_error(action,&format!("[LLMSystem. _record_action] Record ENV <-> Agent action error: [LLMSystem. _record_action] Missing faction mapping for agent {agent}. Agents must call register_agent_info before issuing actions."),2012).into();
            }
        }
        result
    }

    /// One exclusive runtime call, preserving accepted order and all write boundaries.
    /// Only action counters are deferred within a read segment: faction projections
    /// never read them, and they are committed in request order before releasing the
    /// exclusive runtime lock or executing any subsequent command.
    pub fn execute_requests(&mut self, mut requests: Vec<Request>) -> Result<BatchReport, String> {
        if requests.iter().any(|r| !r.wall_time.is_finite()) {
            return Err("wall metadata must be finite".into());
        }
        if !self.config.interface.is_object() {
            return Err("missing native action bootstrap metadata".into());
        }
        let mut results = vec![];
        let mut segments = vec![];
        let mut pending = requests.drain(..).peekable();
        while let Some(mut request) = pending.next() {
            if request.action.as_deref() != Some("get_faction_state") {
                results.push(self.execute_request(request)?);
                continue;
            }
            self.ensure_action_stats()?;
            request.normalize_identity();
            let start = results.len();
            let mut queries = vec![request];
            while pending
                .peek()
                .is_some_and(|r| r.action.as_deref() == Some("get_faction_state"))
            {
                let mut request = pending.next().unwrap();
                request.normalize_identity();
                queries.push(request);
            }
            let allowed = self
                .allowed_actions()
                .iter()
                .any(|a| a == "get_faction_state");
            let mut read = ObservationBatch::new(self);
            let mut counted = vec![];
            for request in &queries {
                if let Some(rejection) = self.authorize_request(request) {
                    results.push(rejection.into());
                    counted.push(false);
                } else {
                    results.push(if allowed {
                        read.faction_state(&request.parameters)
                    } else {
                        self.system_error_at(
                            "get_faction_state",
                            "Operation not supported in current game mode",
                            2003,
                            request.wall_time,
                        )
                        .into()
                    });
                    counted.push(true);
                }
            }
            segments.push(json!({"start":start,"end":results.len(),"metrics":read.metrics}));
            drop(read);
            for (index, (request, counted)) in queries.iter().zip(counted).enumerate() {
                self.wall_time = request.wall_time;
                if counted {
                    let result = std::mem::replace(&mut results[start + index], Value::Null.into());
                    results[start + index] = self.record_action_result(request, result);
                }
            }
        }
        Ok(BatchReport {
            results,
            observation_segments: segments,
        })
    }
    /// Only JSON-shaped, normalized local requests enter here. Python/Hub supplies identity.
    pub fn admitted_faction_query_is_readonly(&self) -> bool {
        self.config.interface["action_specs"]["get_faction_state"]["kind"].as_str() == Some("query")
    }
    /// Small per-request diagnostic, deliberately not a full authority export.
    pub fn admitted_query_accounting_snapshot(&self, agent: Option<&str>) -> Value {
        let stats = self.singletons.get("GameStats");
        let faction = stats.and_then(|s| agent.and_then(|a| s["agent_id_to_faction"][a].as_str()));
        json!({"wall_time":self.wall_time,"epoch":self.epoch,"revision":self.revision,
            "agent":agent,"registered_faction":faction,
            "agent_actions":stats.and_then(|s| agent.map(|a| s["action_counts_by_agent"][a].clone())),
            "faction_actions":stats.and_then(|s| faction.map(|f| s["action_counts_by_faction"][f].clone()))})
    }
    pub fn execute_request(&mut self, request: Request) -> Result<Response, String> {
        self.execute_request_with_read_cache(request, &mut None, None)
    }
    /// Research ingress only. All timing, authorization and accounting retain
    /// the single-request order; only owned observation facts may survive.
    pub fn execute_request_with_read_cache(
        &mut self,
        mut request: Request,
        cache: &mut Option<ReadSegmentCache>,
        diagnostic: Option<&mut Value>,
    ) -> Result<Response, String> {
        if !request.wall_time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        self.wall_time = request.wall_time;
        if !self.config.interface.is_object() {
            return Err("missing native action bootstrap metadata".into());
        }
        self.ensure_action_stats()?;
        request.normalize_identity();
        let action = request.action.as_deref().unwrap_or("");
        if action.is_empty() {
            return Ok(self
                .system_error("unknown", "Missing action name", 2007)
                .into());
        }
        if action == "turn_start_ack" {
            return Ok(json!({"success":true}).into());
        }
        let agent = request.agent_id.as_deref().filter(|a| !a.is_empty());
        let params = &request.parameters;
        if let Some(rejection) = self.authorize_request(&request) {
            return Ok(rejection.into());
        }
        let mut result = match action {
            "strategy_ping" => self.strategy_ping(params),
            "report_llm_stats" => self.report_llm_stats(params, request.integer_string_limit),
            "retrieve_game_status" => self.retrieve_game_status(request.connected_agents),
            "register_agent_info" => self.register_agent(&request, params),
            "release_units" => match self.release_request(params) {
                Ok(result) => result,
                Err(message) => {
                    self.revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
                    return Ok(self.system_error(action, &message, 2012).into());
                }
            },
            "claim_units" | "list_team" | "broadcast_to_team" | "read_team_messages" => {
                self.team_action(action, params)
            }
            "get_action_list" => {
                let p = self.action_docs();
                json!({"result":true,"success":true,"actions":p["docs"],"names":p["names"]})
            }
            // Image bytes are attached by the Python display adapter after this
            // authorized projection, before any later request is admitted.
            "get_faction_state" | "get_faction_state_vlm"
                if self.allowed_actions().iter().any(|n| n == action) =>
            {
                let response = if let Some(owned) = cache.take() {
                    let mut batch = ObservationBatch::from_cache(self, owned);
                    let response = batch.faction_state(params);
                    let metrics = diagnostic
                        .as_ref()
                        .map(|_| serde_json::to_value(&batch.metrics).expect("metrics encode"));
                    let owned = batch.into_cache();
                    if let Some(output) = diagnostic {
                        *output = json!({"metrics":metrics,"cache":owned.diagnostic_summary()});
                    }
                    *cache = Some(owned);
                    response
                } else {
                    ObservationBatch::new(self).faction_state(params)
                };
                let response = self.record_action_result(&request, response);
                // Preserve imported action-spec semantics, including a custom
                // kind that classifies this otherwise read-only action as a write.
                if self.config.interface["action_specs"][action]["kind"].as_str() != Some("query") {
                    self.revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
                }
                return Ok(response);
            }
            "observation" if self.allowed_actions().iter().any(|n| n == action) => {
                self.legacy_observation(params)
            }
            "unit_observation"
            | "faction_observation"
            | "limited_observation"
            | "godview_observation"
                if self.allowed_actions().iter().any(|n| n == action) =>
            {
                self.named_observation(action, params)
            }
            "rest" if self.allowed_actions().iter().any(|n| n == action) => {
                self.handle_rest(params)
            }
            "skill" if self.allowed_actions().iter().any(|n| n == action) => {
                self.handle_skill(params)
            }
            "occupy" | "fortify" if self.allowed_actions().iter().any(|n| n == action) => {
                self.handle_territory(action, params)
            }
            "end_turn" if self.allowed_actions().iter().any(|n| n == action) => {
                self.handle_end_turn(params)
            }
            "move" if self.allowed_actions().iter().any(|n| n == action) => {
                self.handle_move(params)
            }
            "attack" if self.allowed_actions().iter().any(|n| n == action) => {
                // A failing combat may have consumed a roll or written components.
                match self.handle_attack(params) {
                    Ok(result) => result,
                    Err(message) => extra_handler_error(&message),
                }
            }
            _ if !self.config.interface["action_specs"][action].is_null()
                && !self.allowed_actions().iter().any(|n| n == action) =>
            {
                self.system_error(action, "Operation not supported in current game mode", 2003)
            }
            _ if !self.config.interface["action_specs"][action].is_null() => {
                return Err(format!("native action {action} is not implemented yet"));
            }
            _ => self.system_error(action, &format!("UNKNOWN ACTION: {action}"), 2010),
        };
        let rejected_before_dispatch = matches!(result["error_code"].as_i64(), Some(2003 | 2010));
        if action == "register_agent_info" && result["success"].as_bool() == Some(true) {
            let faction = params["faction"].as_str().unwrap();
            let stats = self.singletons.get_mut("GameStats").unwrap();
            if let Some(agent) = agent {
                stats["agent_id_to_faction"][agent] = json!(faction);
            }
            stats["expected_llm_stats_count"] = json!(
                stats["registered_factions"]["$set"]
                    .as_array()
                    .unwrap()
                    .len()
            );
        }
        result = self.record_action_result(&request, result);
        if action != "get_action_list"
            && self.config.interface["action_specs"][action]["kind"].as_str() != Some("query")
            && !rejected_before_dispatch
        {
            self.revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        }
        Ok(result.into())
    }
}

fn extra_handler_error(message: &str) -> Value {
    let mut result = error(&format!("Action execution failed: {message}"));
    result["error_code"] = json!(2012);
    result
}

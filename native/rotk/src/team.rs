//! Native team ownership and bounded inboxes. No transport or model calls.
use crate::{codec::id_map, runtime::Runtime};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TeamState {
    #[serde(with = "id_map")]
    unit_owners: BTreeMap<u64, String>,
    faction_members: BTreeMap<String, Vec<String>>,
    team_inboxes: BTreeMap<String, VecDeque<Value>>,
    team_history: BTreeMap<String, VecDeque<Value>>,
    history_cap: usize,
    inbox_cap: usize,
    // A Python deque retains its original maxlen if the tunable cap later changes.
    inbox_maxlen: BTreeMap<String, Option<usize>>,
    history_maxlen: BTreeMap<String, Option<usize>>,
}
impl Default for TeamState {
    fn default() -> Self {
        Self {
            unit_owners: BTreeMap::new(),
            faction_members: BTreeMap::new(),
            team_inboxes: BTreeMap::new(),
            team_history: BTreeMap::new(),
            history_cap: 256,
            inbox_cap: 64,
            inbox_maxlen: BTreeMap::new(),
            history_maxlen: BTreeMap::new(),
        }
    }
}
#[derive(Default)]
pub struct Team {
    pub state: TeamState,
    // Derived once on import, then maintained at writes. Release-all visits owned IDs only.
    owned: HashMap<String, BTreeSet<u64>>,
    members: HashMap<String, HashSet<String>>,
}
impl Team {
    pub fn restore(state: TeamState) -> Result<Self, String> {
        for (queues, limits) in [
            (&state.team_inboxes, &state.inbox_maxlen),
            (&state.team_history, &state.history_maxlen),
        ] {
            if queues.len() != limits.len()
                || queues.iter().any(|(k, q)| {
                    limits
                        .get(k)
                        .is_none_or(|cap| cap.is_some_and(|cap| q.len() > cap))
                })
            {
                return Err("inconsistent team queue limits".into());
            }
        }
        let mut owned: HashMap<String, BTreeSet<u64>> = HashMap::new();
        for (&id, agent) in &state.unit_owners {
            owned.entry(agent.clone()).or_default().insert(id);
        }
        let members = state
            .faction_members
            .iter()
            .map(|(f, ids)| (f.clone(), ids.iter().cloned().collect()))
            .collect();
        Ok(Self {
            state,
            owned,
            members,
        })
    }
    pub fn register_member(&mut self, faction: &str, agent: &str) -> bool {
        if !self
            .members
            .entry(faction.into())
            .or_default()
            .insert(agent.into())
        {
            return false;
        }
        self.state
            .faction_members
            .entry(faction.into())
            .or_default()
            .push(agent.into());
        if !self.state.team_inboxes.contains_key(agent) {
            self.state
                .team_inboxes
                .insert(agent.into(), VecDeque::new());
            self.state
                .inbox_maxlen
                .insert(agent.into(), Some(self.state.inbox_cap));
        }
        true
    }
    pub fn teammates(&self, faction: &str, agent: Option<&str>) -> Vec<String> {
        self.state
            .faction_members
            .get(faction)
            .into_iter()
            .flatten()
            .filter(|s| Some(s.as_str()) != agent)
            .cloned()
            .collect()
    }
    pub fn owner(&self, id: u64) -> Option<&str> {
        self.state.unit_owners.get(&id).map(String::as_str)
    }
    pub fn authorized(&self, id: u64, agent: Option<&str>) -> bool {
        self.owner(id).is_none_or(|owner| Some(owner) == agent)
    }
    pub fn claim(&mut self, agent: &str, ids: &[u64], exclusive: bool) -> Value {
        if exclusive {
            let conflicts: BTreeMap<_, _> = ids
                .iter()
                .filter_map(|id| {
                    self.state
                        .unit_owners
                        .get(id)
                        .filter(|owner| owner.as_str() != agent)
                        .map(|owner| (id.to_string(), owner))
                })
                .collect();
            if !conflicts.is_empty() {
                return json!({"success":false,"claimed":[],"conflicts":conflicts,
                "message":format!("Exclusive claim refused: {} units already owned by other agents.",conflicts.len())});
            }
        }
        for &id in ids {
            if let Some(old) = self.state.unit_owners.insert(id, agent.into())
                && let Some(previous) = self.owned.get_mut(&old)
            {
                previous.remove(&id);
            }
            self.owned.entry(agent.into()).or_default().insert(id);
        }
        json!({"success":true,"claimed":ids,"conflicts":{},"message":format!("Claimed {} units for agent {agent}.",ids.len())})
    }
    pub fn release(&mut self, agent: &str, ids: Option<&[u64]>) -> Value {
        let all;
        let ids = match ids {
            Some(ids) => ids,
            None => {
                all = self
                    .owned
                    .get(agent)
                    .map(|ids| ids.iter().copied().collect::<Vec<_>>())
                    .unwrap_or_default();
                &all
            }
        };
        let mut released = vec![];
        for &id in ids {
            if self.owner(id) == Some(agent) {
                self.state.unit_owners.remove(&id);
                self.owned.get_mut(agent).unwrap().remove(&id);
                released.push(id);
            }
        }
        json!({"success":true,"released":released,"message":format!("Released {} units.",released.len())})
    }
    pub fn broadcast(
        &mut self,
        sender: &str,
        faction: &str,
        text: &str,
        metadata: Value,
        wall: f64,
    ) -> Value {
        let teammates = self.teammates(faction, Some(sender));
        let metadata = if crate::codec::truthy(&metadata) {
            metadata
        } else {
            json!({})
        };
        let message =
            json!({"from":sender,"faction":faction,"ts":wall,"text":text,"metadata":metadata});
        for member in &teammates {
            let inbox = self.state.team_inboxes.entry(member.clone()).or_default();
            let cap = *self
                .state
                .inbox_maxlen
                .entry(member.clone())
                .or_insert(Some(self.state.inbox_cap));
            append(inbox, message.clone(), cap);
        }
        let history = self.state.team_history.entry(faction.into()).or_default();
        let cap = *self
            .state
            .history_maxlen
            .entry(faction.into())
            .or_insert(Some(self.state.history_cap));
        append(history, message, cap);
        json!({"success":true,"delivered_to":teammates,"teammate_count":teammates.len(),"message":
            if teammates.is_empty() { "No teammates currently registered; message recorded in history.".into() }
            else { format!("Delivered to {} teammate(s).",teammates.len()) }})
    }
    pub fn drain(&mut self, agent: &str) -> Value {
        let messages: Vec<_> = self
            .state
            .team_inboxes
            .get_mut(agent)
            .map(|q| q.drain(..).collect())
            .unwrap_or_default();
        json!(messages)
    }
    pub fn snapshot(&self) -> Value {
        json!({"unit_owners":self.state.unit_owners,"faction_members":self.state.faction_members,
            "history_lengths":self.state.team_history.iter().map(|(k,v)| (k,v.len())).collect::<BTreeMap<_,_>>(),
            "pending_inbox_sizes":self.state.team_inboxes.iter().map(|(k,v)| (k,v.len())).collect::<BTreeMap<_,_>>()})
    }
}
fn append(queue: &mut VecDeque<Value>, item: Value, limit: Option<usize>) {
    if limit == Some(0) {
        return;
    }
    if let Some(n) = limit {
        while queue.len() >= n {
            queue.pop_front();
        }
    }
    queue.push_back(item);
}

impl Runtime {
    /// Internal component contract probe; public dispatch supplies identity/faction validation.
    pub fn team_probe(&mut self, operations: Vec<Value>) -> Result<Vec<Value>, String> {
        let mut out = vec![];
        for op in operations {
            let kind = op["kind"].as_str().ok_or("missing team operation")?;
            let agent = op["agent_id"].as_str();
            let faction = op["faction"].as_str();
            let revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
            let team = self.team.get_or_insert_with(Team::default);
            let result = match kind {
                "member" => json!(team.register_member(
                    faction.ok_or("missing faction")?,
                    agent.ok_or("missing agent")?
                )),
                "teammates" => json!(team.teammates(faction.ok_or("missing faction")?, agent)),
                "owner" => json!(team.owner(op["unit_id"].as_u64().ok_or("invalid unit ID")?)),
                "authorized" => {
                    json!(team.authorized(op["unit_id"].as_u64().ok_or("invalid unit ID")?, agent))
                }
                "claim" | "release" => {
                    let ids: Option<Vec<u64>> = if op["unit_ids"].is_null() {
                        None
                    } else {
                        Some(
                            serde_json::from_value(op["unit_ids"].clone())
                                .map_err(|e| e.to_string())?,
                        )
                    };
                    let agent = agent.ok_or("missing agent")?;
                    if kind == "claim" {
                        team.claim(
                            agent,
                            ids.as_deref().ok_or("missing IDs")?,
                            op["exclusive"].as_bool().unwrap_or(true),
                        )
                    } else {
                        team.release(agent, ids.as_deref())
                    }
                }
                "broadcast" => team.broadcast(
                    agent.ok_or("missing agent")?,
                    faction.ok_or("missing faction")?,
                    op["text"].as_str().ok_or("missing text")?,
                    op.get("metadata").cloned().unwrap_or(json!({})),
                    self.wall_time,
                ),
                "drain" => team.drain(agent.ok_or("missing agent")?),
                "snapshot" => team.snapshot(),
                _ => return Err("unknown team operation".into()),
            };
            if !["owner", "authorized", "teammates", "snapshot"].contains(&kind) {
                self.revision = revision;
            }
            out.push(result);
        }
        Ok(out)
    }
}

//! Read-only faction projection. A borrow scopes all caches to one write-free batch.
use crate::{
    components::{ActionPoints, CombatStats, Headcount, Position, UnitInfo},
    hex::{self, Hex},
    runtime::Runtime,
};
use serde::{Serialize, Serializer, ser::SerializeMap};
use serde_json::{Value, json, value::RawValue};
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::sync::Arc;

/// Owned immutable fields, encoded once inside a write-free observation segment.
/// RawValue is produced only by serde from kernel JSON, never from caller strings.
struct EncodedObject(Vec<(String, Box<RawValue>)>);
impl EncodedObject {
    fn new(value: Value) -> Self {
        let Value::Object(fields) = value else {
            unreachable!("native observation object");
        };
        Self(
            fields
                .into_iter()
                .map(|(key, value)| {
                    (
                        key,
                        serde_json::value::to_raw_value(&value).expect("JSON value encodes"),
                    )
                })
                .collect(),
        )
    }
    fn fields<M: SerializeMap>(&self, map: &mut M) -> Result<(), M::Error> {
        for (key, value) in &self.0 {
            map.serialize_entry(key, value)?;
        }
        Ok(())
    }
}

struct UnitResponse {
    panel: Arc<EncodedObject>,
    owner: Option<String>,
    commandable: bool,
}
impl Serialize for UnitResponse {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.panel.0.len() + 2))?;
        self.panel.fields(&mut map)?;
        map.serialize_entry("owner", &self.owner)?;
        map.serialize_entry("commandable", &self.commandable)?;
        map.end()
    }
}

pub struct FactionResponse {
    public: Arc<EncodedObject>,
    units: Vec<UnitResponse>,
}
impl Serialize for FactionResponse {
    fn serialize<S: Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.public.0.len() + 1))?;
        self.public.fields(&mut map)?;
        map.serialize_entry("units", &self.units)?;
        map.end()
    }
}

/// Responses own their facts, not a live borrow of the runtime. A subsequent
/// write may destroy/reset entities before the entire mixed batch is encoded.
#[derive(Serialize)]
#[serde(untagged)]
pub enum Response {
    Plain(Value),
    Faction(FactionResponse),
}
impl From<Value> for Response {
    fn from(value: Value) -> Self {
        Self::Plain(value)
    }
}

#[derive(Serialize)]
pub struct ObservationReport {
    pub results: Vec<Response>,
    pub metrics: Metrics,
}

#[derive(Default)]
struct Census {
    totals: BTreeMap<String, usize>,
    alive: BTreeMap<String, Vec<u64>>,
    actionable: BTreeMap<String, usize>,
}
struct FactionFacts {
    alive: Vec<u64>,
    enemies: BTreeSet<u64>,
    public: Arc<EncodedObject>,
}
#[derive(Default, serde::Serialize)]
pub struct Metrics {
    census_builds: usize,
    faction_builds: usize,
    panel_builds: usize,
    enemy_builds: usize,
    tile_builds: usize,
    census_entities_visited: usize,
    enemy_entities_visited: usize,
    terrain_cells_visited: usize,
    attack_cell_lookups: usize,
    attack_distance_checks: usize,
    attack_rule_checks: usize,
    public_encodes: usize,
    panel_encodes: usize,
    shared_public_results: usize,
    shared_panel_results: usize,
    parallel_panel_batches: usize,
    panel_tasks: usize,
    panel_worker_threads: usize,
}
/// Opt-in diagnostic wall times. Nested fields are not additive.
#[derive(Default, serde::Serialize)]
pub struct Profile {
    census_ns: u64,
    faction_ns: u64,
    public_encode_ns: u64,
    panels_ns: u64,
}
pub struct ObservationBatch<'a> {
    runtime: &'a Runtime,
    census: Option<Census>,
    factions: HashMap<String, FactionFacts>,
    panels: HashMap<u64, Arc<EncodedObject>>,
    enemies: HashMap<u64, Value>,
    tiles: HashMap<Hex, Value>,
    panel_workers: HashSet<std::thread::ThreadId>,
    pub metrics: Metrics,
    pub profile: Option<Profile>,
}
pub fn error(message: &str) -> Value {
    json!({"success":false,"result":false,"details":message,"message":message})
}
impl<'a> ObservationBatch<'a> {
    pub fn new(runtime: &'a Runtime) -> Self {
        Self {
            runtime,
            census: None,
            factions: HashMap::new(),
            panels: HashMap::new(),
            enemies: HashMap::new(),
            tiles: HashMap::new(),
            panel_workers: HashSet::new(),
            metrics: Metrics::default(),
            profile: None,
        }
    }
    pub fn profiled(runtime: &'a Runtime) -> Self {
        let mut batch = Self::new(runtime);
        batch.profile = Some(Profile::default());
        batch
    }
    fn census(&mut self) {
        if self.census.is_some() {
            return;
        }
        let start = self.profile.as_ref().map(|_| std::time::Instant::now());
        self.metrics.census_builds += 1;
        let r = self.runtime;
        let mut c = Census::default();
        for (&id, &e) in &r.unit_entities {
            self.metrics.census_entities_visited += 1;
            let Some(u) = r.world.ecs.get::<UnitInfo>(e) else {
                continue;
            };
            *c.totals.entry(u.faction.clone()).or_default() += 1;
            if r.world
                .ecs
                .get::<Headcount>(e)
                .is_some_and(|n| n.current_count > 0)
            {
                c.alive.entry(u.faction.clone()).or_default().push(id);
                if r.world
                    .ecs
                    .get::<ActionPoints>(e)
                    .is_some_and(|p| p.current_ap > 0)
                {
                    *c.actionable.entry(u.faction.clone()).or_default() += 1;
                }
            }
        }
        self.census = Some(c);
        if let Some(start) = start {
            self.profile.as_mut().unwrap().census_ns += start.elapsed().as_nanos() as u64;
        }
    }
    fn faction_status(&self, faction: &str) -> &'static str {
        let r = self.runtime;
        if let Some(g) = r.singletons.get("GameState")
            && g["game_over"].as_bool() == Some(true)
        {
            return if g["winner"].as_str() == Some(faction) {
                "victory"
            } else if g["winner"].is_null() {
                "draw"
            } else {
                "defeat"
            };
        }
        if let Some(winner) = r
            .singletons
            .get("Winner")
            .and_then(|w| w["faction"].as_str())
        {
            return if winner == faction {
                "victory"
            } else {
                "defeat"
            };
        }
        let c = self.census.as_ref().unwrap();
        if c.alive.get(faction).is_none_or(Vec::is_empty) {
            return "eliminated";
        }
        if !c
            .alive
            .iter()
            .any(|(f, ids)| f != faction && !ids.is_empty())
        {
            return "victory";
        }
        if r.singletons
            .get("BattleLog")
            .and_then(|b| b["entries"].as_array())
            .is_some_and(|entries| {
                entries.iter().rev().take(3).any(|e| {
                    e["attacker_faction"].as_str() == Some(faction)
                        || e["defender_faction"].as_str() == Some(faction)
                })
            })
        {
            return "in_battle";
        }
        "active"
    }
    fn faction(&mut self, faction: &str) {
        if self.factions.contains_key(faction) {
            return;
        }
        let start = self.profile.as_ref().map(|_| std::time::Instant::now());
        self.census();
        self.metrics.faction_builds += 1;
        let r = self.runtime;
        let lifted = r.fog.as_ref().is_none_or(|f| !f.enabled);
        let visible = r.fog.as_ref().and_then(|f| f.faction_vision.get(faction));
        let mut enemy_ids = BTreeSet::new();
        let mut enemies = vec![];
        for (&id, &e) in &r.unit_entities {
            self.metrics.enemy_entities_visited += 1;
            let (Some(u), Some(p), Some(n)) = (
                r.world.ecs.get::<UnitInfo>(e),
                r.world.ecs.get::<Position>(e),
                r.world.ecs.get::<Headcount>(e),
            ) else {
                continue;
            };
            if u.faction == faction
                || n.current_count <= 0
                || (!lifted && visible.is_none_or(|v| !v.contains(&p.hex())))
            {
                continue;
            }
            enemy_ids.insert(id);
            let fact = self.enemies.entry(id).or_insert_with(|| {
                self.metrics.enemy_builds += 1;
                json!({"unit_id":id,"unit_type":u.unit_type,"faction":u.faction,
                    "position":{"col":p.col,"row":p.row},"unit_status":{"current_count":n.current_count}})
            });
            enemies.push(fact.clone());
        }
        let mut terrain = vec![];
        // Fog-positive queries need only visit the smaller existing set. Keep
        // coordinate ordering and the map intersection (Fog can include off-map
        // cells); zero tile ID and missing Terrain are handled below as before.
        let cells: BTreeSet<_> = if !lifted && visible.is_none() {
            BTreeSet::new()
        } else if !lifted && visible.is_some_and(|v| v.len() < r.spatial.tiles.len()) {
            let visible = visible.unwrap();
            self.metrics.terrain_cells_visited += visible.len();
            visible
                .iter()
                .copied()
                .filter(|cell| r.spatial.tiles.contains_key(cell))
                .collect()
        } else {
            self.metrics.terrain_cells_visited += r.spatial.tiles.len();
            r.spatial
                .tiles
                .keys()
                .copied()
                .filter(|cell| lifted || visible.is_some_and(|v| v.contains(cell)))
                .collect()
        };
        for cell in cells {
            let tile = &r.spatial.tiles[&cell];
            // Preserve historical falsy external ID zero lookup.
            if tile.entity == 0 || !tile.has_terrain {
                continue;
            }
            terrain.push(self.tiles.entry(cell).or_insert_with(|| {
                self.metrics.tile_builds += 1;
                json!({"col":cell.0,"row":cell.1,"type":tile.terrain,"movement_cost":tile.cost,"passable":tile.cost<999})
            }).clone());
        }
        let c = self.census.as_ref().unwrap();
        let alive = c.alive.get(faction).cloned().unwrap_or_default();
        let mut public = json!({"success":true,"result":true,"state":self.faction_status(faction),"faction":faction,
            "fog":if lifted {"disabled"} else {"active"}, "total_units":c.totals.get(faction).copied().unwrap_or(0),
            "alive_units":alive.len(),"actionable_units":c.actionable.get(faction).copied().unwrap_or(0),
            "visible_enemy_units":null,"visible_terrain":null});
        // These arrays already own JSON values. Serialize-to-Value would copy
        // every nested key/string again; move them into their final container.
        public["visible_enemy_units"] = Value::Array(enemies);
        public["visible_terrain"] = Value::Array(terrain);
        self.metrics.public_encodes += 1;
        let encode_start = self.profile.as_ref().map(|_| std::time::Instant::now());
        let public = Arc::new(EncodedObject::new(public));
        if let Some(start) = encode_start {
            self.profile.as_mut().unwrap().public_encode_ns += start.elapsed().as_nanos() as u64;
        }
        self.factions.insert(
            faction.into(),
            FactionFacts {
                alive,
                enemies: enemy_ids,
                public,
            },
        );
        if let Some(start) = start {
            self.profile.as_mut().unwrap().faction_ns += start.elapsed().as_nanos() as u64;
        }
    }
    fn prepare_panels(&mut self, ids: &[u64], faction: &str) {
        let start = self.profile.as_ref().map(|_| std::time::Instant::now());
        let missing: Vec<_> = ids
            .iter()
            .copied()
            .filter(|id| !self.panels.contains_key(id))
            .collect();
        let r = self.runtime;
        let enemies = &self.factions[faction].enemies;
        let compute = |ids: &[u64]| {
            ids.iter()
                .map(|&id| {
                    let mut metrics = Metrics::default();
                    let attackable = Self::attackable(r, id, enemies, &mut metrics);
                    let reachable = r
                        .reachable(id)
                        .iter()
                        .map(|p| json!({"col":p.0,"row":p.1}))
                        .collect();
                    let mut info = r.detailed_unit_info(id);
                    info["reachable"] = Value::Array(reachable);
                    info["attackable"] = json!(attackable);
                    (id, Arc::new(EncodedObject::new(info)), metrics)
                })
                .collect::<Vec<_>>()
        };
        let outputs = if let Some(pool) = r.observation_pool.as_ref().filter(|_| missing.len() > 1)
        {
            self.metrics.parallel_panel_batches += 1;
            let chunks = pool.map_chunks(&missing, compute);
            self.metrics.panel_tasks += chunks.len();
            for (_, worker) in &chunks {
                self.panel_workers.insert(*worker);
            }
            self.metrics.panel_worker_threads = self.panel_workers.len();
            chunks.into_iter().flat_map(|(values, _)| values).collect()
        } else {
            compute(&missing)
        };
        // Commit caches/counters only after the scoped read jobs have joined.
        for (id, panel, metrics) in outputs {
            self.metrics.panel_builds += 1;
            self.metrics.panel_encodes += 1;
            self.metrics.attack_cell_lookups += metrics.attack_cell_lookups;
            self.metrics.attack_distance_checks += metrics.attack_distance_checks;
            self.metrics.attack_rule_checks += metrics.attack_rule_checks;
            self.panels.insert(id, panel);
        }
        if let Some(start) = start {
            self.profile.as_mut().unwrap().panels_ns += start.elapsed().as_nanos() as u64;
        }
    }
    /// Exact broad phase: range is a necessary condition of can_attack. Reuse
    /// authoritative occupancy and the faction's visible-enemy set; never expand
    /// information access or cache across a write. Work is bounded by the smaller
    /// of the hex disc and enemy list, plus occupants of the visited cells.
    fn attackable(
        r: &Runtime,
        id: u64,
        enemies: &BTreeSet<u64>,
        metrics: &mut Metrics,
    ) -> Vec<u64> {
        if !r.can_attack(id, None) {
            return vec![];
        }
        let Some(position) = r.component::<Position>(id) else {
            return vec![];
        };
        let radius = r.component::<CombatStats>(id).unwrap().attack_range;
        if radius < 0 {
            return vec![];
        }
        let wide = radius as u128;
        let cells = 1 + 3 * wide * (wide + 1);
        let mut candidates = vec![];
        if cells <= enemies.len() as u128 {
            let (q, s) = hex::axial(position.hex());
            for dq in -radius..=radius {
                for ds in (-radius).max(-dq - radius)..=radius.min(-dq + radius) {
                    metrics.attack_cell_lookups += 1;
                    let cell = hex::offset((q + dq, s + ds));
                    if let Some(occupants) = r.spatial.cells.get(&cell) {
                        candidates
                            .extend(occupants.keys().filter(|id| enemies.contains(id)).copied());
                    }
                }
            }
            // Cell traversal order is not the oracle's external entity-ID order.
            candidates.sort_unstable();
        } else {
            // Huge/custom ranges and small enemy sets must not allocate/enumerate
            // a huge disc. Distance rejection also avoids constructing error JSON.
            for &enemy in enemies {
                metrics.attack_distance_checks += 1;
                if r.component::<Position>(enemy)
                    .is_some_and(|p| hex::distance(position.hex(), p.hex()) <= radius)
                {
                    candidates.push(enemy);
                }
            }
        }
        candidates.retain(|&enemy| {
            metrics.attack_rule_checks += 1;
            r.can_attack(id, Some(enemy))
        });
        candidates
    }
    /// Handler-level projection; trusted identity is checked by the action dispatcher.
    pub fn faction_state(&mut self, params: &Value) -> Response {
        let r = self.runtime;
        let requested = &params["faction"];
        if !crate::codec::truthy(requested) {
            return error("faction parameter required").into();
        }
        let faction = match requested.as_str() {
            Some(f @ ("wei" | "shu" | "wu")) => f,
            _ => {
                return error(&format!(
                    "Invalid faction: {}",
                    requested
                        .as_str()
                        .map(String::from)
                        .unwrap_or_else(|| requested.to_string())
                ))
                .into();
            }
        };
        let agent = params["agent_id"].as_str().filter(|a| !a.is_empty());
        let mapped = agent.and_then(|a| {
            r.singletons
                .get("GameStats")
                .and_then(|s| s["agent_id_to_faction"][a].as_str())
        });
        if let Some(observer) = mapped.filter(|o| *o != faction) {
            let mut result = error(&format!(
                "Agent is registered to {observer}; get_faction_state only reports that faction's screen. Visible enemies are in visible_enemy_units."
            ));
            result["error_code"] = json!(2005);
            result["registered_faction"] = json!(observer);
            result["requested_faction"] = json!(faction);
            return result.into();
        }
        let selected = if let Some(ids) = params.get("unit_ids") {
            let Some(ids) = ids.as_array() else {
                return error("unit_ids must be a list of integer unit IDs").into();
            };
            if ids.iter().any(|id| !id.is_i64() && !id.is_u64()) {
                return error("unit_ids must be a list of integer unit IDs").into();
            }
            let mut seen = BTreeSet::new();
            let mut ordered = vec![];
            for id in ids {
                let uid = id.as_u64();
                if uid
                    .and_then(|id| r.world.entity(id))
                    .and_then(|e| r.world.ecs.get::<UnitInfo>(e))
                    .is_none_or(|u| u.faction != faction)
                {
                    let mut result = error("unit_ids must name existing units of your own faction");
                    result["error_code"] = json!(2005);
                    return result.into();
                }
                let uid = uid.unwrap();
                if seen.insert(uid)
                    && r.world
                        .entity(uid)
                        .and_then(|e| r.world.ecs.get::<Headcount>(e))
                        .is_some_and(|n| n.current_count > 0)
                {
                    ordered.push(uid);
                }
            }
            Some(ordered)
        } else {
            None
        };
        self.faction(faction);
        let ids = selected.unwrap_or_else(|| self.factions[faction].alive.clone());
        self.prepare_panels(&ids, faction);
        let mut units = vec![];
        for id in ids {
            let owner = r.team.as_ref().and_then(|t| t.owner(id));
            units.push(UnitResponse {
                panel: Arc::clone(&self.panels[&id]),
                owner: owner.map(str::to_owned),
                commandable: agent.is_none() || owner.is_none_or(|owner| Some(owner) == agent),
            });
            self.metrics.shared_panel_results += 1;
        }
        self.metrics.shared_public_results += 1;
        Response::Faction(FactionResponse {
            public: Arc::clone(&self.factions[faction].public),
            units,
        })
    }
}

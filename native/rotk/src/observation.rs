//! Read-only faction projection. A borrow scopes all caches to one write-free batch.
use crate::{
    components::{ActionPoints, CombatStats, Headcount, Position, UnitInfo},
    hex::{self, Hex},
    runtime::Runtime,
};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet, HashMap};

#[derive(Default)]
struct Census {
    totals: BTreeMap<String, usize>,
    alive: BTreeMap<String, Vec<u64>>,
    actionable: BTreeMap<String, usize>,
}
struct FactionFacts {
    alive: Vec<u64>,
    enemies: BTreeSet<u64>,
    public: Value,
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
}
pub struct ObservationBatch<'a> {
    runtime: &'a Runtime,
    census: Option<Census>,
    factions: HashMap<String, FactionFacts>,
    panels: HashMap<u64, Value>,
    enemies: HashMap<u64, Value>,
    tiles: HashMap<Hex, Value>,
    pub metrics: Metrics,
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
            metrics: Metrics::default(),
        }
    }
    fn census(&mut self) {
        if self.census.is_some() {
            return;
        }
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
        let public = json!({"success":true,"result":true,"state":self.faction_status(faction),"faction":faction,
            "fog":if lifted {"disabled"} else {"active"}, "total_units":c.totals.get(faction).copied().unwrap_or(0),
            "alive_units":alive.len(),"actionable_units":c.actionable.get(faction).copied().unwrap_or(0),
            "visible_enemy_units":enemies,"visible_terrain":terrain});
        self.factions.insert(
            faction.into(),
            FactionFacts {
                alive,
                enemies: enemy_ids,
                public,
            },
        );
    }
    fn panel(&mut self, id: u64, faction: &str) {
        if self.panels.contains_key(&id) {
            return;
        }
        self.metrics.panel_builds += 1;
        let r = self.runtime;
        let attackable = self.attackable(id, faction);
        let reachable: Vec<_> = r
            .reachable(id)
            .iter()
            .map(|p| json!({"col":p.0,"row":p.1}))
            .collect();
        let mut info = r.detailed_unit_info(id);
        info["reachable"] = json!(reachable);
        info["attackable"] = json!(attackable);
        self.panels.insert(id, info);
    }
    /// Exact broad phase: range is a necessary condition of can_attack. Reuse
    /// authoritative occupancy and the faction's visible-enemy set; never expand
    /// information access or cache across a write. Work is bounded by the smaller
    /// of the hex disc and enemy list, plus occupants of the visited cells.
    fn attackable(&mut self, id: u64, faction: &str) -> Vec<u64> {
        let r = self.runtime;
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
        let enemies = &self.factions[faction].enemies;
        let wide = radius as u128;
        let cells = 1 + 3 * wide * (wide + 1);
        let mut candidates = vec![];
        if cells <= enemies.len() as u128 {
            let (q, s) = hex::axial(position.hex());
            for dq in -radius..=radius {
                for ds in (-radius).max(-dq - radius)..=radius.min(-dq + radius) {
                    self.metrics.attack_cell_lookups += 1;
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
                self.metrics.attack_distance_checks += 1;
                if r.component::<Position>(enemy)
                    .is_some_and(|p| hex::distance(position.hex(), p.hex()) <= radius)
                {
                    candidates.push(enemy);
                }
            }
        }
        candidates.retain(|&enemy| {
            self.metrics.attack_rule_checks += 1;
            r.can_attack(id, Some(enemy))
        });
        candidates
    }
    /// Handler-level projection; trusted identity is checked by the action dispatcher.
    pub fn faction_state(&mut self, params: &Value) -> Value {
        let r = self.runtime;
        let requested = &params["faction"];
        if !crate::codec::truthy(requested) {
            return error("faction parameter required");
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
                ));
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
            return result;
        }
        let selected = if let Some(ids) = params.get("unit_ids") {
            let Some(ids) = ids.as_array() else {
                return error("unit_ids must be a list of integer unit IDs");
            };
            if ids.iter().any(|id| !id.is_i64() && !id.is_u64()) {
                return error("unit_ids must be a list of integer unit IDs");
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
                    return result;
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
        let mut units = vec![];
        for id in ids {
            self.panel(id, faction);
            let mut panel = self.panels[&id].clone();
            let owner = r.team.as_ref().and_then(|t| t.owner(id));
            panel["owner"] = json!(owner);
            panel["commandable"] =
                json!(agent.is_none() || owner.is_none_or(|owner| Some(owner) == agent));
            units.push(panel);
        }
        let mut result = self.factions[faction].public.clone();
        result["units"] = json!(units);
        result
    }
}

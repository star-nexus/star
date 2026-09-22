//! Legacy observation variants. Their data/visibility contracts deliberately differ
//! from get_faction_state; immutable results are cached only at the same revision.
use crate::{
    codec::{action_integer, scalar_display, truthy},
    components::{
        ActionPoints, CombatStats, ConstructionPoints, Headcount, MovePoints, Movement, Position,
        SkillPoints, Status, TerritoryControl, UnitInfo,
    },
    hex::{self, Hex},
    observation::error,
    runtime::{InitialComponents, Runtime},
    vision::{HexSet, Vision},
};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Default)]
pub(crate) struct QueryCache {
    revision: u64,
    entries: BTreeMap<String, Value>,
}
impl QueryCache {
    pub fn import(value: &Value) -> Result<Self, String> {
        Ok(Self {
            revision: 0,
            entries: serde_json::from_value(value.clone())
                .map_err(|e| format!("invalid observation cache: {e}"))?,
        })
    }
    pub fn export(&self, revision: u64) -> Value {
        if self.revision == revision {
            json!(self.entries)
        } else {
            json!({})
        }
    }
}

fn cells(values: &BTreeSet<Hex>) -> Vec<Value> {
    values
        .iter()
        .map(|&(col, row)| json!({"col":col,"row":row}))
        .collect()
}
fn py_repr(v: &Value) -> String {
    match v {
        Value::String(s) => crate::codec::string_repr(s),
        Value::Array(a) => format!("[{}]", a.iter().map(py_repr).collect::<Vec<_>>().join(", ")),
        Value::Object(o) => format!(
            "{{{}}}",
            o.iter()
                .map(|(k, v)| format!("{}: {}", crate::codec::string_repr(k), py_repr(v)))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        _ => scalar_display(v),
    }
}
pub(crate) fn py_display(v: &Value) -> String {
    if let Some(s) = v.as_str() {
        s.into()
    } else {
        py_repr(v)
    }
}

impl Runtime {
    fn cold(&self, uid: u64, name: &str) -> Option<&Value> {
        self.component::<InitialComponents>(uid)
            .and_then(|c| c.0.get(name))
    }
    pub(crate) fn detailed_unit_info(&self, uid: u64) -> Value {
        let u = self.component::<UnitInfo>(uid).expect("validated Unit");
        let p = self.component::<Position>(uid);
        let n = self.component::<Headcount>(uid);
        let mp = self.component::<MovePoints>(uid);
        let ap = self.component::<ActionPoints>(uid);
        let c = self.component::<CombatStats>(uid);
        let v = self.component::<Vision>(uid);
        let s = self.component::<Status>(uid);
        let mut properties = json!({"attack_range":c.map_or(1,|c|c.attack_range),
            "attack_power":c.map_or(10,|c|c.base_attack),"vision_range":v.map_or(2,|v|v.range)});
        if let Some(c) = c {
            properties["defense"] = json!(c.base_defense);
        }
        let mut skills: Vec<_> = self
            .cold(uid, "UnitSkills")
            .and_then(|s| {
                s["available_skills"]
                    .as_array()
                    .or_else(|| s["available_skills"]["$set"].as_array())
            })
            .into_iter()
            .flatten()
            .map(py_display)
            .collect();
        skills.sort();
        json!({"unit_id":uid,"unit_type":u.unit_type,"faction":u.faction,
            "position":{"col":p.map_or(0,|p|p.col),"row":p.map_or(0,|p|p.row)},
            "unit_status":{"current_count":n.map_or(0,|n|n.current_count),"max_count":n.map_or(0,|n|n.max_count),
                "health_percentage":n.map_or(0.,|n|n.ratio()*100.),
                "morale":s.filter(|s|!s.current_status.is_empty()).map_or("normal",|s|s.current_status.as_str()),"fatigue":"none"},
            "capabilities":{"properties":properties,"unit_resources":{
                "remaining_action_points":ap.map_or(0,|p|p.current_ap),"remaining_movement_points":mp.map_or(0,|p|p.current_mp)}},
            "available_skills":skills})
    }
    fn observation_can_attack(&self, uid: u64) -> bool {
        if self.config.interface["combat_system"] == true {
            self.can_attack(uid, None)
        } else {
            self.component::<CombatStats>(uid).is_some()
        }
    }
    fn combat_summary(&self, uid: u64, c: &CombatStats) -> Value {
        json!({"attack":c.base_attack,"defense":c.base_defense,"range":c.attack_range,
            "can_attack":self.observation_can_attack(uid)})
    }
    fn unit_summary(&self, uid: u64, hidden: bool) -> Value {
        let u = self.component::<UnitInfo>(uid).expect("unit query");
        let mut out = json!({"id":uid,"name":u.name,"faction":u.faction,"type":u.unit_type});
        if let Some(p) = self.component::<Position>(uid) {
            out["position"] = json!(p);
        }
        if let Some(n) = self.component::<Headcount>(uid) {
            out["unit_count"] =
                json!({"current":n.current_count,"max":n.max_count,"percentage":n.ratio()});
        }
        if hidden {
            if let Some(m) = self.component::<MovePoints>(uid) {
                out["movement"] = json!({"current":m.current_mp,"max":m.max_mp});
            }
            if let Some(c) = self.component::<CombatStats>(uid) {
                out["combat"] = self.combat_summary(uid, c);
            }
            if self.component::<Status>(uid).is_some() {
                out["status"] =
                    json!({"is_defending":false,"is_fortified":false,"is_moving":false});
            }
        }
        out
    }
    fn visible_area(&self, uid: u64) -> BTreeSet<Hex> {
        let (Some(p), Some(v)) = (
            self.component::<Position>(uid),
            self.component::<Vision>(uid),
        ) else {
            return BTreeSet::new();
        };
        if !v.visible_tiles.is_empty() {
            return v.visible_tiles.0.clone();
        }
        // Legacy pre-VisionSystem fallback: an unclipped disc, without terrain LOS.
        let mut area = BTreeSet::new();
        for col in p.col - v.range..=p.col + v.range {
            for row in p.row - v.range..=p.row + v.range {
                if hex::distance(p.hex(), (col, row)) <= v.range {
                    area.insert((col, row));
                }
            }
        }
        area
    }
    fn faction_area(&self, faction: &str) -> BTreeSet<Hex> {
        let mut out = BTreeSet::new();
        for (uid, e) in self.world.ordered() {
            if self
                .world
                .ecs
                .get::<UnitInfo>(e)
                .is_some_and(|u| u.faction == faction)
            {
                out.extend(self.visible_area(uid));
            }
        }
        out
    }
    fn terrain_info(&self, cell: Hex, terrain: Option<&str>, type_key: &str) -> Value {
        let mut out = json!({"position":{"col":cell.0,"row":cell.1},"passable":true});
        if let Some(t) = terrain {
            let effect = &self.config.rules["terrain_effects"][t];
            let cost = effect["movement_cost"].as_i64().unwrap_or(1);
            out[type_key] = json!(t);
            out["movement_cost"] = json!(cost);
            out["defense_bonus"] = effect.get("defense_bonus").cloned().unwrap_or(json!(0.));
            out["passable"] = json!(cost < 999);
        }
        out
    }
    fn territory_at(
        &self,
        cell: Hex,
        fallback: bool,
        allow_zero: bool,
    ) -> Option<&TerritoryControl> {
        if let Some(tile) = self.spatial.tiles.get(&cell) {
            return (allow_zero || tile.entity != 0)
                .then(|| self.component::<TerritoryControl>(tile.entity))
                .flatten();
        }
        if fallback {
            return self.world.ordered().find_map(|(id, _)| {
                (self
                    .component::<Position>(id)
                    .is_some_and(|p| p.hex() == cell))
                .then(|| self.component::<TerritoryControl>(id))
                .flatten()
            });
        }
        None
    }
    fn action_options(&self, uid: u64) -> Vec<&'static str> {
        let allowed = self.allowed_actions();
        let ap = self
            .component::<ActionPoints>(uid)
            .map_or(0, |p| p.current_ap);
        let p = self.component::<Position>(uid);
        let u = self.component::<UnitInfo>(uid).expect("unit query");
        ["move", "attack", "rest", "occupy", "fortify", "skill"]
            .into_iter()
            .filter(|&action| {
                if !allowed.iter().any(|n| n == action) {
                    return false;
                }
                match action {
                    "move" => self
                        .component::<MovePoints>(uid)
                        .is_some_and(|p| p.current_mp > 0),
                    "attack" => self.observation_can_attack(uid),
                    "rest" => self.component::<Status>(uid).is_some(),
                    "occupy" => {
                        ap >= 1
                            && p.is_some_and(|p| {
                                std::iter::once(p.hex()).chain(hex::neighbors(p.hex())).any(
                                    |cell| {
                                        self.territory_at(cell, true, true).is_some_and(|t| {
                                            t.controlling_faction.as_deref() != Some(&u.faction)
                                        })
                                    },
                                )
                            })
                    }
                    "fortify" => {
                        ap >= 1
                            && self
                                .component::<ConstructionPoints>(uid)
                                .is_some_and(|c| c.current_cp >= 1)
                            && p.is_some_and(|p| {
                                self.territory_at(p.hex(), true, true).is_some_and(|t| {
                                    t.controlling_faction.as_deref() == Some(&u.faction)
                                        && !t.fortified
                                })
                            })
                    }
                    "skill" => {
                        ap >= 1
                            && self.component::<SkillPoints>(uid).is_some_and(|sp| {
                                sp.current_sp >= 1
                                    && self.cold(uid, "UnitSkills").is_some_and(|s| {
                                        s["available_skills"]["$set"].as_array().is_some_and(
                                            |names| {
                                                names.iter().filter_map(Value::as_str).any(|n| {
                                                    s["skill_cooldowns"][n].as_i64().unwrap_or(0)
                                                        <= 0
                                                        && sp
                                                            .skill_cooldowns
                                                            .get(n)
                                                            .is_none_or(|&v| v <= 0)
                                                })
                                            },
                                        )
                                    })
                            })
                    }
                    _ => false,
                }
            })
            .collect()
    }
    fn unit_observation(&self, raw: &Value) -> Value {
        let integer = action_integer(raw).expect("wrapper validated integer");
        let id = u64::try_from(integer).ok();
        if id.is_none_or(|id| self.world.entity(id).is_none()) {
            return json!({"error":format!("Unit {integer} does not exist"),"error_code":"UNIT_NOT_FOUND"});
        }
        let uid = id.unwrap();
        if self.component::<UnitInfo>(uid).is_none() || self.component::<Position>(uid).is_none() {
            return json!({"error":format!("Unit {uid} missing essential components (Unit or HexPosition)"),"error_code":"COMPONENT_MISSING"});
        }
        let mut unit = self.unit_summary(uid, false);
        if let Some(n) = self.component::<Headcount>(uid) {
            unit["unit_count"]["is_alive"] = json!(n.current_count > 0);
        }
        if let Some(m) = self.component::<MovePoints>(uid) {
            unit["movement"] =
                json!({"current":m.current_mp,"max":m.max_mp,"can_move":m.current_mp>0});
        }
        if let Some(c) = self.component::<CombatStats>(uid) {
            unit["combat"] = self.combat_summary(uid, c);
        }
        let area = self.visible_area(uid);
        let visible_units: Vec<_> = self
            .world
            .ordered()
            .filter(|&(id, _)| {
                id != uid
                    && self.component::<UnitInfo>(id).is_some()
                    && self
                        .component::<Position>(id)
                        .is_some_and(|p| area.contains(&p.hex()))
            })
            .map(|(id, _)| self.unit_summary(id, false))
            .collect();
        let terrain: Vec<_> = area
            .iter()
            .map(|&cell| {
                self.terrain_info(
                    cell,
                    self.spatial
                        .tiles
                        .get(&cell)
                        .filter(|t| t.has_terrain)
                        .map(|t| t.terrain.as_str()),
                    "type",
                )
            })
            .collect();
        json!({"unit":unit,"visible_area":HexSet(area),"visible_units":visible_units,
            "visible_terrain":terrain,"action_options":self.action_options(uid)})
    }
    fn faction_observation(&self, faction: &str, hidden: bool) -> Value {
        let area = self.faction_area(faction);
        let (mut own, mut enemies) = (vec![], vec![]);
        let (mut ready, mut wounded) = (0, 0);
        for (id, e) in self.world.ordered() {
            let Some(u) = self.world.ecs.get::<UnitInfo>(e) else {
                continue;
            };
            if u.faction == faction {
                own.push(self.unit_summary(id, hidden));
                ready += usize::from(
                    self.component::<MovePoints>(id)
                        .is_some_and(|p| p.current_mp > 0),
                );
                wounded += usize::from(
                    self.component::<Headcount>(id)
                        .is_some_and(|n| n.current_count < n.max_count),
                );
            } else if self
                .component::<Position>(id)
                .is_some_and(|p| area.contains(&p.hex()))
            {
                enemies.push(self.unit_summary(id, false));
            }
        }
        let (mut controlled, mut fortified, mut contested, mut points) =
            (0, 0, BTreeSet::new(), vec![]);
        for (id, _) in self.world.ordered() {
            let (Some(t), Some(p)) = (
                self.component::<TerritoryControl>(id),
                self.component::<Position>(id),
            ) else {
                continue;
            };
            let owns = t.controlling_faction.as_deref() == Some(faction);
            if owns {
                controlled += 1;
                fortified += usize::from(t.fortified);
                if t.is_city {
                    points.push(p.hex());
                }
            }
            if t.being_captured
                && (owns
                    || t.capturing_unit
                        .and_then(|id| self.component::<UnitInfo>(id))
                        .is_some_and(|u| u.faction == faction))
            {
                contested.insert(p.hex());
            }
        }
        points.sort();
        let points: Vec<_> = points
            .iter()
            .map(|p| json!({"col":p.0,"row":p.1,"kind":"city"}))
            .collect();
        json!({"faction":faction,"strategic_info":{"total_units":own.len(),"units_ready_to_act":ready,"wounded_units":wounded},
            "own_units":own,"known_enemy_units":enemies,
            "territory_control":{"controlled_tiles":controlled,"fortified_tiles":fortified,"contested_tiles":contested.len(),"strategic_points":points},
            "resources":{"manpower":0,"supplies":0,"morale":0}})
    }
    fn limited_observation(&self, faction: &str) -> Value {
        if let Some(fog) = self.fog.as_ref().filter(|f| f.enabled) {
            let empty = BTreeSet::new();
            let explored = fog.explored_tiles.get(faction).map_or(&empty, |s| &s.0);
            let fallback;
            let visible = if let Some(v) = fog.faction_vision.get(faction) {
                &v.0
            } else {
                fallback = self.faction_area(faction);
                &fallback
            };
            json!({"faction":faction,"explored_areas":cells(explored),"current_visible_areas":cells(visible),"fog_of_war_status":"active"})
        } else {
            let all = cells(&self.spatial.tiles.keys().copied().collect());
            json!({"faction":faction,"explored_areas":all,"current_visible_areas":all,"fog_of_war_status":"disabled"})
        }
    }
    fn godview_observation(&self) -> Result<Value, String> {
        let mut all = vec![];
        let mut grouped: BTreeMap<String, Vec<Value>> = BTreeMap::new();
        let mut tiles = vec![];
        for (id, e) in self.world.ordered() {
            if let Some(u) = self.world.ecs.get::<UnitInfo>(e) {
                let info = self.unit_summary(id, true);
                grouped
                    .entry(u.faction.clone())
                    .or_default()
                    .push(info.clone());
                all.push(info);
            }
            if self.cold(id, "Tile").is_some()
                && let Some(p) = self.component::<Position>(id)
            {
                tiles.push((
                    p.hex(),
                    self.terrain_info(
                        p.hex(),
                        self.cold(id, "Terrain")
                            .and_then(|t| t["terrain_type"].as_str()),
                        "terrain_type",
                    ),
                ));
            }
        }
        tiles.sort_by_key(|v| v.0);
        let tiles: Vec<_> = tiles.into_iter().map(|v| v.1).collect();
        let stats = self.singletons.get("GameStats");
        let attr = |name, default| {
            stats
                .and_then(|s| s.get(name))
                .cloned()
                .unwrap_or(json!(default))
        };
        // The Python handler expects obsolete attribute names. Real BattleLogEntry
        // records lack `turn`; preserve that error instead of inventing history.
        let mut history = vec![];
        if let Some(entries) = self
            .singletons
            .get("BattleLog")
            .and_then(|s| s["entries"].as_array())
        {
            for e in entries.iter().skip(entries.len().saturating_sub(10)) {
                for field in ["turn", "attacker_name", "defender_name", "damage", "result"] {
                    if e.get(field).is_none() {
                        return Err(format!(
                            "'BattleLogEntry' object has no attribute '{field}'"
                        ));
                    }
                }
                history.push(json!({"turn":e["turn"],"attacker":e["attacker_name"],"defender":e["defender_name"],"damage":e["damage"],"result":e["result"]}));
            }
        }
        Ok(
            json!({"all_units":all,"units_by_faction":grouped,"map_info":{"tiles":tiles},
            "global_statistics":{"turn_number":attr("turn_number",1),"total_battles":attr("total_battles",0),"total_casualties":attr("total_casualties",0)},"battle_history":history}),
        )
    }
    fn observation_game_state(&self) -> Value {
        if let Some(s) = self.singletons.get("GameState") {
            json!({"current_player":py_display(&s["current_player"]),"game_mode":py_display(&s["game_mode"]),
                "turn_number":s.get("turn_number").cloned().unwrap_or(json!(1)),"phase":s.get("phase").cloned().unwrap_or(json!("action"))})
        } else {
            json!({"current_player":"Unknown","game_mode":"Unknown","turn_number":1,"phase":"action"})
        }
    }
    pub(crate) fn named_observation(&mut self, action: &str, params: &Value) -> Value {
        let raw_faction = &params["faction"];
        let mut faction = if truthy(raw_faction) {
            Some(py_display(raw_faction))
        } else {
            None
        };
        if let Some(s) = raw_faction.as_str().filter(|s| !s.is_empty()) {
            let normalized = s.to_lowercase();
            if !["wei", "shu", "wu"].contains(&normalized.as_str()) {
                return error(&format!("Invalid faction: {s}"));
            }
            faction = Some(normalized);
        }
        let level = action.strip_suffix("_observation").expect("named action");
        let mut uid = Value::Null;
        let mut hidden = json!(false);
        match level {
            "unit" => {
                let Some(n) = action_integer(&params["unit_id"]) else {
                    return error("unit_id must be integer");
                };
                uid = serde_json::to_value(n).expect("JSON integer input");
                faction = None;
            }
            "faction" | "limited" => {
                if faction.is_none() {
                    return error("faction parameter required");
                }
                if level == "faction" {
                    hidden = params
                        .get("include_hidden")
                        .cloned()
                        .unwrap_or(json!(false));
                }
            }
            "godview" => faction = None,
            _ => unreachable!("named action list"),
        }
        let faction_key = match &faction {
            Some(f) if raw_faction.is_string() => format!("Faction.{}", f.to_uppercase()),
            Some(f) => f.clone(),
            None => "None".into(),
        };
        let key = format!(
            "{level}_{faction_key}_{}_{}",
            py_display(&uid),
            py_display(&hidden)
        );
        if self.query_cache.revision != self.revision {
            self.query_cache.entries.clear();
            self.query_cache.revision = self.revision;
        }
        if let Some(cached) = self.query_cache.entries.get(&key) {
            let mut out = cached.clone();
            out["from_cache"] = json!(true);
            return out;
        }
        if level == "limited"
            && self.fog.as_ref().is_some_and(|f| f.enabled)
            && (raw_faction.is_array() || raw_faction.is_object())
        {
            let kind = if raw_faction.is_array() {
                "list"
            } else {
                "dict"
            };
            return json!({"success":false,"error":format!("Unexpected error in get_observation: unhashable type: '{kind}'"),
                "error_code":"INTERNAL_ERROR","operation":"get_observation",
                "params":{"observation_level":level,"faction":raw_faction,"unit_id":null,"include_hidden":false}});
        }
        let data = match level {
            "unit" => self.unit_observation(&uid),
            "faction" => self.faction_observation(faction.as_deref().unwrap(), truthy(&hidden)),
            "limited" => self.limited_observation(faction.as_deref().unwrap()),
            "godview" => match self.godview_observation() {
                Ok(data) => data,
                Err(message) => {
                    return json!({"success":false,"error":format!("Unexpected error in get_observation: {message}"),
                    "error_code":"INTERNAL_ERROR","operation":"get_observation",
                    "params":{"observation_level":level,"faction":null,"unit_id":null,"include_hidden":false}});
                }
            },
            _ => unreachable!(),
        };
        let result = if !data["error"].is_null() {
            json!({"success":false,"error":data["error"],"error_code":data["error_code"],"operation":"get_observation","observation_level":level})
        } else {
            json!({"success":true,"data":data,"metadata":{"timestamp":self.wall_time,"observation_level":level,
                "faction":faction,"unit_id":uid,"include_hidden":hidden,"game_state":self.observation_game_state()},"operation":"get_observation"})
        };
        self.query_cache.entries.insert(key, result.clone());
        result
    }
    fn movement_accessibility(&self, uid: u64, target: Hex) -> Value {
        let mp = self.component::<MovePoints>(uid);
        let remaining = mp.map_or(0, |p| p.current_mp);
        let rejected = |reason| json!({"reachable":false,"reason":reason,"movement_cost":-1,"remaining_movement_points":remaining});
        let (Some(p), Some(mp), Some(n)) = (
            self.component::<Position>(uid),
            mp,
            self.component::<Headcount>(uid),
        ) else {
            return rejected("missing_movement_components");
        };
        if p.hex() == target {
            return json!({"reachable":true,"reason":"current_position","movement_cost":0,"remaining_movement_points":remaining,"is_current_position":true});
        }
        if self.component::<Movement>(uid).is_some_and(|m| m.is_moving) {
            return rejected("already_moving");
        }
        if self
            .component::<Status>(uid)
            .is_some_and(|s| s.current_status == "confusion")
        {
            return rejected("confused");
        }
        if self.spatial.occupied(target, uid) {
            return rejected("destination_occupied");
        }
        let path = self.plan_path(uid, target, None);
        if path.len() < 2 {
            return rejected("no_path");
        }
        let cost: i64 = path
            .iter()
            .skip(1)
            .map(|p| self.spatial.tiles.get(p).map_or(999, |t| t.cost))
            .sum();
        let mut out = json!({"reachable":cost<=mp.spendable(n),"movement_cost":cost,"remaining_movement_points":remaining});
        if cost > mp.spendable(n) {
            out["reason"] = json!("insufficient_mp");
        }
        out
    }
    pub(crate) fn legacy_observation(&self, params: &Value) -> Value {
        let raw = &params["unit_id"];
        let Some(n) = action_integer(raw) else {
            return error("unit_id must be integer");
        };
        let Some(uid) = u64::try_from(n)
            .ok()
            .filter(|&id| self.component::<UnitInfo>(id).is_some())
        else {
            return error(&format!("Unit {} not found", py_display(raw)));
        };
        let mut environment = vec![];
        // Build one occupant table, including dead Units just like the legacy query.
        let mut occupants: BTreeMap<Hex, Vec<Value>> = BTreeMap::new();
        for (id, _) in self.world.ordered() {
            if let (Some(u), Some(p)) = (
                self.component::<UnitInfo>(id),
                self.component::<Position>(id),
            ) {
                occupants
                    .entry(p.hex())
                    .or_default()
                    .push(json!({"unit_id":id,"unit_type":u.unit_type,"faction":u.faction}));
            }
        }
        if let Some(v) = self.component::<Vision>(uid) {
            for &cell in v.visible_tiles.iter() {
                let control = self.territory_at(cell, false, false);
                let territory = if self.config.systems.contains_key("TerritorySystem") {
                    json!({"controlled_by":control.and_then(|t|t.controlling_faction.as_deref())})
                } else {
                    json!({"controlled_by":null,"is_friendly":false,"is_enemy":false,"is_neutral":true,"can_occupy":false,"occupation_bonus":0.})
                };
                let range = if let (Some(p), Some(c)) = (
                    self.component::<Position>(uid),
                    self.component::<CombatStats>(uid),
                ) {
                    let distance = hex::distance(p.hex(), cell);
                    let in_range = distance <= c.attack_range;
                    json!({"in_attack_range":in_range,"distance":distance,"attack_range":c.attack_range,
                        "can_attack":in_range && (self.config.interface["combat_system"]!=true || self.can_attack(uid,None))})
                } else {
                    json!({"in_attack_range":false,"distance":-1,"attack_range":0,"can_attack":false})
                };
                environment.push(json!({"position":{"col":cell.0,"row":cell.1},"terrain":self.action_terrain(cell),
                    "units":occupants.get(&cell).cloned().unwrap_or_default(),"fortifications":control.filter(|t|t.fortified).map_or(0,|t|t.fortification_level),
                    "territory_control":territory,"movement_accessibility":self.movement_accessibility(uid,cell),"attack_range_info":range}));
            }
        }
        let mut result = json!({"success":true,"result":true,"unit_info":self.detailed_unit_info(uid),"visible_environment":environment});
        if params["observation_level"]
            .as_str()
            .is_some_and(|s| ["detailed", "tactical"].contains(&s))
        {
            result["tactical_info"] =
                json!({"threats":[],"opportunities":[],"movement_options":[]});
        }
        result
    }
}

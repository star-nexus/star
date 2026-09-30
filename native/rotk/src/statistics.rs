//! Game statistics and bounded window sampling; timestamps are injected metadata.
use crate::{
    codec::{TaggedSet, id_map},
    components::{Headcount, MovePoints, Position, UnitInfo},
    hex::Hex,
    runtime::{InitialComponents, Runtime},
};
use bevy_ecs::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

/// Per-call diagnostics only; never serialized into authoritative scene state.
#[derive(Default, Serialize)]
pub struct StatisticsTimings {
    pub observation_rows: usize,
    pub gather_ns: u64,
    pub compute_ns: u64,
    pub records_ns: u64,
    pub commit_ns: u64,
    pub trim_ns: u64,
    pub visibility_ns: u64,
    pub factions_ns: u64,
    pub kernel_wall_ns: u64,
    pub worker_max_ns: u64,
    pub dispatch_residual_ns: u64,
    pub parallel_batches: usize,
    pub jobs: usize,
    pub worker_threads: usize,
}
// E2 alternating complete-step controls: 1..32 rows lose, 64 rows have little
// headroom; 128+ rows win on M4 at 2/4 workers. Keep canonical 128-row batches
// and larger legacy batches eligible; tiny/tail batches stay inline. Threads=1
// still has no pool. See docs/native-statistics-parallel.md and Lab E2 evidence.
pub(crate) const STATISTICS_PARALLEL_MIN_ROWS: usize = 128;
fn start<const PROFILE: bool>() -> Option<std::time::Instant> {
    PROFILE.then(std::time::Instant::now)
}
fn elapsed(start: Option<std::time::Instant>) -> u64 {
    start.map_or(0, |s| s.elapsed().as_nanos() as u64)
}

// Borrow only this batch's typed facts; no world export, prior-history copy or
// mutable ECS access enters a compute kernel. Inputs stop at the first bad row.
struct ObservationInput<'a> {
    id: u64,
    entity: Entity,
    faction: &'a str,
    unit_type: &'a str,
    position: Hex,
    count: i64,
    max_count: i64,
    movement: Option<&'a MovePoints>,
    terrain: &'a str,
    previous_remaining: i64,
}
struct ObservationRow {
    entity: Entity,
    position: Hex,
    health: f64,
    movement: Option<MovePoints>,
    terrain: String,
    record: Value,
}
fn observation_rows<const PROFILE: bool>(
    input: &[ObservationInput<'_>],
    timestamp: &Value,
) -> (Vec<Result<ObservationRow, String>>, u64, u64) {
    let mark = start::<PROFILE>();
    let health: Vec<Result<f64, String>> = input
        .iter()
        .map(|row| {
            if row.max_count == 0 {
                Err("statistics health division by zero".into())
            } else {
                Ok((row.count as f64 / row.max_count as f64) * 100.)
            }
        })
        .collect();
    let compute_ns = elapsed(mark);
    let mark = start::<PROFILE>();
    let rows = input
        .iter()
        .zip(health)
        .map(|(row, health)| {
            let health = health?;
            let remaining = row
                .movement
                .map_or(row.previous_remaining, |m| m.current_mp);
            Ok(ObservationRow {
                entity: row.entity,
                position: row.position,
                health,
                movement: row.movement.cloned(),
                terrain: row.terrain.to_string(),
                record: json!({"entity":row.id,"faction":row.faction,"unit_type":row.unit_type,
                "position":row.position,"health_percentage":health,"movement_remaining":remaining,
                "terrain_type":row.terrain,"timestamp":timestamp}),
            })
        })
        .collect();
    (rows, compute_ns, elapsed(mark))
}

#[derive(Component, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnitObservation {
    pub current_position: Hex,
    pub previous_position: Hex,
    pub health_percentage: f64,
    pub movement_remaining: i64,
    pub has_acted_this_turn: bool,
    pub is_visible_to: TaggedSet<String>,
    pub last_seen_time: f64,
    pub current_terrain_type: String,
    pub terrain_bonus_active: bool,
    pub movement_path: Vec<Hex>,
    pub total_distance_moved: i64,
}
impl UnitObservation {
    fn new(wall: f64) -> Self {
        Self {
            current_position: (0, 0),
            previous_position: (0, 0),
            health_percentage: 100.,
            movement_remaining: 0,
            has_acted_this_turn: false,
            is_visible_to: TaggedSet::default(),
            last_seen_time: wall,
            current_terrain_type: "plains".into(),
            terrain_bonus_active: false,
            movement_path: vec![],
            total_distance_moved: 0,
        }
    }
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VisibilityTracker {
    pub faction_visible_units: BTreeMap<String, TaggedSet<u64>>,
    #[serde(with = "id_map")]
    pub visibility_history: BTreeMap<u64, Vec<Value>>,
    pub reconnaissance_stats: BTreeMap<String, BTreeMap<String, i64>>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cycle {
    phase: String,
    index: usize,
    observation_entities: Vec<u64>,
    visibility_entities: Vec<u64>,
    faction_counts: BTreeMap<String, i64>,
    visibility_cleared: bool,
    fog_disabled_visible_to: Option<TaggedSet<String>>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StatisticsSystem {
    pub enabled: bool,
    pub window: bool,
    pub indexed: bool,
    pub last_update_time: f64,
    pub observation_interval: f64,
    pub batch_size: usize,
    pub history_limit: usize,
    pub visibility_limit: usize,
    pub cycle: Option<Cycle>,
}
fn bump(value: &mut Value, key: &str, amount: i64) {
    value[key] = json!(value[key].as_i64().unwrap_or(0) + amount);
}
fn faction_stats<'a>(stats: &'a mut Value, faction: &str) -> &'a mut Value {
    stats["faction_stats"].as_object_mut().expect("faction stats").entry(faction.to_string()).or_insert_with(||json!({
        "kills":0,"losses":0,"damage_dealt":0,"damage_taken":0,"units_created":0,"turns_played":0,
        "territory_controlled":0,"actions_taken":0,"movement_distance":0,"battles_won":0,"battles_lost":0}))
}

impl StatisticsSystem {
    fn ids(r: &Runtime, need_count: bool) -> Vec<u64> {
        r.world
            .ordered()
            .filter_map(|(id, e)| {
                (r.world.ecs.get::<UnitInfo>(e).is_some()
                    && r.world.ecs.get::<Position>(e).is_some()
                    && (!need_count || r.world.ecs.get::<Headcount>(e).is_some()))
                .then_some(id)
            })
            .collect()
    }
    fn observations<const PROFILE: bool>(
        &self,
        r: &mut Runtime,
        ids: &[u64],
        timings: &mut StatisticsTimings,
        min_rows: usize,
    ) -> Result<(), String> {
        if !r.singletons.contains_key("GameStats") {
            return Ok(());
        }
        let mark = start::<PROFILE>();
        let mut input = Vec::with_capacity(ids.len());
        for &id in ids {
            let Some((e, u, c, p)) = r.world.entity(id).and_then(|e| {
                Some((
                    e,
                    r.world.ecs.get::<UnitInfo>(e)?,
                    r.world.ecs.get::<Headcount>(e)?,
                    r.world.ecs.get::<Position>(e)?.hex(),
                ))
            }) else {
                continue;
            };
            let terrain = r
                .spatial
                .tiles
                .get(&p)
                .filter(|t| t.has_terrain)
                .map_or("plains", |t| t.terrain.as_str());
            input.push(ObservationInput {
                id,
                entity: e,
                faction: &u.faction,
                unit_type: &u.unit_type,
                position: p,
                count: c.current_count,
                max_count: c.max_count,
                movement: r.world.ecs.get::<MovePoints>(e),
                terrain,
                previous_remaining: r
                    .world
                    .ecs
                    .get::<UnitObservation>(e)
                    .map_or(0, |o| o.movement_remaining),
            });
            if c.max_count == 0 {
                break;
            }
        }
        if PROFILE {
            timings.gather_ns += elapsed(mark);
            timings.observation_rows += input.len();
        }
        let mark = start::<PROFILE>();
        let timestamp = &r.singletons["GameStats"]["total_game_time"];
        let mut worker_max = 0;
        let rows = if !input.is_empty()
            && input.len() >= min_rows
            && let Some(pool) = &r.observation_pool
        {
            let jobs = pool.map_chunks(&input, |chunk| {
                observation_rows::<PROFILE>(chunk, timestamp)
            });
            let mut rows = Vec::with_capacity(input.len());
            if PROFILE {
                timings.parallel_batches += 1;
                timings.jobs += jobs.len();
                timings.worker_threads += jobs
                    .iter()
                    .map(|(_, worker)| *worker)
                    .collect::<std::collections::HashSet<_>>()
                    .len();
            }
            for ((mut chunk, compute, records), _) in jobs {
                if PROFILE {
                    timings.compute_ns += compute;
                    timings.records_ns += records;
                    worker_max = worker_max.max(compute + records);
                }
                rows.append(&mut chunk);
            }
            rows
        } else {
            let (rows, compute, records) = observation_rows::<PROFILE>(&input, timestamp);
            if PROFILE {
                timings.compute_ns += compute;
                timings.records_ns += records;
            }
            rows
        };
        if PROFILE {
            let wall = elapsed(mark);
            timings.kernel_wall_ns += wall;
            timings.worker_max_ns += worker_max;
            if worker_max > 0 {
                timings.dispatch_residual_ns += wall.saturating_sub(worker_max);
            }
        }
        let mark = start::<PROFILE>();
        let trim_before = timings.trim_ns;
        // Insertion and every patch/history append retain original row order,
        // including duplicate IDs in an imported cycle and the first-error prefix.
        for row in rows {
            let row = row?;
            let e = row.entity;
            if r.world.ecs.get::<UnitObservation>(e).is_none() {
                r.world
                    .ecs
                    .entity_mut(e)
                    .insert(UnitObservation::new(r.wall_time));
            }
            let mut observation = r.world.ecs.get_mut::<UnitObservation>(e).unwrap();
            observation.previous_position = observation.current_position;
            observation.current_position = row.position;
            observation.health_percentage = row.health;
            if let Some(m) = row.movement {
                observation.movement_remaining = m.current_mp;
                observation.has_acted_this_turn = m.has_moved;
                if observation.previous_position != observation.current_position {
                    observation.total_distance_moved += 1;
                    observation.movement_path.push(row.position);
                    let len = observation.movement_path.len();
                    if len > 50 {
                        observation.movement_path.drain(..len - 50);
                    }
                }
            }
            observation.current_terrain_type = row.terrain;
            let stats = r.singletons.get_mut("GameStats").unwrap();
            let history = stats["unit_observation_history"]
                .as_array_mut()
                .expect("observation history");
            history.push(row.record);
            if !self.window && history.len() > 10000 {
                let trim = start::<PROFILE>();
                history.drain(..history.len() - 5000);
                if PROFILE {
                    timings.trim_ns += elapsed(trim);
                }
            }
        }
        if PROFILE {
            timings.commit_ns += elapsed(mark).saturating_sub(timings.trim_ns - trim_before);
        }
        if self.window {
            let mark = start::<PROFILE>();
            let history = r.singletons.get_mut("GameStats").unwrap()["unit_observation_history"]
                .as_array_mut()
                .unwrap();
            if history.len() > self.history_limit {
                history.drain(..history.len() - self.history_limit);
            }
            if PROFILE {
                timings.trim_ns += elapsed(mark);
            }
        }
        Ok(())
    }
    fn visibility(&self, r: &mut Runtime, ids: &[u64], all: Option<&BTreeSet<String>>) {
        let Some(tracker) = &mut r.visibility_tracker else {
            return;
        };
        let Some(fog) = &r.fog else { return };
        for &id in ids {
            let Some((e, u, p)) = r.world.entity(id).and_then(|e| {
                Some((
                    e,
                    r.world.ecs.get::<UnitInfo>(e)?,
                    r.world.ecs.get::<Position>(e)?.hex(),
                ))
            }) else {
                continue;
            };
            let mut visible = if let Some(all) = all {
                all.clone()
            } else {
                fog.faction_vision
                    .iter()
                    .filter_map(|(f, cells)| {
                        (f != &u.faction && cells.contains(&p)).then_some(f.clone())
                    })
                    .collect()
            };
            visible.insert(u.faction.clone());
            for faction in &visible {
                tracker
                    .faction_visible_units
                    .entry(faction.clone())
                    .or_default()
                    .insert(id);
            }
            let mut observation = r.world.ecs.get_mut::<UnitObservation>(e);
            let previous = observation
                .as_ref()
                .map(|o| o.is_visible_to.0.clone())
                .unwrap_or_default();
            if let Some(o) = observation.as_mut() {
                o.last_seen_time = r.wall_time;
            }
            if self.window && previous == visible {
                continue;
            }
            let history = tracker.visibility_history.entry(id).or_default();
            let baseline = history.is_empty() && previous.is_empty();
            let newly = self.window && !baseline && visible.iter().any(|f| !previous.contains(f));
            let lost = self.window && !baseline && previous.iter().any(|f| !visible.contains(f));
            history.push(json!({"timestamp":r.wall_time,"visible_to":visible,"newly_spotted":newly,"lost_sight":lost}));
            if history.len() > self.visibility_limit {
                history.drain(..history.len() - self.visibility_limit);
            }
            if let Some(o) = observation.as_mut() {
                o.is_visible_to = TaggedSet(visible);
            }
        }
    }
    fn factions(
        &self,
        r: &mut Runtime,
        ids: &[u64],
        counts: &mut BTreeMap<String, i64>,
        finish: bool,
    ) {
        let Some(stats) = r.singletons.get_mut("GameStats") else {
            return;
        };
        for &id in ids {
            let Some((u, c)) = r.world.entity(id).and_then(|e| {
                Some((
                    r.world.ecs.get::<UnitInfo>(e)?,
                    r.world.ecs.get::<Headcount>(e)?,
                ))
            }) else {
                continue;
            };
            if c.current_count <= 0 {
                continue;
            }
            faction_stats(stats, &u.faction);
            *counts.entry(u.faction.clone()).or_default() += 1;
        }
        if finish {
            for (f, count) in counts {
                stats["faction_stats"][f.as_str()]["territory_controlled"] = json!(*count);
            }
        }
    }
    pub fn update(&mut self, r: &mut Runtime, dt: f64) -> Result<(), String> {
        self.update_profile::<false>(
            r,
            dt,
            &mut StatisticsTimings::default(),
            STATISTICS_PARALLEL_MIN_ROWS,
        )
    }
    fn update_profile<const PROFILE: bool>(
        &mut self,
        r: &mut Runtime,
        dt: f64,
        timings: &mut StatisticsTimings,
        min_rows: usize,
    ) -> Result<(), String> {
        if let Some(stats) = r.singletons.get_mut("GameStats") {
            stats["total_game_time"] = if r.clock.realtime {
                json!(r.clock.elapsed)
            } else {
                json!(stats["total_game_time"].as_f64().unwrap_or(0.) + dt)
            };
        }
        if let Some(mode) = r.singletons.get_mut("GameModeStatistics") {
            if r.clock.realtime {
                mode["realtime_stats"]["total_game_time"] = json!(r.clock.elapsed);
            } else if mode["current_mode"] == "realtime" {
                let elapsed = mode["realtime_stats"]["total_game_time"]
                    .as_f64()
                    .unwrap_or(0.);
                mode["realtime_stats"]["total_game_time"] = json!(elapsed + dt);
            }
        }
        let due = r.wall_time - self.last_update_time >= self.observation_interval;
        if !self.window {
            if due {
                let observations = Self::ids(r, true);
                let visibility = Self::ids(r, false);
                self.observations::<PROFILE>(r, &observations, timings, min_rows)?;
                if r.fog.is_some()
                    && let Some(tracker) = &mut r.visibility_tracker
                {
                    for units in tracker.faction_visible_units.values_mut() {
                        units.clear();
                    }
                }
                let mark = start::<PROFILE>();
                self.visibility(r, &visibility, None);
                if PROFILE {
                    timings.visibility_ns += elapsed(mark);
                }
                let mark = start::<PROFILE>();
                self.factions(r, &observations, &mut BTreeMap::new(), true);
                if PROFILE {
                    timings.factions_ns += elapsed(mark);
                }
                self.last_update_time = r.wall_time;
            }
            return Ok(());
        }
        if self.cycle.is_none() && due {
            self.cycle = Some(Cycle {
                phase: "observations".into(),
                index: 0,
                observation_entities: Self::ids(r, true),
                visibility_entities: Self::ids(r, false),
                faction_counts: BTreeMap::new(),
                visibility_cleared: false,
                fog_disabled_visible_to: None,
            });
            self.last_update_time = r.wall_time;
        }
        let Some(mut cycle) = self.cycle.take() else {
            return Ok(());
        };
        let ids = if cycle.phase == "visibility" {
            &cycle.visibility_entities
        } else {
            &cycle.observation_entities
        };
        let end = (cycle.index + self.batch_size).min(ids.len());
        let batch = &ids[cycle.index..end];
        let mut complete = false;
        match cycle.phase.as_str() {
            "observations" => {
                self.observations::<PROFILE>(r, batch, timings, min_rows)?;
                cycle.index = end;
                if end >= ids.len() {
                    cycle.phase = "visibility".into();
                    cycle.index = 0;
                }
            }
            "visibility" => {
                if r.visibility_tracker.is_none() || r.fog.is_none() {
                    cycle.phase = "factions".into();
                    cycle.index = 0;
                } else {
                    if !cycle.visibility_cleared {
                        for units in r
                            .visibility_tracker
                            .as_mut()
                            .unwrap()
                            .faction_visible_units
                            .values_mut()
                        {
                            units.clear();
                        }
                        cycle.visibility_cleared = true;
                    }
                    let disabled = !r.fog.as_ref().unwrap().enabled;
                    if disabled && cycle.fog_disabled_visible_to.is_none() {
                        let mut factions: BTreeSet<_> = r
                            .fog
                            .as_ref()
                            .unwrap()
                            .faction_vision
                            .keys()
                            .cloned()
                            .collect();
                        if self.indexed {
                            for (_, e) in r.world.ordered() {
                                if r.world
                                    .ecs
                                    .get::<Headcount>(e)
                                    .is_some_and(|c| c.current_count > 0)
                                    && let Some(u) = r.world.ecs.get::<UnitInfo>(e)
                                {
                                    factions.insert(u.faction.clone());
                                }
                            }
                        }
                        cycle.fog_disabled_visible_to = Some(TaggedSet(factions));
                    }
                    let mark = start::<PROFILE>();
                    self.visibility(
                        r,
                        batch,
                        if disabled {
                            cycle.fog_disabled_visible_to.as_ref().map(|s| &s.0)
                        } else {
                            None
                        },
                    );
                    if PROFILE {
                        timings.visibility_ns += elapsed(mark);
                    }
                    cycle.index = end;
                    if end >= ids.len() {
                        cycle.phase = "factions".into();
                        cycle.index = 0;
                    }
                }
            }
            "factions" => {
                let mark = start::<PROFILE>();
                self.factions(r, batch, &mut cycle.faction_counts, end >= ids.len());
                if PROFILE {
                    timings.factions_ns += elapsed(mark);
                }
                cycle.index = end;
                complete = end >= ids.len();
            }
            _ => complete = true,
        }
        if !complete {
            self.cycle = Some(cycle);
        }
        Ok(())
    }
}

impl Runtime {
    pub fn advance_statistics(&mut self, dt: f64) -> Result<(), String> {
        self.advance_statistics_profile::<false>(
            dt,
            &mut StatisticsTimings::default(),
            STATISTICS_PARALLEL_MIN_ROWS,
        )
    }
    pub(crate) fn advance_statistics_profile<const PROFILE: bool>(
        &mut self,
        dt: f64,
        timings: &mut StatisticsTimings,
        min_rows: usize,
    ) -> Result<(), String> {
        if let Some(mut system) = self.statistics.take() {
            let result = if system.enabled {
                system.update_profile::<PROFILE>(self, dt, timings, min_rows)
            } else {
                Ok(())
            };
            self.statistics = Some(system);
            result
        } else {
            Ok(())
        }
    }
}
impl Runtime {
    fn unit_stats(&mut self, id: u64) -> &mut Value {
        let entity = self.world.entity(id).expect("statistics unit");
        let cold = self
            .world
            .ecs
            .get_mut::<InitialComponents>(entity)
            .expect("unit columns");
        cold.into_inner().0.entry("UnitStatistics".into()).or_insert_with(||json!({
            "kills":0,"deaths":0,"damage_dealt":0,"damage_taken":0,"moves_made":0,"attacks_made":0,
            "turns_survived":0,"battles_participated":0,"battles_won":0,"battles_lost":0,
            "terrain_types_visited":{"$set":[]},"terrain_bonuses_used":0,"total_active_time":0.0,"creation_time":self.wall_time}))
    }
    fn time_display(&self) -> (String, Value) {
        if self.clock.realtime {
            let seconds = self.clock.elapsed as i64;
            (
                if seconds < 3600 {
                    format!("{:02}:{:02}", seconds / 60, seconds % 60)
                } else {
                    format!("{}h{:02}m", seconds / 3600, seconds % 3600 / 60)
                },
                Value::Null,
            )
        } else {
            let turn = self.singletons["GameTime"]["current_turn"].clone();
            (format!("T{}", turn.as_i64().unwrap_or(1)), turn)
        }
    }
    fn battle_log(
        &mut self,
        message: String,
        kind: &str,
        faction: &str,
        color: [u8; 3],
        time: Option<(String, Value)>,
    ) {
        let (display, turn) = time.unwrap_or_else(|| self.time_display());
        let Some(log) = self.singletons.get_mut("BattleLog") else {
            return;
        };
        let cap = log["max_entries"].as_u64().unwrap_or(100) as usize;
        let visible = log["visible_lines"].as_u64().unwrap_or(8) as usize;
        let entries = log["entries"].as_array_mut().expect("battle log");
        let entry = json!({"message":message,"log_type":kind,"faction":faction,"color":color,"game_time_display":display,"turn_number":turn});
        if !self.presentation_log_full {
            self.presentation_log_entries.push(entry.clone());
        }
        entries.push(entry);
        // Python's [-0:] retains the whole array, including a zero configured cap.
        if cap > 0 && entries.len() > cap {
            entries.drain(..entries.len() - cap);
        }
        let scroll = entries.len().saturating_sub(visible);
        log["scroll_offset"] = json!(scroll);
    }
    pub(crate) fn record_turn_change_native(&mut self, previous: Option<&str>, next: &str) {
        if self.statistics.is_none() {
            return;
        }
        let Some(state) = self.singletons.get("GameState") else {
            return;
        };
        let turn = state["turn_number"].clone();
        let mode = state["game_mode"].clone();
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            let timestamp = stats["total_game_time"].clone();
            stats["turn_history"].as_array_mut().expect("turn history").push(json!({
                "turn_number":turn,"previous_faction":previous,"new_faction":next,"game_mode":mode,"timestamp":timestamp}));
        }
        if let Some(mode) = self.singletons.get_mut("GameModeStatistics")
            && mode["current_mode"] == "turn_based"
        {
            let started = mode["current_turn_start_time"].as_f64().unwrap_or(0.);
            let actions = mode["actions_this_turn"].clone();
            let stats = &mut mode["turn_based_stats"];
            if let Some(previous) = previous.filter(|_| started > 0.) {
                let duration = self.wall_time - started;
                bump(stats, "total_turns", 1);
                stats["turn_durations"]
                    .as_array_mut()
                    .unwrap()
                    .push(json!(duration));
                let times = stats["faction_turn_times"]
                    .as_object_mut()
                    .unwrap()
                    .entry(previous)
                    .or_insert(json!([]));
                times.as_array_mut().unwrap().push(json!(duration));
                let values = stats["turn_durations"].as_array().unwrap();
                let mut sum = 0_f64;
                let mut correction = 0_f64;
                let mut longest = f64::NEG_INFINITY;
                let mut shortest = f64::INFINITY;
                for value in values {
                    let x = value.as_f64().expect("finite turn duration");
                    let t = sum + x;
                    correction += if sum.abs() >= x.abs() {
                        (sum - t) + x
                    } else {
                        (x - t) + sum
                    };
                    sum = t;
                    longest = longest.max(x);
                    shortest = shortest.min(x);
                }
                // CPython 3.13 float sum uses Neumaier compensation and only
                // applies a finite nonzero residual (Python/bltinmodule.c).
                if correction != 0. && correction.is_finite() {
                    sum += correction;
                }
                let average = sum / values.len() as f64;
                stats["average_turn_duration"] = json!(average);
                stats["longest_turn"] = json!(longest);
                stats["shortest_turn"] = json!(shortest);
                let number = stats["total_turns"].clone();
                let counts = &mut stats["actions_per_turn"];
                if counts.get("$map").is_none() {
                    *counts = json!({"$map":[]});
                }
                let pairs = counts["$map"].as_array_mut().unwrap();
                if let Some(pair) = pairs.iter_mut().find(|pair| pair[0] == number) {
                    pair[1] = actions;
                } else {
                    pairs.push(json!([number, actions]));
                }
                pairs.sort_by_cached_key(|pair| pair[0].to_string());
            }
            stats["faction_turn_times"]
                .as_object_mut()
                .unwrap()
                .entry(next)
                .or_insert(json!([]));
            mode["current_turn_start_time"] = json!(self.wall_time);
            mode["actions_this_turn"] = json!(0);
        }
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            faction_stats(stats, next);
        }
        let message = previous.map_or_else(
            || format!("{next} turn started"),
            |p| format!("{p} turn ended, {next} turn started"),
        );
        self.battle_log(message, "turn", next, [255, 255, 100], None);
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            bump(faction_stats(stats, next), "turns_played", 1);
        }
    }
    fn record_mode_action(&mut self, faction: &str, kind: &str) {
        let Some(mode) = self.singletons.get_mut("GameModeStatistics") else {
            return;
        };
        if mode["current_mode"] == "turn_based" {
            bump(mode, "actions_this_turn", 1);
        } else {
            if self.wall_time - mode["last_action_time"].as_f64().unwrap_or(0.) > 60. {
                mode["actions_this_minute"] = json!(0);
            }
            bump(mode, "actions_this_minute", 1);
            bump(&mut mode["realtime_stats"]["faction_activity"], faction, 1);
            mode["realtime_stats"]["action_frequency"]
                .as_array_mut()
                .expect("action frequency")
                .push(json!({"timestamp":self.wall_time,"faction":faction,"action_type":kind}));
        }
        mode["last_action_time"] = json!(self.wall_time);
    }
    pub fn record_movement(&mut self, id: u64, from: Hex, to: Hex) {
        if self.statistics.is_none() {
            return;
        }
        let Some(u) = self.component::<UnitInfo>(id).cloned() else {
            return;
        };
        bump(self.unit_stats(id), "moves_made", 1);
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            let f = faction_stats(stats, &u.faction);
            bump(f, "actions_taken", 1);
            bump(f, "movement_distance", 1);
        }
        self.record_mode_action(&u.faction, "movement");
        self.battle_log(
            format!(
                "{}'s {} moved ({},{})->({},{})",
                u.faction, u.unit_type, from.0, from.1, to.0, to.1
            ),
            "movement",
            &u.faction,
            [100, 200, 255],
            None,
        );
    }
    pub fn record_combat(&mut self, a: u64, t: u64, damage: i64, killed: bool) {
        if self.statistics.is_none() {
            self.record_fallback_combat(a, t, damage);
            return;
        }
        let au = self.component::<UnitInfo>(a).unwrap().clone();
        let tu = self.component::<UnitInfo>(t).unwrap().clone();
        for (id, keys) in [
            (a, ["attacks_made", "battles_participated"]),
            (t, ["battles_participated", ""]),
        ] {
            let stats = self.unit_stats(id);
            for key in keys {
                if !key.is_empty() {
                    bump(stats, key, 1);
                }
            }
            bump(
                stats,
                if id == a {
                    "damage_dealt"
                } else {
                    "damage_taken"
                },
                damage,
            );
        }
        if killed {
            let stats = self.unit_stats(a);
            bump(stats, "kills", 1);
            bump(stats, "battles_won", 1);
            let stats = self.unit_stats(t);
            bump(stats, "deaths", 1);
            bump(stats, "battles_lost", 1);
        }
        let result = if killed { "kill" } else { "damage" };
        if let Some(stats) = self.singletons.get_mut("GameStats") {
            let f = faction_stats(stats, &au.faction);
            bump(f, "damage_dealt", damage);
            if killed {
                bump(f, "kills", 1);
            }
            let f = faction_stats(stats, &tu.faction);
            bump(f, "damage_taken", damage);
            if killed {
                bump(f, "losses", 1);
            }
            let timestamp = stats["total_game_time"].clone();
            stats["battle_history"].as_array_mut().expect("battle history").push(json!({"attacker_faction":au.faction,
                "target_faction":tu.faction,"damage":damage,"result":result,"attacker_entity":a,"target_entity":t,"timestamp":timestamp}));
        }
        let message = if killed {
            format!("{} defeated {}'s {}", au.faction, tu.faction, tu.unit_type)
        } else {
            format!("{} dealt {damage} damage to {}", au.faction, tu.faction)
        };
        self.battle_log(
            message,
            "combat",
            &au.faction,
            if killed {
                [255, 100, 100]
            } else {
                [255, 200, 100]
            },
            None,
        );
        self.record_mode_action(&au.faction, "combat");
    }
    pub fn record_death(&mut self, id: u64, killer: u64) {
        if self.statistics.is_none() {
            return;
        }
        let u = self.component::<UnitInfo>(id).unwrap().clone();
        let killer = self.component::<UnitInfo>(killer).filter(|_| killer != 0);
        let message = if let Some(k) = killer {
            format!(
                "{}'s {} was defeated by {}",
                u.faction, u.unit_type, k.faction
            )
        } else {
            format!("{}'s {} died in battle", u.faction, u.unit_type)
        };
        let state = self.singletons.get("GameState");
        let time = if state.is_some_and(|s| s["game_mode"] == "turn_based") {
            let turn = state.unwrap()["turn_number"].clone();
            (format!("Turn {}", turn.as_i64().unwrap_or(1)), turn)
        } else {
            let elapsed = self
                .singletons
                .get("GameStats")
                .and_then(|s| s["total_game_time"].as_f64())
                .unwrap_or(0.) as i64;
            (
                format!("{:02}:{:02}", elapsed / 60, elapsed % 60),
                Value::Null,
            )
        };
        self.battle_log(message, "death", &u.faction, [255, 0, 0], Some(time));
    }
}

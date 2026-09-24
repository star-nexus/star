use crate::{
    RULES_VERSION,
    components::{self, Headcount, Movement, Position, UnitInfo},
    recovery::Recovery,
    spatial::Spatial,
};
use bevy_ecs::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use star_core::{
    clock::SimClock,
    rng::{DomainRng, RandomState},
    world::OrderedWorld,
};
use std::collections::{BTreeMap, BTreeSet};

/// Cold scene columns retain all initial game data while typed rule components
/// are ported. This format is never polled across Python per unit during a tick.
#[derive(Component, Clone)]
pub struct InitialComponents(pub BTreeMap<String, Value>);

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EntitySpec {
    pub id: u64,
    pub components: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SceneSpec {
    pub schema: u32,
    pub oracle: String,
    pub display: String,
    pub mode: String,
    pub seed: String,
    pub seed_source: String,
    pub entity_counter: u64,
    pub entities: Vec<EntitySpec>,
    pub singletons: BTreeMap<String, Value>,
    pub clock: SimClock,
    pub rng: BTreeMap<String, RandomState>,
    pub rules: Value,
    #[serde(default)]
    pub interface: Value,
    #[serde(default)]
    pub systems: BTreeMap<String, Value>,
}

pub struct Runtime {
    pub world: OrderedWorld,
    pub clock: SimClock,
    pub rng: DomainRng,
    pub singletons: BTreeMap<String, Value>,
    pub(crate) config: SceneSpec,
    pub spatial: Spatial,
    pub(crate) living: crate::lifecycle::LivingFactions,
    pub(crate) players: Vec<(u64, String)>,
    pub(crate) unit_entities: BTreeMap<u64, Entity>,
    pub(crate) moving: BTreeSet<u64>,
    pub(crate) capturing: BTreeSet<u64>,
    pub(crate) vision_dirty: BTreeSet<u64>,
    pub recovery: Option<Recovery>,
    pub(crate) vision: Option<crate::vision::VisionSystem>,
    pub(crate) fog: Option<crate::vision::Fog>,
    pub(crate) statistics: Option<crate::statistics::StatisticsSystem>,
    pub(crate) visibility_tracker: Option<crate::statistics::VisibilityTracker>,
    pub(crate) wall_time: f64,
    pub(crate) team: Option<crate::team::Team>,
    pub(crate) visuals: crate::presentation::Visuals,
    pub(crate) query_cache: crate::named_observation::QueryCache,
    pub epoch: u64,
    pub revision: u64,
    pub threads: usize,
    pub(crate) observation_pool: Option<std::sync::Arc<star_core::read_pool::ReadPool>>,
    pub(crate) presentation_dirty: BTreeSet<u64>,
    pub(crate) presentation_tiles: BTreeSet<u64>,
    pub(crate) presentation_fog: BTreeMap<String, BTreeSet<crate::hex::Hex>>,
    pub(crate) presentation_fog_full: bool,
    pub(crate) presentation_removed: Vec<u64>,
    pub(crate) presentation_log_full: bool,
    pub(crate) presentation_log_entries: Vec<Value>,
    pub(crate) presentation_players_full: bool,
    pub(crate) presentation_player_removals: BTreeMap<u64, BTreeSet<u64>>,
    pub(crate) events: Vec<Value>,
}

impl Runtime {
    pub fn from_json(payload: &str, threads: usize, epoch: u64) -> Result<Self, String> {
        Self::from_json_with_pool(payload, threads, epoch, None)
    }
    pub fn reset(&mut self, payload: &str) -> Result<(), String> {
        let epoch = self.epoch.checked_add(1).ok_or("lifecycle exhausted")?;
        let replacement =
            Self::from_json_with_pool(payload, self.threads, epoch, self.observation_pool.clone())?;
        *self = replacement;
        Ok(())
    }
    fn from_json_with_pool(
        payload: &str,
        threads: usize,
        epoch: u64,
        pool: Option<std::sync::Arc<star_core::read_pool::ReadPool>>,
    ) -> Result<Self, String> {
        let mut config: SceneSpec = serde_json::from_str(payload).map_err(|e| e.to_string())?;
        if config.schema != crate::SCHEMA_VERSION || config.oracle != RULES_VERSION {
            return Err("unsupported scene schema or oracle".into());
        }
        if ![1, 2, 4].contains(&threads) {
            return Err("threads must be 1, 2 or 4".into());
        }
        if !["none", "dummy", "window"].contains(&config.display.as_str()) {
            return Err("invalid display configuration".into());
        }
        if !["real_time", "turn_based"].contains(&config.mode.as_str())
            || config.clock.realtime != (config.mode == "real_time")
        {
            return Err("inconsistent game mode".into());
        }
        if !config.clock.elapsed.is_finite()
            || config.clock.elapsed < 0.
            || !config.clock.time_scale.is_finite()
            || config.clock.time_scale <= 0.
        {
            return Err("invalid simulation clock".into());
        }
        let game_time = config
            .singletons
            .get("GameTime")
            .ok_or("missing GameTime")?;
        if game_time["game_elapsed_time"].as_f64() != Some(config.clock.elapsed)
            || game_time["time_scale"].as_f64() != Some(config.clock.time_scale)
            || game_time["paused"].as_bool() != Some(config.clock.paused)
            || game_time["current_mode"].as_str() != Some(config.mode.as_str())
        {
            return Err("inconsistent initial GameTime".into());
        }
        let rng = DomainRng::new(&config.seed, std::mem::take(&mut config.rng))?;
        config.seed = star_core::rng::canonical_seed(&config.seed)?;
        let mut world = OrderedWorld::new(config.entity_counter);
        let mut presentation_dirty = BTreeSet::new();
        let mut presentation_tiles = BTreeSet::new();
        let mut unit_entities = BTreeMap::new();
        for mut spec in std::mem::take(&mut config.entities) {
            let entity = world.import(spec.id)?;
            if spec.components.contains_key("Unit") {
                presentation_dirty.insert(spec.id);
                unit_entities.insert(spec.id, entity);
            }
            if spec.components.contains_key("TerritoryControl") {
                presentation_tiles.insert(spec.id);
            }
            components::import(&mut world.ecs, entity, &mut spec.components)?;
            world
                .ecs
                .entity_mut(entity)
                .insert(InitialComponents(spec.components));
        }
        let mut singletons = std::mem::take(&mut config.singletons);
        let team = singletons
            .remove("TeamCoordination")
            .map(serde_json::from_value::<crate::team::TeamState>)
            .transpose()
            .map_err(|e| e.to_string())?
            .map(crate::team::Team::restore)
            .transpose()?;
        let clock = config.clock.clone();
        let wall_time = singletons["GameTime"]["last_update_time"]
            .as_f64()
            .ok_or("invalid wall metadata")?;
        let statistics = config
            .systems
            .remove("StatisticsSystem")
            .map(serde_json::from_value::<crate::statistics::StatisticsSystem>)
            .transpose()
            .map_err(|e| e.to_string())?;
        if statistics.as_ref().is_some_and(|s| {
            s.batch_size == 0
                || !s.last_update_time.is_finite()
                || !s.observation_interval.is_finite()
                || s.observation_interval < 0.
        }) {
            return Err("invalid statistics sampler".into());
        }
        let visibility_tracker = singletons
            .remove("VisibilityTracker")
            .map(serde_json::from_value::<crate::statistics::VisibilityTracker>)
            .transpose()
            .map_err(|e| e.to_string())?;
        let spatial = Spatial::build(&world, &singletons, &config.rules, &config.display)?;
        let fog = singletons
            .remove("FogOfWar")
            .map(serde_json::from_value::<crate::vision::Fog>)
            .transpose()
            .map_err(|e| e.to_string())?;
        let vision = config
            .systems
            .remove("VisionSystem")
            .map(serde_json::from_value::<crate::vision::VisionState>)
            .transpose()
            .map_err(|e| e.to_string())?
            .map(crate::vision::VisionSystem::restore)
            .transpose()?;
        let recovery = config
            .systems
            .remove("ResourceRecoverySystem")
            .map(serde_json::from_value::<Recovery>)
            .transpose()
            .map_err(|e| e.to_string())?;
        if let Some(r) = &recovery {
            r.validate(world.next_id())?;
        }
        let visuals = crate::presentation::Visuals::import(
            config
                .systems
                .get("VisualLifecycle")
                .cloned()
                .ok_or("missing visual lifecycle metadata")?,
            &world,
        )?;
        let moving = world
            .ordered()
            .filter_map(|(id, e)| {
                world
                    .ecs
                    .get::<Movement>(e)
                    .filter(|m| m.is_moving)
                    .map(|_| id)
            })
            .collect();
        let living = crate::lifecycle::LivingFactions::build(&world);
        let capturing = world
            .ordered()
            .filter_map(|(id, e)| {
                world
                    .ecs
                    .get::<components::CaptureAction>(e)
                    .filter(|c| !c.completed)
                    .map(|_| id)
            })
            .collect();
        // Player membership/faction only changes through scene reset today.
        let players = world
            .ordered()
            .filter_map(|(id, e)| {
                world.ecs.get::<InitialComponents>(e)?.0.get("Player")?["faction"]
                    .as_str()
                    .map(|f| (id, f.to_string()))
            })
            .collect();
        Ok(Self {
            living,
            players,
            unit_entities,
            world,
            spatial,
            moving,
            visuals,
            capturing,
            vision_dirty: BTreeSet::new(),
            recovery,
            vision,
            fog,
            statistics,
            visibility_tracker,
            wall_time,
            team,
            clock,
            rng,
            singletons,
            query_cache: crate::named_observation::QueryCache::import(
                &config
                    .systems
                    .get("LLMObservationSystem")
                    .ok_or("missing observation bootstrap metadata")?["cache"],
            )?,
            config,
            epoch,
            revision: 0,
            threads,
            observation_pool: if threads == 1 {
                None
            } else {
                Some(pool.unwrap_or_else(|| {
                    std::sync::Arc::new(star_core::read_pool::ReadPool::new(threads))
                }))
            },
            presentation_dirty,
            presentation_tiles,
            presentation_fog: BTreeMap::new(),
            presentation_fog_full: true,
            presentation_removed: Vec::new(),
            presentation_log_full: true,
            presentation_log_entries: Vec::new(),
            presentation_players_full: true,
            presentation_player_removals: BTreeMap::new(),
            events: Vec::new(),
        })
    }

    /// Remove derived unit membership at the same point as ECS destruction.
    /// Both combat and expiring visual entities use this path; imported hybrid
    /// entities must not leave stale membership behind either.
    pub(crate) fn remove_entity(&mut self, id: u64) -> bool {
        self.unit_entities.remove(&id);
        self.world.remove(id)
    }

    /// R1 clock/lifecycle boundary. Gameplay systems join this step in R2/R3.
    pub fn step(&mut self, dt: f64, wall_time: f64) -> Result<(), String> {
        if !wall_time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        let revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        if !dt.is_finite() || dt < 0. {
            return Err("dt must be finite and nonnegative".into());
        }
        let clock_enabled = self
            .config
            .systems
            .get("GameTimeSystem")
            .is_none_or(|s| s["enabled"] == true);
        self.clock.step(if clock_enabled { dt } else { 0. })?;
        self.wall_time = wall_time;
        self.revision = revision;
        if clock_enabled && let Some(clock) = self.singletons.get_mut("GameTime") {
            clock["game_elapsed_time"] = json!(self.clock.elapsed);
            clock["last_update_time"] = json!(wall_time);
        }
        if clock_enabled {
            self.sync_turn_clock();
        }
        self.advance_statistics(dt)?;
        if self
            .config
            .systems
            .get("AnimationSystem")
            .is_none_or(|s| s["enabled"] == true)
        {
            self.advance_movement(dt);
            if self.config.systems.contains_key("AnimationSystem") {
                self.advance_visuals(dt)?;
            }
        }
        self.advance_recovery();
        self.advance_lifecycle();
        self.advance_vision();
        self.advance_captures()?;
        self.revision = revision;
        Ok(())
    }
    pub fn set_clock(&mut self, paused: bool, time_scale: f64) -> Result<(), String> {
        if !time_scale.is_finite() || time_scale <= 0. {
            return Err("time_scale must be positive and finite".into());
        }
        let revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        self.clock.paused = paused;
        self.clock.time_scale = time_scale;
        let clock = self
            .singletons
            .get_mut("GameTime")
            .expect("validated GameTime");
        clock["paused"] = json!(paused);
        clock["time_scale"] = json!(time_scale);
        self.revision = revision;
        Ok(())
    }
    pub fn export(&self) -> SceneSpec {
        let mut out = self.config.clone();
        out.clock = self.clock.clone();
        out.entity_counter = self.world.next_id();
        out.entities = self
            .world
            .ordered()
            .map(|(id, e)| {
                let mut cold = self
                    .world
                    .ecs
                    .get::<InitialComponents>(e)
                    .expect("imported components")
                    .0
                    .clone();
                components::export(&self.world.ecs, e, &mut cold);
                EntitySpec {
                    id,
                    components: cold,
                }
            })
            .collect();
        out.systems.insert(
            "LLMObservationSystem".into(),
            json!({"cache":self.query_cache.export(self.revision)}),
        );
        out.systems
            .insert("VisualLifecycle".into(), self.visuals.export());
        out.singletons = self.singletons.clone();
        if let Some(team) = &self.team {
            out.singletons.insert(
                "TeamCoordination".into(),
                serde_json::to_value(&team.state).unwrap(),
            );
        }
        if let Some(tracker) = &self.visibility_tracker {
            out.singletons.insert(
                "VisibilityTracker".into(),
                serde_json::to_value(tracker).unwrap(),
            );
        }
        if let Some(stats) = &self.statistics {
            out.systems.insert(
                "StatisticsSystem".into(),
                serde_json::to_value(stats).unwrap(),
            );
        }
        if let Some(fog) = &self.fog {
            out.singletons
                .insert("FogOfWar".into(), serde_json::to_value(fog).unwrap());
        }
        out.rng = self.rng.states();
        if let Some(recovery) = &self.recovery {
            out.systems.insert(
                "ResourceRecoverySystem".into(),
                serde_json::to_value(recovery).expect("validated recovery"),
            );
        }
        if let Some(vision) = &self.vision {
            out.systems
                .insert("VisionSystem".into(), vision.export(&self.vision_dirty));
        }
        out
    }
    pub fn presentation(&mut self) -> Value {
        let mut units = Vec::with_capacity(self.presentation_dirty.len());
        for id in std::mem::take(&mut self.presentation_dirty) {
            if let Some(entity) = self.world.entity(id) {
                units.push(json!({"id": id, "position": self.world.ecs.get::<Position>(entity),
                    "unit": self.world.ecs.get::<UnitInfo>(entity), "count": self.world.ecs.get::<Headcount>(entity),
                    "movement": self.world.ecs.get::<Movement>(entity),
                    "movement_points":self.world.ecs.get::<components::MovePoints>(entity),
                    "action_points":self.world.ecs.get::<components::ActionPoints>(entity),
                    "status":self.world.ecs.get::<components::Status>(entity),
                    "skill_points":self.world.ecs.get::<components::SkillPoints>(entity),
                    "construction_points":self.world.ecs.get::<components::ConstructionPoints>(entity)}));
            }
        }
        let tiles: Vec<_> = std::mem::take(&mut self.presentation_tiles)
            .into_iter()
            .filter_map(|id| {
                self.component::<components::TerritoryControl>(id)
                    .map(|control| json!({"id":id,"control":control}))
            })
            .collect();
        let state: BTreeMap<_, _> = ["GameTime", "GameState", "GameModeComponent", "TurnManager"]
            .into_iter()
            .filter_map(|name| self.singletons.get(name).map(|value| (name, value.clone())))
            .collect();
        let fog = self.fog_presentation();
        let hud = self.hud_presentation();
        let full = std::mem::take(&mut self.presentation_players_full);
        let rows: Vec<_> = if full {
            self.players
                .iter()
                .filter_map(|(id, _)| {
                    let player = self.component::<InitialComponents>(*id)?.0.get("Player")?;
                    Some(json!({"id":id,"player":player}))
                })
                .collect()
        } else {
            Vec::new()
        };
        // Only membership removals currently mutate Player after import. Send
        // changed IDs, never clone a faction's entire unit set on every death.
        let removed = std::mem::take(&mut self.presentation_player_removals);
        let units_removed: Vec<_> = if full {
            Vec::new()
        } else {
            removed
                .into_iter()
                .map(|(id, unit_ids)| json!({"id":id,"unit_ids":unit_ids}))
                .collect()
        };
        let players = json!({"full":full,"rows":rows,"units_removed":units_removed});
        json!({"players":players,"hud":hud,"state":state,"tiles":tiles,"fog":fog,"visuals":self.visuals.delta(), "epoch": self.epoch, "revision": self.revision, "tick": self.clock.tick,
               "units": units, "removed": std::mem::take(&mut self.presentation_removed),
               "events": std::mem::take(&mut self.events)})
    }
    pub fn diagnostics(&self) -> Value {
        json!({"stage": "R3-in-progress", "gameplay_ready": false, "epoch": self.epoch,
            "revision": self.revision, "threads": self.threads, "clock": self.clock,
            "api_version": crate::API_VERSION, "schema_version": crate::SCHEMA_VERSION,
            "entities": self.world.ordered().count(), "living_units": self.living.all.values().sum::<usize>(),
            "living_by_faction": self.living.all, "moving_units": self.moving.len(), "rules_version": RULES_VERSION})
    }
    pub fn set_wall_metadata(&mut self, time: f64) -> Result<(), String> {
        if !time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        self.wall_time = time;
        Ok(())
    }
}

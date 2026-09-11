use crate::RULES_VERSION;
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
}

pub struct Runtime {
    pub world: OrderedWorld,
    pub clock: SimClock,
    pub rng: DomainRng,
    pub singletons: BTreeMap<String, Value>,
    config: SceneSpec,
    pub epoch: u64,
    pub revision: u64,
    pub threads: usize,
    presentation_dirty: BTreeSet<u64>,
}

impl Runtime {
    pub fn from_json(payload: &str, threads: usize, epoch: u64) -> Result<Self, String> {
        let mut config: SceneSpec = serde_json::from_str(payload).map_err(|e| e.to_string())?;
        if config.schema != 1 || config.oracle != RULES_VERSION {
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
        for spec in std::mem::take(&mut config.entities) {
            let entity = world.import(spec.id)?;
            if spec.components.contains_key("Unit") {
                presentation_dirty.insert(spec.id);
            }
            world
                .ecs
                .entity_mut(entity)
                .insert(InitialComponents(spec.components));
        }
        let singletons = std::mem::take(&mut config.singletons);
        let clock = config.clock.clone();
        Ok(Self {
            world,
            clock,
            rng,
            singletons,
            config,
            epoch,
            revision: 0,
            threads,
            presentation_dirty,
        })
    }

    /// R1 clock/lifecycle boundary. Gameplay systems join this step in R2/R3.
    pub fn step(&mut self, dt: f64, wall_time: f64) -> Result<(), String> {
        if !wall_time.is_finite() {
            return Err("wall metadata must be finite".into());
        }
        let revision = self.revision.checked_add(1).ok_or("revision exhausted")?;
        self.clock.step(dt)?;
        if let Some(clock) = self.singletons.get_mut("GameTime") {
            clock["game_elapsed_time"] = json!(self.clock.elapsed);
            clock["last_update_time"] = json!(wall_time);
        }
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
            .map(|(id, e)| EntitySpec {
                id,
                components: self
                    .world
                    .ecs
                    .get::<InitialComponents>(e)
                    .expect("imported components")
                    .0
                    .clone(),
            })
            .collect();
        out.singletons = self.singletons.clone();
        out.rng = self.rng.states();
        out
    }
    pub fn presentation(&mut self) -> Value {
        let mut units = Vec::with_capacity(self.presentation_dirty.len());
        for id in std::mem::take(&mut self.presentation_dirty) {
            if let Some(entity) = self.world.entity(id) {
                let c = &self
                    .world
                    .ecs
                    .get::<InitialComponents>(entity)
                    .expect("components")
                    .0;
                units.push(json!({"id": id, "position": c.get("HexPosition"),
                    "unit": c.get("Unit"), "count": c.get("UnitCount")}));
            }
        }
        json!({"epoch": self.epoch, "revision": self.revision, "tick": self.clock.tick,
               "units": units, "removed": [], "events": []})
    }
    pub fn diagnostics(&self) -> Value {
        json!({"stage": "R1", "gameplay_ready": false, "epoch": self.epoch,
            "revision": self.revision, "threads": self.threads, "clock": self.clock,
            "entities": self.world.ordered().count(), "rules_version": RULES_VERSION})
    }
}

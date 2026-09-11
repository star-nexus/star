//! Incremental faction visibility; geometry is independent of faction ownership.
use crate::{
    components::{Position, UnitInfo},
    hex::{self, Hex},
    runtime::Runtime,
};
use bevy_ecs::prelude::*;
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet, HashMap},
    ops::{Deref, DerefMut},
    sync::Arc,
};

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct HexSet(pub BTreeSet<Hex>);
impl Deref for HexSet {
    type Target = BTreeSet<Hex>;
    fn deref(&self) -> &Self::Target {
        &self.0
    }
}
impl DerefMut for HexSet {
    fn deref_mut(&mut self) -> &mut Self::Target {
        &mut self.0
    }
}
impl Serialize for HexSet {
    fn serialize<S: serde::Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut values: Vec<_> = self.0.iter().copied().collect();
        values.sort_by_cached_key(|p| serde_json::to_string(p).unwrap());
        serde_json::json!({"$set":values}).serialize(s)
    }
}
impl<'de> Deserialize<'de> for HexSet {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Tagged {
            #[serde(rename = "$set")]
            cells: Vec<Hex>,
        }
        let tagged = Tagged::deserialize(d)?;
        let cells: BTreeSet<_> = tagged.cells.iter().copied().collect();
        if cells.len() != tagged.cells.len() {
            return Err(serde::de::Error::custom("duplicate set member"));
        }
        Ok(Self(cells))
    }
}
#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Vision {
    pub range: i64,
    pub visible_tiles: HexSet,
    #[serde(rename = "_last_observed_pos")]
    pub last_pos: Option<Hex>,
    #[serde(rename = "_last_range")]
    pub last_range: i64,
    pub dirty: bool,
}
#[derive(Default, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Fog {
    pub faction_vision: BTreeMap<String, HexSet>,
    pub explored_tiles: BTreeMap<String, HexSet>,
    pub enabled: bool,
}

type GeometryKey = (Hex, i64, u64);
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VisionState {
    pub enabled: bool,
    pub window: bool,
    pub indexed: bool,
    pub audit_interval: u64,
    pub frames: u64,
    pub bootstrapped: bool,
    pub last_fog_enabled: Option<bool>,
    pub terrain_revision: u64,
    pub capacity: usize,
    pub dirty: BTreeSet<u64>,
    pub unit_visibility: BTreeMap<u64, HexSet>,
    pub unit_faction: BTreeMap<u64, String>,
    pub counts: BTreeMap<String, Vec<(Hex, u64)>>,
    pub geometry: Vec<(GeometryKey, HexSet)>,
    pub recomputes: u64,
    pub cache_hits: u64,
    pub geometry_hits: u64,
    pub geometry_misses: u64,
    pub geometry_evictions: u64,
}
pub struct VisionSystem {
    pub state: VisionState,
    counts: BTreeMap<String, BTreeMap<Hex, u64>>,
    cache: HashMap<GeometryKey, (Arc<HexSet>, u64)>,
    lru: BTreeMap<u64, GeometryKey>,
    cache_clock: u64,
    pub delta: BTreeMap<String, HexSet>,
}
impl VisionSystem {
    pub fn restore(mut state: VisionState) -> Result<Self, String> {
        if state.capacity == 0 || state.audit_interval == 0 || state.geometry.len() > state.capacity
        {
            return Err("invalid vision cache/audit configuration".into());
        }
        let mut cache = HashMap::new();
        let mut lru = BTreeMap::new();
        for (i, (key, value)) in std::mem::take(&mut state.geometry).into_iter().enumerate() {
            if cache.insert(key, (Arc::new(value), i as u64)).is_some() {
                return Err("duplicate vision cache key".into());
            }
            lru.insert(i as u64, key);
        }
        let mut counts = BTreeMap::new();
        for (f, entries) in std::mem::take(&mut state.counts) {
            let mut cells = BTreeMap::new();
            for (cell, count) in entries {
                if count == 0 || cells.insert(cell, count).is_some() {
                    return Err("invalid vision refcount".into());
                }
            }
            counts.insert(f, cells);
        }
        Ok(Self {
            cache_clock: cache.len() as u64,
            state,
            counts,
            cache,
            lru,
            delta: BTreeMap::new(),
        })
    }
    pub fn export(&self, pending: &BTreeSet<u64>) -> serde_json::Value {
        let mut value = serde_json::to_value(&self.state).unwrap();
        value["counts"] = serde_json::to_value(
            self.counts
                .iter()
                .map(|(f, c)| (f, c.iter().map(|(p, n)| (*p, *n)).collect::<Vec<_>>()))
                .collect::<BTreeMap<_, _>>(),
        )
        .unwrap();
        value["geometry"] = serde_json::to_value(
            self.lru
                .values()
                .map(|k| (*k, self.cache[k].0.as_ref()))
                .collect::<Vec<_>>(),
        )
        .unwrap();
        value["dirty"] =
            serde_json::json!(self.state.dirty.union(pending).copied().collect::<Vec<_>>());
        value
    }
    fn audit(&mut self, r: &Runtime, force: bool) {
        let mut current = BTreeSet::new();
        for (id, e) in r.world.ordered() {
            let (Some(p), Some(v), Some(u)) = (
                r.world.ecs.get::<Position>(e),
                r.world.ecs.get::<Vision>(e),
                r.world.ecs.get::<UnitInfo>(e),
            ) else {
                continue;
            };
            current.insert(id);
            if force
                || !self.state.unit_visibility.contains_key(&id)
                || v.dirty
                || v.last_pos != Some(p.hex())
                || v.last_range != v.range
                || self.state.unit_faction.get(&id) != Some(&u.faction)
            {
                self.state.dirty.insert(id);
            }
        }
        self.state.dirty.extend(
            self.state
                .unit_visibility
                .keys()
                .filter(|id| !current.contains(id)),
        );
    }
    fn remove_tiles(&mut self, fog: &mut Fog, faction: &str, tiles: &BTreeSet<Hex>) {
        let counts = self.counts.entry(faction.into()).or_default();
        let visible = fog.faction_vision.entry(faction.into()).or_default();
        for tile in tiles {
            let old = counts.get(tile).copied().unwrap_or(0);
            if old <= 1 {
                if old != 0 {
                    counts.remove(tile);
                    visible.remove(tile);
                    self.delta.entry(faction.into()).or_default().insert(*tile);
                }
            } else {
                counts.insert(*tile, old - 1);
            }
        }
    }
    fn add_tiles(&mut self, fog: &mut Fog, faction: &str, tiles: &BTreeSet<Hex>) {
        let counts = self.counts.entry(faction.into()).or_default();
        let visible = fog.faction_vision.entry(faction.into()).or_default();
        for tile in tiles {
            let count = counts.entry(*tile).or_default();
            if *count == 0 {
                visible.insert(*tile);
                fog.explored_tiles
                    .entry(faction.into())
                    .or_default()
                    .insert(*tile);
                self.delta.entry(faction.into()).or_default().insert(*tile);
            }
            *count += 1;
        }
    }
    fn terrain_bonus(r: &Runtime, center: Hex) -> i64 {
        r.spatial
            .tiles
            .get(&center)
            .filter(|t| t.entity != 0 && t.has_terrain)
            .and_then(|t| r.config.rules["terrain_effects"][&t.terrain]["vision_bonus"].as_i64())
            .unwrap_or(0)
    }
    fn visible_geometry(r: &Runtime, center: Hex, range: i64) -> HexSet {
        let mut result = HexSet::default();
        for col in center.0 - range..=center.0 + range {
            for row in center.1 - range..=center.1 + range {
                let target = (col, row);
                if hex::distance(center, target) > range {
                    continue;
                }
                let ray = hex::line(center, target);
                let blocked=ray.iter().skip(1).take(ray.len().saturating_sub(2)).any(|cell| {
                    r.spatial.tiles.get(cell).filter(|t|t.entity!=0 && t.has_terrain).is_some_and(|t|
                        r.config.rules["terrain_effects"][&t.terrain]["blocks_line_of_sight"].as_bool().unwrap_or(false))
                });
                if !blocked {
                    result.insert(target);
                }
            }
        }
        result
    }
    pub fn visibility_for(&mut self, r: &Runtime, center: Hex, range: i64) -> Arc<HexSet> {
        let effective = range + Self::terrain_bonus(r, center);
        let key = (
            center,
            if self.state.window { range } else { effective },
            self.state.terrain_revision,
        );
        let stamp = self.cache_clock;
        self.cache_clock = self
            .cache_clock
            .checked_add(1)
            .expect("vision cache revision exhausted");
        if let Some((cells, old)) = self.cache.get_mut(&key) {
            self.lru.remove(old);
            self.lru.insert(stamp, key);
            *old = stamp;
            self.state.geometry_hits += 1;
            return cells.clone();
        }
        let visible = Arc::new(Self::visible_geometry(r, center, effective));
        self.cache.insert(key, (visible.clone(), stamp));
        self.lru.insert(stamp, key);
        if self.cache.len() > self.state.capacity {
            let (_, old) = self.lru.pop_first().unwrap();
            self.cache.remove(&old);
            self.state.geometry_evictions += 1;
        }
        self.state.geometry_misses += 1;
        visible
    }
    pub fn update(&mut self, r: &mut Runtime) {
        self.state.frames += 1;
        self.delta.clear();
        if r.fog.is_none() {
            r.fog = Some(Fog {
                enabled: true,
                ..Default::default()
            });
        }
        self.state.last_fog_enabled = Some(r.fog.as_ref().unwrap().enabled);
        if !self.state.bootstrapped {
            self.audit(r, true);
            self.state.bootstrapped = true;
        } else if !(self.state.window && self.state.indexed)
            && self.state.frames.is_multiple_of(if self.state.indexed {
                self.state.audit_interval
            } else {
                1
            })
        {
            self.audit(r, false);
        }
        self.state.dirty.append(&mut r.vision_dirty);
        for id in std::mem::take(&mut self.state.dirty) {
            let values = r.world.entity(id).and_then(|e| {
                Some((
                    e,
                    r.world.ecs.get::<Position>(e)?.hex(),
                    r.world.ecs.get::<Vision>(e)?.clone(),
                    r.world.ecs.get::<UnitInfo>(e)?.faction.clone(),
                ))
            });
            let Some((e, pos, v, faction)) = values else {
                let old = self.state.unit_visibility.remove(&id).unwrap_or_default();
                if let Some(f) = self.state.unit_faction.remove(&id)
                    && !old.is_empty()
                {
                    self.remove_tiles(r.fog.as_mut().unwrap(), &f, &old);
                }
                continue;
            };
            if !v.dirty
                && v.last_pos == Some(pos)
                && v.last_range == v.range
                && self.state.unit_visibility.contains_key(&id)
                && self.state.unit_faction.get(&id) == Some(&faction)
            {
                self.state.cache_hits += 1;
                continue;
            }
            let visible = self.visibility_for(r, pos, v.range);
            let mut old = self
                .state
                .unit_visibility
                .get(&id)
                .cloned()
                .unwrap_or_default();
            if let Some(old_faction) = self
                .state
                .unit_faction
                .get(&id)
                .filter(|f| **f != faction)
                .cloned()
            {
                self.remove_tiles(r.fog.as_mut().unwrap(), &old_faction, &old);
                old.clear();
            }
            let removed = old.difference(&visible).copied().collect::<BTreeSet<_>>();
            let added = visible.difference(&old).copied().collect::<BTreeSet<_>>();
            if !removed.is_empty() {
                self.remove_tiles(r.fog.as_mut().unwrap(), &faction, &removed);
            }
            if !added.is_empty() {
                self.add_tiles(r.fog.as_mut().unwrap(), &faction, &added);
            }
            self.state
                .unit_visibility
                .insert(id, visible.as_ref().clone());
            self.state.unit_faction.insert(id, faction);
            let mut vision = r.world.ecs.get_mut::<Vision>(e).unwrap();
            vision.visible_tiles = visible.as_ref().clone();
            vision.last_pos = Some(pos);
            vision.last_range = v.range;
            vision.dirty = false;
            self.state.recomputes += 1;
        }
    }
}
impl Runtime {
    pub fn vision_probe(&mut self, op: &serde_json::Value) -> Result<serde_json::Value, String> {
        match op["kind"].as_str() {
            Some("toggle") => {
                self.fog.as_mut().ok_or("missing fog")?.enabled =
                    op["enabled"].as_bool().ok_or("invalid fog toggle")?;
                Ok(serde_json::Value::Null)
            }
            Some("range") => {
                let id = op["unit_id"].as_u64().ok_or("invalid unit_id")?;
                let range = op["range"].as_i64().ok_or("invalid vision range")?;
                let e = self.world.entity(id).ok_or("missing unit")?;
                let mut v = self
                    .world
                    .ecs
                    .get_mut::<Vision>(e)
                    .ok_or("missing vision")?;
                v.range = range;
                v.dirty = true;
                self.vision_dirty.insert(id);
                Ok(serde_json::Value::Null)
            }
            Some("geometry") => {
                let center: Hex =
                    serde_json::from_value(op["center"].clone()).map_err(|e| e.to_string())?;
                let range = op["range"].as_i64().ok_or("invalid range")?;
                let mut v = self.vision.take().ok_or("missing vision system")?;
                let result = v.visibility_for(self, center, range);
                self.vision = Some(v);
                Ok(serde_json::to_value(result.as_ref()).unwrap())
            }
            _ => Err("unknown vision probe".into()),
        }
    }
    pub fn advance_vision(&mut self) {
        if let Some(mut v) = self.vision.take() {
            if v.state.enabled {
                v.update(self);
            }
            self.vision = Some(v);
        }
    }
}

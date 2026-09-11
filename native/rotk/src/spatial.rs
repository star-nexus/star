use crate::{
    components::{Headcount, Position, UnitInfo},
    hex::{self, Hex},
    runtime::InitialComponents,
};
use serde_json::Value;
use star_core::world::OrderedWorld;
use std::{
    cmp::Reverse,
    collections::{BTreeMap, BTreeSet, BinaryHeap, HashMap},
};

#[derive(Clone, Debug)]
pub struct TileInfo {
    pub entity: u64,
    pub terrain: String,
    pub cost: i64,
    pub has_terrain: bool,
}
#[derive(Default)]
pub struct Spatial {
    pub tiles: HashMap<Hex, TileInfo>,
    pub cells: HashMap<Hex, BTreeMap<u64, String>>,
}
impl Spatial {
    pub fn build(
        world: &OrderedWorld,
        singletons: &BTreeMap<String, Value>,
        rules: &Value,
        display: &str,
    ) -> Result<Self, String> {
        let mut out = Self::default();
        let map = singletons.get("MapData").ok_or("missing MapData")?;
        let pairs = map["tiles"]["$map"].as_array().ok_or("invalid map tiles")?;
        for pair in pairs {
            let cell: Hex = serde_json::from_value(pair[0].clone()).map_err(|e| e.to_string())?;
            if cell.0.unsigned_abs() > i32::MAX as u64 || cell.1.unsigned_abs() > i32::MAX as u64 {
                return Err("map coordinates exceed native range".into());
            }
            let id = pair[1].as_u64().ok_or("invalid tile ID")?;
            let e = world.entity(id).ok_or("map refers to missing tile")?;
            let cold = &world
                .ecs
                .get::<InitialComponents>(e)
                .ok_or("missing tile components")?
                .0;
            let terrain = cold
                .get("Terrain")
                .and_then(|t| t["terrain_type"].as_str())
                .unwrap_or("plain")
                .to_string();
            let has_terrain = cold.contains_key("Terrain");
            let cost = if has_terrain {
                rules["terrain_effects"][&terrain]["movement_cost"]
                    .as_i64()
                    .unwrap_or(1)
            } else {
                999
            };
            if cost < 1 {
                return Err("terrain movement costs must be positive".into());
            }
            if out
                .tiles
                .insert(
                    cell,
                    TileInfo {
                        entity: id,
                        terrain,
                        cost,
                        has_terrain,
                    },
                )
                .is_some()
            {
                return Err("duplicate map coordinate".into());
            }
        }
        for (id, e) in world.ordered() {
            if let (Some(u), Some(p)) = (world.ecs.get::<UnitInfo>(e), world.ecs.get::<Position>(e))
            {
                let included = display != "window"
                    || world
                        .ecs
                        .get::<Headcount>(e)
                        .is_some_and(|c| c.current_count > 0);
                if included {
                    out.cells
                        .entry(p.hex())
                        .or_default()
                        .insert(id, u.faction.clone());
                }
            }
        }
        Ok(out)
    }
    pub fn occupied(&self, cell: Hex, mover: u64) -> bool {
        self.cells
            .get(&cell)
            .is_some_and(|v| v.keys().any(|&id| id != mover))
    }
    pub fn blocked(&self, cell: Hex, mover: u64, faction: Option<&str>) -> bool {
        self.tiles.get(&cell).is_some_and(|t| t.cost >= 999)
            || self.cells.get(&cell).is_some_and(|v| {
                v.iter()
                    .any(|(&id, f)| id != mover && Some(f.as_str()) != faction)
            })
    }
    pub fn cost(&self, cell: Hex) -> i64 {
        self.tiles.get(&cell).map_or(999, |t| t.cost)
    }
    pub fn terrain(&self, cell: Hex) -> &str {
        self.tiles.get(&cell).map_or("plain", |t| &t.terrain)
    }
    pub fn path(
        &self,
        start: Hex,
        goal: Hex,
        mover: u64,
        faction: Option<&str>,
        max_cost: Option<i64>,
    ) -> Vec<Hex> {
        if start == goal {
            return vec![start];
        }
        if self.blocked(goal, mover, faction) || !self.tiles.contains_key(&goal) {
            return vec![];
        }
        let mut frontier = BinaryHeap::from([Reverse((0, start))]);
        let mut came = HashMap::from([(start, None)]);
        let mut costs = HashMap::from([(start, 0_i64)]);
        while let Some(Reverse((_, current))) = frontier.pop() {
            if current == goal {
                let mut result = vec![];
                let mut cell = Some(current);
                while let Some(p) = cell {
                    result.push(p);
                    cell = came[&p];
                }
                result.reverse();
                return result;
            }
            for neighbor in hex::neighbors(current) {
                if self.blocked(neighbor, mover, faction) || !self.tiles.contains_key(&neighbor) {
                    continue;
                }
                let cost = costs[&current] + self.cost(neighbor);
                if max_cost.is_some_and(|limit| cost > limit) {
                    continue;
                }
                if costs.get(&neighbor).is_none_or(|&old| cost < old) {
                    costs.insert(neighbor, cost);
                    frontier.push(Reverse((cost + hex::distance(neighbor, goal), neighbor)));
                    came.insert(neighbor, Some(current));
                }
            }
        }
        vec![]
    }
    pub fn reachable(
        &self,
        start: Hex,
        budget: i64,
        mover: u64,
        faction: Option<&str>,
    ) -> Vec<Hex> {
        let mut frontier = BinaryHeap::from([Reverse((0, start))]);
        let mut costs = HashMap::from([(start, 0_i64)]);
        let mut reached = BTreeSet::from([start]);
        while let Some(Reverse((current_cost, current))) = frontier.pop() {
            if current_cost > costs[&current] {
                continue;
            }
            for neighbor in hex::neighbors(current) {
                if self.blocked(neighbor, mover, faction) || !self.tiles.contains_key(&neighbor) {
                    continue;
                }
                let cost = current_cost + self.cost(neighbor);
                if cost > budget {
                    continue;
                }
                if costs.get(&neighbor).is_none_or(|&old| cost < old) {
                    costs.insert(neighbor, cost);
                    reached.insert(neighbor);
                    frontier.push(Reverse((cost, neighbor)));
                }
            }
        }
        reached
            .into_iter()
            .filter(|&cell| !self.occupied(cell, mover))
            .collect()
    }
    pub fn moved(&mut self, id: u64, old: Hex, new: Hex) {
        if old == new {
            return;
        }
        if let Some(faction) = self.cells.get_mut(&old).and_then(|v| v.remove(&id)) {
            if self.cells[&old].is_empty() {
                self.cells.remove(&old);
            }
            self.cells.entry(new).or_default().insert(id, faction);
        }
    }
    pub fn remove(&mut self, id: u64, pos: Hex) {
        if let Some(cell) = self.cells.get_mut(&pos) {
            cell.remove(&id);
            if cell.is_empty() {
                self.cells.remove(&pos);
            }
        }
    }
}

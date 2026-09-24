//! Animation lifetimes affect external ID allocation. Interpolation and pixels
//! belong to the Python presentation layer; the world exports only changed rows.
use crate::{
    components::Position,
    runtime::{InitialComponents, Runtime},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Default, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct Visuals {
    attack: BTreeMap<u64, Value>,
    damage: BTreeMap<u64, Value>,
    effect: BTreeMap<u64, Value>,
    projectile: BTreeMap<u64, Value>,
    #[serde(skip)]
    dirty: BTreeSet<u64>,
    #[serde(skip)]
    removed: Vec<u64>,
}
fn f(row: &Value, key: &str) -> f64 {
    row[key].as_f64().expect("validated visual number")
}
fn point(row: &Value, key: &str) -> (f64, f64) {
    (
        row[key][0].as_f64().expect("visual x"),
        row[key][1].as_f64().expect("visual y"),
    )
}
impl Visuals {
    pub fn import(value: Value, world: &star_core::world::OrderedWorld) -> Result<Self, String> {
        let mut out: Self =
            serde_json::from_value(value).map_err(|e| format!("invalid visual lifecycle: {e}"))?;
        for (kind, rows, fields) in [
            (
                "attack",
                &out.attack,
                &[
                    "progress",
                    "speed",
                    "total_duration",
                    "prepare_ratio",
                    "aim_ratio",
                    "strike_ratio",
                    "return_ratio",
                ][..],
            ),
            ("damage", &out.damage, &["elapsed_time", "lifetime"][..]),
            ("effect", &out.effect, &["elapsed_time", "duration"][..]),
            (
                "projectile",
                &out.projectile,
                &["flight_progress", "flight_speed"][..],
            ),
        ] {
            for (&uid, row) in rows {
                if world.entity(uid).is_none() || !row.is_object() {
                    return Err("visual refers to missing entity or invalid row".into());
                }
                for field in fields {
                    if !row[*field].as_f64().is_some_and(f64::is_finite) {
                        return Err(format!("invalid {kind}.{field}"));
                    }
                }
                let points: &[&str] = match kind {
                    "attack" => &["start_pixel_pos", "target_pixel_pos"],
                    "damage" => &["world_position", "velocity"],
                    "projectile" => &["start_pos", "target_pos"],
                    _ => &[],
                };
                for &key in points {
                    if kind == "attack" && row[key].is_null() {
                        continue;
                    }
                    if !row[key].as_array().is_some_and(|p| {
                        p.len() == 2 && p.iter().all(|v| v.as_f64().is_some_and(f64::is_finite))
                    }) {
                        return Err(format!("invalid {kind}.{key}"));
                    }
                }
                out.dirty.insert(uid);
            }
        }
        Ok(out)
    }
    pub fn export(&self) -> Value {
        serde_json::to_value(self).expect("visual state")
    }
    pub fn forget(&mut self, id: u64) {
        let existed = self.attack.remove(&id).is_some()
            | self.damage.remove(&id).is_some()
            | self.effect.remove(&id).is_some()
            | self.projectile.remove(&id).is_some();
        if existed {
            self.dirty.remove(&id);
            self.removed.push(id);
        }
    }
    pub fn delta(&mut self) -> Value {
        let mut rows = vec![];
        for id in std::mem::take(&mut self.dirty) {
            let mut components = serde_json::Map::new();
            for (kind, map) in [
                ("attack", &self.attack),
                ("damage", &self.damage),
                ("effect", &self.effect),
                ("projectile", &self.projectile),
            ] {
                if let Some(row) = map.get(&id) {
                    components.insert(kind.into(), row.clone());
                }
            }
            rows.push(json!({"id":id,"components":components}));
        }
        json!({"rows":rows,"removed":std::mem::take(&mut self.removed)})
    }
    fn spawn(r: &mut Runtime) -> Result<u64, String> {
        let (id, e) = r.world.spawn()?;
        r.world
            .ecs
            .entity_mut(e)
            .insert(InitialComponents(BTreeMap::new()));
        Ok(id)
    }
    fn advance(&mut self, r: &mut Runtime, dt: f64) -> Result<(), String> {
        // Keep legacy phases: attack -> projectile -> effect -> floating text.
        // A projectile born this tick receives this tick's full dt as in Python.
        let mut complete = vec![];
        let mut arrows = vec![];
        for (&id, attack) in &mut self.attack {
            if r.component::<Position>(id).is_none() || attack["is_attacking"] != true {
                continue;
            }
            let progress = f(attack, "progress") + f(attack, "speed") * dt;
            attack["progress"] = json!(progress);
            self.dirty.insert(id);
            if progress >= f(attack, "total_duration") {
                complete.push(id);
                continue;
            }
            let ratio = progress / f(attack, "total_duration");
            let start = f(attack, "prepare_ratio") + f(attack, "aim_ratio");
            if ratio > start
                && ratio <= start + f(attack, "strike_ratio")
                && attack["attack_type"] != "melee"
            {
                if attack["projectile_created"] != true
                    && !attack["start_pixel_pos"].is_null()
                    && !attack["target_pixel_pos"].is_null()
                {
                    arrows.push(attack.clone());
                }
                attack["projectile_created"] = json!(true);
            }
        }
        for id in complete {
            self.attack.remove(&id);
            self.dirty.insert(id);
        }
        for attack in arrows {
            let id = Self::spawn(r)?;
            let ranged = attack["attack_type"] == "ranged";
            self.projectile.insert(id,json!({"start_pos":attack["start_pixel_pos"],"target_pos":attack["target_pixel_pos"],
                "flight_progress":0.,"flight_speed":if ranged{600.}else{800.},"is_flying":true,
                "projectile_type":if ranged{"arrow"}else{"bolt"},"arc_height":if ranged{30.}else{20.},
                "size":1.,"color":if ranged{[139,69,19]}else{[192,192,192]}}));
            self.dirty.insert(id);
        }
        let mut remove = vec![];
        for (&id, p) in &mut self.projectile {
            if p["is_flying"] != true {
                continue;
            }
            let (x, y) = point(p, "start_pos");
            let (tx, ty) = point(p, "target_pos");
            let distance = ((tx - x).powi(2) + (ty - y).powi(2)).sqrt();
            if distance <= 0. {
                remove.push(id);
                continue;
            }
            p["flight_progress"] =
                json!(f(p, "flight_progress") + (f(p, "flight_speed") / distance) * dt);
            self.dirty.insert(id);
            if f(p, "flight_progress") >= 1. {
                remove.push(id);
            }
        }
        for id in remove {
            self.forget(id);
            r.remove_entity(id);
        }
        let mut remove = vec![];
        for (&id, e) in &mut self.effect {
            if e["is_playing"] != true {
                continue;
            }
            e["elapsed_time"] = json!(f(e, "elapsed_time") + dt);
            self.dirty.insert(id);
            if f(e, "duration") == 0. {
                return Err("float division by zero in effect animation".into());
            }
            if f(e, "elapsed_time") >= f(e, "duration") {
                remove.push(id);
            }
        }
        for id in remove {
            self.forget(id);
            r.remove_entity(id);
        }
        let mut remove = vec![];
        for (&id, d) in &mut self.damage {
            let elapsed = f(d, "elapsed_time") + dt;
            d["elapsed_time"] = json!(elapsed);
            self.dirty.insert(id);
            if elapsed >= f(d, "lifetime") {
                remove.push(id);
                continue;
            }
            let (x, y) = point(d, "world_position");
            let (vx, vy) = point(d, "velocity");
            d["world_position"] = json!([x + vx * dt, y + vy * dt]);
        }
        for id in remove {
            self.forget(id);
            r.remove_entity(id);
        }
        Ok(())
    }
}
impl Runtime {
    fn visual_pixel(&self, p: (i64, i64)) -> (f64, f64) {
        crate::movement::pixel(
            p,
            self.config.rules["hex_size"].as_f64().unwrap(),
            self.config.rules["hex_orientation"] == "pointy",
        )
    }
    pub(crate) fn start_combat_visual(&mut self, a: u64, t: u64, ranged: bool) {
        if !self.config.systems.contains_key("AnimationSystem") {
            return;
        }
        let p = self.component::<Position>(a).unwrap().hex();
        let q = self.component::<Position>(t).unwrap().hex();
        let start = self.visual_pixel(p);
        let target = self.visual_pixel(q);
        self.visuals.attack.insert(a,json!({"target_position":q,"progress":0.,"speed":if ranged{5.}else{8.},
            "is_attacking":true,"attack_type":if ranged{"ranged"}else{"melee"},
            "start_pixel_pos":start,"target_pixel_pos":target,"total_duration":if ranged{1.}else{0.8},
            "prepare_ratio":if ranged{0.15}else{0.2},"aim_ratio":if ranged{0.25}else{0.15},
            "strike_ratio":0.45,"return_ratio":if ranged{0.15}else{0.2},
            "aim_line_color":if ranged{[255,100,100]}else{[255,255,100]},"projectile_created":false}));
        self.visuals.dirty.insert(a);
    }
    pub(crate) fn combat_visual_damage(
        &mut self,
        t: u64,
        damage: i64,
        critical: bool,
        ranged: bool,
    ) -> Result<(), String> {
        if !self.config.systems.contains_key("AnimationSystem") {
            return Ok(());
        }
        let pos = self.visual_pixel(self.component::<Position>(t).unwrap().hex());
        if critical {
            let id = Visuals::spawn(self)?;
            self.visuals.damage.insert(
                id,
                json!({"text":"CRIT!","world_position":[pos.0,pos.1-50.],"lifetime":2.5,
                "elapsed_time":0.,"velocity":[0,-60],"color":[255,255,0],"font_size":28}),
            );
            self.visuals.dirty.insert(id);
        }
        let id = Visuals::spawn(self)?;
        self.visuals.damage.insert(id,json!({"text":damage.to_string(),"world_position":[pos.0,pos.1-30.],"lifetime":2.,
            "elapsed_time":0.,"velocity":[0,-50],"color":if damage>0{[255,0,0]}else{[0,255,0]},"font_size":24}));
        self.visuals.dirty.insert(id);
        let id = Visuals::spawn(self)?;
        self.visuals.effect.insert(id,json!({"effect_type":if critical{"explosion"}else if ranged{"impact"}else{"slash"},
            "is_playing":true,"effect_position":pos,"effect_size":1.,"effect_color":[255,255,255],"duration":0.5,"elapsed_time":0.}));
        self.visuals.dirty.insert(id);
        Ok(())
    }
    pub(crate) fn advance_visuals(&mut self, dt: f64) -> Result<(), String> {
        let mut visuals = std::mem::take(&mut self.visuals);
        let result = visuals.advance(self, dt);
        self.visuals = visuals;
        result
    }
}

impl Runtime {
    pub(crate) fn fog_presentation(&mut self) -> Value {
        let full = std::mem::take(&mut self.presentation_fog_full);
        let mut changes = std::mem::take(&mut self.presentation_fog);
        if full && let Some(fog) = &self.fog {
            for (faction, area) in fog.faction_vision.iter().chain(&fog.explored_tiles) {
                changes
                    .entry(faction.clone())
                    .or_default()
                    .extend(area.iter().copied());
            }
        }
        let factions: Vec<_> = changes
            .into_iter()
            .map(|(faction, cells)| {
                let visible = self
                    .fog
                    .as_ref()
                    .and_then(|fog| fog.faction_vision.get(&faction));
                let explored = self
                    .fog
                    .as_ref()
                    .and_then(|fog| fog.explored_tiles.get(&faction));
                let cells: Vec<_> = cells
                    .into_iter()
                    .map(|cell| {
                        json!({"col":cell.0,"row":cell.1,
                "visible":visible.is_some_and(|area|area.contains(&cell)),
                "explored":explored.is_some_and(|area|area.contains(&cell))})
                    })
                    .collect();
                json!({"faction":faction,"cells":cells})
            })
            .collect();
        json!({"full":full,"enabled":self.fog.as_ref().map(|fog|fog.enabled),"factions":factions})
    }
}

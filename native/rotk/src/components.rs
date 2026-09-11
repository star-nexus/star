//! Typed authoritative gameplay columns. Import removes their cold originals.
use bevy_ecs::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Position {
    pub col: i64,
    pub row: i64,
}
impl Position {
    pub fn hex(&self) -> (i64, i64) {
        (self.col, self.row)
    }
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UnitInfo {
    pub unit_type: String,
    pub faction: String,
    pub name: String,
    pub level: i64,
    pub experience: i64,
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Headcount {
    pub current_count: i64,
    pub max_count: i64,
}
impl Headcount {
    pub fn ratio(&self) -> f64 {
        if self.max_count > 0 {
            self.current_count as f64 / self.max_count as f64
        } else {
            0.
        }
    }
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MovePoints {
    pub current_mp: i64,
    pub max_mp: i64,
    pub base_mp: i64,
    pub has_moved: bool,
}
impl MovePoints {
    pub fn effective(&self, count: &Headcount) -> i64 {
        (self.base_mp - i64::from(count.ratio() <= 0.2)).max(2)
    }
    pub fn spendable(&self, count: &Headcount) -> i64 {
        self.effective(count).min(self.current_mp)
    }
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ActionPoints {
    pub current_ap: i64,
    pub max_ap: i64,
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SkillPoints {
    pub current_sp: i64,
    pub max_sp: i64,
    pub skill_cooldowns: BTreeMap<String, i64>,
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CombatStats {
    pub base_attack: i64,
    pub base_defense: i64,
    pub attack_range: i64,
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Status {
    pub current_status: String,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub current_status_is_enum: bool,
    pub status_duration: i64,
    pub wait_turns: i64,
    pub charge_stacks: i64,
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CombatRoll {
    pub hit_roll: Option<i64>,
    pub damage_roll: Option<i64>,
    pub crit_roll: Option<i64>,
    pub hit_threshold: i64,
    pub crit_threshold: i64,
}
impl Default for CombatRoll {
    fn default() -> Self {
        Self {
            hit_roll: None,
            damage_roll: None,
            crit_roll: None,
            hit_threshold: 1,
            crit_threshold: 19,
        }
    }
}

#[derive(Component, Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Movement {
    pub path: Vec<(i64, i64)>,
    pub current_target_index: usize,
    pub progress: f64,
    pub speed: f64,
    pub is_moving: bool,
    pub start_pixel_pos: Option<(f64, f64)>,
    pub target_pixel_pos: Option<(f64, f64)>,
}
impl Default for Movement {
    fn default() -> Self {
        Self {
            path: vec![],
            current_target_index: 0,
            progress: 0.,
            speed: 2.,
            is_moving: false,
            start_pixel_pos: None,
            target_pixel_pos: None,
        }
    }
}

pub fn import(
    world: &mut World,
    e: Entity,
    cold: &mut BTreeMap<String, Value>,
) -> Result<(), String> {
    macro_rules! take {
        ($name:literal, $ty:ty) => {
            if let Some(value) = cold.remove($name) {
                let component: $ty =
                    serde_json::from_value(value).map_err(|err| format!("{}: {err}", $name))?;
                world.entity_mut(e).insert(component);
            }
        };
    }
    take!("HexPosition", Position);
    take!("Unit", UnitInfo);
    take!("UnitCount", Headcount);
    take!("MovementPoints", MovePoints);
    take!("ActionPoints", ActionPoints);
    take!("SkillPoints", SkillPoints);
    take!("Combat", CombatStats);
    take!("CombatRoll", CombatRoll);
    take!("UnitStatus", Status);
    take!("MovementAnimation", Movement);
    Ok(())
}

pub fn export(world: &World, e: Entity, cold: &mut BTreeMap<String, Value>) {
    macro_rules! put {
        ($name:literal, $ty:ty) => {
            if let Some(component) = world.get::<$ty>(e) {
                cold.insert(
                    $name.into(),
                    serde_json::to_value(component).expect("finite typed component"),
                );
            }
        };
    }
    put!("HexPosition", Position);
    put!("Unit", UnitInfo);
    put!("UnitCount", Headcount);
    put!("MovementPoints", MovePoints);
    put!("ActionPoints", ActionPoints);
    put!("SkillPoints", SkillPoints);
    put!("Combat", CombatStats);
    put!("CombatRoll", CombatRoll);
    put!("UnitStatus", Status);
    put!("MovementAnimation", Movement);
}

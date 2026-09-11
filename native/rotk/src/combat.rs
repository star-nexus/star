//! Deterministic combat calculation. Permission checks belong to the action gate.
use crate::{
    components::{ActionPoints, CombatRoll, CombatStats, Headcount, Position, Status, UnitInfo},
    hex,
    runtime::{InitialComponents, Runtime},
};
use bevy_ecs::prelude::*;
use serde_json::{Value, json};

impl Runtime {
    pub(crate) fn component<T: Component>(&self, id: u64) -> Option<&T> {
        self.world
            .entity(id)
            .and_then(|e| self.world.ecs.get::<T>(e))
    }
    fn validate_attack(&self, a: u64, t: u64) -> Option<Value> {
        let ap = self.component::<Position>(a);
        let tp = self.component::<Position>(t);
        let combat = self.component::<CombatStats>(a);
        let count = self.component::<Headcount>(a);
        let au = self.component::<UnitInfo>(a);
        let tu = self.component::<UnitInfo>(t);
        let missing: Vec<_> = [
            ("attacker_pos", ap.is_some()),
            ("target_pos", tp.is_some()),
            ("attacker_combat", combat.is_some()),
            ("attacker_count", count.is_some()),
            ("attacker_unit", au.is_some()),
            ("target_unit", tu.is_some()),
        ]
        .into_iter()
        .filter_map(|(n, p)| (!p).then_some(n))
        .collect();
        let (error, details) = if !missing.is_empty() {
            (
                "missing_components",
                json!({"missing":missing,"attacker_entity":a,"target_entity":t,
                "suggestion":"Ensure both attacker and target units exist and are initialized correctly"}),
            )
        } else {
            let distance = hex::distance(ap.unwrap().hex(), tp.unwrap().hex());
            if distance > combat.unwrap().attack_range {
                (
                    "target_out_of_range",
                    json!({"attacker_entity":a,"target_entity":t,"distance":distance,
                    "attack_range":combat.unwrap().attack_range,"suggestion":"Move closer to the target before attacking"}),
                )
            } else if au.unwrap().faction == tu.unwrap().faction {
                (
                    "friendly_fire",
                    json!({"attacker_entity":a,"target_entity":t,"attacker_faction":au.unwrap().faction,
                    "target_faction":tu.unwrap().faction,"suggestion":"Select an enemy unit instead of a friendly unit"}),
                )
            } else {
                return None;
            }
        };
        Some(
            json!({"success":false,"error":error,"message":"Attack validation failed","details":details}),
        )
    }
    pub fn can_attack(&self, a: u64, t: Option<u64>) -> bool {
        self.component::<CombatStats>(a).is_some()
            && self
                .component::<Headcount>(a)
                .is_some_and(|c| c.current_count > 0)
            && self
                .component::<ActionPoints>(a)
                .is_some_and(|p| p.current_ap >= 1)
            && t.is_none_or(|t| self.validate_attack(a, t).is_none())
    }
    fn attack_rejection(&self, a: u64, t: u64) -> Value {
        if self.component::<CombatStats>(a).is_none() {
            return json!({"success":false,"error":"missing_components","message":"Attack validation failed",
                "details":{"missing":["attacker_combat"],"attacker_entity":a,"target_entity":t,
                "suggestion":"Ensure both attacker and target units exist and are initialized correctly"}});
        }
        if self
            .component::<Headcount>(a)
            .is_none_or(|c| c.current_count <= 0)
        {
            return json!({"success":false,"error":"unit_not_alive","message":"Attacker is destroyed and cannot attack",
                "details":{"attacker_entity":a,"current_count":self.component::<Headcount>(a).map(|c|c.current_count)}});
        }
        if self
            .component::<ActionPoints>(a)
            .is_none_or(|p| p.current_ap < 1)
        {
            return json!({"success":false,"error":"insufficient_action_points","message":"Insufficient action points for attack",
                "details":{"attacker_entity":a,"current_ap":self.component::<ActionPoints>(a).map(|p|p.current_ap),
                "required_ap":1,"suggestion":"Wait for action points to recover before attacking"}});
        }
        self.validate_attack(a, t).unwrap_or_else(|| {
            json!({"success":false,"error":"cannot_attack",
            "message":"Unit cannot attack","details":{"attacker_entity":a,"target_entity":t}})
        })
    }
    pub fn effective_stats(&self, id: u64) -> Result<(i64, i64), String> {
        let combat = self.component::<CombatStats>(id).ok_or("missing combat")?;
        let count = self.component::<Headcount>(id).ok_or("missing count")?;
        let status = self.component::<Status>(id).ok_or("missing status")?;
        let unit = self.component::<UnitInfo>(id).ok_or("missing unit")?;
        let pos = self.component::<Position>(id).ok_or("missing position")?;
        // Preserve the Python helper's historical falsy-ID-zero terrain lookup.
        let terrain = self
            .spatial
            .tiles
            .get(&pos.hex())
            .filter(|t| t.entity != 0)
            .map_or("plain", |t| t.terrain.as_str());
        let coeff = self.config.rules["terrain_coefficients"][terrain][&unit.unit_type]
            .as_f64()
            .unwrap_or(1.);
        let state = if status.current_status_is_enum {
            self.config.rules["state_coefficients"][&status.current_status]
                .as_f64()
                .unwrap_or(1.)
        } else {
            1.
        };
        Ok((
            (combat.base_attack as f64 * attack_multiplier(count.ratio()) * state * coeff) as i64,
            (combat.base_defense as f64 * 1. * state * coeff) as i64,
        ))
    }
    fn terrain_bonus(&self, id: u64, key: &str) -> f64 {
        let Some(pos) = self.component::<Position>(id) else {
            return 0.;
        };
        let Some(tile) = self.spatial.tiles.get(&pos.hex()).filter(|t| t.has_terrain) else {
            return 0.;
        };
        self.config.rules["terrain_effects"][&tile.terrain][key]
            .as_f64()
            .unwrap_or(0.)
    }
    pub fn calculate_damage(&mut self, a: u64, t: u64) -> Result<i64, String> {
        let attack = self.effective_stats(a)?.0 as f64 + self.terrain_bonus(a, "attack_bonus");
        let target = self.component::<UnitInfo>(t).ok_or("missing target unit")?;
        let defense = (self.effective_stats(t)?.1 + i64::from(target.unit_type == "infantry"))
            as f64
            + self.terrain_bonus(t, "defense_bonus");
        let mut damage = ((attack - (defense * 0.5) as i64 as f64).max(1.) * 1.) as i64;
        if self
            .component::<UnitInfo>(a)
            .is_some_and(|u| u.unit_type == "cavalry")
        {
            let e = self.world.entity(a).unwrap();
            if let Some(mut status) = self
                .world
                .ecs
                .get_mut::<Status>(e)
                .filter(|s| s.charge_stacks > 0)
            {
                damage = (damage as f64 * 1.5) as i64;
                status.charge_stacks = 0;
            }
        }
        Ok(damage.max(1))
    }
    pub fn execute_attack(&mut self, a: u64, t: u64) -> Result<Value, String> {
        if !self.can_attack(a, Some(t)) {
            return Ok(self.attack_rejection(a, t));
        }
        // R2 intermediate gate: presentation entity allocation and statistics
        // subscribers are added before this becomes the public Agent boundary.
        if self.config.display != "none" {
            return Err("native combat display handoff is not implemented yet".into());
        }
        let au = self.component::<UnitInfo>(a).unwrap().clone();
        let tu = self.component::<UnitInfo>(t).unwrap().clone();
        let attacker_count = self.component::<Headcount>(a).unwrap().current_count;
        let old_count = self
            .component::<Headcount>(t)
            .ok_or("missing target count")?
            .current_count;
        let ap = self.component::<ActionPoints>(a).unwrap().current_ap;
        let ae = self.world.entity(a).unwrap();
        let te = self.world.entity(t).unwrap();
        self.world.ecs.entity_mut(ae).insert(CombatRoll::default());
        let hit = self.rng.get("combat").randint(1, 20)?;
        self.world.ecs.get_mut::<CombatRoll>(ae).unwrap().hit_roll = Some(hit);
        // Fresh CombatRoll's forest penalty has no effect before the first roll.
        let base_damage = self.calculate_damage(a, t)?;
        let crit_roll = self.rng.get("combat").randint(1, 20)?;
        self.world.ecs.get_mut::<CombatRoll>(ae).unwrap().crit_roll = Some(crit_roll);
        let crit = crit_roll >= 19;
        let damage = if crit {
            (base_damage as f64 * 1.5) as i64
        } else {
            base_damage
        };
        let casualties = damage.min(old_count);
        let new_count = old_count - casualties;
        self.world
            .ecs
            .get_mut::<Headcount>(te)
            .unwrap()
            .current_count = new_count;
        self.world
            .ecs
            .get_mut::<ActionPoints>(ae)
            .unwrap()
            .current_ap -= 1;
        self.mark_ap_spent(a);
        for e in [ae, te] {
            if let Some(mut status) = self.world.ecs.get_mut::<Status>(e) {
                status.current_status = "normal".into();
                status.current_status_is_enum = true;
                status.status_duration = 0;
            }
        }
        let af = &au.faction;
        let tf = &tu.faction;
        let mut log = Vec::new();
        if crit {
            log.push("Critical hit! Damage ×1.5!".to_string());
        }
        log.push(if crit {
            format!(
                "{af} forces critical hit on {tf}! damage:{damage}, count:{old_count}->{new_count}"
            )
        } else {
            format!("{af} forces attacked {tf}! damage:{damage}, count:{old_count}->{new_count}")
        });
        let terrain_effects = json!({"attacker_terrain_bonus":self.terrain_bonus(a,"attack_bonus"),
            "target_terrain_defense":self.terrain_bonus(t,"defense_bonus")});
        self.record_combat(a, t, damage, new_count <= 0);
        self.events.push(json!({"type":"BattleEvent","fields":{"attacker_entity":a,"target_entity":t,"damage":damage}}));
        if new_count <= 0 {
            self.record_death(t, a);
            self.remove_combat_unit(t);
            log.push(format!("{tf} unit destroyed!"));
        }
        self.presentation_dirty.extend([a, t]);
        Ok(json!({"success":true,"battle_result":{
            "battle_type":if au.unit_type=="archer" {"ranged"} else {"melee"},"hit_success":true,
            "is_critical":crit,"damage_dealt":damage,"casualties_inflicted":casualties,"target_destroyed":new_count<=0,
            "attacker_casualties":0,"terrain_effects":terrain_effects,
            "dice_rolls":{"hit_roll":hit,"damage_roll":base_damage,"crit_roll":if crit {json!(true)} else {Value::Null}},
            "combat_log":log,"pre_battle_state":{"attacker_count":attacker_count,"target_count":old_count,"attacker_ap":ap},
            "post_battle_state":{"attacker_count":attacker_count,"target_count":new_count,"attacker_ap":ap-1},"action_points_consumed":1}}))
    }
    pub(crate) fn record_fallback_combat(&mut self, a: u64, t: u64, damage: i64) {
        let af = self.component::<UnitInfo>(a).unwrap().faction.clone();
        let tf = self.component::<UnitInfo>(t).unwrap().faction.clone();
        let turn = self
            .singletons
            .get("GameState")
            .map(|s| s["turn_number"].clone())
            .unwrap_or(Value::Null);
        let Some(stats) = self.singletons.get_mut("GameStats") else {
            return;
        };
        for f in [&af, &tf] {
            let factions = stats["faction_stats"]
                .as_object_mut()
                .expect("faction statistics");
            factions
                .entry(f.clone())
                .or_insert_with(|| json!({"kills":0,"losses":0,"damage_dealt":0,"damage_taken":0}));
        }
        for (f, key) in [(&af, "damage_dealt"), (&tf, "damage_taken")] {
            let v = &mut stats["faction_stats"][f][key];
            *v = json!(v.as_i64().unwrap_or(0) + damage);
        }
        stats["battle_history"]
            .as_array_mut()
            .expect("battle history")
            .push(json!({"turn":turn,"attacker":af,"target":tf,"damage":damage}));
    }
    fn remove_combat_unit(&mut self, id: u64) {
        let unit = self.component::<UnitInfo>(id).unwrap().clone();
        let pos = self.component::<Position>(id).map(|p| p.hex());
        if let Some(stats) = self.singletons.get_mut("GameStats")
            && let Some(f) = stats["faction_stats"].get_mut(&unit.faction)
        {
            f["losses"] = json!(f["losses"].as_i64().unwrap_or(0) + 1);
        }
        let player = self.world.ordered().find_map(|(_, e)| {
            self.world
                .ecs
                .get::<InitialComponents>(e)
                .and_then(|c| c.0.get("Player"))
                .filter(|p| p["faction"].as_str() == Some(&unit.faction))
                .map(|_| e)
        });
        if let Some(e) = player {
            let mut cold = self.world.ecs.get_mut::<InitialComponents>(e).unwrap();
            if let Some(units) = cold
                .0
                .get_mut("Player")
                .and_then(|p| p["units"]["$set"].as_array_mut())
            {
                units.retain(|v| v.as_u64() != Some(id));
            }
        }
        self.events
            .push(json!({"type":"UnitDeathEvent","fields":{"entity":id,"faction":unit.faction}}));
        if let Some(pos) = pos {
            self.spatial.remove(id, pos);
        }
        self.moving.remove(&id);
        self.vision_dirty.insert(id);
        self.world.remove(id);
        self.presentation_removed.push(id);
    }
}

pub fn attack_multiplier(h: f64) -> f64 {
    if h <= 0. {
        return 0.;
    }
    let w = 1. / (1. + (-(h - 0.3) / 0.035).exp());
    let linear = 0.92 + (1. - 0.92) / 0.7 * (h - 0.3);
    let power = 0.92 * (h / 0.3).powf(0.5550325);
    w * linear + (1. - w) * power
}

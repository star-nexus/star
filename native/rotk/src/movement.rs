//! MovementSystem and authoritative per-segment progression from AnimationSystem.
use crate::{
    components::{Headcount, MovePoints, Movement, Position, Status, UnitInfo},
    hex::{self, Hex},
    runtime::Runtime,
};
use serde_json::{Value, json};

fn pixel(cell: Hex, size: f64, pointy: bool) -> (f64, f64) {
    let (c, r) = cell;
    let sqrt3 = 1.7320508075688772;
    if pointy {
        (
            size * sqrt3 * (c as f64 + 0.5 * (r & 1) as f64),
            -size * 3. / 2. * r as f64,
        )
    } else {
        (
            size * 3. / 2. * c as f64,
            -size * sqrt3 * (r as f64 + 0.5 * (c & 1) as f64),
        )
    }
}

impl Runtime {
    pub fn plan_path(&self, id: u64, goal: Hex, cap: Option<i64>) -> Vec<Hex> {
        let Some(e) = self.world.entity(id) else {
            return vec![];
        };
        let Some(p) = self.world.ecs.get::<Position>(e) else {
            return vec![];
        };
        let faction = self
            .world
            .ecs
            .get::<UnitInfo>(e)
            .map(|u| u.faction.as_str());
        self.spatial.path(p.hex(), goal, id, faction, cap)
    }
    pub fn reachable(&self, id: u64) -> Vec<Hex> {
        let Some(e) = self.world.entity(id) else {
            return vec![];
        };
        let (Some(p), Some(mp), Some(count)) = (
            self.world.ecs.get::<Position>(e),
            self.world.ecs.get::<MovePoints>(e),
            self.world.ecs.get::<Headcount>(e),
        ) else {
            return vec![];
        };
        if count.current_count <= 0
            || mp.current_mp <= 0
            || self
                .world
                .ecs
                .get::<Movement>(e)
                .is_some_and(|m| m.is_moving)
            || self
                .world
                .ecs
                .get::<Status>(e)
                .is_some_and(|s| s.current_status == "confusion")
        {
            return vec![];
        }
        let faction = self
            .world
            .ecs
            .get::<UnitInfo>(e)
            .map(|u| u.faction.as_str());
        self.spatial
            .reachable(p.hex(), mp.spendable(count), id, faction)
            .into_iter()
            .filter(|&c| c != p.hex())
            .collect()
    }
    fn adjacent_free(&self, start: Hex, id: u64, faction: Option<&str>) -> Vec<Hex> {
        hex::neighbors(start)
            .into_iter()
            .filter(|&c| {
                self.spatial.tiles.contains_key(&c)
                    && !self.spatial.blocked(c, id, faction)
                    && !self.spatial.occupied(c, id)
            })
            .collect()
    }

    /// Low-level MovementSystem contract. The Agent gate is installed separately.
    pub fn move_unit(&mut self, id: u64, goal: Hex) -> Value {
        let entity = self.world.entity(id);
        let position = entity.and_then(|e| self.world.ecs.get::<Position>(e));
        let movement = entity.and_then(|e| self.world.ecs.get::<MovePoints>(e));
        let count = entity.and_then(|e| self.world.ecs.get::<Headcount>(e));
        let mut missing = Vec::new();
        if position.is_none() {
            missing.push("HexPosition");
        }
        if movement.is_none() {
            missing.push("MovementPoints");
        }
        if count.is_none() {
            missing.push("UnitCount");
        }
        if !missing.is_empty() {
            return json!({"success":false,"reason":"missing_components",
            "message":format!("Unit {id} missing required components: {}",missing.join(", ")),
            "unit_id":id,"missing_components":missing});
        }
        let e = entity.expect("validated entity");
        if self
            .world
            .ecs
            .get::<Movement>(e)
            .is_some_and(|m| m.is_moving)
        {
            return json!({"success":false,"reason":"already_moving","message":format!("Unit {id} is already moving"),"unit_id":id});
        }
        if self
            .world
            .ecs
            .get::<Status>(e)
            .is_some_and(|s| s.current_status == "confusion")
        {
            return json!({"success":false,"reason":"confused","message":format!("Unit {id} is confused and cannot move"),
                "unit_id":id,"current_status":"confusion","blocking_statuses":["confusion"],
                "suggestion":"Wait for confusion to clear or use skill to remove it"});
        }
        let mp = movement.expect("validated MP");
        let current_mp = mp.current_mp;
        let start = position.expect("validated position").hex();
        if current_mp <= 0 {
            return json!({"success":false,"reason":"no_mp","message":format!("Unit has no movement points left: {current_mp}"),
            "unit_id":id,"current_movement_points":current_mp,"suggestion":"Use end_turn tool or wait for movement points to recover"});
        }
        let effective = mp.effective(count.expect("validated count"));
        let budget = mp.spendable(count.expect("validated count"));
        let faction = self
            .world
            .ecs
            .get::<UnitInfo>(e)
            .map(|u| u.faction.as_str());
        if self.spatial.occupied(goal, id) {
            return json!({"success":false,"reason":"destination_occupied",
            "message":format!("Target position {} is already occupied by a unit",hex::repr(goal)),"unit_id":id,
            "start_position":start,"target_position":goal,
            "suggestion":"Pick an unoccupied hex; this unit's reachable list only contains hexes that were free when it was computed"});
        }
        let path = self.spatial.path(start, goal, id, faction, None);
        if path.len() < 2 {
            let distance = hex::distance(start, goal);
            let blocked = self.spatial.blocked(goal, id, faction);
            let adjacent = self.adjacent_free(start, id, faction);
            let mut causes = Vec::new();
            if distance > effective {
                causes.push("Target position out of movement range");
            }
            if blocked {
                causes.push("Target position blocked by obstacles");
            }
            causes.push("No valid route exists");
            return json!({"success":false,"reason":"no_path","message":format!("No valid path to target position {}",hex::repr(goal)),
                "unit_id":id,"start_position":start,"target_position":goal,"effective_movement":effective,
                "hex_distance":distance,"distance_exceeds_range":distance>effective,"target_blocked":blocked,
                "path_found":!path.is_empty(),"path_length":path.len(),"adjacent_free_positions":adjacent,
                "possible_causes":causes,"suggestion":if adjacent.is_empty() { "No adjacent free positions available".into() }
                    else { format!("Try one of these nearby positions: {}",hex::repr_list(&adjacent[..adjacent.len().min(3)])) }});
        }
        let cost: i64 = path[1..].iter().map(|&c| self.spatial.cost(c)).sum();
        if cost > budget {
            let mut consumed = 0;
            let mut reachable = Vec::new();
            for &cell in &path[1..] {
                let cost = self.spatial.cost(cell);
                if consumed + cost > budget {
                    break;
                }
                consumed += cost;
                if !self.spatial.occupied(cell, id) {
                    reachable.push(cell);
                }
            }
            let closest = reachable.last().copied().unwrap_or(start);
            let mut nearby: Vec<_> = self
                .adjacent_free(start, id, faction)
                .into_iter()
                .filter(|&c| self.spatial.cost(c) <= budget)
                .collect();
            nearby.sort_by_key(|&c| hex::distance(c, goal));
            nearby.truncate(3);
            let (suggestion, target) = if closest != start {
                (
                    format!(
                        "Try moving to the farthest hex on this path this turn: {}",
                        hex::repr(closest)
                    ),
                    Some(closest),
                )
            } else if !nearby.is_empty() {
                (
                    format!(
                        "No step along the path is reachable this turn. Try one of these nearby positions: {}",
                        hex::repr_list(&nearby)
                    ),
                    Some(nearby[0]),
                )
            } else {
                (
                    "No nearby reachable positions this turn. Wait to recover movement points."
                        .into(),
                    None,
                )
            };
            let terrain_costs:Vec<_> = path[1..].iter().enumerate().map(|(i,&(col,row))| json!({"position":{"col":col,"row":row},
                "terrain":self.spatial.terrain((col,row)),"movement_cost":self.spatial.cost((col,row)),"step":i+1})).collect();
            let farthest = json!({"col":closest.0,"row":closest.1});
            let mut result = json!({"success":false,"reason":"insufficient_mp","failure_reason":"insufficient_movement_points",
                "message":format!("Shortest path costs {cost} MP; unit has {budget} MP. Farthest reachable hex along this path: ({}, {}).",closest.0,closest.1),
                "unit_id":id,"required_movement_points":cost,"current_movement_points":current_mp,"deficit":cost-budget,
                "path":path,"path_length":path.len()-1,"effective_movement":effective,"terrain_costs":terrain_costs,
                "closest_reachable_position":farthest,"farthest_reachable_on_path":farthest,"reachable_steps":reachable.len(),
                "nearby_reachable_positions":nearby.iter().map(|&(c,r)|json!({"col":c,"row":r})).collect::<Vec<_>>(),"suggestion":suggestion});
            if let Some((col, row)) = target {
                result["suggested_action"] = json!({"action":"move","params":{"unit_id":id,"target_position":{"col":col,"row":row}}});
            }
            return result;
        }
        self.world
            .ecs
            .get_mut::<MovePoints>(e)
            .expect("MP")
            .current_mp -= cost;
        self.mark_mp_spent(id);
        let animated = self.config.display != "none";
        if animated {
            if self.world.ecs.get::<Movement>(e).is_none() {
                self.world.ecs.entity_mut(e).insert(Movement::default());
            }
            let mut animation = self.world.ecs.get_mut::<Movement>(e).expect("movement");
            animation.path = path[1..].to_vec();
            animation.current_target_index = 0;
            animation.progress = 0.;
            animation.is_moving = true;
            let size = self.config.rules["hex_size"].as_f64().unwrap_or(50.);
            let pointy = self.config.rules["hex_orientation"].as_str() == Some("pointy");
            animation.start_pixel_pos = Some(pixel(start, size, pointy));
            animation.target_pixel_pos = Some(pixel(path[1], size, pointy));
            self.moving.insert(id);
        } else {
            let mut p = self.world.ecs.get_mut::<Position>(e).expect("position");
            p.col = goal.0;
            p.row = goal.1;
            self.spatial.moved(id, start, goal);
        }
        self.presentation_dirty.insert(id);
        self.record_movement(id, start, goal);
        json!({"success":true,"path":path,"cost":cost,"from":start,"to":goal,"animated":animated})
    }

    pub(crate) fn advance_movement(&mut self, dt: f64) {
        if self.config.display == "none" || self.moving.is_empty() {
            return;
        }
        let size = self.config.rules["hex_size"].as_f64().unwrap_or(50.);
        let pointy = self.config.rules["hex_orientation"].as_str() == Some("pointy");
        let mut finished = Vec::new();
        let mut query = self.world.ecs.query::<(&mut Position, &mut Movement)>();
        for &id in &self.moving {
            let Some(e) = self.world.entity(id) else {
                finished.push(id);
                continue;
            };
            let Ok((mut position, mut anim)) = query.get_mut(&mut self.world.ecs, e) else {
                finished.push(id);
                continue;
            };
            if !anim.is_moving {
                finished.push(id);
                continue;
            }
            if anim.path.is_empty() || anim.current_target_index >= anim.path.len() {
                anim.is_moving = false;
                anim.progress = 0.;
                anim.current_target_index = 0;
                anim.path.clear();
                finished.push(id);
                continue;
            }
            anim.progress += anim.speed * dt;
            while anim.is_moving
                && anim.current_target_index < anim.path.len()
                && anim.progress >= 1. - 1e-12
            {
                let target = anim.path[anim.current_target_index];
                let old = position.hex();
                position.col = target.0;
                position.row = target.1;
                self.spatial.moved(id, old, target);
                if old != target && self.config.display == "window" {
                    self.vision_dirty.insert(id);
                }
                anim.current_target_index += 1;
                anim.progress = (anim.progress - 1.).max(0.);
                if anim.current_target_index >= anim.path.len() {
                    anim.is_moving = false;
                    anim.progress = 0.;
                } else {
                    anim.start_pixel_pos = Some(pixel(target, size, pointy));
                    anim.target_pixel_pos =
                        Some(pixel(anim.path[anim.current_target_index], size, pointy));
                }
            }
            self.presentation_dirty.insert(id);
            if !anim.is_moving {
                finished.push(id);
            }
        }
        for id in finished {
            self.moving.remove(&id);
        }
    }
}

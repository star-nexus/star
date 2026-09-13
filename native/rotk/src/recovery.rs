//! R0 resource scheduler, including MP's next-boundary timer semantics.
use crate::{
    components::{ActionPoints, MovePoints, SkillPoints},
    runtime::Runtime,
};
use serde::{Deserialize, Serialize};
use star_core::{deadline::Deadlines, world::OrderedWorld};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Recovery {
    pub enabled: bool,
    pub ap_interval: f64,
    pub ap_amount: i64,
    pub mp_interval: f64,
    pub skill_interval: f64,
    pub last: Option<f64>,
    pub known: u64,
    pub ap: Deadlines,
    pub mp: Deadlines,
    pub skill: Deadlines,
    pub ap_elapsed: BTreeMap<u64, f64>,
    pub mp_elapsed: BTreeMap<u64, f64>,
    pub skill_elapsed: BTreeMap<u64, f64>,
    pub mp_last_points: BTreeMap<u64, i64>,
    pub mp_pending: BTreeSet<u64>,
}
impl Recovery {
    pub fn validate(&self, counter: u64) -> Result<(), String> {
        if [self.ap_interval, self.mp_interval, self.skill_interval]
            .iter()
            .any(|v| !v.is_finite() || *v <= 0.)
            || self.last.is_some_and(|v| !v.is_finite() || v < 0.)
            || self.known > counter
            || self
                .ap_elapsed
                .values()
                .chain(self.mp_elapsed.values())
                .chain(self.skill_elapsed.values())
                .any(|v| !v.is_finite() || *v < 0.)
        {
            return Err("invalid recovery ledger".into());
        }
        Ok(())
    }
    pub fn mark_ap(&mut self, world: &OrderedWorld, id: u64, elapsed: f64) {
        let Some(ap) = world
            .entity(id)
            .and_then(|e| world.ecs.get::<ActionPoints>(e))
        else {
            return;
        };
        if ap.current_ap < ap.max_ap && !self.ap.contains(id) {
            self.ap_elapsed.insert(id, 0.);
            self.ap
                .schedule(id, self.last.unwrap_or(elapsed) + self.ap_interval);
        }
    }
    pub fn mark_mp(&mut self, world: &OrderedWorld, id: u64) {
        let Some(mp) = world
            .entity(id)
            .and_then(|e| world.ecs.get::<MovePoints>(e))
        else {
            return;
        };
        if mp.current_mp < mp.max_mp {
            self.mp.cancel(id);
            self.mp_pending.insert(id);
            self.mp_elapsed.insert(id, 0.);
            self.mp_last_points.insert(id, mp.current_mp);
        }
    }
    pub fn mark_skill(&mut self, world: &OrderedWorld, id: u64, elapsed: f64) {
        let Some(sp) = world
            .entity(id)
            .and_then(|e| world.ecs.get::<SkillPoints>(e))
        else {
            return;
        };
        if !sp.skill_cooldowns.is_empty() && !self.skill.contains(id) {
            self.skill_elapsed.insert(id, 0.);
            self.skill
                .schedule(id, self.last.unwrap_or(elapsed) + self.skill_interval);
        }
    }
    fn cancel_ap(&mut self, id: u64) {
        self.ap.cancel(id);
        self.ap_elapsed.remove(&id);
    }
    fn cancel_mp(&mut self, id: u64) {
        self.mp.cancel(id);
        self.mp_pending.remove(&id);
        self.mp_elapsed.remove(&id);
        self.mp_last_points.remove(&id);
    }
    fn cancel_skill(&mut self, id: u64) {
        self.skill.cancel(id);
        self.skill_elapsed.remove(&id);
    }
    pub fn update(&mut self, world: &mut OrderedWorld, now: f64, dirty: &mut BTreeSet<u64>) {
        let Some(last) = self.last else {
            self.last = Some(now);
            return;
        };
        if now - last <= 0. {
            return;
        }
        // Only new IDs are audited, never all resident Units on each tick.
        for id in self.known..world.next_id() {
            self.mark_ap(world, id, last);
            if !self.mp.contains(id)
                && world
                    .entity(id)
                    .and_then(|e| world.ecs.get::<MovePoints>(e))
                    .is_some_and(|m| m.current_mp < m.max_mp)
            {
                self.mp_pending.insert(id);
            }
            self.mark_skill(world, id, last);
        }
        self.known = self.known.max(world.next_id());
        self.last = Some(now);
        for id in std::mem::take(&mut self.mp_pending) {
            let points = world
                .entity(id)
                .and_then(|e| world.ecs.get::<MovePoints>(e));
            if let Some(mp) = points.filter(|m| m.current_mp < m.max_mp) {
                self.mp_elapsed.insert(id, 0.);
                self.mp_last_points.insert(id, mp.current_mp);
                self.mp.schedule(id, now + self.mp_interval);
            } else {
                self.cancel_mp(id);
            }
        }
        while let Some((due, entries)) = self.ap.pop_due(now) {
            let ticks = python_floor_div(now - due, self.ap_interval) + 1.;
            for (version, id) in entries {
                if !self.ap.is_current(id, due, version) {
                    continue;
                }
                let ap = world
                    .entity(id)
                    .and_then(|e| world.ecs.get_mut::<ActionPoints>(e));
                let Some(mut ap) = ap.filter(|p| p.current_ap < p.max_ap) else {
                    self.cancel_ap(id);
                    continue;
                };
                let amount = (self.ap_amount.max(0) as f64 * ticks).min(i64::MAX as f64) as i64;
                ap.current_ap = ap.max_ap.min(ap.current_ap.saturating_add(amount));
                dirty.insert(id);
                if ap.current_ap >= ap.max_ap {
                    self.cancel_ap(id)
                } else {
                    let next = due + self.ap_interval * ticks;
                    self.ap_elapsed
                        .insert(id, (self.ap_interval - (next - now)).max(0.));
                    self.ap.schedule(id, next);
                }
            }
        }
        while let Some((due, entries)) = self.mp.pop_due(now) {
            for (version, id) in entries {
                if !self.mp.is_current(id, due, version) {
                    continue;
                }
                if let Some(mut mp) = world
                    .entity(id)
                    .and_then(|e| world.ecs.get_mut::<MovePoints>(e))
                {
                    mp.current_mp = mp.max_mp;
                    mp.has_moved = false;
                    dirty.insert(id);
                }
                self.cancel_mp(id);
            }
        }
        while let Some((due, entries)) = self.skill.pop_due(now) {
            let ticks = python_floor_div(now - due, self.skill_interval) + 1.;
            for (version, id) in entries {
                if !self.skill.is_current(id, due, version) {
                    continue;
                }
                let sp = world
                    .entity(id)
                    .and_then(|e| world.ecs.get_mut::<SkillPoints>(e));
                let Some(mut sp) = sp.filter(|p| !p.skill_cooldowns.is_empty()) else {
                    self.cancel_skill(id);
                    continue;
                };
                let ticks = ticks.min(i64::MAX as f64) as i64;
                sp.skill_cooldowns.retain(|_, remaining| {
                    *remaining = remaining.saturating_sub(ticks);
                    *remaining > 0
                });
                dirty.insert(id);
                if sp.skill_cooldowns.is_empty() {
                    self.cancel_skill(id)
                } else {
                    let next = due + self.skill_interval * ticks as f64;
                    self.skill_elapsed
                        .insert(id, (self.skill_interval - (next - now)).max(0.));
                    self.skill.schedule(id, next);
                }
            }
        }
    }
}

/// CPython float // derives the quotient from fmod, including its rounding
/// correction; plain floor(a/b) differs at values such as 1.0 // 0.1.
fn python_floor_div(a: f64, b: f64) -> f64 {
    let remainder = a % b;
    let div = (a - remainder) / b;
    let floor = div.floor();
    if div - floor > 0.5 { floor + 1. } else { floor }
}

impl Runtime {
    pub fn mark_ap_spent(&mut self, id: u64) {
        self.presentation_dirty.insert(id);
        if let Some(r) = &mut self.recovery {
            r.mark_ap(&self.world, id, self.clock.elapsed);
        }
    }
    pub fn mark_mp_spent(&mut self, id: u64) {
        self.presentation_dirty.insert(id);
        if let Some(r) = &mut self.recovery {
            r.mark_mp(&self.world, id);
        }
    }
    pub fn mark_skill_started(&mut self, id: u64) {
        self.presentation_dirty.insert(id);
        if let Some(r) = &mut self.recovery {
            r.mark_skill(&self.world, id, self.clock.elapsed);
        }
    }
    pub fn advance_recovery(&mut self) {
        if self.clock.realtime
            && let Some(r) = self.recovery.as_mut().filter(|r| r.enabled)
        {
            r.update(
                &mut self.world,
                self.clock.elapsed,
                &mut self.presentation_dirty,
            );
        }
    }
}

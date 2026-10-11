//! Stable, versioned deadline buckets. No scan of inactive entities per tick.
use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::BTreeMap;

#[derive(Clone, Copy, Debug, PartialEq)]
struct Time(f64);
impl Eq for Time {}
impl Ord for Time {
    fn cmp(&self, other: &Self) -> Ordering {
        self.0.total_cmp(&other.0)
    }
}
impl PartialOrd for Time {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DeadlineState {
    pub buckets: Vec<(f64, Vec<(u64, u64)>)>, // time -> (version, external ID), insertion order
    pub active: Vec<(u64, (f64, u64))>,
    pub versions: Vec<(u64, u64)>,
}

#[derive(Default)]
pub struct Deadlines {
    buckets: BTreeMap<Time, Vec<(u64, u64)>>,
    active: BTreeMap<u64, (f64, u64)>,
    versions: BTreeMap<u64, u64>,
}
impl Serialize for Deadlines {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        self.state().serialize(serializer)
    }
}
impl<'de> Deserialize<'de> for Deadlines {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        Self::restore(DeadlineState::deserialize(deserializer)?).map_err(serde::de::Error::custom)
    }
}
impl Deadlines {
    pub fn restore(state: DeadlineState) -> Result<Self, String> {
        let mut out = Self::default();
        for (id, version) in state.versions {
            if version == 0 || out.versions.insert(id, version).is_some() {
                return Err("invalid deadline version".into());
            }
        }
        for (due, entries) in state.buckets {
            if !due.is_finite()
                || due < 0.
                || entries.is_empty()
                || entries
                    .iter()
                    .any(|(v, id)| *v == 0 || out.versions.get(id).is_none_or(|max| v > max))
                || out.buckets.insert(Time(due), entries).is_some()
            {
                return Err("invalid deadline bucket".into());
            }
        }
        for (id, (due, version)) in state.active {
            if !due.is_finite()
                || due < 0.
                || out.versions.get(&id) != Some(&version)
                || out
                    .buckets
                    .get(&Time(due))
                    .is_none_or(|b| b.iter().filter(|x| **x == (version, id)).count() != 1)
                || out.active.insert(id, (due, version)).is_some()
            {
                return Err("invalid active deadline".into());
            }
        }
        Ok(out)
    }
    pub fn state(&self) -> DeadlineState {
        DeadlineState {
            buckets: self.buckets.iter().map(|(t, b)| (t.0, b.clone())).collect(),
            active: self.active.iter().map(|(id, d)| (*id, *d)).collect(),
            versions: self.versions.iter().map(|(id, v)| (*id, *v)).collect(),
        }
    }
    fn next_version(&mut self, id: u64) -> u64 {
        let version = self.versions.entry(id).or_default();
        *version = version.checked_add(1).expect("deadline version exhausted");
        *version
    }
    pub fn schedule(&mut self, id: u64, due: f64) {
        assert!(due.is_finite() && due >= 0., "invalid internal deadline");
        let version = self.next_version(id);
        self.active.insert(id, (due, version));
        self.buckets
            .entry(Time(due))
            .or_default()
            .push((version, id));
    }
    pub fn cancel(&mut self, id: u64) {
        self.active.remove(&id);
        self.next_version(id);
    }
    pub fn contains(&self, id: u64) -> bool {
        self.active.contains_key(&id)
    }
    pub fn is_current(&self, id: u64, due: f64, version: u64) -> bool {
        self.active.get(&id) == Some(&(due, version))
    }
    /// Read-only bucket test includes stale entries, which still cost work to drain.
    pub fn has_due(&self, now: f64) -> bool {
        self.buckets
            .first_key_value()
            .is_some_and(|(t, _)| t.0 <= now)
    }
    pub fn pop_due(&mut self, now: f64) -> Option<(f64, Vec<(u64, u64)>)> {
        if self
            .buckets
            .first_key_value()
            .is_some_and(|(t, _)| t.0 <= now)
        {
            self.buckets.pop_first().map(|(t, b)| (t.0, b))
        } else {
            None
        }
    }
    pub fn len(&self) -> usize {
        self.active.len()
    }
    pub fn is_empty(&self) -> bool {
        self.active.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn shared_bucket_preserves_order_and_canceled_work_cannot_fire() {
        let mut q = Deadlines::default();
        q.schedule(9, 1.);
        q.schedule(2, 1.);
        q.cancel(9);
        q.schedule(9, 2.);
        let state = q.state();
        let mut q = Deadlines::restore(state).unwrap();
        assert!(q.pop_due(0.99).is_none());
        let (due, b) = q.pop_due(1.).unwrap();
        assert_eq!(b, vec![(1, 9), (1, 2)]);
        assert!(!q.is_current(9, due, 1));
        assert!(q.is_current(2, due, 1));
        assert_eq!(q.pop_due(10.).unwrap(), (2., vec![(3, 9)]));
    }
}

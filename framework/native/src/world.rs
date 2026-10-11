use bevy_ecs::prelude::*;
use std::collections::BTreeMap;

/// Stable wire ID; Bevy's generation/index never crosses the language boundary.
#[derive(Component, Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct ExternalId(pub u64);

pub struct OrderedWorld {
    pub ecs: World,
    ids: BTreeMap<u64, Entity>,
    next_id: u64,
}

impl OrderedWorld {
    pub fn new(next_id: u64) -> Self {
        Self {
            ecs: World::new(),
            ids: BTreeMap::new(),
            next_id,
        }
    }
    pub fn import(&mut self, id: u64) -> Result<Entity, String> {
        if id >= self.next_id || self.ids.contains_key(&id) {
            return Err(format!("duplicate or out-of-range entity ID {id}"));
        }
        let entity = self.ecs.spawn(ExternalId(id)).id();
        self.ids.insert(id, entity);
        Ok(entity)
    }
    pub fn spawn(&mut self) -> Result<(u64, Entity), String> {
        let id = self.next_id;
        self.next_id = id.checked_add(1).ok_or("entity ID exhausted")?;
        let entity = self.ecs.spawn(ExternalId(id)).id();
        self.ids.insert(id, entity);
        Ok((id, entity))
    }
    pub fn entity(&self, id: u64) -> Option<Entity> {
        self.ids.get(&id).copied()
    }
    pub fn ordered(&self) -> impl Iterator<Item = (u64, Entity)> + '_ {
        self.ids.iter().map(|(&id, &e)| (id, e))
    }
    pub fn next_id(&self) -> u64 {
        self.next_id
    }
    pub fn remove(&mut self, id: u64) -> bool {
        self.ids
            .remove(&id)
            .is_some_and(|entity| self.ecs.despawn(entity))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn ids_survive_archetype_moves_and_never_reuse_despawned_ids() {
        let mut w = OrderedWorld::new(100);
        let b = w.import(9).unwrap();
        let a = w.import(0).unwrap();
        #[derive(Component)]
        struct Marker;
        w.ecs.entity_mut(a).insert(Marker);
        assert_eq!(w.ordered().collect::<Vec<_>>(), [(0, a), (9, b)]);
        assert!(w.import(9).is_err());
        assert!(w.import(100).is_err());
        assert!(w.remove(0));
        assert_eq!(w.spawn().unwrap().0, 100);
        assert_eq!(w.entity(9), Some(b));
    }
}

//! Bounded direct tile lookup with sparse fallback. Values have one owner.
use crate::{hex::Hex, spatial::TileInfo};
use std::collections::HashMap;

const MAX_SLOTS: usize = 1_000_000;

struct Dense {
    origin: Hex,
    width: usize,
    height: usize,
    slots: Vec<Option<usize>>,
    rows: Vec<Option<(Hex, TileInfo)>>,
    free: Vec<usize>,
    overflow: HashMap<Hex, usize>,
    len: usize,
}

impl Dense {
    fn slot(&self, cell: Hex) -> Option<usize> {
        let x = usize::try_from(cell.0.checked_sub(self.origin.0)?).ok()?;
        let y = usize::try_from(cell.1.checked_sub(self.origin.1)?).ok()?;
        (x < self.width && y < self.height).then(|| y * self.width + x)
    }
    fn index(&self, cell: Hex) -> Option<usize> {
        match self.slot(cell) {
            Some(slot) => self.slots[slot],
            None => self.overflow.get(&cell).copied(),
        }
    }
    fn insert(&mut self, cell: Hex, tile: TileInfo) -> Option<TileInfo> {
        if let Some(index) = self.index(cell) {
            return self.rows[index].replace((cell, tile)).map(|(_, t)| t);
        }
        let index = if let Some(index) = self.free.pop() {
            self.rows[index] = Some((cell, tile));
            index
        } else {
            self.rows.push(Some((cell, tile)));
            self.rows.len() - 1
        };
        if let Some(slot) = self.slot(cell) {
            self.slots[slot] = Some(index);
        } else {
            self.overflow.insert(cell, index);
        }
        self.len += 1;
        None
    }
}

#[derive(Default)]
pub struct TileMap {
    sparse: HashMap<Hex, TileInfo>,
    dense: Option<Dense>,
    requested: bool,
}

impl TileMap {
    pub fn get(&self, cell: &Hex) -> Option<&TileInfo> {
        match &self.dense {
            Some(d) => d
                .index(*cell)
                .and_then(|i| d.rows[i].as_ref().map(|(_, t)| t)),
            None => self.sparse.get(cell),
        }
    }
    pub fn get_mut(&mut self, cell: &Hex) -> Option<&mut TileInfo> {
        match &mut self.dense {
            Some(d) => d
                .index(*cell)
                .and_then(|i| d.rows[i].as_mut().map(|(_, t)| t)),
            None => self.sparse.get_mut(cell),
        }
    }
    pub fn contains_key(&self, cell: &Hex) -> bool {
        match &self.dense {
            Some(d) => d.index(*cell).is_some(),
            None => self.sparse.contains_key(cell),
        }
    }
    pub fn insert(&mut self, cell: Hex, tile: TileInfo) -> Option<TileInfo> {
        match &mut self.dense {
            Some(d) => d.insert(cell, tile),
            None => self.sparse.insert(cell, tile),
        }
    }
    pub fn remove(&mut self, cell: &Hex) -> Option<TileInfo> {
        match &mut self.dense {
            Some(d) => {
                let i = d.index(*cell)?;
                if let Some(slot) = d.slot(*cell) {
                    d.slots[slot] = None;
                } else {
                    d.overflow.remove(cell);
                }
                d.len -= 1;
                d.free.push(i);
                d.rows[i].take().map(|(_, t)| t)
            }
            None => self.sparse.remove(cell),
        }
    }
    pub fn len(&self) -> usize {
        self.dense.as_ref().map_or(self.sparse.len(), |d| d.len)
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
    pub fn iter(&self) -> impl Iterator<Item = (&Hex, &TileInfo)> {
        self.sparse.iter().chain(self.dense.iter().flat_map(|d| {
            d.rows
                .iter()
                .filter_map(|v| v.as_ref().map(|(cell, tile)| (cell, tile)))
        }))
    }
    pub fn keys(&self) -> impl Iterator<Item = &Hex> {
        self.iter().map(|(cell, _)| cell)
    }
    pub fn set_dense(&mut self, enabled: bool) {
        self.requested = enabled;
        if !enabled {
            if let Some(d) = self.dense.take() {
                self.sparse.extend(d.rows.into_iter().flatten());
            }
            return;
        }
        if self.dense.is_some() || self.sparse.is_empty() {
            return;
        }
        let min_x = self.sparse.keys().map(|c| c.0).min().unwrap();
        let min_y = self.sparse.keys().map(|c| c.1).min().unwrap();
        let max_x = self.sparse.keys().map(|c| c.0).max().unwrap();
        let max_y = self.sparse.keys().map(|c| c.1).max().unwrap();
        let extent = |lo: i64, hi: i64| {
            hi.checked_sub(lo)?
                .checked_add(1)
                .and_then(|n| usize::try_from(n).ok())
        };
        let Some((width, height, area)) = extent(min_x, max_x)
            .zip(extent(min_y, max_y))
            .and_then(|(w, h)| w.checked_mul(h).map(|area| (w, h, area)))
        else {
            return;
        };
        if area > MAX_SLOTS || area > self.sparse.len().saturating_mul(2) {
            return;
        }
        // Capture the old iterator before removing anything; do not impose new order.
        let order: Vec<_> = self.sparse.keys().copied().collect();
        let mut d = Dense {
            origin: (min_x, min_y),
            width,
            height,
            slots: vec![None; area],
            rows: Vec::with_capacity(order.len()),
            free: vec![],
            overflow: HashMap::new(),
            len: 0,
        };
        for cell in order {
            d.insert(cell, self.sparse.remove(&cell).unwrap());
        }
        self.sparse.shrink_to_fit();
        self.dense = Some(d);
    }
    pub fn diagnostics(&self) -> serde_json::Value {
        serde_json::json!({"requested":self.requested,"active":self.dense.is_some(),"tiles":self.len(),
            "slots":self.dense.as_ref().map_or(0,|d|d.slots.len()),
            "rows":self.dense.as_ref().map_or(0,|d|d.rows.len()),
            "overflow":self.dense.as_ref().map_or(0,|d|d.overflow.len())})
    }
}
impl std::ops::Index<&Hex> for TileMap {
    type Output = TileInfo;
    fn index(&self, cell: &Hex) -> &Self::Output {
        self.get(cell).expect("no entry found for key")
    }
}
impl FromIterator<(Hex, TileInfo)> for TileMap {
    fn from_iter<I: IntoIterator<Item = (Hex, TileInfo)>>(i: I) -> Self {
        Self {
            sparse: i.into_iter().collect(),
            ..Default::default()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn tile(id: u64) -> TileInfo {
        TileInfo {
            entity: id,
            terrain: "雪原🗺".into(),
            cost: 1,
            has_terrain: true,
        }
    }
    #[test]
    fn dense_holes_overflow_mutation_and_switch_own_values() {
        let mut m: TileMap = [
            ((-2, -2), tile(0)),
            ((-1, -2), tile(1)),
            ((-2, -1), tile(2)),
        ]
        .into_iter()
        .collect();
        let order: Vec<_> = m.keys().copied().collect();
        m.set_dense(true);
        assert_eq!(m.keys().copied().collect::<Vec<_>>(), order);
        assert!(m.dense.is_some());
        assert!(!m.contains_key(&(-1, -1)));
        assert!(m.get(&(i64::MAX, i64::MIN)).is_none());
        m.get_mut(&(-2, -2)).unwrap().cost = 999;
        assert_eq!(m.remove(&(-1, -2)).unwrap().entity, 1);
        for id in 3..100 {
            m.insert((i64::MAX, i64::MIN), tile(id));
            assert_eq!(m.remove(&(i64::MAX, i64::MIN)).unwrap().entity, id);
        }
        assert_eq!(m.dense.as_ref().unwrap().rows.len(), 3);
        m.insert((-1, -1), tile(100));
        m.insert((500, 600), tile(101));
        assert_eq!(m.get(&(500, 600)).unwrap().entity, 101);
        m.set_dense(false);
        assert_eq!(m.len(), 4);
        assert_eq!(m[&(-2, -2)].cost, 999);
        m.set_dense(true);
        assert!(m.dense.is_none()); // expanded sparse bounds
        assert_eq!(m[&(-1, -1)].entity, 100);
    }
    #[test]
    fn sparse_extreme_and_empty_maps_do_not_allocate_by_coordinate_span() {
        let mut empty = TileMap::default();
        empty.set_dense(true);
        assert!(empty.is_empty());
        for (a, b) in [((0, 0), (100000, 100000)), ((i64::MIN, 0), (i64::MAX, 0))] {
            let mut m: TileMap = [(a, tile(1)), (b, tile(2))].into_iter().collect();
            m.set_dense(true);
            assert!(m.dense.is_none());
            assert_eq!(m[&a].entity, 1);
        }
    }
}

//! E10 instance-owned, opt-in window history storage. JSON rows stay owned.
//! The array slot is an empty placeholder only while `rows` owns the history;
//! Runtime export materializes the logical array without changing this owner.
use crate::statistics::StatisticsTimings;
use serde_json::Value;
use std::collections::{BTreeMap, VecDeque};

impl crate::runtime::Runtime {
    pub fn set_statistics_history_mode(&mut self, mode: &str) -> Result<(), String> {
        if !matches!(mode, "baseline" | "deque") {
            return Err("invalid statistics history mode".into());
        }
        self.statistics_history
            .configure(mode, &mut self.singletons);
        Ok(())
    }
}

#[derive(Default)]
pub(crate) struct StatisticsHistory {
    deque: bool,
    rows: Option<VecDeque<Value>>,
}

impl StatisticsHistory {
    pub(crate) fn configure(&mut self, mode: &str, singletons: &mut BTreeMap<String, Value>) {
        if mode == "baseline"
            && let Some(rows) = self.rows.take()
        {
            singletons.get_mut("GameStats").expect("history owner")["unit_observation_history"] =
                Value::Array(rows.into());
        }
        self.deque = mode == "deque";
    }

    pub(crate) fn export_into(&self, singletons: &mut BTreeMap<String, Value>) {
        if let Some(rows) = &self.rows {
            singletons.get_mut("GameStats").expect("history owner")["unit_observation_history"] =
                Value::Array(rows.iter().cloned().collect());
        }
    }

    fn access<'a, const PROFILE: bool>(
        &'a mut self,
        singletons: &'a mut BTreeMap<String, Value>,
        window: bool,
        append: bool,
        timings: &mut StatisticsTimings,
    ) -> HistoryMut<'a> {
        if window
            && self.deque
            && let Some(ref mut rows) = self.rows
        {
            return HistoryMut::Deque(rows);
        }
        let array = &mut singletons.get_mut("GameStats").unwrap()["unit_observation_history"];
        let array = if append {
            array.as_array_mut().expect("observation history")
        } else {
            array.as_array_mut().unwrap()
        };
        if window && self.deque && append {
            let mark = PROFILE.then(std::time::Instant::now);
            // Move only on the first real history access, after row validation
            // and component writes. Never validate malformed imports early.
            self.rows = Some(std::mem::take(array).into());
            if let Some(mark) = mark {
                timings.history_transfer_ns += mark.elapsed().as_nanos() as u64;
                timings.history_transfers += 1;
            }
            HistoryMut::Deque(self.rows.as_mut().unwrap())
        } else {
            HistoryMut::Array(array)
        }
    }

    pub(crate) fn append<const PROFILE: bool>(
        &mut self,
        singletons: &mut BTreeMap<String, Value>,
        row: Value,
        window: bool,
        timings: &mut StatisticsTimings,
    ) {
        let mut history = self.access::<PROFILE>(singletons, window, true, timings);
        let mark = PROFILE.then(std::time::Instant::now);
        history.push(row);
        if let Some(mark) = mark {
            timings.history_append_ns += mark.elapsed().as_nanos() as u64;
            timings.history_appended += 1;
            timings.history_max_len = timings.history_max_len.max(history.len());
        }
        if !window && history.len() > 10000 {
            let mark = PROFILE.then(std::time::Instant::now);
            history.trim::<PROFILE>(5000, timings);
            if let Some(mark) = mark {
                timings.trim_ns += mark.elapsed().as_nanos() as u64;
            }
        }
    }

    pub(crate) fn trim_window<const PROFILE: bool>(
        &mut self,
        singletons: &mut BTreeMap<String, Value>,
        limit: usize,
        timings: &mut StatisticsTimings,
    ) {
        let mut history = self.access::<PROFILE>(singletons, true, false, timings);
        if PROFILE {
            timings.history_before_trim = history.len();
        }
        history.trim::<PROFILE>(limit, timings);
        if PROFILE {
            timings.history_after_trim = history.len();
            timings.history_wrapped =
                matches!(&history, HistoryMut::Deque(q) if !q.as_slices().1.is_empty());
        }
    }
}

enum HistoryMut<'a> {
    Array(&'a mut Vec<Value>),
    Deque(&'a mut VecDeque<Value>),
}

impl HistoryMut<'_> {
    fn len(&self) -> usize {
        match self {
            Self::Array(v) => v.len(),
            Self::Deque(v) => v.len(),
        }
    }
    fn push(&mut self, row: Value) {
        match self {
            Self::Array(v) => v.push(row),
            Self::Deque(v) => v.push_back(row),
        }
    }
    fn trim<const PROFILE: bool>(&mut self, limit: usize, timings: &mut StatisticsTimings) {
        let overflow = self.len().saturating_sub(limit);
        if overflow == 0 {
            return;
        }
        if PROFILE {
            timings.history_dropped += overflow;
            timings.history_trim_operations += 1;
        }
        match self {
            Self::Array(v) => {
                if PROFILE {
                    timings.history_retained_slots_relocated += v.len() - overflow;
                    let mut drain = v.drain(..overflow);
                    let mark = std::time::Instant::now();
                    drain.by_ref().for_each(drop);
                    timings.history_dispose_ns += mark.elapsed().as_nanos() as u64;
                    let mark = std::time::Instant::now();
                    drop(drain);
                    timings.history_compact_ns += mark.elapsed().as_nanos() as u64;
                } else {
                    v.drain(..overflow);
                }
            }
            Self::Deque(v) => {
                if PROFILE {
                    let mut drain = v.drain(..overflow);
                    let mark = std::time::Instant::now();
                    drain.by_ref().for_each(drop);
                    timings.history_dispose_ns += mark.elapsed().as_nanos() as u64;
                    let mark = std::time::Instant::now();
                    drop(drain);
                    timings.history_compact_ns += mark.elapsed().as_nanos() as u64;
                } else {
                    v.drain(..overflow);
                }
            }
        }
    }
}

//! Opt-in, per-call attribution for prospective System compute leaves.
//! No fields persist in Runtime/export; false specialization never reads timers.
use serde::Serialize;
use std::time::Instant;

pub(crate) fn start<const PROFILE: bool>() -> Option<Instant> {
    PROFILE.then(Instant::now)
}
pub(crate) fn elapsed(start: Option<Instant>) -> u64 {
    start.map_or(0, |t| t.elapsed().as_nanos() as u64)
}
#[derive(Default, Serialize)]
pub(crate) struct VisionTimings {
    pub audit_ns: u64,
    pub audit_runs: u64,
    pub dirty_rows: u64,
    pub removed_rows: u64,
    pub unit_cache_hits: u64,
    pub recompute_rows: u64,
    pub gather_ns: u64,
    pub cache_ns: u64,
    pub geometry_ns: u64,
    pub geometry_hits: u64,
    pub geometry_misses: u64,
    pub geometry_evictions: u64,
    pub max_effective_range: i64,
    pub geometry_tiles: u64,
    pub commit_ns: u64,
    pub presentation_ns: u64,
    pub component_set_copies: u64,
    pub old_set_copies: u64,
    pub published_set_copies: u64,
    pub copied_tiles: u64,
    pub temporary_difference_sets: u64,
    pub removed_tiles: u64,
    pub added_tiles: u64,
    pub fog_became_visible: u64,
    pub fog_became_invisible: u64,
}
#[derive(Default, Serialize)]
pub(crate) struct MovementTimings {
    pub active_rows: u64,
    pub advanced_rows: u64,
    pub invalid_rows: u64,
    pub crossings: u64,
    pub row_ns: u64,
    pub spatial_ns: u64,
    pub pixel_ns: u64,
    pub dirty_ns: u64,
    pub cleanup_ns: u64,
}
#[derive(Default, Serialize)]
pub(crate) struct VisualTimings {
    pub attack_rows: u64,
    pub projectile_rows: u64,
    pub effect_rows: u64,
    pub damage_rows: u64,
    pub spawned: u64,
    pub removed: u64,
    pub attack_ns: u64,
    pub projectile_ns: u64,
    pub effect_ns: u64,
    pub damage_ns: u64,
    pub structural_ns: u64,
}
#[derive(Default, Serialize)]
pub(crate) struct RecoveryTimings {
    pub new_ids: u64,
    pub mp_pending: u64,
    pub ap_entries: u64,
    pub mp_entries: u64,
    pub skill_entries: u64,
    pub stale_entries: u64,
    pub ap_ns: u64,
    pub mp_ns: u64,
    pub skill_ns: u64,
}
#[derive(Default, Serialize)]
pub(crate) struct CandidateTimings {
    pub vision: VisionTimings,
    pub movement: MovementTimings,
    pub visuals: VisualTimings,
    pub recovery: RecoveryTimings,
}
#[derive(Default)]
pub(crate) struct StepTimings {
    pub statistics: crate::statistics::StatisticsTimings,
    pub candidates: CandidateTimings,
}

//! RoTK ENV rules; Python-independent authoritative state.
pub mod actions;
pub mod codec;
pub mod combat;
pub mod components;
pub mod hex;
pub mod lifecycle;
pub mod movement;
pub mod observation;
pub mod recovery;
pub mod runtime;
pub mod spatial;
pub mod statistics;
pub mod team;
pub mod unit_actions;
pub mod vision;
pub const RULES_VERSION: &str = "python-r0b-17b1776";

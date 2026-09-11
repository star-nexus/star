//! RoTK ENV rules; Python-independent authoritative state.
pub mod codec;
pub mod combat;
pub mod components;
pub mod hex;
pub mod movement;
pub mod recovery;
pub mod runtime;
pub mod spatial;
pub mod statistics;
pub mod vision;
pub const RULES_VERSION: &str = "python-r0-78cc8da";

//! Monaco is designed to work as a standalone tool that reads a configuration file and spawn the appropiate commands.
//! Nonetheless, it is designed to work also as a rust library, so other users can extend the way jobs can be launched.
//!
//! Monaco directly has support for YAML, TOML and JSON formats.

pub mod config;
pub mod job;
pub mod runner;
pub mod utils;

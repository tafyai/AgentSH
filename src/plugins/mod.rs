//! Plugin system for agentsh
//!
//! Provides extensibility through external tools that can be invoked
//! by the AI. Plugins communicate via JSON over stdin/stdout.

#![allow(dead_code)]
#![allow(unused_imports)]

mod builtin;
mod executor;
mod loader;
mod protocol;

pub use builtin::BuiltinTools;
pub use executor::PluginExecutor;
pub use loader::PluginLoader;
pub use protocol::{PluginRequest, PluginResponse, ToolDefinition};

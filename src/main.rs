//! agentsh - An AI-powered login shell
//!
//! This is the main entry point for the agentsh binary.

use anyhow::Result;
use clap::Parser;
use tracing::{error, info};

mod cli;
mod config;
mod context;
mod error;
mod execution_engine;
mod ai_orchestrator;
mod input_router;
mod logging;
mod pty;
mod safety;
mod shell;

use cli::Args;
use config::Config;
use shell::ShellRunner;

#[tokio::main]
async fn main() -> Result<()> {
    // Parse command line arguments
    let args = Args::parse();

    // Initialize logging
    init_logging(args.debug);

    info!("Starting agentsh v{}", env!("CARGO_PKG_VERSION"));

    // Load configuration
    let config = match Config::load(args.config.as_deref()) {
        Ok(cfg) => cfg,
        Err(e) => {
            error!("Failed to load configuration: {}", e);
            Config::default()
        }
    };

    // Determine shell to spawn
    let shell = args.shell.unwrap_or_else(|| {
        config.mode.shell.clone().unwrap_or_else(|| {
            std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".to_string())
        })
    });

    info!("Using shell: {}", shell);

    // Check for AI mode override
    let mut config = config;
    if let Some(mode) = args.mode {
        config.mode.default = mode;
    }

    // Create and run the shell
    let mut runner = ShellRunner::new(config);

    if let Err(e) = runner.run(&shell).await {
        error!("Shell error: {}", e);
        std::process::exit(1);
    }

    info!("agentsh exited");
    Ok(())
}

/// Initialize the logging/tracing subsystem
fn init_logging(debug: bool) {
    use tracing_subscriber::{fmt, prelude::*, EnvFilter};

    let filter = if debug {
        EnvFilter::new("debug")
    } else {
        EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("warn"))
    };

    tracing_subscriber::registry()
        .with(fmt::layer().with_target(false).with_writer(std::io::stderr))
        .with(filter)
        .init();
}

//! Error types for agentsh

#![allow(dead_code)]

use thiserror::Error;

/// Main error type for agentsh
#[derive(Error, Debug)]
pub enum AgentshError {
    #[error("PTY error: {0}")]
    Pty(#[from] PtyError),

    #[error("Configuration error: {0}")]
    Config(#[from] ConfigError),

    #[error("AI error: {0}")]
    Ai(#[from] AiError),

    #[error("Execution error: {0}")]
    Execution(#[from] ExecutionError),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

/// PTY-related errors
#[derive(Error, Debug)]
pub enum PtyError {
    #[error("Failed to create PTY: {0}")]
    Create(String),

    #[error("Failed to spawn shell: {0}")]
    Spawn(String),

    #[error("Failed to read from PTY: {0}")]
    Read(String),

    #[error("Failed to write to PTY: {0}")]
    Write(String),

    #[error("Failed to resize PTY: {0}")]
    Resize(String),

    #[error("Shell exited with code: {0}")]
    ShellExit(i32),
}

/// Configuration-related errors
#[derive(Error, Debug)]
pub enum ConfigError {
    #[error("Failed to read config file: {0}")]
    Read(String),

    #[error("Failed to parse config: {0}")]
    Parse(String),

    #[error("Invalid configuration: {0}")]
    Invalid(String),

    #[error("Missing required field: {0}")]
    MissingField(String),
}

/// AI/LLM-related errors
#[derive(Error, Debug)]
pub enum AiError {
    #[error("Network error: {0}")]
    Network(String),

    #[error("API error: {status} - {message}")]
    Api { status: u16, message: String },

    #[error("Failed to parse AI response: {0}")]
    Parse(String),

    #[error("AI request timeout")]
    Timeout,

    #[error("AI unavailable: {0}")]
    Unavailable(String),
}

/// Command execution errors
#[derive(Error, Debug)]
pub enum ExecutionError {
    #[error("Command failed: {0}")]
    CommandFailed(String),

    #[error("Command blocked by safety policy: {0}")]
    Blocked(String),

    #[error("User cancelled execution")]
    Cancelled,

    #[error("Step failed: {step} - {reason}")]
    StepFailed { step: String, reason: String },
}

/// Result type alias using AgentshError
pub type Result<T> = std::result::Result<T, AgentshError>;

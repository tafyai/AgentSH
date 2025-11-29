//! Error types for agentsh
//!
//! Provides structured error types with user-friendly formatting.

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

impl AgentshError {
    /// Get a user-friendly error message with suggestions
    pub fn user_message(&self) -> String {
        match self {
            AgentshError::Ai(ai_err) => ai_err.user_message(),
            AgentshError::Config(cfg_err) => cfg_err.user_message(),
            AgentshError::Execution(exec_err) => exec_err.user_message(),
            AgentshError::Pty(pty_err) => format!("Shell error: {}", pty_err),
            AgentshError::Io(io_err) => format!("IO error: {}", io_err),
        }
    }
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

impl ConfigError {
    /// Get a user-friendly error message
    pub fn user_message(&self) -> String {
        match self {
            ConfigError::Read(path) => {
                format!(
                    "Could not read configuration file: {}\n\
                     Tip: Check that the file exists and you have read permissions.",
                    path
                )
            }
            ConfigError::Parse(details) => {
                format!(
                    "Configuration syntax error: {}\n\
                     Tip: Validate your TOML syntax at https://www.toml-lint.com/",
                    details
                )
            }
            ConfigError::Invalid(msg) => {
                format!("Invalid configuration: {}", msg)
            }
            ConfigError::MissingField(field) => {
                format!(
                    "Missing required configuration: {}\n\
                     Tip: Add this field to your ~/.aishell/config.toml",
                    field
                )
            }
        }
    }
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

impl AiError {
    /// Get a user-friendly error message with suggestions
    pub fn user_message(&self) -> String {
        match self {
            AiError::Network(msg) => {
                format!(
                    "Network error: {}\n\
                     Tip: Check your internet connection and try again.",
                    msg
                )
            }
            AiError::Api { status, message } => {
                let suggestion = match *status {
                    401 => "Check that your API key is valid and not expired.",
                    403 => "Your API key may not have permission for this model.",
                    429 => "Rate limit exceeded. Wait a moment and try again.",
                    500..=599 => "The AI service is experiencing issues. Try again later.",
                    _ => "Check your API configuration.",
                };
                format!(
                    "AI API error ({}): {}\n\
                     Tip: {}",
                    status, message, suggestion
                )
            }
            AiError::Parse(details) => {
                format!(
                    "Could not understand AI response: {}\n\
                     Tip: The AI may have returned an unexpected format. Try rephrasing your request.",
                    details
                )
            }
            AiError::Timeout => {
                "AI request timed out.\n\
                 Tip: The request took too long. Try a simpler query or increase the timeout in config."
                    .to_string()
            }
            AiError::Unavailable(reason) => {
                format!(
                    "AI is not available: {}\n\
                     Tip: Set your API key with: export OPENAI_API_KEY=your-key",
                    reason
                )
            }
        }
    }
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

impl ExecutionError {
    /// Get a user-friendly error message
    pub fn user_message(&self) -> String {
        match self {
            ExecutionError::CommandFailed(cmd) => {
                format!(
                    "Command failed: {}\n\
                     Tip: Use 'ai fix' to diagnose and fix the error.",
                    cmd
                )
            }
            ExecutionError::Blocked(reason) => {
                format!(
                    "Command blocked: {}\n\
                     This command was blocked by the safety policy for your protection.",
                    reason
                )
            }
            ExecutionError::Cancelled => "Execution cancelled by user.".to_string(),
            ExecutionError::StepFailed { step, reason } => {
                format!(
                    "Step '{}' failed: {}\n\
                     Tip: You can retry, skip, or use 'ai fix' to diagnose.",
                    step, reason
                )
            }
        }
    }
}

/// Result type alias using AgentshError
pub type Result<T> = std::result::Result<T, AgentshError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ai_error_user_message_401() {
        let err = AiError::Api {
            status: 401,
            message: "Unauthorized".to_string(),
        };
        let msg = err.user_message();
        assert!(msg.contains("401"));
        assert!(msg.contains("API key"));
    }

    #[test]
    fn test_ai_error_user_message_429() {
        let err = AiError::Api {
            status: 429,
            message: "Too many requests".to_string(),
        };
        let msg = err.user_message();
        assert!(msg.contains("Rate limit"));
    }

    #[test]
    fn test_ai_error_user_message_timeout() {
        let err = AiError::Timeout;
        let msg = err.user_message();
        assert!(msg.contains("timed out"));
    }

    #[test]
    fn test_ai_error_user_message_unavailable() {
        let err = AiError::Unavailable("No API key".to_string());
        let msg = err.user_message();
        assert!(msg.contains("OPENAI_API_KEY"));
    }

    #[test]
    fn test_config_error_user_message() {
        let err = ConfigError::MissingField("ai.model".to_string());
        let msg = err.user_message();
        assert!(msg.contains("ai.model"));
        assert!(msg.contains("config.toml"));
    }

    #[test]
    fn test_execution_error_user_message_blocked() {
        let err = ExecutionError::Blocked("rm -rf /".to_string());
        let msg = err.user_message();
        assert!(msg.contains("blocked"));
        assert!(msg.contains("safety"));
    }

    #[test]
    fn test_execution_error_user_message_failed() {
        let err = ExecutionError::CommandFailed("npm install".to_string());
        let msg = err.user_message();
        assert!(msg.contains("ai fix"));
    }
}

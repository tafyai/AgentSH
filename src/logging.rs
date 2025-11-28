//! Logging module for audit trails
//!
//! Handles logging of AI-generated commands and execution results
//! for auditing and debugging purposes.

#![allow(dead_code)]

use crate::ai_orchestrator::AiAction;
use crate::config::SafetyConfig;
use crate::execution_engine::StepResult;
use chrono::{DateTime, Utc};
use once_cell::sync::Lazy;
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::Path;
use tracing::{debug, error, warn};
use uuid::Uuid;

/// Session ID for the current shell session
static SESSION_ID: Lazy<String> = Lazy::new(|| Uuid::new_v4().to_string());

/// Secret patterns for redaction
static SECRET_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        // API keys and tokens
        Regex::new(
            r#"(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[=:]\s*['"]?([^'"\s]+)['"]?"#,
        )
        .unwrap(),
        // Bearer tokens
        Regex::new(r"(?i)bearer\s+[a-zA-Z0-9._-]+").unwrap(),
        // AWS keys
        Regex::new(r"AKIA[A-Z0-9]{16}").unwrap(),
        // Private keys
        Regex::new(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----").unwrap(),
        // Generic long alphanumeric strings that might be keys
        Regex::new(r"[a-zA-Z0-9_-]{32,}").unwrap(),
    ]
});

/// Log entry structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogEntry {
    /// Session ID
    pub session_id: String,
    /// Timestamp
    pub timestamp: DateTime<Utc>,
    /// Event type
    pub event: LogEvent,
    /// User who ran the command
    pub user: String,
    /// Current working directory
    pub cwd: String,
    /// User's request/query
    pub request: String,
    /// AI's response action
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ai_action: Option<AiAction>,
    /// Commands that were executed
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub executed_commands: Vec<ExecutedCommand>,
    /// Total duration in milliseconds
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<u64>,
}

/// Types of log events
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LogEvent {
    /// AI query was made
    Query,
    /// Commands were executed
    Execute,
    /// Command was blocked
    Blocked,
    /// Error occurred
    Error,
}

/// Record of an executed command
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutedCommand {
    pub command: String,
    pub exit_code: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stdout_preview: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub stderr_preview: Option<String>,
}

/// Logger for AI command auditing
pub struct AuditLogger {
    config: SafetyConfig,
    log_file: Option<BufWriter<File>>,
}

impl AuditLogger {
    /// Create a new audit logger
    pub fn new(config: SafetyConfig) -> Self {
        let log_file = if config.log_ai_generated_commands {
            Self::open_log_file(&config.log_path)
        } else {
            None
        };

        Self { config, log_file }
    }

    /// Open or create the log file
    fn open_log_file(path: &Path) -> Option<BufWriter<File>> {
        // Ensure directory exists
        if let Some(parent) = path.parent() {
            if let Err(e) = fs::create_dir_all(parent) {
                error!("Failed to create log directory: {}", e);
                return None;
            }
        }

        // Open file for appending
        match OpenOptions::new().create(true).append(true).open(path) {
            Ok(file) => Some(BufWriter::new(file)),
            Err(e) => {
                error!("Failed to open log file {:?}: {}", path, e);
                None
            }
        }
    }

    /// Log an AI query
    pub fn log_query(&mut self, request: &str, action: &AiAction) {
        if !self.config.log_ai_generated_commands {
            return;
        }

        let entry = LogEntry {
            session_id: SESSION_ID.clone(),
            timestamp: Utc::now(),
            event: LogEvent::Query,
            user: std::env::var("USER").unwrap_or_else(|_| "unknown".to_string()),
            cwd: std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| ".".to_string()),
            request: self.redact_if_needed(request),
            ai_action: Some(self.redact_action(action)),
            executed_commands: vec![],
            duration_ms: None,
        };

        self.write_entry(&entry);
    }

    /// Log command execution
    pub fn log_execution(&mut self, request: &str, results: &[StepResult], duration_ms: u64) {
        if !self.config.log_ai_generated_commands {
            return;
        }

        let executed_commands: Vec<ExecutedCommand> = results
            .iter()
            .map(|r| ExecutedCommand {
                command: self.redact_if_needed(&r.command),
                exit_code: r.exit_code,
                stdout_preview: Some(truncate_preview(&self.redact_if_needed(&r.stdout))),
                stderr_preview: if r.stderr.is_empty() {
                    None
                } else {
                    Some(truncate_preview(&self.redact_if_needed(&r.stderr)))
                },
            })
            .collect();

        let entry = LogEntry {
            session_id: SESSION_ID.clone(),
            timestamp: Utc::now(),
            event: LogEvent::Execute,
            user: std::env::var("USER").unwrap_or_else(|_| "unknown".to_string()),
            cwd: std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| ".".to_string()),
            request: self.redact_if_needed(request),
            ai_action: None,
            executed_commands,
            duration_ms: Some(duration_ms),
        };

        self.write_entry(&entry);
    }

    /// Log a blocked command
    pub fn log_blocked(&mut self, request: &str, command: &str, reason: &str) {
        if !self.config.log_ai_generated_commands {
            return;
        }

        let entry = LogEntry {
            session_id: SESSION_ID.clone(),
            timestamp: Utc::now(),
            event: LogEvent::Blocked,
            user: std::env::var("USER").unwrap_or_else(|_| "unknown".to_string()),
            cwd: std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| ".".to_string()),
            request: self.redact_if_needed(request),
            ai_action: None,
            executed_commands: vec![ExecutedCommand {
                command: self.redact_if_needed(command),
                exit_code: -1,
                stdout_preview: None,
                stderr_preview: Some(reason.to_string()),
            }],
            duration_ms: None,
        };

        self.write_entry(&entry);
    }

    /// Log an error
    pub fn log_error(&mut self, request: &str, _error: &str) {
        if !self.config.log_ai_generated_commands {
            return;
        }

        let entry = LogEntry {
            session_id: SESSION_ID.clone(),
            timestamp: Utc::now(),
            event: LogEvent::Error,
            user: std::env::var("USER").unwrap_or_else(|_| "unknown".to_string()),
            cwd: std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| ".".to_string()),
            request: self.redact_if_needed(request),
            ai_action: None,
            executed_commands: vec![],
            duration_ms: None,
        };

        self.write_entry(&entry);
    }

    /// Write a log entry
    fn write_entry(&mut self, entry: &LogEntry) {
        if let Some(ref mut file) = self.log_file {
            match serde_json::to_string(entry) {
                Ok(json) => {
                    if let Err(e) = writeln!(file, "{}", json) {
                        error!("Failed to write log entry: {}", e);
                    }
                    if let Err(e) = file.flush() {
                        warn!("Failed to flush log file: {}", e);
                    }
                }
                Err(e) => {
                    error!("Failed to serialize log entry: {}", e);
                }
            }
        }
    }

    /// Redact secrets from text if configured
    fn redact_if_needed(&self, text: &str) -> String {
        if self.config.redact_secrets {
            redact_secrets(text)
        } else {
            text.to_string()
        }
    }

    /// Redact secrets from AI action
    fn redact_action(&self, action: &AiAction) -> AiAction {
        if !self.config.redact_secrets {
            return action.clone();
        }

        let mut redacted = action.clone();

        if let Some(ref summary) = redacted.summary {
            redacted.summary = Some(redact_secrets(summary));
        }

        for step in &mut redacted.steps {
            step.shell_command = redact_secrets(&step.shell_command);
            step.description = redact_secrets(&step.description);
        }

        redacted
    }

    /// Rotate log file if needed
    pub fn maybe_rotate(&mut self) {
        if !self.config.log_ai_generated_commands {
            return;
        }

        let path = &self.config.log_path;
        if let Ok(metadata) = fs::metadata(path) {
            if metadata.len() > self.config.max_log_size {
                self.rotate_logs();
            }
        }
    }

    /// Rotate log files
    fn rotate_logs(&mut self) {
        let path = &self.config.log_path;
        debug!("Rotating log files");

        // Close current file
        self.log_file = None;

        // Rotate existing files
        for i in (1..self.config.log_retention).rev() {
            let old = format!("{}.{}", path.display(), i);
            let new = format!("{}.{}", path.display(), i + 1);
            let _ = fs::rename(&old, &new);
        }

        // Rename current to .1
        let rotated = format!("{}.1", path.display());
        let _ = fs::rename(path, &rotated);

        // Open new file
        self.log_file = Self::open_log_file(path);
    }

    /// Get session ID
    pub fn session_id() -> &'static str {
        &SESSION_ID
    }
}

/// Redact secrets from text
fn redact_secrets(text: &str) -> String {
    let mut result = text.to_string();

    for pattern in SECRET_PATTERNS.iter() {
        result = pattern.replace_all(&result, "[REDACTED]").to_string();
    }

    result
}

/// Truncate text for preview
fn truncate_preview(text: &str) -> String {
    const MAX_PREVIEW: usize = 500;
    if text.len() > MAX_PREVIEW {
        format!("{}...[truncated]", &text[..MAX_PREVIEW])
    } else {
        text.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_redact_api_key() {
        let text = "API_KEY=sk-1234567890abcdef";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
        assert!(!redacted.contains("sk-1234567890"));
    }

    #[test]
    fn test_redact_bearer() {
        let text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
    }

    #[test]
    fn test_truncate_preview() {
        let short = "short text";
        assert_eq!(truncate_preview(short), short);

        let long = "a".repeat(1000);
        let truncated = truncate_preview(&long);
        assert!(truncated.ends_with("...[truncated]"));
        assert!(truncated.len() < long.len());
    }

    #[test]
    fn test_session_id() {
        let id1 = AuditLogger::session_id();
        let id2 = AuditLogger::session_id();
        assert_eq!(id1, id2); // Same session
        assert!(!id1.is_empty());
    }
}

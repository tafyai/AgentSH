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
    use crate::ai_orchestrator::{ActionKind, Step};
    use std::io::Read;
    use tempfile::TempDir;

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
    fn test_redact_password() {
        let text = "password=mysecretpassword123";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
        assert!(!redacted.contains("mysecretpassword123"));
    }

    #[test]
    fn test_redact_aws_key() {
        let text = "export AWS_KEY=AKIAIOSFODNN7EXAMPLE";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
        assert!(!redacted.contains("AKIAIOSFODNN7EXAMPLE"));
    }

    #[test]
    fn test_redact_token() {
        let text = "token: ghp_abcdefghijklmnopqrstuvwxyz123456";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
    }

    #[test]
    fn test_redact_private_key() {
        let text = "-----BEGIN RSA PRIVATE KEY-----\ndata\n-----END RSA PRIVATE KEY-----";
        let redacted = redact_secrets(text);
        assert!(redacted.contains("[REDACTED]"));
    }

    #[test]
    fn test_no_redact_normal_text() {
        let text = "ls -la /home/user";
        let redacted = redact_secrets(text);
        // Short alphanumeric strings should not be redacted
        assert!(redacted.contains("ls"));
        assert!(redacted.contains("home"));
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
    fn test_truncate_exact_boundary() {
        let exact = "b".repeat(500);
        let truncated = truncate_preview(&exact);
        assert_eq!(truncated, exact); // Should not truncate at exactly 500
    }

    #[test]
    fn test_session_id() {
        let id1 = AuditLogger::session_id();
        let id2 = AuditLogger::session_id();
        assert_eq!(id1, id2); // Same session
        assert!(!id1.is_empty());
    }

    #[test]
    fn test_session_id_format() {
        let id = AuditLogger::session_id();
        // UUID format: 8-4-4-4-12
        assert_eq!(id.len(), 36);
        assert_eq!(id.chars().filter(|c| *c == '-').count(), 4);
    }

    #[test]
    fn test_log_entry_serialization() {
        let entry = LogEntry {
            session_id: "test-session".to_string(),
            timestamp: Utc::now(),
            event: LogEvent::Query,
            user: "testuser".to_string(),
            cwd: "/home/test".to_string(),
            request: "ai list files".to_string(),
            ai_action: None,
            executed_commands: vec![],
            duration_ms: None,
        };

        let json = serde_json::to_string(&entry).unwrap();
        assert!(json.contains("test-session"));
        assert!(json.contains("testuser"));
        assert!(json.contains("query"));
    }

    #[test]
    fn test_log_entry_with_commands() {
        let entry = LogEntry {
            session_id: "test-session".to_string(),
            timestamp: Utc::now(),
            event: LogEvent::Execute,
            user: "testuser".to_string(),
            cwd: "/home/test".to_string(),
            request: "ai list files".to_string(),
            ai_action: None,
            executed_commands: vec![ExecutedCommand {
                command: "ls -la".to_string(),
                exit_code: 0,
                stdout_preview: Some("file1\nfile2".to_string()),
                stderr_preview: None,
            }],
            duration_ms: Some(100),
        };

        let json = serde_json::to_string(&entry).unwrap();
        assert!(json.contains("ls -la"));
        assert!(json.contains("exit_code"));
        assert!(json.contains("100"));
    }

    #[test]
    fn test_log_event_types() {
        let query = LogEvent::Query;
        let execute = LogEvent::Execute;
        let blocked = LogEvent::Blocked;
        let error = LogEvent::Error;

        assert_eq!(serde_json::to_string(&query).unwrap(), "\"query\"");
        assert_eq!(serde_json::to_string(&execute).unwrap(), "\"execute\"");
        assert_eq!(serde_json::to_string(&blocked).unwrap(), "\"blocked\"");
        assert_eq!(serde_json::to_string(&error).unwrap(), "\"error\"");
    }

    #[test]
    fn test_audit_logger_disabled() {
        let mut config = SafetyConfig::default();
        config.log_ai_generated_commands = false;

        let mut logger = AuditLogger::new(config);

        // These should not panic or write anything
        let action = AiAction {
            kind: ActionKind::AnswerOnly,
            summary: Some("test".to_string()),
            steps: vec![],
        };
        logger.log_query("test", &action);
        logger.log_blocked("test", "cmd", "reason");
        logger.log_error("test", "error");
    }

    #[test]
    fn test_audit_logger_creates_directory() {
        let temp_dir = TempDir::new().unwrap();
        let log_path = temp_dir.path().join("subdir/commands.log");

        let mut config = SafetyConfig::default();
        config.log_ai_generated_commands = true;
        config.log_path = log_path.clone();

        let mut logger = AuditLogger::new(config);

        let action = AiAction {
            kind: ActionKind::AnswerOnly,
            summary: Some("test answer".to_string()),
            steps: vec![],
        };
        logger.log_query("test query", &action);

        // Verify directory was created and file exists
        assert!(log_path.exists());
    }

    #[test]
    fn test_audit_logger_writes_json() {
        let temp_dir = TempDir::new().unwrap();
        let log_path = temp_dir.path().join("commands.log");

        let mut config = SafetyConfig::default();
        config.log_ai_generated_commands = true;
        config.log_path = log_path.clone();
        config.redact_secrets = false;

        let mut logger = AuditLogger::new(config);

        let action = AiAction {
            kind: ActionKind::CommandSequence,
            summary: Some("list files".to_string()),
            steps: vec![Step {
                id: "1".to_string(),
                description: "List all files".to_string(),
                shell_command: "ls -la".to_string(),
                needs_confirmation: false,
                is_destructive: false,
                requires_sudo: false,
                working_directory: None,
            }],
        };
        logger.log_query("ai list files", &action);

        // Read and verify log content
        drop(logger); // Ensure file is flushed
        let mut content = String::new();
        File::open(&log_path)
            .unwrap()
            .read_to_string(&mut content)
            .unwrap();

        assert!(content.contains("ai list files"));
        assert!(content.contains("ls -la"));
        assert!(content.contains("command_sequence"));
    }

    #[test]
    fn test_audit_logger_redacts_secrets() {
        let temp_dir = TempDir::new().unwrap();
        let log_path = temp_dir.path().join("commands.log");

        let mut config = SafetyConfig::default();
        config.log_ai_generated_commands = true;
        config.log_path = log_path.clone();
        config.redact_secrets = true;

        let mut logger = AuditLogger::new(config);

        let action = AiAction {
            kind: ActionKind::CommandSequence,
            summary: Some("set API key".to_string()),
            steps: vec![Step {
                id: "1".to_string(),
                description: "Export API key".to_string(),
                shell_command: "export API_KEY=sk-secretkey12345678901234567890".to_string(),
                needs_confirmation: false,
                is_destructive: false,
                requires_sudo: false,
                working_directory: None,
            }],
        };
        logger.log_query(
            "ai set api key to sk-secretkey12345678901234567890",
            &action,
        );

        // Read and verify secrets are redacted
        drop(logger);
        let mut content = String::new();
        File::open(&log_path)
            .unwrap()
            .read_to_string(&mut content)
            .unwrap();

        assert!(!content.contains("sk-secretkey"));
        assert!(content.contains("[REDACTED]"));
    }
}

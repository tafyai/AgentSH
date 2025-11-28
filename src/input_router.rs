//! Input Router module
//!
//! Handles routing of user input between the shell and AI,
//! including detection of AI commands and line editing.

#![allow(dead_code)]

use crate::ai_orchestrator::QueryMode;
use once_cell::sync::Lazy;
use regex::Regex;

/// AI command prefix patterns
static AI_PREFIX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^(@?ai\s+)").unwrap());

/// AI run command pattern
static AI_RUN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"^@?ai\s+run\s+["']?(.+?)["']?\s*$"#).unwrap());

/// AI explain command pattern
static AI_EXPLAIN: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"^@?ai\s+explain\s+['"]?(.+?)['"]?\s*$"#).unwrap());

/// AI do command pattern
static AI_DO: Lazy<Regex> =
    Lazy::new(|| Regex::new(r#"^@?ai\s+do\s+["']?(.+?)["']?\s*$"#).unwrap());

/// AI fix command pattern
static AI_FIX: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+fix\s*$").unwrap());

/// AI sysinfo command pattern
static AI_SYSINFO: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+sysinfo\s*$").unwrap());

/// AI services command pattern
static AI_SERVICES: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+services\s*$").unwrap());

/// AI packages command pattern
static AI_PACKAGES: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+packages\s*$").unwrap());

/// AI mode command pattern
static AI_MODE: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+mode\s+(\w+)\s*$").unwrap());

/// AI help command pattern
static AI_HELP: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+(help|\?)\s*$").unwrap());

/// AI history command pattern
static AI_HISTORY: Lazy<Regex> = Lazy::new(|| Regex::new(r"^@?ai\s+history\s*$").unwrap());

/// Routing decision for user input
#[derive(Debug, Clone)]
pub enum InputRoute {
    /// Pass through to shell unchanged
    Shell(String),
    /// Route to AI with parsed query
    Ai(AiCommand),
    /// Internal command (mode switch, etc.)
    Internal(InternalCommand),
}

/// Parsed AI command
#[derive(Debug, Clone)]
pub struct AiCommand {
    /// The query mode
    pub mode: QueryMode,
    /// The query text
    pub query: String,
}

/// Internal commands
#[derive(Debug, Clone)]
pub enum InternalCommand {
    /// Switch AI mode
    SetMode(String),
    /// Show help
    Help,
    /// Show command history
    History,
    /// Clear AI conversation
    Clear,
}

/// Route user input to appropriate handler
pub fn route_input(input: &str) -> InputRoute {
    let trimmed = input.trim();

    // Check for AI help
    if AI_HELP.is_match(trimmed) {
        return InputRoute::Internal(InternalCommand::Help);
    }

    // Check for AI mode switch
    if let Some(caps) = AI_MODE.captures(trimmed) {
        let mode = caps
            .get(1)
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();
        return InputRoute::Internal(InternalCommand::SetMode(mode));
    }

    // Check for AI history
    if AI_HISTORY.is_match(trimmed) {
        return InputRoute::Internal(InternalCommand::History);
    }

    // Check for AI run command
    if let Some(caps) = AI_RUN.captures(trimmed) {
        let query = caps
            .get(1)
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::Run,
            query,
        });
    }

    // Check for AI explain command
    if let Some(caps) = AI_EXPLAIN.captures(trimmed) {
        let command = caps
            .get(1)
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::Explain {
                command: command.clone(),
            },
            query: command,
        });
    }

    // Check for AI do command
    if let Some(caps) = AI_DO.captures(trimmed) {
        let query = caps
            .get(1)
            .map(|m| m.as_str().to_string())
            .unwrap_or_default();
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::Do,
            query,
        });
    }

    // Check for AI fix command
    if AI_FIX.is_match(trimmed) {
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::Fix,
            query: String::new(),
        });
    }

    // Check for AI sysinfo command
    if AI_SYSINFO.is_match(trimmed) {
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::SysInfo,
            query: "system information".to_string(),
        });
    }

    // Check for AI services command
    if AI_SERVICES.is_match(trimmed) {
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::SysInfo,
            query: "list running services".to_string(),
        });
    }

    // Check for AI packages command
    if AI_PACKAGES.is_match(trimmed) {
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::SysInfo,
            query: "list installed packages".to_string(),
        });
    }

    // Check for generic AI prefix
    if let Some(caps) = AI_PREFIX.captures(trimmed) {
        let prefix_len = caps.get(1).map(|m| m.end()).unwrap_or(0);
        let query = trimmed[prefix_len..].trim().to_string();
        return InputRoute::Ai(AiCommand {
            mode: QueryMode::General,
            query,
        });
    }

    // Default: pass to shell
    InputRoute::Shell(input.to_string())
}

/// Check if input is an AI command
pub fn is_ai_command(input: &str) -> bool {
    AI_PREFIX.is_match(input.trim())
}

/// Extract query from AI command, removing prefix
pub fn extract_query(input: &str) -> Option<String> {
    let trimmed = input.trim();
    if let Some(caps) = AI_PREFIX.captures(trimmed) {
        let prefix_len = caps.get(1).map(|m| m.end()).unwrap_or(0);
        Some(trimmed[prefix_len..].trim().to_string())
    } else {
        None
    }
}

/// Show AI help text
pub fn show_help() {
    println!(
        r#"
agentsh - AI-powered shell assistant

COMMANDS:
  ai <question>           Ask a question or get help
  ai run "task"           Get commands for a task
  ai explain 'command'    Explain what a command does
  ai fix                  Diagnose and fix the last error
  ai do "task"            Multi-step autonomous task

SYSTEM INFO:
  ai sysinfo              Show system information
  ai services             List running services
  ai packages             List installed packages

SETTINGS:
  ai mode <off|assist>    Switch AI mode
  ai history              Show AI command history
  ai help                 Show this help

EXAMPLES:
  ai find files larger than 100MB
  ai run "set up nginx with SSL"
  ai explain 'rsync -avz --delete src/ dst/'
  ai do "deploy the application to production"
  ai fix

KEYBINDINGS:
  Alt-A                   Send current line to AI
  Alt-M                   Toggle AI mode

For more info: https://github.com/yourusername/agentsh
"#
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_route_shell_command() {
        match route_input("ls -la") {
            InputRoute::Shell(cmd) => assert_eq!(cmd, "ls -la"),
            _ => panic!("Expected Shell route"),
        }
    }

    #[test]
    fn test_route_ai_general() {
        match route_input("ai what time is it") {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::General));
                assert_eq!(cmd.query, "what time is it");
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_with_at() {
        match route_input("@ai help me") {
            InputRoute::Ai(cmd) => {
                assert_eq!(cmd.query, "help me");
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_run() {
        match route_input(r#"ai run "set up nginx""#) {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::Run));
                assert_eq!(cmd.query, "set up nginx");
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_explain() {
        match route_input("ai explain 'ls -la'") {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::Explain { .. }));
                assert_eq!(cmd.query, "ls -la");
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_do() {
        match route_input(r#"ai do "deploy app""#) {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::Do));
                assert_eq!(cmd.query, "deploy app");
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_fix() {
        match route_input("ai fix") {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::Fix));
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_sysinfo() {
        match route_input("ai sysinfo") {
            InputRoute::Ai(cmd) => {
                assert!(matches!(cmd.mode, QueryMode::SysInfo));
            }
            _ => panic!("Expected Ai route"),
        }
    }

    #[test]
    fn test_route_ai_mode() {
        match route_input("ai mode off") {
            InputRoute::Internal(InternalCommand::SetMode(mode)) => {
                assert_eq!(mode, "off");
            }
            _ => panic!("Expected Internal route"),
        }
    }

    #[test]
    fn test_route_ai_help() {
        match route_input("ai help") {
            InputRoute::Internal(InternalCommand::Help) => {}
            _ => panic!("Expected Help route"),
        }
    }

    #[test]
    fn test_is_ai_command() {
        assert!(is_ai_command("ai test"));
        assert!(is_ai_command("@ai test"));
        assert!(!is_ai_command("ls -la"));
        assert!(!is_ai_command("echo ai"));
    }

    #[test]
    fn test_extract_query() {
        assert_eq!(
            extract_query("ai hello world"),
            Some("hello world".to_string())
        );
        assert_eq!(extract_query("@ai hello"), Some("hello".to_string()));
        assert_eq!(extract_query("ls -la"), None);
    }
}

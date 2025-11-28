//! Configuration management for agentsh
//!
//! Handles loading and merging configuration from multiple sources:
//! 1. Compiled defaults
//! 2. System config (/etc/aishell/config.toml)
//! 3. User config (~/.aishell/config.toml)
//! 4. Project config (.aishellrc)
//! 5. Environment variables
//! 6. CLI arguments

use crate::error::ConfigError;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tracing::debug;

/// Main configuration structure
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct Config {
    pub ai: AiConfig,
    pub mode: ModeConfig,
    pub safety: SafetyConfig,
    pub ui: UiConfig,
    pub context: ContextConfig,
    pub history: HistoryConfig,
    pub keys: KeyConfig,
    pub plugins: PluginConfig,
}

/// AI/LLM provider configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct AiConfig {
    /// LLM provider: openai, anthropic, azure, local
    pub provider: String,
    /// Model identifier
    pub model: String,
    /// API endpoint URL
    pub endpoint: String,
    /// Environment variable containing API key
    pub api_key_env: String,
    /// Maximum tokens for response
    pub max_tokens: u32,
    /// Request timeout in seconds
    pub timeout: u64,
    /// Temperature for generation
    pub temperature: f32,
    /// Maximum context window size
    pub max_context: u32,
}

/// Mode and shell configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ModeConfig {
    /// Default AI mode: off, assist, auto
    pub default: String,
    /// Path to underlying shell
    pub shell: Option<String>,
    /// Arguments to pass to shell
    pub shell_args: Vec<String>,
}

/// Safety and security configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SafetyConfig {
    /// Require confirmation for destructive commands
    pub require_confirmation_for_destructive: bool,
    /// Require confirmation for sudo commands
    pub require_confirmation_for_sudo: bool,
    /// Allow AI to execute sudo commands after confirmation
    pub allow_ai_to_execute_sudo: bool,
    /// Log all AI-generated commands
    pub log_ai_generated_commands: bool,
    /// Log file path
    pub log_path: PathBuf,
    /// Maximum log file size before rotation
    pub max_log_size: u64,
    /// Number of rotated logs to keep
    pub log_retention: u32,
    /// Redact secrets from logs
    pub redact_secrets: bool,
    /// Command patterns that are always blocked
    pub blocked_patterns: Vec<String>,
    /// Paths requiring extra confirmation
    pub protected_paths: Vec<String>,
}

/// UI and display configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UiConfig {
    /// Show plan before execution
    pub show_plan_before_execution: bool,
    /// Show step numbers
    pub show_step_numbers: bool,
    /// Prompt format string
    pub prompt: String,
    /// Mode indicators in prompt
    pub mode_indicators: ModeIndicators,
    /// Enable color output
    pub color: bool,
    /// Color configuration
    pub colors: ColorConfig,
    /// Show timestamps
    pub show_timestamps: bool,
    /// Spinner style
    pub spinner: String,
}

/// Mode indicator strings
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ModeIndicators {
    pub off: String,
    pub assist: String,
    pub auto: String,
}

/// Color configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ColorConfig {
    pub prompt_user: String,
    pub prompt_host: String,
    pub prompt_cwd: String,
    pub ai_plan: String,
    pub ai_command: String,
    pub ai_warning: String,
    pub ai_success: String,
}

/// Context collection configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ContextConfig {
    /// Files to include in AI context
    pub include_files: Vec<String>,
    /// Patterns to exclude
    pub exclude_patterns: Vec<String>,
    /// Maximum file size to include
    pub max_file_size: u64,
    /// Maximum total context size
    pub max_context_size: u64,
    /// Number of history lines to include
    pub history_lines: u32,
    /// Domain hint for AI
    pub domain_hint: String,
}

/// Command history configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct HistoryConfig {
    /// Enable history
    pub enabled: bool,
    /// History file path
    pub file: PathBuf,
    /// Maximum entries
    pub max_entries: u32,
    /// Share with underlying shell
    pub share_with_shell: bool,
    /// Ignore commands starting with space
    pub ignore_space: bool,
    /// Patterns to exclude from history
    pub ignore_patterns: Vec<String>,
}

/// Keybinding configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct KeyConfig {
    /// Send line to AI
    pub ai_mode: String,
    /// Toggle assist mode
    pub toggle_assist: String,
    /// Show AI help
    pub ai_help: String,
    /// Cancel operation
    pub cancel: String,
    /// Accept suggestion
    pub accept: String,
    /// Edit suggestion
    pub edit: String,
    /// Reject suggestion
    pub reject: String,
}

/// Plugin configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct PluginConfig {
    /// Enable plugins
    pub enabled: bool,
    /// Plugin directory
    pub directory: PathBuf,
    /// Auto-load plugins
    pub auto_load: bool,
    /// Specific plugins to load
    pub load: Vec<String>,
    /// Plugin timeout
    pub timeout: u64,
}

// Default implementations

impl Default for Config {
    fn default() -> Self {
        Self {
            ai: AiConfig::default(),
            mode: ModeConfig::default(),
            safety: SafetyConfig::default(),
            ui: UiConfig::default(),
            context: ContextConfig::default(),
            history: HistoryConfig::default(),
            keys: KeyConfig::default(),
            plugins: PluginConfig::default(),
        }
    }
}

impl Default for AiConfig {
    fn default() -> Self {
        Self {
            provider: "openai".to_string(),
            model: "gpt-4".to_string(),
            endpoint: "https://api.openai.com/v1/chat/completions".to_string(),
            api_key_env: "OPENAI_API_KEY".to_string(),
            max_tokens: 2048,
            timeout: 30,
            temperature: 0.7,
            max_context: 8192,
        }
    }
}

impl Default for ModeConfig {
    fn default() -> Self {
        Self {
            default: "assist".to_string(),
            shell: None,
            shell_args: vec!["-l".to_string()],
        }
    }
}

impl Default for SafetyConfig {
    fn default() -> Self {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        Self {
            require_confirmation_for_destructive: true,
            require_confirmation_for_sudo: true,
            allow_ai_to_execute_sudo: false,
            log_ai_generated_commands: true,
            log_path: home.join(".aishell/logs/commands.log"),
            max_log_size: 10 * 1024 * 1024, // 10MB
            log_retention: 5,
            redact_secrets: true,
            blocked_patterns: vec![
                r"rm\s+-rf\s+/\s*$".to_string(),
                r"rm\s+-rf\s+/\*".to_string(),
                r"dd\s+.*of=/dev/sd[a-z]\s*$".to_string(),
                r"mkfs\.\S+\s+/dev/sd[a-z]\s*$".to_string(),
                r":\(\)\{\s*:\|:\s*&\s*\}\s*;".to_string(), // Fork bomb
            ],
            protected_paths: vec![
                "/etc/passwd".to_string(),
                "/etc/shadow".to_string(),
                "/etc/sudoers".to_string(),
                "~/.ssh/authorized_keys".to_string(),
            ],
        }
    }
}

impl Default for UiConfig {
    fn default() -> Self {
        Self {
            show_plan_before_execution: true,
            show_step_numbers: true,
            prompt: "{user}@{host}:{cwd} [{mode}]$ ".to_string(),
            mode_indicators: ModeIndicators::default(),
            color: true,
            colors: ColorConfig::default(),
            show_timestamps: false,
            spinner: "dots".to_string(),
        }
    }
}

impl Default for ModeIndicators {
    fn default() -> Self {
        Self {
            off: "shell".to_string(),
            assist: "ai:assist".to_string(),
            auto: "ai:auto".to_string(),
        }
    }
}

impl Default for ColorConfig {
    fn default() -> Self {
        Self {
            prompt_user: "green".to_string(),
            prompt_host: "blue".to_string(),
            prompt_cwd: "cyan".to_string(),
            ai_plan: "yellow".to_string(),
            ai_command: "white".to_string(),
            ai_warning: "red".to_string(),
            ai_success: "green".to_string(),
        }
    }
}

impl Default for ContextConfig {
    fn default() -> Self {
        Self {
            include_files: vec![
                "README.md".to_string(),
                "Makefile".to_string(),
                "docker-compose.yml".to_string(),
                "package.json".to_string(),
                "Cargo.toml".to_string(),
            ],
            exclude_patterns: vec![
                "*.log".to_string(),
                "node_modules/*".to_string(),
                "target/*".to_string(),
                ".git/*".to_string(),
            ],
            max_file_size: 100 * 1024, // 100KB
            max_context_size: 512 * 1024, // 512KB
            history_lines: 20,
            domain_hint: String::new(),
        }
    }
}

impl Default for HistoryConfig {
    fn default() -> Self {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        Self {
            enabled: true,
            file: home.join(".aishell/history"),
            max_entries: 10000,
            share_with_shell: true,
            ignore_space: true,
            ignore_patterns: vec![
                r"^ai\s+.*password".to_string(),
                r"^export.*API_KEY".to_string(),
            ],
        }
    }
}

impl Default for KeyConfig {
    fn default() -> Self {
        Self {
            ai_mode: "Alt-a".to_string(),
            toggle_assist: "Alt-m".to_string(),
            ai_help: "Alt-h".to_string(),
            cancel: "Ctrl-c".to_string(),
            accept: "Enter".to_string(),
            edit: "e".to_string(),
            reject: "n".to_string(),
        }
    }
}

impl Default for PluginConfig {
    fn default() -> Self {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        Self {
            enabled: true,
            directory: home.join(".aishell/plugins"),
            auto_load: true,
            load: vec![],
            timeout: 30,
        }
    }
}

impl Config {
    /// Load configuration from all sources
    pub fn load(cli_config: Option<&Path>) -> Result<Self, ConfigError> {
        let mut config = Config::default();

        // Load system config
        let system_config = Path::new("/etc/aishell/config.toml");
        if system_config.exists() {
            debug!("Loading system config from {:?}", system_config);
            config.merge_from_file(system_config)?;
        }

        // Load user config
        if let Some(home) = dirs::home_dir() {
            let user_config = home.join(".aishell/config.toml");
            if user_config.exists() {
                debug!("Loading user config from {:?}", user_config);
                config.merge_from_file(&user_config)?;
            }
        }

        // Load CLI-specified config
        if let Some(path) = cli_config {
            debug!("Loading CLI config from {:?}", path);
            config.merge_from_file(path)?;
        }

        // Apply environment overrides
        config.apply_env_overrides();

        Ok(config)
    }

    /// Load and merge project config (.aishellrc)
    pub fn load_project_config(&mut self, dir: &Path) -> Result<(), ConfigError> {
        let project_config = dir.join(".aishellrc");
        if project_config.exists() {
            debug!("Loading project config from {:?}", project_config);
            self.merge_from_file(&project_config)?;
        }
        Ok(())
    }

    /// Merge configuration from a file
    fn merge_from_file(&mut self, path: &Path) -> Result<(), ConfigError> {
        let contents = std::fs::read_to_string(path)
            .map_err(|e| ConfigError::Read(format!("{}: {}", path.display(), e)))?;

        let file_config: Config = toml::from_str(&contents)
            .map_err(|e| ConfigError::Parse(format!("{}: {}", path.display(), e)))?;

        self.merge(file_config);
        Ok(())
    }

    /// Merge another config into this one (other takes precedence)
    fn merge(&mut self, other: Config) {
        // AI config
        if other.ai.provider != AiConfig::default().provider {
            self.ai.provider = other.ai.provider;
        }
        if other.ai.model != AiConfig::default().model {
            self.ai.model = other.ai.model;
        }
        if other.ai.endpoint != AiConfig::default().endpoint {
            self.ai.endpoint = other.ai.endpoint;
        }
        if other.ai.api_key_env != AiConfig::default().api_key_env {
            self.ai.api_key_env = other.ai.api_key_env;
        }

        // Mode config
        if other.mode.default != ModeConfig::default().default {
            self.mode.default = other.mode.default;
        }
        if other.mode.shell.is_some() {
            self.mode.shell = other.mode.shell;
        }

        // Safety config - always take explicit values
        self.safety.require_confirmation_for_destructive =
            other.safety.require_confirmation_for_destructive;
        self.safety.require_confirmation_for_sudo = other.safety.require_confirmation_for_sudo;
        self.safety.allow_ai_to_execute_sudo = other.safety.allow_ai_to_execute_sudo;
        self.safety.log_ai_generated_commands = other.safety.log_ai_generated_commands;

        // Context config
        if !other.context.include_files.is_empty() {
            self.context.include_files = other.context.include_files;
        }
        if !other.context.exclude_patterns.is_empty() {
            self.context.exclude_patterns = other.context.exclude_patterns;
        }
        if !other.context.domain_hint.is_empty() {
            self.context.domain_hint = other.context.domain_hint;
        }
    }

    /// Apply environment variable overrides
    fn apply_env_overrides(&mut self) {
        if let Ok(mode) = std::env::var("AISHELL_MODE") {
            self.mode.default = mode;
        }
        if let Ok(shell) = std::env::var("AISHELL_SHELL") {
            self.mode.shell = Some(shell);
        }
        if let Ok(log) = std::env::var("AISHELL_LOG") {
            self.safety.log_path = PathBuf::from(log);
        }
        if std::env::var("AISHELL_DEBUG").is_ok() {
            // Debug mode handled in main
        }
    }

    /// Validate configuration
    pub fn validate(&self) -> Result<(), ConfigError> {
        // Validate AI config
        if self.ai.provider.is_empty() {
            return Err(ConfigError::MissingField("ai.provider".to_string()));
        }
        if self.ai.model.is_empty() {
            return Err(ConfigError::MissingField("ai.model".to_string()));
        }

        // Validate mode
        let valid_modes = ["off", "assist", "auto"];
        if !valid_modes.contains(&self.mode.default.as_str()) {
            return Err(ConfigError::Invalid(format!(
                "mode.default must be one of: {:?}",
                valid_modes
            )));
        }

        Ok(())
    }

    /// Get API key from environment
    pub fn get_api_key(&self) -> Option<String> {
        std::env::var(&self.ai.api_key_env).ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = Config::default();
        assert_eq!(config.ai.provider, "openai");
        assert_eq!(config.mode.default, "assist");
        assert!(config.safety.require_confirmation_for_destructive);
    }

    #[test]
    fn test_config_validation() {
        let config = Config::default();
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_invalid_mode() {
        let mut config = Config::default();
        config.mode.default = "invalid".to_string();
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_parse_config() {
        let toml_str = r#"
            [ai]
            provider = "anthropic"
            model = "claude-3"

            [mode]
            default = "off"

            [safety]
            allow_ai_to_execute_sudo = true
        "#;

        let config: Config = toml::from_str(toml_str).unwrap();
        assert_eq!(config.ai.provider, "anthropic");
        assert_eq!(config.mode.default, "off");
        assert!(config.safety.allow_ai_to_execute_sudo);
    }
}

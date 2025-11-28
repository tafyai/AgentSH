//! AI Orchestrator module
//!
//! Handles communication with the LLM backend, prompt construction,
//! and parsing of AI responses.

use crate::config::Config;
use crate::error::AiError;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tracing::{debug, warn};

/// Result type for AI operations
type Result<T> = std::result::Result<T, AiError>;

/// Type of action returned by AI
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ActionKind {
    /// Pure text answer, no commands
    AnswerOnly,
    /// One or more commands to execute
    CommandSequence,
    /// Multi-step plan with commands
    PlanAndCommands,
}

/// A single step in an AI action plan
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Step {
    /// Unique identifier for this step
    pub id: String,
    /// Human-readable description
    pub description: String,
    /// The shell command to execute
    pub shell_command: String,
    /// Whether step requires explicit confirmation
    #[serde(default)]
    pub needs_confirmation: bool,
    /// Whether step is destructive
    #[serde(default)]
    pub is_destructive: bool,
    /// Whether step requires sudo
    #[serde(default)]
    pub requires_sudo: bool,
    /// Working directory for command
    #[serde(default)]
    pub working_directory: Option<PathBuf>,
}

/// AI response action
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiAction {
    /// Type of action
    pub kind: ActionKind,
    /// Summary/explanation text
    #[serde(default)]
    pub summary: Option<String>,
    /// Steps to execute (for command types)
    #[serde(default)]
    pub steps: Vec<Step>,
}

impl AiAction {
    /// Create an answer-only action
    pub fn answer_only(text: &str) -> Self {
        Self {
            kind: ActionKind::AnswerOnly,
            summary: Some(text.to_string()),
            steps: vec![],
        }
    }

    /// Check if this action has commands to execute
    pub fn has_commands(&self) -> bool {
        !self.steps.is_empty()
    }
}

/// Context information sent to AI
#[derive(Debug, Clone, Serialize)]
pub struct AiContext {
    /// Operating system info
    pub os: String,
    /// Current working directory
    pub cwd: String,
    /// Current user
    pub user: String,
    /// Last command (for ai fix)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_command: Option<String>,
    /// Last exit code
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_exit_code: Option<i32>,
    /// Last stderr output
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_stderr: Option<String>,
    /// Recent command history
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub history: Vec<String>,
}

impl Default for AiContext {
    fn default() -> Self {
        Self {
            os: get_os_info(),
            cwd: std::env::current_dir()
                .map(|p| p.to_string_lossy().to_string())
                .unwrap_or_else(|_| ".".to_string()),
            user: std::env::var("USER").unwrap_or_else(|_| "unknown".to_string()),
            last_command: None,
            last_exit_code: None,
            last_stderr: None,
            history: vec![],
        }
    }
}

/// AI Orchestrator handles LLM communication
pub struct AiOrchestrator {
    config: Config,
    client: reqwest::Client,
    context: AiContext,
    conversation_history: Vec<Message>,
}

/// Message in conversation
#[derive(Debug, Clone, Serialize, Deserialize)]
struct Message {
    role: String,
    content: String,
}

impl AiOrchestrator {
    /// Create a new AI orchestrator
    pub fn new(config: Config) -> Self {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(config.ai.timeout))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            config,
            client,
            context: AiContext::default(),
            conversation_history: vec![],
        }
    }

    /// Update context with current state
    pub fn update_context(&mut self, context: AiContext) {
        self.context = context;
    }

    /// Set last command info (for ai fix)
    pub fn set_last_command(&mut self, cmd: &str, exit_code: i32, stderr: Option<String>) {
        self.context.last_command = Some(cmd.to_string());
        self.context.last_exit_code = Some(exit_code);
        self.context.last_stderr = stderr;
    }

    /// Clear conversation history
    pub fn clear_history(&mut self) {
        self.conversation_history.clear();
    }

    /// Send a query to the AI and get an action response
    pub async fn query(&mut self, user_input: &str, mode: QueryMode) -> Result<AiAction> {
        let api_key = self.config.get_api_key().ok_or_else(|| {
            AiError::Unavailable(format!(
                "API key not found in {}",
                self.config.ai.api_key_env
            ))
        })?;

        // Build the system prompt based on mode
        let system_prompt = build_system_prompt(&mode);

        // Build user message with context
        let user_message = build_user_message(user_input, &self.context, &mode);

        // Build messages array
        let mut messages = vec![Message {
            role: "system".to_string(),
            content: system_prompt,
        }];

        // Add conversation history (limited)
        let history_limit = 10;
        let start = self.conversation_history.len().saturating_sub(history_limit);
        messages.extend(self.conversation_history[start..].iter().cloned());

        // Add current user message
        messages.push(Message {
            role: "user".to_string(),
            content: user_message.clone(),
        });

        debug!("Sending request to AI with {} messages", messages.len());

        // Send request
        let response = self.send_request(&api_key, &messages).await?;

        // Store in history
        self.conversation_history.push(Message {
            role: "user".to_string(),
            content: user_message,
        });
        self.conversation_history.push(Message {
            role: "assistant".to_string(),
            content: response.clone(),
        });

        // Parse response
        parse_ai_response(&response, &mode)
    }

    /// Send HTTP request to LLM API
    async fn send_request(&self, api_key: &str, messages: &[Message]) -> Result<String> {
        let request_body = serde_json::json!({
            "model": self.config.ai.model,
            "messages": messages,
            "max_tokens": self.config.ai.max_tokens,
            "temperature": self.config.ai.temperature,
        });

        let response = self
            .client
            .post(&self.config.ai.endpoint)
            .header("Authorization", format!("Bearer {}", api_key))
            .header("Content-Type", "application/json")
            .json(&request_body)
            .send()
            .await
            .map_err(|e| AiError::Network(e.to_string()))?;

        let status = response.status();
        if !status.is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(AiError::Api {
                status: status.as_u16(),
                message: error_text,
            });
        }

        let response_json: serde_json::Value = response
            .json()
            .await
            .map_err(|e| AiError::Parse(e.to_string()))?;

        // Extract content from response (OpenAI format)
        let content = response_json["choices"][0]["message"]["content"]
            .as_str()
            .ok_or_else(|| AiError::Parse("No content in response".to_string()))?;

        Ok(content.to_string())
    }
}

/// Query mode determines prompt construction
#[derive(Debug, Clone)]
pub enum QueryMode {
    /// General query (ai <question>)
    General,
    /// Run mode (ai run "task")
    Run,
    /// Explain mode (ai explain 'command')
    Explain { command: String },
    /// Fix mode (ai fix)
    Fix,
    /// Do mode (ai do "task")
    Do,
    /// System info mode
    SysInfo,
}

/// Build system prompt based on query mode
fn build_system_prompt(mode: &QueryMode) -> String {
    let base = r#"You are a shell operations assistant for agentsh.

RULES:
1. You NEVER run commands directly - only propose actions in JSON format
2. Prefer minimal, safe, auditable commands
3. Mark destructive operations (rm -rf, mkfs, dd, etc.) with is_destructive: true
4. Mark privileged operations with requires_sudo: true
5. Use available context instead of guessing system state

RESPONSE FORMAT:
Always respond with valid JSON matching this schema:
{
  "kind": "answer_only" | "command_sequence" | "plan_and_commands",
  "summary": "Brief explanation (optional)",
  "steps": [
    {
      "id": "step1",
      "description": "What this step does",
      "shell_command": "the command",
      "needs_confirmation": false,
      "is_destructive": false,
      "requires_sudo": false,
      "working_directory": null
    }
  ]
}
"#;

    match mode {
        QueryMode::Explain { .. } => format!(
            "{}\n\nFor this EXPLAIN request, respond with kind=\"answer_only\" and put your explanation in the summary field. Do NOT include any commands.",
            base
        ),
        QueryMode::Fix => format!(
            "{}\n\nFor this FIX request, analyze the error and propose commands to fix it. Explain what went wrong in the summary.",
            base
        ),
        QueryMode::Do => format!(
            "{}\n\nFor this DO request, create a comprehensive multi-step plan. Use kind=\"plan_and_commands\" with detailed steps.",
            base
        ),
        QueryMode::SysInfo => format!(
            "{}\n\nFor this SYSINFO request, propose commands to gather system information. Keep commands read-only and safe.",
            base
        ),
        _ => base.to_string(),
    }
}

/// Build user message with context
fn build_user_message(input: &str, context: &AiContext, mode: &QueryMode) -> String {
    let mut message = String::new();

    // Add context
    message.push_str(&format!(
        "Context:\n- OS: {}\n- CWD: {}\n- User: {}\n",
        context.os, context.cwd, context.user
    ));

    // Add last command info for fix mode
    if let QueryMode::Fix = mode {
        if let Some(cmd) = &context.last_command {
            message.push_str(&format!("- Last command: {}\n", cmd));
        }
        if let Some(code) = context.last_exit_code {
            message.push_str(&format!("- Exit code: {}\n", code));
        }
        if let Some(stderr) = &context.last_stderr {
            message.push_str(&format!("- Error output:\n```\n{}\n```\n", stderr));
        }
    }

    message.push_str(&format!("\nRequest: {}", input));

    message
}

/// Parse AI response into AiAction
fn parse_ai_response(response: &str, mode: &QueryMode) -> Result<AiAction> {
    // Try to parse as JSON directly
    if let Ok(action) = serde_json::from_str::<AiAction>(response) {
        return Ok(action);
    }

    // Try to extract JSON from markdown code block
    if let Some(json_str) = extract_json_from_markdown(response) {
        if let Ok(action) = serde_json::from_str::<AiAction>(&json_str) {
            return Ok(action);
        }
    }

    // Try to find JSON object in response
    if let Some(json_str) = extract_json_object(response) {
        if let Ok(action) = serde_json::from_str::<AiAction>(&json_str) {
            return Ok(action);
        }
    }

    // Fallback: treat as answer-only
    warn!("Could not parse AI response as JSON, treating as answer-only");
    Ok(AiAction::answer_only(response))
}

/// Extract JSON from markdown code block
fn extract_json_from_markdown(text: &str) -> Option<String> {
    let patterns = ["```json\n", "```JSON\n", "```\n"];

    for pattern in patterns {
        if let Some(start) = text.find(pattern) {
            let json_start = start + pattern.len();
            if let Some(end) = text[json_start..].find("```") {
                return Some(text[json_start..json_start + end].to_string());
            }
        }
    }
    None
}

/// Extract JSON object from text
fn extract_json_object(text: &str) -> Option<String> {
    let start = text.find('{')?;
    let mut depth = 0;
    let mut end = start;

    for (i, c) in text[start..].char_indices() {
        match c {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    end = start + i + 1;
                    break;
                }
            }
            _ => {}
        }
    }

    if depth == 0 && end > start {
        Some(text[start..end].to_string())
    } else {
        None
    }
}

/// Get OS information string
fn get_os_info() -> String {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;

    #[cfg(unix)]
    {
        if let Ok(output) = std::process::Command::new("uname").arg("-r").output() {
            let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
            return format!("{} {} {}", os, arch, version);
        }
    }

    format!("{} {}", os, arch)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_answer_only() {
        let json = r#"{"kind": "answer_only", "summary": "This is the answer"}"#;
        let action: AiAction = serde_json::from_str(json).unwrap();
        assert_eq!(action.kind, ActionKind::AnswerOnly);
        assert_eq!(action.summary, Some("This is the answer".to_string()));
    }

    #[test]
    fn test_parse_command_sequence() {
        let json = r#"{
            "kind": "command_sequence",
            "summary": "List files",
            "steps": [
                {
                    "id": "step1",
                    "description": "List all files",
                    "shell_command": "ls -la"
                }
            ]
        }"#;
        let action: AiAction = serde_json::from_str(json).unwrap();
        assert_eq!(action.kind, ActionKind::CommandSequence);
        assert_eq!(action.steps.len(), 1);
        assert_eq!(action.steps[0].shell_command, "ls -la");
    }

    #[test]
    fn test_extract_json_from_markdown() {
        let text = "Here's the response:\n```json\n{\"kind\": \"answer_only\"}\n```\n";
        let json = extract_json_from_markdown(text).unwrap();
        assert!(json.contains("answer_only"));
    }

    #[test]
    fn test_extract_json_object() {
        let text = "Some text {\"key\": \"value\"} more text";
        let json = extract_json_object(text).unwrap();
        assert_eq!(json, "{\"key\": \"value\"}");
    }

    #[test]
    fn test_parse_fallback() {
        let result = parse_ai_response("Just plain text", &QueryMode::General);
        assert!(result.is_ok());
        let action = result.unwrap();
        assert_eq!(action.kind, ActionKind::AnswerOnly);
    }
}

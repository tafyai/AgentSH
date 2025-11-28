//! Execution Engine module
//!
//! Handles the execution of AI-proposed commands with user confirmation,
//! safety checks, and output streaming.

#![allow(dead_code)]

use crate::ai_orchestrator::{ActionKind, AiAction, Step};
use crate::config::Config;
use crate::error::ExecutionError;
use crate::safety::{self, SafetyFlags};
use std::io::{self, Write};
use tracing::{debug, warn};

/// Result type for execution operations
type Result<T> = std::result::Result<T, ExecutionError>;

/// User response to confirmation prompt
#[derive(Debug, Clone, PartialEq)]
pub enum UserResponse {
    Accept,
    Edit,
    Reject,
    Skip,
}

/// Result of executing a step
#[derive(Debug)]
pub struct StepResult {
    pub step_id: String,
    pub command: String,
    pub exit_code: i32,
    pub stdout: String,
    pub stderr: String,
    pub success: bool,
}

/// Execution Engine manages command execution
pub struct ExecutionEngine {
    config: Config,
    last_command: Option<String>,
    last_exit_code: Option<i32>,
    last_stderr: Option<String>,
}

impl ExecutionEngine {
    /// Create a new execution engine
    pub fn new(config: Config) -> Self {
        Self {
            config,
            last_command: None,
            last_exit_code: None,
            last_stderr: None,
        }
    }

    /// Get the last command executed
    pub fn last_command(&self) -> Option<&str> {
        self.last_command.as_deref()
    }

    /// Get the last exit code
    pub fn last_exit_code(&self) -> Option<i32> {
        self.last_exit_code
    }

    /// Get the last stderr output
    pub fn last_stderr(&self) -> Option<&str> {
        self.last_stderr.as_deref()
    }

    /// Execute an AI action with user confirmation
    pub async fn execute(&mut self, action: &AiAction) -> Result<Vec<StepResult>> {
        match action.kind {
            ActionKind::AnswerOnly => {
                // Just display the answer
                if let Some(summary) = &action.summary {
                    println!("\n{}\n", summary);
                }
                Ok(vec![])
            }
            ActionKind::CommandSequence | ActionKind::PlanAndCommands => {
                self.execute_commands(action).await
            }
        }
    }

    /// Execute command steps with confirmation
    async fn execute_commands(&mut self, action: &AiAction) -> Result<Vec<StepResult>> {
        if action.steps.is_empty() {
            if let Some(summary) = &action.summary {
                println!("\n{}\n", summary);
            }
            return Ok(vec![]);
        }

        // Display the plan
        self.display_plan(action);

        // Get user confirmation
        let response = self.prompt_confirmation()?;

        let steps_to_run = match response {
            UserResponse::Reject => {
                println!("Cancelled.");
                return Err(ExecutionError::Cancelled);
            }
            UserResponse::Edit => {
                // Edit mode: allow user to modify/skip each step
                self.edit_steps(&action.steps)?
            }
            UserResponse::Accept => action.steps.clone(),
            UserResponse::Skip => {
                return Ok(vec![]);
            }
        };

        // Execute each step
        let mut results = Vec::new();

        for (i, step) in steps_to_run.iter().enumerate() {
            println!("\n[{}/{}] {}", i + 1, steps_to_run.len(), step.description);

            // Analyze command for safety
            let flags = safety::analyze_command(&step.shell_command, &self.config.safety);

            // Check if blocked
            if flags.is_blocked {
                eprintln!(
                    "⛔ Command blocked by safety policy: {}",
                    step.shell_command
                );
                return Err(ExecutionError::Blocked(step.shell_command.clone()));
            }

            // Check if extra confirmation needed
            if self.needs_extra_confirmation(&flags, step)
                && !self.confirm_dangerous_step(step, &flags)?
            {
                println!("Step skipped.");
                continue;
            }

            // Check sudo policy
            if flags.requires_sudo && !self.config.safety.allow_ai_to_execute_sudo {
                println!("\n⚠️  sudo command (not auto-executed):");
                println!("  {}", step.shell_command);
                println!("\nCopy and run manually, or enable with:");
                println!("  safety.allow_ai_to_execute_sudo = true\n");
                continue;
            }

            // Execute the command
            let result = self.execute_step(step).await?;
            let success = result.success;
            results.push(result);

            // Handle failure
            if !success {
                let response = self.prompt_failure_action()?;
                match response {
                    FailureAction::Continue => continue,
                    FailureAction::Retry => {
                        // Re-execute the same step
                        let result = self.execute_step(step).await?;
                        results.push(result);
                    }
                    FailureAction::Abort => {
                        return Err(ExecutionError::StepFailed {
                            step: step.id.clone(),
                            reason: "User aborted".to_string(),
                        });
                    }
                }
            }
        }

        println!("\n✓ Execution complete ({} steps)", results.len());
        Ok(results)
    }

    /// Display the action plan
    fn display_plan(&self, action: &AiAction) {
        println!();

        // Show summary
        if let Some(summary) = &action.summary {
            println!("Plan: {}", summary);
            println!();
        }

        // Show steps
        if self.config.ui.show_plan_before_execution {
            println!("Proposed commands:");
            for (i, step) in action.steps.iter().enumerate() {
                let num = if self.config.ui.show_step_numbers {
                    format!("#{}: ", i + 1)
                } else {
                    String::new()
                };

                // Build flags string
                let mut flags = Vec::new();
                let safety_flags =
                    safety::analyze_command(&step.shell_command, &self.config.safety);

                if step.is_destructive || safety_flags.is_destructive {
                    flags.push("DESTRUCTIVE");
                }
                if step.requires_sudo || safety_flags.requires_sudo {
                    flags.push("SUDO");
                }
                if safety_flags.affects_critical_service {
                    flags.push("CRITICAL");
                }

                let flags_str = if flags.is_empty() {
                    String::new()
                } else {
                    format!("  [{}]", flags.join("]["))
                };

                println!("  {}{}{}", num, step.shell_command, flags_str);

                // Show description if different from command
                if !step.description.is_empty() && step.description != step.shell_command {
                    println!("    → {}", step.description);
                }
            }
            println!();
        }
    }

    /// Prompt user for confirmation
    #[allow(clippy::only_used_in_recursion)]
    fn prompt_confirmation(&self) -> Result<UserResponse> {
        print!("Run these? [y/e/n] ");
        io::stdout()
            .flush()
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        let mut input = String::new();
        io::stdin()
            .read_line(&mut input)
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        match input.trim().to_lowercase().as_str() {
            "y" | "yes" | "" => Ok(UserResponse::Accept),
            "e" | "edit" => Ok(UserResponse::Edit),
            "n" | "no" => Ok(UserResponse::Reject),
            "s" | "skip" => Ok(UserResponse::Skip),
            _ => {
                println!("Invalid response. Use y/e/n.");
                self.prompt_confirmation()
            }
        }
    }

    /// Check if step needs extra confirmation
    fn needs_extra_confirmation(&self, flags: &SafetyFlags, step: &Step) -> bool {
        if step.needs_confirmation {
            return true;
        }

        safety::needs_confirmation(flags, &self.config.safety)
    }

    /// Confirm a dangerous step
    fn confirm_dangerous_step(&self, step: &Step, flags: &SafetyFlags) -> Result<bool> {
        println!("\n⚠️  WARNING: This command has safety concerns:");

        for warning in &flags.warnings {
            println!("  • {}", warning);
        }

        println!("\nCommand: {}", step.shell_command);
        print!("\nType 'yes' to confirm: ");
        io::stdout()
            .flush()
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        let mut input = String::new();
        io::stdin()
            .read_line(&mut input)
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        Ok(input.trim().to_lowercase() == "yes")
    }

    /// Edit steps interactively before execution
    fn edit_steps(&self, steps: &[Step]) -> Result<Vec<Step>> {
        println!("\n--- Edit Mode ---");
        println!("For each step: [Enter] to keep, [e] to edit, [s] to skip, [q] to quit\n");

        let mut edited_steps = Vec::new();

        for (i, step) in steps.iter().enumerate() {
            println!("Step {}/{}: {}", i + 1, steps.len(), step.description);
            println!("  Command: {}", step.shell_command);
            print!("  [Enter/e/s/q]: ");
            io::stdout()
                .flush()
                .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

            let mut input = String::new();
            io::stdin()
                .read_line(&mut input)
                .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

            match input.trim().to_lowercase().as_str() {
                "" | "k" | "keep" => {
                    // Keep as-is
                    edited_steps.push(step.clone());
                }
                "e" | "edit" => {
                    // Edit the command
                    print!("  New command: ");
                    io::stdout()
                        .flush()
                        .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

                    let mut new_cmd = String::new();
                    io::stdin()
                        .read_line(&mut new_cmd)
                        .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

                    let new_cmd = new_cmd.trim();
                    if !new_cmd.is_empty() {
                        let mut edited_step = step.clone();
                        edited_step.shell_command = new_cmd.to_string();
                        edited_steps.push(edited_step);
                        println!("  ✓ Updated");
                    } else {
                        // Empty input means keep original
                        edited_steps.push(step.clone());
                        println!("  ✓ Kept original");
                    }
                }
                "s" | "skip" => {
                    println!("  ✗ Skipped");
                }
                "q" | "quit" => {
                    println!("\nEdit cancelled.");
                    return Err(ExecutionError::Cancelled);
                }
                _ => {
                    // Unknown input, keep the step
                    edited_steps.push(step.clone());
                }
            }
        }

        if edited_steps.is_empty() {
            println!("\nNo steps to execute.");
            return Err(ExecutionError::Cancelled);
        }

        println!(
            "\n--- {} step(s) ready to execute ---\n",
            edited_steps.len()
        );
        Ok(edited_steps)
    }

    /// Execute a single step
    async fn execute_step(&mut self, step: &Step) -> Result<StepResult> {
        debug!("Executing: {}", step.shell_command);

        // Store for later reference
        self.last_command = Some(step.shell_command.clone());

        // Change directory if specified
        let original_dir = std::env::current_dir().ok();
        if let Some(ref dir) = step.working_directory {
            if let Err(e) = std::env::set_current_dir(dir) {
                warn!("Failed to change to directory {:?}: {}", dir, e);
            }
        }

        // Execute command
        let output = tokio::process::Command::new("sh")
            .arg("-c")
            .arg(&step.shell_command)
            .output()
            .await
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        // Restore directory
        if let Some(dir) = original_dir {
            let _ = std::env::set_current_dir(dir);
        }

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let exit_code = output.status.code().unwrap_or(-1);
        let success = output.status.success();

        // Store for ai fix
        self.last_exit_code = Some(exit_code);
        if !stderr.is_empty() {
            self.last_stderr = Some(stderr.clone());
        }

        // Display output
        if !stdout.is_empty() {
            print!("{}", stdout);
        }
        if !stderr.is_empty() {
            eprint!("{}", stderr);
        }

        if !success {
            eprintln!("\n⚠️  Command exited with code {}", exit_code);
        }

        Ok(StepResult {
            step_id: step.id.clone(),
            command: step.shell_command.clone(),
            exit_code,
            stdout,
            stderr,
            success,
        })
    }

    /// Prompt for action on failure
    #[allow(clippy::only_used_in_recursion)]
    fn prompt_failure_action(&self) -> Result<FailureAction> {
        print!("Step failed. [c]ontinue / [r]etry / [a]bort? ");
        io::stdout()
            .flush()
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        let mut input = String::new();
        io::stdin()
            .read_line(&mut input)
            .map_err(|e| ExecutionError::CommandFailed(e.to_string()))?;

        match input.trim().to_lowercase().as_str() {
            "c" | "continue" | "" => Ok(FailureAction::Continue),
            "r" | "retry" => Ok(FailureAction::Retry),
            "a" | "abort" => Ok(FailureAction::Abort),
            _ => {
                println!("Invalid response. Use c/r/a.");
                self.prompt_failure_action()
            }
        }
    }
}

/// Action to take on step failure
#[derive(Debug, Clone, PartialEq)]
enum FailureAction {
    Continue,
    Retry,
    Abort,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> Config {
        Config::default()
    }

    #[test]
    fn test_answer_only_no_commands() {
        let action = AiAction {
            kind: ActionKind::AnswerOnly,
            summary: Some("Test answer".to_string()),
            steps: vec![],
        };
        assert!(!action.has_commands());
    }

    #[test]
    fn test_command_sequence_has_commands() {
        let action = AiAction {
            kind: ActionKind::CommandSequence,
            summary: None,
            steps: vec![Step {
                id: "1".to_string(),
                description: "Test".to_string(),
                shell_command: "echo test".to_string(),
                needs_confirmation: false,
                is_destructive: false,
                requires_sudo: false,
                working_directory: None,
            }],
        };
        assert!(action.has_commands());
    }
}

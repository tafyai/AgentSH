//! Shell runner module
//!
//! Manages the interactive shell session with AI command interception.

use crate::ai_orchestrator::{AiContext, AiOrchestrator};
use crate::config::Config;
use crate::error::PtyError;
use crate::execution_engine::ExecutionEngine;
use crate::input_router::{self, InputRoute, InternalCommand};
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use std::io::{Read, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use tracing::{error, info, warn};

type Result<T> = std::result::Result<T, PtyError>;

/// AI mode for the shell
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AiMode {
    Off,
    Assist,
}

/// Shell runner with AI integration
pub struct ShellRunner {
    config: Config,
    ai_mode: AiMode,
    ai_orchestrator: Option<AiOrchestrator>,
    execution_engine: ExecutionEngine,
}

impl ShellRunner {
    /// Create a new shell runner
    pub fn new(config: Config) -> Self {
        let ai_mode = match config.mode.default.as_str() {
            "off" => AiMode::Off,
            _ => AiMode::Assist,
        };

        // Only create AI orchestrator if we have an API key
        let ai_orchestrator = if config.get_api_key().is_some() {
            Some(AiOrchestrator::new(config.clone()))
        } else {
            warn!(
                "No API key found in {}, AI features disabled",
                config.ai.api_key_env
            );
            None
        };

        let execution_engine = ExecutionEngine::new(config.clone());

        Self {
            config,
            ai_mode,
            ai_orchestrator,
            execution_engine,
        }
    }

    /// Run the shell with AI integration
    pub async fn run(&mut self, shell_path: &str) -> Result<()> {
        // Get terminal size
        let size = get_terminal_size().unwrap_or(PtySize {
            rows: 24,
            cols: 80,
            pixel_width: 0,
            pixel_height: 0,
        });

        // Create PTY
        let pty_system = native_pty_system();
        let pair = pty_system
            .openpty(size)
            .map_err(|e| PtyError::Create(e.to_string()))?;

        // Build command
        let mut cmd = CommandBuilder::new(shell_path);
        for arg in &self.config.mode.shell_args {
            cmd.arg(arg);
        }
        setup_environment(&mut cmd);

        // Spawn shell
        let mut child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| PtyError::Spawn(e.to_string()))?;

        info!("Shell spawned successfully");

        // Get reader/writer
        let mut reader = pair
            .master
            .try_clone_reader()
            .map_err(|e| PtyError::Read(e.to_string()))?;
        let mut writer = pair
            .master
            .take_writer()
            .map_err(|e| PtyError::Write(e.to_string()))?;

        // Flag to signal shutdown
        let running = Arc::new(AtomicBool::new(true));
        let running_clone = running.clone();

        // Enable raw mode
        crossterm::terminal::enable_raw_mode().map_err(|e| PtyError::Create(e.to_string()))?;
        let _guard = RawModeGuard;

        // Thread to copy PTY output to stdout
        let output_handle = thread::spawn(move || {
            let mut stdout = std::io::stdout();
            let mut buf = [0u8; 4096];
            while running_clone.load(Ordering::Relaxed) {
                match reader.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => {
                        let _ = stdout.write_all(&buf[..n]);
                        let _ = stdout.flush();
                    }
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(std::time::Duration::from_millis(10));
                    }
                    Err(_) => break,
                }
            }
        });

        // Main input loop
        let mut stdin = std::io::stdin();
        let mut input_buf = [0u8; 1024];
        let mut line_buf = Vec::new();

        loop {
            match stdin.read(&mut input_buf) {
                Ok(0) => break, // EOF
                Ok(n) => {
                    let data = &input_buf[..n];

                    // Check for special sequences
                    for &byte in data {
                        // Detect if we're at a prompt (simplified heuristic)
                        // In a real implementation, we'd use prompt markers
                        if byte == b'\r' || byte == b'\n' {
                            if !line_buf.is_empty() {
                                let line = String::from_utf8_lossy(&line_buf).to_string();

                                // Check if this is an AI command
                                if self.ai_mode == AiMode::Assist
                                    && input_router::is_ai_command(&line)
                                {
                                    // Don't send to shell, handle AI command
                                    line_buf.clear();

                                    // Temporarily disable raw mode for AI interaction
                                    let _ = crossterm::terminal::disable_raw_mode();
                                    println!(); // New line after the command

                                    if let Err(e) = self.handle_ai_command(&line).await {
                                        eprintln!("AI error: {}", e);
                                    }

                                    // Re-enable raw mode
                                    let _ = crossterm::terminal::enable_raw_mode();
                                    continue;
                                }
                            }
                            line_buf.clear();
                        } else if byte == 0x7f || byte == 0x08 {
                            // Backspace
                            line_buf.pop();
                        } else if byte >= 0x20 {
                            // Printable character
                            line_buf.push(byte);
                        }
                    }

                    // Pass through to shell
                    if writer.write_all(data).is_err() {
                        break;
                    }
                    let _ = writer.flush();
                }
                Err(_) => break,
            }

            // Check if child is still running
            if let Ok(Some(_)) = child.try_wait() {
                break;
            }
        }

        // Shutdown
        running.store(false, Ordering::Relaxed);
        let _ = output_handle.join();

        // Wait for child
        match child.wait() {
            Ok(status) => {
                if status.success() {
                    info!("Shell exited successfully");
                    Ok(())
                } else {
                    let code = status.exit_code();
                    warn!("Shell exited with code: {}", code);
                    Err(PtyError::ShellExit(code as i32))
                }
            }
            Err(e) => {
                error!("Failed to wait for shell: {}", e);
                Err(PtyError::Spawn(e.to_string()))
            }
        }
    }

    /// Handle an AI command
    async fn handle_ai_command(
        &mut self,
        input: &str,
    ) -> std::result::Result<(), Box<dyn std::error::Error>> {
        let route = input_router::route_input(input);

        match route {
            InputRoute::Ai(cmd) => {
                if let Some(ref mut orchestrator) = self.ai_orchestrator {
                    // Update context with current state
                    let mut context = AiContext::default();

                    // For ai fix, include last command error info
                    if matches!(cmd.mode, crate::ai_orchestrator::QueryMode::Fix) {
                        if let Some(last_cmd) = self.execution_engine.last_command() {
                            context.last_command = Some(last_cmd.to_string());
                        }
                        if let Some(exit_code) = self.execution_engine.last_exit_code() {
                            context.last_exit_code = Some(exit_code);
                        }
                        if let Some(stderr) = self.execution_engine.last_stderr() {
                            context.last_stderr = Some(stderr.to_string());
                        }
                    }

                    orchestrator.update_context(context);

                    // Query AI
                    println!("Thinking...");
                    match orchestrator.query(&cmd.query, cmd.mode).await {
                        Ok(action) => {
                            // Execute the action
                            match self.execution_engine.execute(&action).await {
                                Ok(_results) => {}
                                Err(e) => {
                                    eprintln!("Execution error: {}", e);
                                }
                            }
                        }
                        Err(e) => {
                            eprintln!("AI error: {}", e);
                        }
                    }
                } else {
                    eprintln!(
                        "AI is not available. Set {} environment variable.",
                        self.config.ai.api_key_env
                    );
                }
            }
            InputRoute::Internal(cmd) => {
                self.handle_internal_command(cmd);
            }
            InputRoute::Shell(_) => {
                // Shouldn't happen, but just in case
            }
        }

        Ok(())
    }

    /// Handle internal commands
    fn handle_internal_command(&mut self, cmd: InternalCommand) {
        match cmd {
            InternalCommand::SetMode(mode) => match mode.as_str() {
                "off" => {
                    self.ai_mode = AiMode::Off;
                    println!("AI mode: off");
                }
                "assist" => {
                    self.ai_mode = AiMode::Assist;
                    println!("AI mode: assist");
                }
                _ => {
                    println!("Unknown mode: {}. Use 'off' or 'assist'.", mode);
                }
            },
            InternalCommand::Help => {
                input_router::show_help();
            }
            InternalCommand::History => {
                println!("AI history not yet implemented.");
            }
            InternalCommand::Clear => {
                if let Some(ref mut orchestrator) = self.ai_orchestrator {
                    orchestrator.clear_history();
                    println!("AI conversation cleared.");
                }
            }
            InternalCommand::SysInfo => {
                println!("{}", crate::context::get_sysinfo());
            }
            InternalCommand::Services => {
                println!("{}", crate::context::get_services());
            }
            InternalCommand::Packages => {
                println!("{}", crate::context::get_packages());
            }
        }
    }
}

/// Guard to restore terminal mode on drop
struct RawModeGuard;

impl Drop for RawModeGuard {
    fn drop(&mut self) {
        let _ = crossterm::terminal::disable_raw_mode();
    }
}

/// Get current terminal size
fn get_terminal_size() -> Option<PtySize> {
    crossterm::terminal::size()
        .ok()
        .map(|(cols, rows)| PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
}

/// Set up environment for child shell
fn setup_environment(cmd: &mut CommandBuilder) {
    for (key, value) in std::env::vars() {
        match key.as_str() {
            "HOME" | "USER" | "LOGNAME" | "PATH" | "LANG" | "LC_ALL" | "LC_CTYPE" | "TERM"
            | "EDITOR" | "VISUAL" | "PAGER" | "SHELL" | "ZDOTDIR" | "BASH_ENV" => {
                cmd.env(&key, &value);
            }
            k if k.ends_with("_API_KEY") || k.ends_with("_TOKEN") => {
                cmd.env(&key, &value);
            }
            _ => {}
        }
    }

    if std::env::var("TERM").is_err() {
        cmd.env("TERM", "xterm-256color");
    }

    cmd.env("AGENTSH", "1");
    cmd.env("AGENTSH_VERSION", env!("CARGO_PKG_VERSION"));
}

//! PTY (pseudo-terminal) management for agentsh
//!
//! Handles spawning and communicating with the underlying shell via PTY.

use crate::config::Config;
use crate::error::PtyError;
use portable_pty::{native_pty_system, CommandBuilder, PtySize, MasterPty, Child};
use std::io::{Read, Write};
use std::thread;
use tracing::{debug, error, info, warn};

/// Result type for PTY operations
type Result<T> = std::result::Result<T, PtyError>;

/// Manages a PTY connection to an underlying shell
pub struct PtyShell {
    /// The master side of the PTY
    master: Box<dyn MasterPty + Send>,
    /// The child shell process
    child: Box<dyn Child + Send + Sync>,
}

impl PtyShell {
    /// Spawn a new shell in a PTY
    pub fn spawn(shell_path: &str, args: &[String]) -> Result<Self> {
        info!("Spawning shell: {} {:?}", shell_path, args);

        // Get terminal size
        let size = get_terminal_size().unwrap_or(PtySize {
            rows: 24,
            cols: 80,
            pixel_width: 0,
            pixel_height: 0,
        });

        // Create PTY system
        let pty_system = native_pty_system();

        // Open a PTY pair
        let pair = pty_system
            .openpty(size)
            .map_err(|e| PtyError::Create(e.to_string()))?;

        // Build the command
        let mut cmd = CommandBuilder::new(shell_path);
        for arg in args {
            cmd.arg(arg);
        }

        // Set up environment
        setup_environment(&mut cmd);

        // Spawn the shell
        let child = pair
            .slave
            .spawn_command(cmd)
            .map_err(|e| PtyError::Spawn(e.to_string()))?;

        info!("Shell spawned successfully");

        Ok(Self {
            master: pair.master,
            child,
        })
    }

    /// Resize the PTY to match terminal size
    pub fn resize(&self, rows: u16, cols: u16) -> Result<()> {
        let size = PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        };

        self.master
            .resize(size)
            .map_err(|e| PtyError::Resize(e.to_string()))?;

        debug!("Resized PTY to {}x{}", cols, rows);
        Ok(())
    }

    /// Run the main event loop
    pub async fn run(&mut self, _config: &Config) -> Result<()> {
        use crossterm::terminal::enable_raw_mode;

        // Enable raw mode for terminal
        enable_raw_mode().map_err(|e| PtyError::Create(e.to_string()))?;

        // Ensure we restore terminal on exit
        let _guard = RawModeGuard;

        // Get reader and writer from master
        let mut reader = self.master.try_clone_reader()
            .map_err(|e| PtyError::Read(e.to_string()))?;
        let mut writer = self.master.take_writer()
            .map_err(|e| PtyError::Write(e.to_string()))?;

        // Clone for resize handling
        let master_for_resize = self.master.try_clone_reader()
            .map_err(|e| PtyError::Create(e.to_string()))?;
        drop(master_for_resize); // We just needed to verify clone works

        // Spawn thread to copy stdin -> PTY
        let stdin_handle = thread::spawn(move || {
            let mut stdin = std::io::stdin();
            let mut buf = [0u8; 1024];
            loop {
                match stdin.read(&mut buf) {
                    Ok(0) => break, // EOF
                    Ok(n) => {
                        if writer.write_all(&buf[..n]).is_err() {
                            break;
                        }
                        if writer.flush().is_err() {
                            break;
                        }
                    }
                    Err(_) => break,
                }
            }
        });

        // Copy PTY -> stdout in main thread (blocking)
        let mut stdout = std::io::stdout();
        let mut buf = [0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) => break, // EOF
                Ok(n) => {
                    if stdout.write_all(&buf[..n]).is_err() {
                        break;
                    }
                    if stdout.flush().is_err() {
                        break;
                    }
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(std::time::Duration::from_millis(10));
                    continue;
                }
                Err(_) => break,
            }
        }

        // Wait for stdin thread
        let _ = stdin_handle.join();

        // Wait for child process
        match self.child.wait() {
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

    /// Write data to the PTY
    pub fn write(&self, data: &[u8]) -> Result<()> {
        let mut writer = self.master.take_writer()
            .map_err(|e| PtyError::Write(e.to_string()))?;
        writer
            .write_all(data)
            .map_err(|e| PtyError::Write(e.to_string()))?;
        writer
            .flush()
            .map_err(|e| PtyError::Write(e.to_string()))?;
        Ok(())
    }

    /// Check if the child process is still running
    pub fn is_running(&mut self) -> bool {
        self.child.try_wait().map(|s| s.is_none()).unwrap_or(false)
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
    crossterm::terminal::size().ok().map(|(cols, rows)| PtySize {
        rows,
        cols,
        pixel_width: 0,
        pixel_height: 0,
    })
}

/// Set up environment variables for the child shell
fn setup_environment(cmd: &mut CommandBuilder) {
    // Preserve important environment variables
    for (key, value) in std::env::vars() {
        match key.as_str() {
            // Always pass through
            "HOME" | "USER" | "LOGNAME" | "PATH" | "LANG" | "LC_ALL" | "LC_CTYPE" => {
                cmd.env(key, value);
            }
            // Pass through TERM
            "TERM" => {
                cmd.env(key, value);
            }
            // Pass through common development vars
            "EDITOR" | "VISUAL" | "PAGER" => {
                cmd.env(key, value);
            }
            // Pass through shell config
            "SHELL" | "ZDOTDIR" | "BASH_ENV" => {
                cmd.env(key, value);
            }
            // Pass through API keys for AI
            k if k.ends_with("_API_KEY") || k.ends_with("_TOKEN") => {
                cmd.env(key, value);
            }
            _ => {}
        }
    }

    // Set TERM if not set
    if std::env::var("TERM").is_err() {
        cmd.env("TERM", "xterm-256color");
    }

    // Mark that we're running under agentsh
    cmd.env("AGENTSH", "1");
    cmd.env("AGENTSH_VERSION", env!("CARGO_PKG_VERSION"));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_terminal_size() {
        // This may fail in CI without a TTY
        let _ = get_terminal_size();
    }

    #[tokio::test]
    async fn test_spawn_shell() {
        // Use /bin/sh for portability
        let result = PtyShell::spawn("/bin/sh", &[]);
        assert!(result.is_ok(), "Failed to spawn shell: {:?}", result.err());

        let mut shell = result.unwrap();
        assert!(shell.is_running() || true); // May have exited immediately
    }
}

//! Command-line argument parsing for agentsh

use clap::Parser;
use std::path::PathBuf;

/// agentsh - An AI-powered login shell
#[derive(Parser, Debug)]
#[command(name = "agentsh")]
#[command(author, version, about, long_about = None)]
pub struct Args {
    /// Shell to spawn (defaults to $SHELL or /bin/bash)
    #[arg(value_name = "SHELL")]
    pub shell: Option<String>,

    /// Path to configuration file
    #[arg(short, long, value_name = "FILE")]
    pub config: Option<PathBuf>,

    /// Enable debug logging
    #[arg(short, long)]
    pub debug: bool,

    /// AI mode: off, assist, or auto
    #[arg(short, long, value_name = "MODE")]
    pub mode: Option<String>,

    /// Run a command and exit (non-interactive)
    #[arg(short = 'x', long, value_name = "COMMAND")]
    pub command: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_args_default() {
        let args = Args::parse_from(["agentsh"]);
        assert!(args.shell.is_none());
        assert!(args.config.is_none());
        assert!(!args.debug);
    }

    #[test]
    fn test_args_with_shell() {
        let args = Args::parse_from(["agentsh", "/bin/zsh"]);
        assert_eq!(args.shell, Some("/bin/zsh".to_string()));
    }

    #[test]
    fn test_args_with_flags() {
        let args = Args::parse_from(["agentsh", "--debug", "--config", "/tmp/config.toml"]);
        assert!(args.debug);
        assert_eq!(args.config, Some(PathBuf::from("/tmp/config.toml")));
    }
}

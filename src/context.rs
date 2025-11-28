//! Context Collector module
//!
//! Gathers system context information to provide to the AI,
//! including OS info, current directory, and file contents.

use crate::config::ContextConfig;
use std::path::Path;
use std::process::Command;
use tracing::{debug, warn};

/// Collected context for AI
#[derive(Debug, Clone, Default)]
pub struct SystemContext {
    pub os: OsInfo,
    pub cwd: String,
    pub user: String,
    pub hostname: String,
    pub files: Vec<FileContext>,
}

/// Operating system information
#[derive(Debug, Clone, Default)]
pub struct OsInfo {
    pub name: String,
    pub version: String,
    pub arch: String,
    pub kernel: String,
}

/// File context
#[derive(Debug, Clone)]
pub struct FileContext {
    pub path: String,
    pub content: String,
    pub truncated: bool,
}

impl SystemContext {
    /// Collect all system context
    pub fn collect(config: &ContextConfig) -> Self {
        let os = collect_os_info();
        let cwd = std::env::current_dir()
            .map(|p| p.to_string_lossy().to_string())
            .unwrap_or_else(|_| ".".to_string());
        let user = std::env::var("USER").unwrap_or_else(|_| "unknown".to_string());
        let hostname = get_hostname();

        let files = collect_files(config);

        Self {
            os,
            cwd,
            user,
            hostname,
            files,
        }
    }

    /// Format as string for AI prompt
    pub fn format_for_prompt(&self) -> String {
        let mut output = String::new();

        output.push_str(&format!("OS: {} {} ({})\n", self.os.name, self.os.version, self.os.arch));
        output.push_str(&format!("Kernel: {}\n", self.os.kernel));
        output.push_str(&format!("User: {}@{}\n", self.user, self.hostname));
        output.push_str(&format!("CWD: {}\n", self.cwd));

        if !self.files.is_empty() {
            output.push_str("\nProject files:\n");
            for file in &self.files {
                output.push_str(&format!("\n--- {} ---\n", file.path));
                output.push_str(&file.content);
                if file.truncated {
                    output.push_str("\n[truncated]");
                }
                output.push('\n');
            }
        }

        output
    }
}

/// Collect OS information
fn collect_os_info() -> OsInfo {
    let name = std::env::consts::OS.to_string();
    let arch = std::env::consts::ARCH.to_string();

    // Get kernel version
    let kernel = get_command_output("uname", &["-r"]).unwrap_or_else(|| "unknown".to_string());

    // Get OS version
    let version = get_os_version().unwrap_or_else(|| "unknown".to_string());

    OsInfo {
        name,
        version,
        arch,
        kernel,
    }
}

/// Get OS version from various sources
fn get_os_version() -> Option<String> {
    // Try /etc/os-release first (Linux)
    if let Ok(content) = std::fs::read_to_string("/etc/os-release") {
        for line in content.lines() {
            if line.starts_with("PRETTY_NAME=") {
                let version = line
                    .trim_start_matches("PRETTY_NAME=")
                    .trim_matches('"')
                    .to_string();
                return Some(version);
            }
        }
    }

    // Try sw_vers (macOS)
    if let Some(output) = get_command_output("sw_vers", &["-productVersion"]) {
        return Some(format!("macOS {}", output));
    }

    None
}

/// Get hostname
fn get_hostname() -> String {
    get_command_output("hostname", &[]).unwrap_or_else(|| {
        std::env::var("HOSTNAME").unwrap_or_else(|_| "localhost".to_string())
    })
}

/// Run a command and get its output
fn get_command_output(cmd: &str, args: &[&str]) -> Option<String> {
    Command::new(cmd)
        .args(args)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
}

/// Collect relevant files based on config
fn collect_files(config: &ContextConfig) -> Vec<FileContext> {
    let mut files = Vec::new();
    let mut total_size: u64 = 0;

    for pattern in &config.include_files {
        let path = Path::new(pattern);
        if path.exists() && path.is_file() {
            if let Some(context) = read_file_context(path, config) {
                total_size += context.content.len() as u64;
                if total_size > config.max_context_size {
                    debug!("Reached max context size, stopping file collection");
                    break;
                }
                files.push(context);
            }
        }
    }

    files
}

/// Read file content for context
fn read_file_context(path: &Path, config: &ContextConfig) -> Option<FileContext> {
    let metadata = std::fs::metadata(path).ok()?;

    // Check file size
    if metadata.len() > config.max_file_size {
        debug!("File {:?} exceeds max size, skipping", path);
        return None;
    }

    // Check exclude patterns
    let path_str = path.to_string_lossy();
    for pattern in &config.exclude_patterns {
        if path_str.contains(pattern.trim_end_matches('*')) {
            debug!("File {:?} matches exclude pattern, skipping", path);
            return None;
        }
    }

    // Read content
    match std::fs::read_to_string(path) {
        Ok(content) => {
            let truncated = content.len() as u64 > config.max_file_size;
            let content = if truncated {
                content.chars().take(config.max_file_size as usize).collect()
            } else {
                content
            };

            Some(FileContext {
                path: path.to_string_lossy().to_string(),
                content,
                truncated,
            })
        }
        Err(e) => {
            warn!("Failed to read {:?}: {}", path, e);
            None
        }
    }
}

/// Get system information summary
pub fn get_sysinfo() -> String {
    let mut output = String::new();

    // OS info
    output.push_str("=== System Information ===\n\n");

    if let Some(uname) = get_command_output("uname", &["-a"]) {
        output.push_str(&format!("System: {}\n", uname));
    }

    // CPU info
    #[cfg(target_os = "linux")]
    {
        if let Ok(cpuinfo) = std::fs::read_to_string("/proc/cpuinfo") {
            for line in cpuinfo.lines() {
                if line.starts_with("model name") {
                    output.push_str(&format!("CPU: {}\n", line.split(':').nth(1).unwrap_or("").trim()));
                    break;
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Some(cpu) = get_command_output("sysctl", &["-n", "machdep.cpu.brand_string"]) {
            output.push_str(&format!("CPU: {}\n", cpu));
        }
    }

    // Memory info
    #[cfg(target_os = "linux")]
    {
        if let Ok(meminfo) = std::fs::read_to_string("/proc/meminfo") {
            for line in meminfo.lines() {
                if line.starts_with("MemTotal:") || line.starts_with("MemAvailable:") {
                    output.push_str(&format!("{}\n", line));
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        if let Some(mem) = get_command_output("sysctl", &["-n", "hw.memsize"]) {
            if let Ok(bytes) = mem.parse::<u64>() {
                let gb = bytes as f64 / 1024.0 / 1024.0 / 1024.0;
                output.push_str(&format!("Memory: {:.1} GB\n", gb));
            }
        }
    }

    // Disk usage
    if let Some(df) = get_command_output("df", &["-h", "/"]) {
        output.push_str("\nDisk Usage:\n");
        output.push_str(&df);
        output.push('\n');
    }

    output
}

/// Get list of running services
pub fn get_services() -> String {
    let mut output = String::new();
    output.push_str("=== Running Services ===\n\n");

    // Try systemctl first (Linux with systemd)
    if let Some(services) = get_command_output("systemctl", &["list-units", "--type=service", "--state=running", "--no-pager"]) {
        output.push_str(&services);
        return output;
    }

    // Try launchctl (macOS)
    #[cfg(target_os = "macos")]
    if let Some(services) = get_command_output("launchctl", &["list"]) {
        output.push_str(&services);
        return output;
    }

    // Fallback: just list common service processes
    if let Some(ps) = get_command_output("ps", &["aux"]) {
        output.push_str("Running processes:\n");
        output.push_str(&ps);
    }

    output
}

/// Get list of installed packages
pub fn get_packages() -> String {
    let mut output = String::new();
    output.push_str("=== Installed Packages ===\n\n");

    // Detect package manager and list packages
    let package_managers = [
        ("dpkg", vec!["-l"]),
        ("rpm", vec!["-qa"]),
        ("pacman", vec!["-Q"]),
        ("brew", vec!["list"]),
    ];

    for (pm, args) in package_managers {
        if let Some(packages) = get_command_output(pm, &args.iter().map(|s| *s).collect::<Vec<_>>()) {
            output.push_str(&format!("Package manager: {}\n\n", pm));
            // Limit output
            let lines: Vec<&str> = packages.lines().take(50).collect();
            output.push_str(&lines.join("\n"));
            if packages.lines().count() > 50 {
                output.push_str(&format!("\n\n... and {} more packages", packages.lines().count() - 50));
            }
            return output;
        }
    }

    output.push_str("No package manager detected.\n");
    output
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collect_os_info() {
        let info = collect_os_info();
        assert!(!info.name.is_empty());
        assert!(!info.arch.is_empty());
    }

    #[test]
    fn test_get_hostname() {
        let hostname = get_hostname();
        assert!(!hostname.is_empty());
    }

    #[test]
    fn test_system_context_format() {
        let config = ContextConfig::default();
        let context = SystemContext::collect(&config);
        let formatted = context.format_for_prompt();
        assert!(formatted.contains("OS:"));
        assert!(formatted.contains("User:"));
    }
}

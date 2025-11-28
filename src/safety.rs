//! Safety module for detecting dangerous commands
//!
//! Analyzes proposed commands to detect destructive operations,
//! privilege escalation, and other potentially dangerous actions.

use crate::config::SafetyConfig;
use once_cell::sync::Lazy;
use regex::Regex;

/// Safety flags returned from command analysis
#[derive(Debug, Clone, Default)]
pub struct SafetyFlags {
    /// Command could cause data loss or damage
    pub is_destructive: bool,
    /// Command requires sudo/root privileges
    pub requires_sudo: bool,
    /// Command affects critical system services
    pub affects_critical_service: bool,
    /// Command modifies installed packages
    pub modifies_packages: bool,
    /// Command modifies protected paths
    pub modifies_protected_path: bool,
    /// Command is in the blocked list
    pub is_blocked: bool,
    /// Specific warnings about the command
    pub warnings: Vec<String>,
}

impl SafetyFlags {
    /// Check if any safety concern was raised
    pub fn has_concerns(&self) -> bool {
        self.is_destructive
            || self.requires_sudo
            || self.affects_critical_service
            || self.modifies_packages
            || self.modifies_protected_path
            || self.is_blocked
    }

    /// Get a summary of concerns
    pub fn summary(&self) -> Vec<&'static str> {
        let mut concerns = Vec::new();
        if self.is_destructive {
            concerns.push("DESTRUCTIVE");
        }
        if self.requires_sudo {
            concerns.push("SUDO");
        }
        if self.affects_critical_service {
            concerns.push("CRITICAL SERVICE");
        }
        if self.modifies_packages {
            concerns.push("PACKAGE CHANGE");
        }
        if self.modifies_protected_path {
            concerns.push("PROTECTED PATH");
        }
        if self.is_blocked {
            concerns.push("BLOCKED");
        }
        concerns
    }
}

/// Destructive filesystem patterns
static DESTRUCTIVE_FS_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"rm\s+.*-[rR]").unwrap(),           // rm -r, rm -R
        Regex::new(r"rm\s+-[^-]*f").unwrap(),           // rm -f
        Regex::new(r"rm\s+/").unwrap(),                 // rm / (anything in root)
        Regex::new(r"rmdir\s+--ignore-fail").unwrap(),  // rmdir with force
        Regex::new(r"find\s+.*-delete").unwrap(),       // find -delete
        Regex::new(r"find\s+.*-exec\s+rm").unwrap(),    // find -exec rm
        Regex::new(r">\s*/dev/sd[a-z]").unwrap(),       // redirect to block device
        Regex::new(r"mv\s+/\s").unwrap(),               // mv / (moving root)
        Regex::new(r"chmod\s+-R\s+777").unwrap(),       // chmod -R 777
        Regex::new(r"chown\s+-R").unwrap(),             // chown -R
    ]
});

/// Block device patterns
static BLOCK_DEVICE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"dd\s+.*of=/dev/").unwrap(),        // dd to device
        Regex::new(r"mkfs").unwrap(),                   // any mkfs
        Regex::new(r"fdisk").unwrap(),                  // fdisk
        Regex::new(r"parted").unwrap(),                 // parted
        Regex::new(r"wipefs").unwrap(),                 // wipefs
        Regex::new(r"shred\s+/dev/").unwrap(),          // shred device
    ]
});

/// Network/firewall patterns
static NETWORK_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"iptables\s+-F").unwrap(),          // flush rules
        Regex::new(r"iptables\s+-P\s+\w+\s+DROP").unwrap(), // default drop
        Regex::new(r"ufw\s+disable").unwrap(),          // disable firewall
        Regex::new(r"firewall-cmd\s+--panic").unwrap(), // panic mode
        Regex::new(r"nft\s+flush").unwrap(),            // nftables flush
    ]
});

/// Critical service patterns
static CRITICAL_SERVICE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"systemctl\s+(stop|restart|disable)\s+ssh").unwrap(),
        Regex::new(r"systemctl\s+(stop|restart|disable)\s+sshd").unwrap(),
        Regex::new(r"service\s+ssh\s+(stop|restart)").unwrap(),
        Regex::new(r"service\s+sshd\s+(stop|restart)").unwrap(),
        Regex::new(r"kill\s+-9\s+1\b").unwrap(),        // kill init
        Regex::new(r"pkill\s+.*init").unwrap(),         // pkill init
        Regex::new(r"systemctl\s+.*halt").unwrap(),     // system halt
        Regex::new(r"shutdown").unwrap(),               // shutdown
        Regex::new(r"reboot").unwrap(),                 // reboot
        Regex::new(r"init\s+[06]").unwrap(),            // init 0/6
    ]
});

/// Package manager patterns
static PACKAGE_PATTERNS: Lazy<Vec<Regex>> = Lazy::new(|| {
    vec![
        Regex::new(r"apt(-get)?\s+(install|remove|purge|autoremove)").unwrap(),
        Regex::new(r"apt\s+.*--purge").unwrap(),
        Regex::new(r"dpkg\s+(-r|-P|--remove|--purge)").unwrap(),
        Regex::new(r"yum\s+(install|remove|erase)").unwrap(),
        Regex::new(r"dnf\s+(install|remove|erase)").unwrap(),
        Regex::new(r"pacman\s+-[RS]").unwrap(),
        Regex::new(r"brew\s+(install|uninstall|remove)").unwrap(),
        Regex::new(r"pip\s+uninstall").unwrap(),
        Regex::new(r"npm\s+(uninstall|remove).*-g").unwrap(),
        Regex::new(r"cargo\s+uninstall").unwrap(),
    ]
});

/// Sudo detection pattern
static SUDO_PATTERN: Lazy<Regex> = Lazy::new(|| {
    Regex::new(r"(^|\||\&\&|\;)\s*sudo\s").unwrap()
});

/// Analyze a command for safety concerns
pub fn analyze_command(cmd: &str, config: &SafetyConfig) -> SafetyFlags {
    let mut flags = SafetyFlags::default();

    // Check for blocked patterns first
    for pattern in &config.blocked_patterns {
        if let Ok(re) = Regex::new(pattern) {
            if re.is_match(cmd) {
                flags.is_blocked = true;
                flags.warnings.push(format!("Command matches blocked pattern: {}", pattern));
                return flags; // Blocked commands stop analysis
            }
        }
    }

    // Check for sudo
    if SUDO_PATTERN.is_match(cmd) || cmd.trim().starts_with("sudo ") {
        flags.requires_sudo = true;
        flags.warnings.push("Command requires elevated privileges".to_string());
    }

    // Check destructive filesystem operations
    for pattern in DESTRUCTIVE_FS_PATTERNS.iter() {
        if pattern.is_match(cmd) {
            flags.is_destructive = true;
            flags.warnings.push("Command may delete or modify files".to_string());
            break;
        }
    }

    // Check block device operations
    for pattern in BLOCK_DEVICE_PATTERNS.iter() {
        if pattern.is_match(cmd) {
            flags.is_destructive = true;
            flags.warnings.push("Command operates on block devices".to_string());
            break;
        }
    }

    // Check network/firewall operations
    for pattern in NETWORK_PATTERNS.iter() {
        if pattern.is_match(cmd) {
            flags.is_destructive = true;
            flags.warnings.push("Command modifies network/firewall configuration".to_string());
            break;
        }
    }

    // Check critical service operations
    for pattern in CRITICAL_SERVICE_PATTERNS.iter() {
        if pattern.is_match(cmd) {
            flags.affects_critical_service = true;
            flags.warnings.push("Command affects critical system services".to_string());
            break;
        }
    }

    // Check package management
    for pattern in PACKAGE_PATTERNS.iter() {
        if pattern.is_match(cmd) {
            flags.modifies_packages = true;
            flags.warnings.push("Command modifies installed packages".to_string());
            break;
        }
    }

    // Check protected paths
    for path in &config.protected_paths {
        let expanded = shellexpand_path(path);
        if cmd.contains(&expanded) {
            flags.modifies_protected_path = true;
            flags.warnings.push(format!("Command affects protected path: {}", path));
        }
    }

    flags
}

/// Expand ~ in paths
fn shellexpand_path(path: &str) -> String {
    if path.starts_with("~/") {
        if let Some(home) = dirs::home_dir() {
            return path.replacen("~", &home.to_string_lossy(), 1);
        }
    }
    path.to_string()
}

/// Check if a command should be blocked entirely
pub fn is_command_blocked(cmd: &str, config: &SafetyConfig) -> bool {
    for pattern in &config.blocked_patterns {
        if let Ok(re) = Regex::new(pattern) {
            if re.is_match(cmd) {
                return true;
            }
        }
    }
    false
}

/// Determine if command needs confirmation based on config and flags
pub fn needs_confirmation(flags: &SafetyFlags, config: &SafetyConfig) -> bool {
    if flags.is_blocked {
        return true; // Always confirm blocked (even though we'll reject)
    }

    if flags.is_destructive && config.require_confirmation_for_destructive {
        return true;
    }

    if flags.requires_sudo && config.require_confirmation_for_sudo {
        return true;
    }

    if flags.affects_critical_service {
        return true; // Always confirm critical services
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> SafetyConfig {
        SafetyConfig::default()
    }

    #[test]
    fn test_detect_rm_rf() {
        let flags = analyze_command("rm -rf /tmp/test", &test_config());
        assert!(flags.is_destructive);
    }

    #[test]
    fn test_detect_sudo() {
        let flags = analyze_command("sudo apt update", &test_config());
        assert!(flags.requires_sudo);
    }

    #[test]
    fn test_detect_pipe_sudo() {
        let flags = analyze_command("echo password | sudo -S rm file", &test_config());
        assert!(flags.requires_sudo);
    }

    #[test]
    fn test_detect_mkfs() {
        let flags = analyze_command("mkfs.ext4 /dev/sda1", &test_config());
        assert!(flags.is_destructive);
    }

    #[test]
    fn test_detect_apt_install() {
        let flags = analyze_command("apt install nginx", &test_config());
        assert!(flags.modifies_packages);
    }

    #[test]
    fn test_detect_systemctl_ssh() {
        let flags = analyze_command("systemctl restart sshd", &test_config());
        assert!(flags.affects_critical_service);
    }

    #[test]
    fn test_safe_command() {
        let flags = analyze_command("ls -la", &test_config());
        assert!(!flags.has_concerns());
    }

    #[test]
    fn test_blocked_pattern() {
        let config = test_config();
        let flags = analyze_command("rm -rf /", &config);
        assert!(flags.is_blocked);
    }

    #[test]
    fn test_protected_path() {
        let flags = analyze_command("vim /etc/passwd", &test_config());
        assert!(flags.modifies_protected_path);
    }

    #[test]
    fn test_summary() {
        let flags = analyze_command("sudo rm -rf /tmp/test", &test_config());
        let summary = flags.summary();
        assert!(summary.contains(&"DESTRUCTIVE"));
        assert!(summary.contains(&"SUDO"));
    }
}

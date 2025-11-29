//! Plugin loader
//!
//! Discovers and loads plugins from the plugin directory.

use super::protocol::ToolDefinition;
use crate::config::PluginConfig;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use tracing::{debug, info, warn};

/// Plugin metadata
#[derive(Debug, Clone)]
pub struct PluginInfo {
    /// Plugin name
    pub name: String,
    /// Path to the plugin executable
    pub path: PathBuf,
    /// Tools provided by this plugin
    pub tools: Vec<ToolDefinition>,
    /// Whether plugin is enabled
    pub enabled: bool,
}

/// Loads and manages plugins
pub struct PluginLoader {
    config: PluginConfig,
    plugins: HashMap<String, PluginInfo>,
    tools: HashMap<String, String>, // tool name -> plugin name
}

impl PluginLoader {
    /// Create a new plugin loader
    pub fn new(config: PluginConfig) -> Self {
        Self {
            config,
            plugins: HashMap::new(),
            tools: HashMap::new(),
        }
    }

    /// Discover and load plugins
    pub fn load_plugins(&mut self) -> Result<usize, String> {
        if !self.config.enabled {
            debug!("Plugins disabled in configuration");
            return Ok(0);
        }

        let plugin_dir = &self.config.directory;
        if !plugin_dir.exists() {
            debug!("Plugin directory does not exist: {:?}", plugin_dir);
            if let Err(e) = fs::create_dir_all(plugin_dir) {
                warn!("Failed to create plugin directory: {}", e);
            }
            return Ok(0);
        }

        let mut loaded = 0;

        // If specific plugins are configured, load only those
        if !self.config.load.is_empty() {
            for name in &self.config.load.clone() {
                if let Err(e) = self.load_plugin(name) {
                    warn!("Failed to load plugin '{}': {}", name, e);
                } else {
                    loaded += 1;
                }
            }
            return Ok(loaded);
        }

        // Auto-load all plugins
        if self.config.auto_load {
            loaded = self.auto_load_plugins()?;
        }

        Ok(loaded)
    }

    /// Load a specific plugin by name
    fn load_plugin(&mut self, name: &str) -> Result<(), String> {
        let plugin_path = self.config.directory.join(name);

        // Check for executable or directory
        let exec_path = if plugin_path.is_file() {
            plugin_path.clone()
        } else if plugin_path.is_dir() {
            // Look for main executable in directory
            let main = plugin_path.join("main");
            let bin = plugin_path.join(name);
            if main.exists() {
                main
            } else if bin.exists() {
                bin
            } else {
                return Err(format!("No executable found in plugin directory: {:?}", plugin_path));
            }
        } else {
            return Err(format!("Plugin not found: {}", name));
        };

        // Validate executable
        if !is_executable(&exec_path) {
            return Err(format!("Plugin is not executable: {:?}", exec_path));
        }

        // Load tool definitions
        let tools = self.load_tool_definitions(&plugin_path)?;

        let info = PluginInfo {
            name: name.to_string(),
            path: exec_path,
            tools: tools.clone(),
            enabled: true,
        };

        // Register tools
        for tool in &tools {
            self.tools.insert(tool.name.clone(), name.to_string());
        }

        info!("Loaded plugin '{}' with {} tools", name, tools.len());
        self.plugins.insert(name.to_string(), info);

        Ok(())
    }

    /// Auto-load all plugins from directory
    fn auto_load_plugins(&mut self) -> Result<usize, String> {
        let plugin_dir = &self.config.directory;
        let entries = fs::read_dir(plugin_dir)
            .map_err(|e| format!("Failed to read plugin directory: {}", e))?;

        let mut loaded = 0;

        for entry in entries.flatten() {
            let path = entry.path();
            let name = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or_default();

            // Skip hidden files and non-executables
            if name.starts_with('.') {
                continue;
            }

            // Skip manifest files
            if name.ends_with(".json") || name.ends_with(".toml") {
                continue;
            }

            if let Err(e) = self.load_plugin(name) {
                debug!("Skipping '{}': {}", name, e);
            } else {
                loaded += 1;
            }
        }

        Ok(loaded)
    }

    /// Load tool definitions from plugin manifest
    fn load_tool_definitions(&self, plugin_path: &Path) -> Result<Vec<ToolDefinition>, String> {
        // Look for manifest file
        let manifest_path = if plugin_path.is_dir() {
            plugin_path.join("manifest.json")
        } else {
            plugin_path.with_extension("json")
        };

        if manifest_path.exists() {
            let content = fs::read_to_string(&manifest_path)
                .map_err(|e| format!("Failed to read manifest: {}", e))?;

            let manifest: PluginManifest = serde_json::from_str(&content)
                .map_err(|e| format!("Failed to parse manifest: {}", e))?;

            return Ok(manifest.tools);
        }

        // No manifest found, return empty (plugin will self-describe)
        Ok(vec![])
    }

    /// Get all loaded tools
    pub fn get_tools(&self) -> Vec<&ToolDefinition> {
        self.plugins
            .values()
            .filter(|p| p.enabled)
            .flat_map(|p| &p.tools)
            .collect()
    }

    /// Get plugin for a tool
    pub fn get_plugin_for_tool(&self, tool_name: &str) -> Option<&PluginInfo> {
        self.tools
            .get(tool_name)
            .and_then(|plugin_name| self.plugins.get(plugin_name))
    }

    /// Get all loaded plugins
    pub fn get_plugins(&self) -> &HashMap<String, PluginInfo> {
        &self.plugins
    }

    /// Check if a tool exists
    pub fn has_tool(&self, tool_name: &str) -> bool {
        self.tools.contains_key(tool_name)
    }

    /// Disable a plugin
    #[allow(dead_code)]
    pub fn disable_plugin(&mut self, name: &str) {
        if let Some(plugin) = self.plugins.get_mut(name) {
            plugin.enabled = false;
            // Remove tool mappings
            for tool in &plugin.tools {
                self.tools.remove(&tool.name);
            }
        }
    }

    /// Enable a plugin
    #[allow(dead_code)]
    pub fn enable_plugin(&mut self, name: &str) {
        if let Some(plugin) = self.plugins.get_mut(name) {
            plugin.enabled = true;
            // Restore tool mappings
            for tool in &plugin.tools {
                self.tools.insert(tool.name.clone(), name.to_string());
            }
        }
    }
}

/// Plugin manifest format
#[derive(Debug, serde::Deserialize)]
struct PluginManifest {
    #[allow(dead_code)]
    name: String,
    #[allow(dead_code)]
    version: Option<String>,
    #[allow(dead_code)]
    description: Option<String>,
    tools: Vec<ToolDefinition>,
}

/// Check if a file is executable
#[cfg(unix)]
fn is_executable(path: &PathBuf) -> bool {
    use std::os::unix::fs::PermissionsExt;
    if let Ok(meta) = fs::metadata(path) {
        let mode = meta.permissions().mode();
        mode & 0o111 != 0
    } else {
        false
    }
}

#[cfg(not(unix))]
fn is_executable(path: &PathBuf) -> bool {
    path.exists()
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn test_config(dir: &TempDir) -> PluginConfig {
        PluginConfig {
            enabled: true,
            directory: dir.path().to_path_buf(),
            auto_load: true,
            load: vec![],
            timeout: 30,
        }
    }

    #[test]
    fn test_loader_empty_dir() {
        let temp_dir = TempDir::new().unwrap();
        let config = test_config(&temp_dir);

        let mut loader = PluginLoader::new(config);
        let loaded = loader.load_plugins().unwrap();

        assert_eq!(loaded, 0);
        assert!(loader.get_tools().is_empty());
    }

    #[test]
    fn test_loader_disabled() {
        let temp_dir = TempDir::new().unwrap();
        let mut config = test_config(&temp_dir);
        config.enabled = false;

        let mut loader = PluginLoader::new(config);
        let loaded = loader.load_plugins().unwrap();

        assert_eq!(loaded, 0);
    }

    #[test]
    fn test_loader_nonexistent_dir() {
        let config = PluginConfig {
            enabled: true,
            directory: PathBuf::from("/nonexistent/plugins"),
            auto_load: true,
            load: vec![],
            timeout: 30,
        };

        let mut loader = PluginLoader::new(config);
        let loaded = loader.load_plugins().unwrap();

        assert_eq!(loaded, 0);
    }

    #[test]
    fn test_has_tool() {
        let temp_dir = TempDir::new().unwrap();
        let config = test_config(&temp_dir);

        let mut loader = PluginLoader::new(config);
        loader.tools.insert("test.tool".to_string(), "test".to_string());

        assert!(loader.has_tool("test.tool"));
        assert!(!loader.has_tool("missing.tool"));
    }

    #[test]
    fn test_get_plugin_for_tool() {
        let temp_dir = TempDir::new().unwrap();
        let config = test_config(&temp_dir);

        let mut loader = PluginLoader::new(config);

        let info = PluginInfo {
            name: "test".to_string(),
            path: temp_dir.path().join("test"),
            tools: vec![],
            enabled: true,
        };

        loader.plugins.insert("test".to_string(), info);
        loader.tools.insert("test.tool".to_string(), "test".to_string());

        let plugin = loader.get_plugin_for_tool("test.tool");
        assert!(plugin.is_some());
        assert_eq!(plugin.unwrap().name, "test");
    }
}

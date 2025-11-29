//! Plugin executor
//!
//! Handles spawning plugin processes and communicating with them.

use super::loader::{PluginInfo, PluginLoader};
use super::protocol::{PluginRequest, PluginResponse, RequestContext};
use crate::config::PluginConfig;
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::time::Duration;
use tracing::{debug, error};

/// Plugin executor manages plugin invocation
pub struct PluginExecutor {
    loader: PluginLoader,
    config: PluginConfig,
}

impl PluginExecutor {
    /// Create a new plugin executor
    pub fn new(config: PluginConfig) -> Self {
        let loader = PluginLoader::new(config.clone());
        Self { loader, config }
    }

    /// Initialize and load plugins
    pub fn init(&mut self) -> Result<usize, String> {
        self.loader.load_plugins()
    }

    /// Execute a tool
    pub fn execute(
        &self,
        tool_name: &str,
        params: HashMap<String, serde_json::Value>,
        context: Option<RequestContext>,
    ) -> Result<PluginResponse, String> {
        let plugin = self
            .loader
            .get_plugin_for_tool(tool_name)
            .ok_or_else(|| format!("Tool not found: {}", tool_name))?;

        self.execute_plugin(plugin, tool_name, params, context)
    }

    /// Execute a plugin
    fn execute_plugin(
        &self,
        plugin: &PluginInfo,
        tool_name: &str,
        params: HashMap<String, serde_json::Value>,
        context: Option<RequestContext>,
    ) -> Result<PluginResponse, String> {
        let mut request = PluginRequest::new(tool_name, params);
        if let Some(ctx) = context {
            request.context = Some(ctx);
        }

        debug!("Executing plugin '{}' for tool '{}'", plugin.name, tool_name);

        // Spawn plugin process
        let mut child = Command::new(&plugin.path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn plugin: {}", e))?;

        // Send request
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize request: {}", e))?;

        if let Some(ref mut stdin) = child.stdin {
            writeln!(stdin, "{}", request_json)
                .map_err(|e| format!("Failed to write to plugin: {}", e))?;
        }

        // Wait for response with timeout
        let timeout = Duration::from_secs(self.config.timeout);
        let response = self.read_response(&mut child, &request.id, timeout)?;

        // Clean up
        let _ = child.kill();
        let _ = child.wait();

        Ok(response)
    }

    /// Read response from plugin
    fn read_response(
        &self,
        child: &mut std::process::Child,
        request_id: &str,
        timeout: Duration,
    ) -> Result<PluginResponse, String> {
        let stdout = child.stdout.take()
            .ok_or("Failed to capture plugin stdout")?;

        let reader = BufReader::new(stdout);
        let start = std::time::Instant::now();

        for line in reader.lines() {
            if start.elapsed() > timeout {
                return Err("Plugin timed out".to_string());
            }

            let line = line.map_err(|e| format!("Failed to read plugin output: {}", e))?;

            // Try to parse as JSON response
            if let Ok(response) = serde_json::from_str::<PluginResponse>(&line) {
                if response.id == request_id {
                    return Ok(response);
                }
            }
        }

        Err("Plugin closed without responding".to_string())
    }

    /// Check if a tool is available
    pub fn has_tool(&self, tool_name: &str) -> bool {
        self.loader.has_tool(tool_name)
    }

    /// Get loader reference for tool listing
    pub fn loader(&self) -> &PluginLoader {
        &self.loader
    }

    /// Execute with simple string params (convenience method)
    pub fn execute_simple(
        &self,
        tool_name: &str,
        params: &[(&str, &str)],
    ) -> Result<PluginResponse, String> {
        let params_map: HashMap<String, serde_json::Value> = params
            .iter()
            .map(|(k, v)| (k.to_string(), serde_json::json!(v)))
            .collect();

        self.execute(tool_name, params_map, None)
    }
}

/// Execute a tool synchronously with timeout
#[allow(dead_code)]
pub fn execute_with_timeout(
    plugin_path: &std::path::Path,
    request: &PluginRequest,
    timeout_secs: u64,
) -> Result<PluginResponse, String> {
    let mut child = Command::new(plugin_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn plugin: {}", e))?;

    let request_json = serde_json::to_string(request)
        .map_err(|e| format!("Failed to serialize request: {}", e))?;

    if let Some(ref mut stdin) = child.stdin {
        writeln!(stdin, "{}", request_json)
            .map_err(|e| format!("Failed to write to plugin: {}", e))?;
    }

    // Wait with timeout
    let timeout = Duration::from_secs(timeout_secs);
    let start = std::time::Instant::now();

    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) => {
                if start.elapsed() > timeout {
                    let _ = child.kill();
                    return Err("Plugin timed out".to_string());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            Err(e) => {
                error!("Error waiting for plugin: {}", e);
                break;
            }
        }
    }

    // Read response
    let stdout = child.stdout.take()
        .ok_or("Failed to capture plugin stdout")?;

    let reader = BufReader::new(stdout);
    for line in reader.lines().map_while(Result::ok) {
        if let Ok(response) = serde_json::from_str::<PluginResponse>(&line) {
            if response.id == request.id {
                return Ok(response);
            }
        }
    }

    Err("Plugin closed without responding".to_string())
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
            timeout: 5,
        }
    }

    #[test]
    fn test_executor_no_plugins() {
        let temp_dir = TempDir::new().unwrap();
        let config = test_config(&temp_dir);

        let mut executor = PluginExecutor::new(config);
        let loaded = executor.init().unwrap();

        assert_eq!(loaded, 0);
        assert!(!executor.has_tool("any.tool"));
    }

    #[test]
    fn test_execute_missing_tool() {
        let temp_dir = TempDir::new().unwrap();
        let config = test_config(&temp_dir);

        let executor = PluginExecutor::new(config);
        let result = executor.execute("missing.tool", HashMap::new(), None);

        assert!(result.is_err());
        assert!(result.unwrap_err().contains("Tool not found"));
    }
}

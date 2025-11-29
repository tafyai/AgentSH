//! Built-in tools
//!
//! Provides core tools without needing external plugins.

use super::protocol::{ParameterDef, PluginRequest, PluginResponse, ToolDefinition};
use std::fs;
use std::io::Read;
use std::process::Command;

/// Built-in tools that don't require external plugins
pub struct BuiltinTools;

impl BuiltinTools {
    /// Get all built-in tool definitions
    pub fn definitions() -> Vec<ToolDefinition> {
        vec![
            ToolDefinition {
                name: "fs.read_file".to_string(),
                description: "Read contents of a file".to_string(),
                parameters: vec![
                    ParameterDef {
                        name: "path".to_string(),
                        param_type: "string".to_string(),
                        description: "File path to read".to_string(),
                        required: true,
                        default: None,
                    },
                    ParameterDef {
                        name: "max_size".to_string(),
                        param_type: "number".to_string(),
                        description: "Maximum bytes to read (default 100KB)".to_string(),
                        required: false,
                        default: Some(serde_json::json!(102400)),
                    },
                ],
                requires_confirmation: false,
                is_destructive: false,
            },
            ToolDefinition {
                name: "fs.write_file".to_string(),
                description: "Write content to a file".to_string(),
                parameters: vec![
                    ParameterDef {
                        name: "path".to_string(),
                        param_type: "string".to_string(),
                        description: "File path to write".to_string(),
                        required: true,
                        default: None,
                    },
                    ParameterDef {
                        name: "content".to_string(),
                        param_type: "string".to_string(),
                        description: "Content to write".to_string(),
                        required: true,
                        default: None,
                    },
                    ParameterDef {
                        name: "append".to_string(),
                        param_type: "boolean".to_string(),
                        description: "Append instead of overwrite".to_string(),
                        required: false,
                        default: Some(serde_json::json!(false)),
                    },
                ],
                requires_confirmation: true,
                is_destructive: true,
            },
            ToolDefinition {
                name: "fs.list_dir".to_string(),
                description: "List directory contents".to_string(),
                parameters: vec![
                    ParameterDef {
                        name: "path".to_string(),
                        param_type: "string".to_string(),
                        description: "Directory path".to_string(),
                        required: true,
                        default: None,
                    },
                    ParameterDef {
                        name: "hidden".to_string(),
                        param_type: "boolean".to_string(),
                        description: "Include hidden files".to_string(),
                        required: false,
                        default: Some(serde_json::json!(false)),
                    },
                ],
                requires_confirmation: false,
                is_destructive: false,
            },
            ToolDefinition {
                name: "cmd.run".to_string(),
                description: "Run a shell command".to_string(),
                parameters: vec![
                    ParameterDef {
                        name: "command".to_string(),
                        param_type: "string".to_string(),
                        description: "Command to execute".to_string(),
                        required: true,
                        default: None,
                    },
                    ParameterDef {
                        name: "cwd".to_string(),
                        param_type: "string".to_string(),
                        description: "Working directory".to_string(),
                        required: false,
                        default: None,
                    },
                ],
                requires_confirmation: true,
                is_destructive: true,
            },
        ]
    }

    /// Execute a built-in tool
    pub fn execute(request: &PluginRequest) -> PluginResponse {
        match request.tool.as_str() {
            "fs.read_file" => Self::read_file(request),
            "fs.write_file" => Self::write_file(request),
            "fs.list_dir" => Self::list_dir(request),
            "cmd.run" => Self::run_command(request),
            _ => PluginResponse::error(&request.id, &format!("Unknown tool: {}", request.tool)),
        }
    }

    /// Check if a tool is built-in
    pub fn is_builtin(tool_name: &str) -> bool {
        matches!(
            tool_name,
            "fs.read_file" | "fs.write_file" | "fs.list_dir" | "cmd.run"
        )
    }

    /// Read a file
    fn read_file(request: &PluginRequest) -> PluginResponse {
        let path = match request.require_string("path") {
            Ok(p) => p,
            Err(e) => return PluginResponse::error(&request.id, &e),
        };

        let max_size = request.get_i64("max_size").unwrap_or(102400) as usize;

        let mut file = match fs::File::open(path) {
            Ok(f) => f,
            Err(e) => {
                return PluginResponse::error(&request.id, &format!("Failed to open file: {}", e))
            }
        };

        let mut buffer = vec![0u8; max_size];
        let bytes_read = match file.read(&mut buffer) {
            Ok(n) => n,
            Err(e) => {
                return PluginResponse::error(&request.id, &format!("Failed to read file: {}", e))
            }
        };

        buffer.truncate(bytes_read);
        let content = String::from_utf8_lossy(&buffer);

        PluginResponse::success_with_output(
            &request.id,
            serde_json::json!({
                "path": path,
                "size": bytes_read,
                "truncated": bytes_read == max_size,
            }),
            &content,
        )
    }

    /// Write to a file
    fn write_file(request: &PluginRequest) -> PluginResponse {
        let path = match request.require_string("path") {
            Ok(p) => p,
            Err(e) => return PluginResponse::error(&request.id, &e),
        };

        let content = match request.require_string("content") {
            Ok(c) => c,
            Err(e) => return PluginResponse::error(&request.id, &e),
        };

        let append = request.get_bool("append", false);

        let result = if append {
            use std::io::Write;
            fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(path)
                .and_then(|mut f| f.write_all(content.as_bytes()))
        } else {
            fs::write(path, content)
        };

        match result {
            Ok(()) => PluginResponse::success(
                &request.id,
                serde_json::json!({
                    "path": path,
                    "bytes_written": content.len(),
                    "appended": append,
                }),
            ),
            Err(e) => PluginResponse::error(&request.id, &format!("Failed to write file: {}", e)),
        }
    }

    /// List directory contents
    fn list_dir(request: &PluginRequest) -> PluginResponse {
        let path = match request.require_string("path") {
            Ok(p) => p,
            Err(e) => return PluginResponse::error(&request.id, &e),
        };

        let show_hidden = request.get_bool("hidden", false);

        let entries = match fs::read_dir(path) {
            Ok(entries) => entries,
            Err(e) => {
                return PluginResponse::error(
                    &request.id,
                    &format!("Failed to read directory: {}", e),
                )
            }
        };

        let mut files: Vec<serde_json::Value> = Vec::new();

        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().to_string();

            // Skip hidden files if not requested
            if !show_hidden && name.starts_with('.') {
                continue;
            }

            let is_dir = entry.file_type().map(|t| t.is_dir()).unwrap_or(false);
            let size = entry.metadata().map(|m| m.len()).unwrap_or(0);

            files.push(serde_json::json!({
                "name": name,
                "is_dir": is_dir,
                "size": size,
            }));
        }

        // Sort by name
        files.sort_by(|a, b| {
            let a_name = a["name"].as_str().unwrap_or("");
            let b_name = b["name"].as_str().unwrap_or("");
            a_name.cmp(b_name)
        });

        let output: Vec<String> = files
            .iter()
            .map(|f| {
                let name = f["name"].as_str().unwrap_or("");
                let is_dir = f["is_dir"].as_bool().unwrap_or(false);
                if is_dir {
                    format!("{}/", name)
                } else {
                    name.to_string()
                }
            })
            .collect();

        PluginResponse::success_with_output(
            &request.id,
            serde_json::json!({
                "path": path,
                "count": files.len(),
                "entries": files,
            }),
            &output.join("\n"),
        )
    }

    /// Run a shell command
    fn run_command(request: &PluginRequest) -> PluginResponse {
        let command = match request.require_string("command") {
            Ok(c) => c,
            Err(e) => return PluginResponse::error(&request.id, &e),
        };

        let cwd = request.get_string("cwd");

        let shell = if cfg!(windows) { "cmd" } else { "sh" };
        let shell_arg = if cfg!(windows) { "/C" } else { "-c" };

        let mut cmd = Command::new(shell);
        cmd.arg(shell_arg).arg(command);

        if let Some(dir) = cwd {
            cmd.current_dir(dir);
        }

        let output = match cmd.output() {
            Ok(o) => o,
            Err(e) => {
                return PluginResponse::error(&request.id, &format!("Failed to run command: {}", e))
            }
        };

        let stdout = String::from_utf8_lossy(&output.stdout);
        let stderr = String::from_utf8_lossy(&output.stderr);
        let exit_code = output.status.code().unwrap_or(-1);

        let combined_output = if stderr.is_empty() {
            stdout.to_string()
        } else {
            format!("{}\n[stderr]\n{}", stdout, stderr)
        };

        PluginResponse::success_with_output(
            &request.id,
            serde_json::json!({
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            }),
            &combined_output,
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use tempfile::TempDir;

    fn make_request(tool: &str, params: &[(&str, serde_json::Value)]) -> PluginRequest {
        let params_map: HashMap<String, serde_json::Value> = params
            .iter()
            .map(|(k, v)| (k.to_string(), v.clone()))
            .collect();
        PluginRequest::new(tool, params_map)
    }

    #[test]
    fn test_definitions() {
        let defs = BuiltinTools::definitions();
        assert!(!defs.is_empty());

        // Verify fs.read_file exists
        assert!(defs.iter().any(|d| d.name == "fs.read_file"));
        assert!(defs.iter().any(|d| d.name == "fs.write_file"));
        assert!(defs.iter().any(|d| d.name == "fs.list_dir"));
        assert!(defs.iter().any(|d| d.name == "cmd.run"));
    }

    #[test]
    fn test_is_builtin() {
        assert!(BuiltinTools::is_builtin("fs.read_file"));
        assert!(BuiltinTools::is_builtin("fs.write_file"));
        assert!(BuiltinTools::is_builtin("cmd.run"));
        assert!(!BuiltinTools::is_builtin("custom.tool"));
    }

    #[test]
    fn test_read_file() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("test.txt");
        fs::write(&file_path, "Hello, World!").unwrap();

        let request = make_request(
            "fs.read_file",
            &[("path", serde_json::json!(file_path.to_str().unwrap()))],
        );

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        assert!(response.output.as_ref().unwrap().contains("Hello, World!"));
    }

    #[test]
    fn test_read_file_not_found() {
        let request = make_request(
            "fs.read_file",
            &[("path", serde_json::json!("/nonexistent/file.txt"))],
        );

        let response = BuiltinTools::execute(&request);

        assert!(!response.success);
        assert!(response.error.is_some());
    }

    #[test]
    fn test_write_file() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("output.txt");

        let request = make_request(
            "fs.write_file",
            &[
                ("path", serde_json::json!(file_path.to_str().unwrap())),
                ("content", serde_json::json!("Test content")),
            ],
        );

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        assert_eq!(fs::read_to_string(&file_path).unwrap(), "Test content");
    }

    #[test]
    fn test_write_file_append() {
        let temp_dir = TempDir::new().unwrap();
        let file_path = temp_dir.path().join("append.txt");
        fs::write(&file_path, "First\n").unwrap();

        let request = make_request(
            "fs.write_file",
            &[
                ("path", serde_json::json!(file_path.to_str().unwrap())),
                ("content", serde_json::json!("Second")),
                ("append", serde_json::json!(true)),
            ],
        );

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        assert_eq!(fs::read_to_string(&file_path).unwrap(), "First\nSecond");
    }

    #[test]
    fn test_list_dir() {
        let temp_dir = TempDir::new().unwrap();
        fs::write(temp_dir.path().join("file1.txt"), "").unwrap();
        fs::write(temp_dir.path().join("file2.txt"), "").unwrap();
        fs::create_dir(temp_dir.path().join("subdir")).unwrap();

        let request = make_request(
            "fs.list_dir",
            &[("path", serde_json::json!(temp_dir.path().to_str().unwrap()))],
        );

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        let output = response.output.unwrap();
        assert!(output.contains("file1.txt"));
        assert!(output.contains("file2.txt"));
        assert!(output.contains("subdir/"));
    }

    #[test]
    fn test_list_dir_hidden() {
        let temp_dir = TempDir::new().unwrap();
        fs::write(temp_dir.path().join("visible.txt"), "").unwrap();
        fs::write(temp_dir.path().join(".hidden"), "").unwrap();

        // Without hidden
        let request = make_request(
            "fs.list_dir",
            &[("path", serde_json::json!(temp_dir.path().to_str().unwrap()))],
        );
        let response = BuiltinTools::execute(&request);
        let output = response.output.unwrap();
        assert!(output.contains("visible.txt"));
        assert!(!output.contains(".hidden"));

        // With hidden
        let request = make_request(
            "fs.list_dir",
            &[
                ("path", serde_json::json!(temp_dir.path().to_str().unwrap())),
                ("hidden", serde_json::json!(true)),
            ],
        );
        let response = BuiltinTools::execute(&request);
        let output = response.output.unwrap();
        assert!(output.contains("visible.txt"));
        assert!(output.contains(".hidden"));
    }

    #[test]
    fn test_run_command() {
        let request = make_request("cmd.run", &[("command", serde_json::json!("echo hello"))]);

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        assert!(response.output.unwrap().contains("hello"));
    }

    #[test]
    fn test_run_command_with_cwd() {
        let temp_dir = TempDir::new().unwrap();
        let request = make_request(
            "cmd.run",
            &[
                ("command", serde_json::json!("pwd")),
                ("cwd", serde_json::json!(temp_dir.path().to_str().unwrap())),
            ],
        );

        let response = BuiltinTools::execute(&request);

        assert!(response.success);
        // The output should contain the temp dir path
        let output = response.output.unwrap();
        assert!(output.contains(temp_dir.path().to_str().unwrap()) || output.contains("private"));
        // macOS uses /private/var/...
    }

    #[test]
    fn test_unknown_tool() {
        let request = make_request("unknown.tool", &[]);
        let response = BuiltinTools::execute(&request);

        assert!(!response.success);
        assert!(response.error.unwrap().contains("Unknown tool"));
    }
}

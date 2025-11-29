//! Plugin protocol definitions
//!
//! Defines the JSON request/response format for plugin communication.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Tool definition for AI prompts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolDefinition {
    /// Tool name (e.g., "fs.read_file")
    pub name: String,
    /// Human-readable description
    pub description: String,
    /// Parameter definitions
    pub parameters: Vec<ParameterDef>,
    /// Whether this tool requires confirmation
    #[serde(default)]
    pub requires_confirmation: bool,
    /// Whether this tool is potentially destructive
    #[serde(default)]
    pub is_destructive: bool,
}

/// Parameter definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParameterDef {
    /// Parameter name
    pub name: String,
    /// Parameter type (string, number, boolean, array, object)
    #[serde(rename = "type")]
    pub param_type: String,
    /// Description
    pub description: String,
    /// Whether parameter is required
    #[serde(default)]
    pub required: bool,
    /// Default value
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default: Option<serde_json::Value>,
}

/// Request sent to a plugin
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginRequest {
    /// Request ID for correlation
    pub id: String,
    /// Tool name to invoke
    pub tool: String,
    /// Parameters passed to the tool
    pub params: HashMap<String, serde_json::Value>,
    /// Context information
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context: Option<RequestContext>,
}

/// Context passed with requests
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RequestContext {
    /// Current working directory
    pub cwd: String,
    /// Current user
    pub user: String,
    /// Session ID
    pub session_id: String,
}

/// Response from a plugin
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginResponse {
    /// Request ID this responds to
    pub id: String,
    /// Whether the operation succeeded
    pub success: bool,
    /// Result data (if success)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    /// Error message (if failure)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    /// Human-readable output
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output: Option<String>,
}

impl PluginResponse {
    /// Create a success response
    pub fn success(id: &str, result: serde_json::Value) -> Self {
        Self {
            id: id.to_string(),
            success: true,
            result: Some(result),
            error: None,
            output: None,
        }
    }

    /// Create a success response with output
    pub fn success_with_output(id: &str, result: serde_json::Value, output: &str) -> Self {
        Self {
            id: id.to_string(),
            success: true,
            result: Some(result),
            error: None,
            output: Some(output.to_string()),
        }
    }

    /// Create an error response
    pub fn error(id: &str, message: &str) -> Self {
        Self {
            id: id.to_string(),
            success: false,
            result: None,
            error: Some(message.to_string()),
            output: None,
        }
    }
}

impl PluginRequest {
    /// Create a new request
    pub fn new(tool: &str, params: HashMap<String, serde_json::Value>) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            tool: tool.to_string(),
            params,
            context: None,
        }
    }

    /// Add context to the request
    pub fn with_context(mut self, cwd: &str, user: &str, session_id: &str) -> Self {
        self.context = Some(RequestContext {
            cwd: cwd.to_string(),
            user: user.to_string(),
            session_id: session_id.to_string(),
        });
        self
    }

    /// Get a string parameter
    pub fn get_string(&self, name: &str) -> Option<&str> {
        self.params.get(name).and_then(|v| v.as_str())
    }

    /// Get a required string parameter
    pub fn require_string(&self, name: &str) -> Result<&str, String> {
        self.get_string(name)
            .ok_or_else(|| format!("Missing required parameter: {}", name))
    }

    /// Get a boolean parameter with default
    pub fn get_bool(&self, name: &str, default: bool) -> bool {
        self.params
            .get(name)
            .and_then(|v| v.as_bool())
            .unwrap_or(default)
    }

    /// Get an integer parameter
    pub fn get_i64(&self, name: &str) -> Option<i64> {
        self.params.get(name).and_then(|v| v.as_i64())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plugin_request_new() {
        let mut params = HashMap::new();
        params.insert("path".to_string(), serde_json::json!("/tmp/test"));

        let req = PluginRequest::new("fs.read_file", params);

        assert_eq!(req.tool, "fs.read_file");
        assert_eq!(req.get_string("path"), Some("/tmp/test"));
    }

    #[test]
    fn test_plugin_request_with_context() {
        let req = PluginRequest::new("test", HashMap::new()).with_context(
            "/home/user",
            "testuser",
            "session-123",
        );

        let ctx = req.context.unwrap();
        assert_eq!(ctx.cwd, "/home/user");
        assert_eq!(ctx.user, "testuser");
        assert_eq!(ctx.session_id, "session-123");
    }

    #[test]
    fn test_plugin_response_success() {
        let resp = PluginResponse::success("req-1", serde_json::json!({"data": "test"}));

        assert!(resp.success);
        assert_eq!(resp.id, "req-1");
        assert!(resp.result.is_some());
        assert!(resp.error.is_none());
    }

    #[test]
    fn test_plugin_response_error() {
        let resp = PluginResponse::error("req-2", "File not found");

        assert!(!resp.success);
        assert_eq!(resp.id, "req-2");
        assert!(resp.result.is_none());
        assert_eq!(resp.error, Some("File not found".to_string()));
    }

    #[test]
    fn test_request_require_string() {
        let mut params = HashMap::new();
        params.insert("name".to_string(), serde_json::json!("test"));

        let req = PluginRequest::new("test", params);

        assert_eq!(req.require_string("name").unwrap(), "test");
        assert!(req.require_string("missing").is_err());
    }

    #[test]
    fn test_request_get_bool() {
        let mut params = HashMap::new();
        params.insert("flag".to_string(), serde_json::json!(true));

        let req = PluginRequest::new("test", params);

        assert!(req.get_bool("flag", false));
        assert!(!req.get_bool("missing", false));
        assert!(req.get_bool("missing", true));
    }

    #[test]
    fn test_tool_definition_serialization() {
        let tool = ToolDefinition {
            name: "fs.read_file".to_string(),
            description: "Read a file".to_string(),
            parameters: vec![ParameterDef {
                name: "path".to_string(),
                param_type: "string".to_string(),
                description: "File path".to_string(),
                required: true,
                default: None,
            }],
            requires_confirmation: false,
            is_destructive: false,
        };

        let json = serde_json::to_string(&tool).unwrap();
        assert!(json.contains("fs.read_file"));
        assert!(json.contains("path"));
    }
}

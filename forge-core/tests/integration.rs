use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use async_trait::async_trait;

use forge_core::agent::{Agent, AgentState, LifecycleAgent};
use forge_core::config::ForgeConfig;
use forge_core::permission::{
    ActionClassification, PermissionContext, PermissionDecision, PermissionGate, PermissionMode,
};
use forge_core::port::{ModelError, ModelPort, ModelResponse, ToolCall, ToolSpec};
use forge_core::verifier::VerifierPipeline;
use forge_core_security::containment::Trusted;
use forge_core_security::sandbox::SandboxRoot;

// ---------------------------------------------------------------------------
// Mock ModelPort
// ---------------------------------------------------------------------------

struct MockModelPort {
    content: String,
    tool_calls: Vec<ToolCall>,
}

#[async_trait]
impl ModelPort for MockModelPort {
    async fn generate(
        &self,
        _system: &str,
        _messages: &[HashMap<String, String>],
    ) -> Result<ModelResponse, ModelError> {
        Ok(ModelResponse::new(
            &self.content,
            self.tool_calls.clone(),
            10,
            5,
            "mock-model",
        ))
    }

    async fn generate_with_tools(
        &self,
        _system: &str,
        _messages: &[HashMap<String, String>],
        _tools: &[ToolSpec],
    ) -> Result<ModelResponse, ModelError> {
        self.generate(_system, _messages).await
    }

    async fn count_tokens(&self, _text: &str) -> Result<u64, ModelError> {
        Ok(15)
    }
}

// ---------------------------------------------------------------------------
// test_agent_loop_completes
// ---------------------------------------------------------------------------

#[tokio::test]
async fn test_agent_loop_completes() {
    let mock_port = Arc::new(MockModelPort {
        content: "Hello, I have completed the task.".to_string(),
        tool_calls: vec![],
    });

    let sandbox = SandboxRoot::new(std::env::current_dir().unwrap()).unwrap();
    let cwd = std::env::current_dir().unwrap();
    let verifier = VerifierPipeline::with_default_gates(None);
    let permission_gate = PermissionGate::new(PermissionMode::Yolo);
    let task = Trusted::new_internal("integration test task".to_string());

    let mut state = AgentState {
        task,
        sandbox,
        cwd,
        steps: vec![],
        files_read_in_session: vec![],
        permission_mode: PermissionMode::Yolo,
        permission_gate,
        verifier,
        model_port: None,
        total_tokens: 0,
        total_cost: 0.0,
        max_steps: 5,
        max_tokens: None,
        max_cost: None,
    };

    let mut agent = LifecycleAgent::new(mock_port, vec![], vec![]);
    let result = agent.run(&mut state).await;

    assert!(
        result.success,
        "Agent run should succeed when model returns no tool calls"
    );
    assert!(
        result.total_steps == 0,
        "Expected 0 steps when model makes no tool calls, got {}",
        result.total_steps
    );
    assert_eq!(result.output, "Hello, I have completed the task.");
}

// ---------------------------------------------------------------------------
// test_permission_yolo_accepts
// ---------------------------------------------------------------------------

#[tokio::test]
async fn test_permission_yolo_accepts() {
    let mut gate = PermissionGate::new(PermissionMode::Yolo);
    let sandbox = SandboxRoot::new(std::env::current_dir().unwrap()).unwrap();

    let ctx = PermissionContext {
        action_label: "test-action".to_string(),
        classification: ActionClassification::Safe,
        tool_name: "test_tool".to_string(),
        tool_args: HashMap::new(),
        cwd: std::env::current_dir().unwrap(),
        sandbox,
        files_read_in_session: vec![],
        permission_mode: PermissionMode::Yolo,
        task: Trusted::new_internal("test task".to_string()),
    };

    let decision = gate.evaluate(&ctx).await;
    assert!(
        matches!(decision, PermissionDecision::Allow { .. }),
        "Yolo mode should Allow Safe actions, got {:?}",
        decision
    );
}

// ---------------------------------------------------------------------------
// test_config_roundtrip
// ---------------------------------------------------------------------------

#[test]
fn test_config_roundtrip() {
    let tmp_dir = unique_temp_dir("forge-config-roundtrip");
    std::fs::create_dir_all(&tmp_dir).unwrap();
    let config_path = tmp_dir.join("config.json");

    let original = ForgeConfig {
        provider: "openrouter".to_string(),
        model: "anthropic/claude-3.5-sonnet".to_string(),
        api_key: "sk-or-v1-test-key".to_string(),
        base_url: "https://openrouter.ai/api/v1".to_string(),
        temperature: 0.3,
        max_tokens: Some(4096),
        max_steps: 100,
        cwd: PathBuf::from("/tmp/work"),
        eval_limit: Some(10),
        eval_benchmark: "spec-bench".to_string(),
        trace_dir: PathBuf::from("/tmp/traces"),
        audit_db: PathBuf::from("/tmp/audit.db"),
        config_file: None,
    };

    original.save(&config_path).unwrap();
    assert!(config_path.exists(), "Config file should exist after save");

    let loaded = ForgeConfig::load(Some(&config_path)).unwrap();

    assert_eq!(loaded.provider, original.provider);
    assert_eq!(loaded.model, original.model);
    assert_eq!(loaded.api_key, original.api_key);
    assert_eq!(loaded.base_url, original.base_url);
    assert!(
        (loaded.temperature - original.temperature).abs() < 1e-9,
        "temperature mismatch: got {}",
        loaded.temperature
    );
    assert_eq!(loaded.max_tokens, original.max_tokens);
    assert_eq!(loaded.max_steps, original.max_steps);
    assert_eq!(loaded.cwd, original.cwd);
    assert_eq!(loaded.eval_limit, original.eval_limit);
    assert_eq!(loaded.eval_benchmark, original.eval_benchmark);
    assert_eq!(loaded.trace_dir, original.trace_dir);
    assert_eq!(loaded.audit_db, original.audit_db);
    assert_eq!(
        loaded.config_file,
        Some(config_path.clone()),
        "config_file should be set to the path loaded from"
    );

    let _ = std::fs::remove_dir_all(tmp_dir);
}

fn unique_temp_dir(prefix: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    std::env::temp_dir().join(format!("{prefix}-{}-{nanos}", std::process::id()))
}

use std::collections::HashMap;

use async_trait::async_trait;
use forge_core::config::ForgeConfig;
use forge_core::port::{ModelError, ModelPort, ModelResponse, ToolCall, ToolSpec};

#[derive(Debug)]
pub struct DeepSeekProvider {
    client: reqwest::Client,
    api_key: String,
    model: String,
    base_url: String,
}

impl DeepSeekProvider {
    pub fn from_config(config: &ForgeConfig) -> Result<Self, ModelError> {
        match config.provider.as_str() {
            "deepseek" | "openrouter" => Ok(Self::new_with_key(
                config.api_key.clone(),
                config.model.clone(),
                default_base_url(&config.provider, &config.base_url),
            )),
            other => Err(ModelError::InvalidRequest(format!(
                "unsupported provider '{other}'; supported providers: deepseek, openrouter"
            ))),
        }
    }

    pub fn new(model: String) -> Self {
        Self::new_with_key(String::new(), model, String::new())
    }

    pub fn new_with_key(api_key: String, model: String, base_url: String) -> Self {
        let model = if model.is_empty() {
            "deepseek-chat".to_string()
        } else {
            model
        };
        let base_url = if base_url.is_empty() {
            "https://api.deepseek.com".to_string()
        } else {
            base_url.trim_end_matches('/').to_string()
        };
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");
        Self {
            client,
            api_key,
            model,
            base_url,
        }
    }
}

fn default_base_url(provider: &str, configured: &str) -> String {
    if !configured.is_empty() {
        return configured.to_string();
    }
    match provider {
        "openrouter" => "https://openrouter.ai/api/v1".to_string(),
        _ => "https://api.deepseek.com".to_string(),
    }
}

#[async_trait]
impl ModelPort for DeepSeekProvider {
    async fn generate(
        &self,
        system: &str,
        messages: &[HashMap<String, String>],
    ) -> Result<ModelResponse, ModelError> {
        self.generate_with_tools(system, messages, &[]).await
    }

    async fn generate_with_tools(
        &self,
        system: &str,
        messages: &[HashMap<String, String>],
        tools: &[ToolSpec],
    ) -> Result<ModelResponse, ModelError> {
        if self.api_key.is_empty() {
            return Err(ModelError::Authentication(
                "FORGE_API_KEY must be set for the configured provider".to_string(),
            ));
        }

        let url = format!("{}/chat/completions", self.base_url);
        let mut body = serde_json::json!({
            "model": self.model
        });
        let mut deepseek_messages = Vec::new();
        deepseek_messages.push(serde_json::json!({
            "role": "system",
            "content": system
        }));
        deepseek_messages.push(serde_json::json!({
            "role": "user",
            "content": messages.iter()
                .map(|m| m.get("content").cloned().unwrap_or_default())
                .collect::<Vec<_>>().join("\n")
        }));
        body["messages"] = serde_json::json!(deepseek_messages);
        if !tools.is_empty() {
            body["tools"] = serde_json::json!(tools
                .iter()
                .map(|t| {
                    serde_json::json!({
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters
                        }
                    })
                })
                .collect::<Vec<_>>());
        }

        let response = self
            .client
            .post(url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                if e.is_timeout() {
                    ModelError::Timeout(e.to_string())
                } else {
                    ModelError::Unknown(e.to_string())
                }
            })?;

        let status = response.status();
        if status.is_success() {
            let data: serde_json::Value = response
                .json()
                .await
                .map_err(|e| ModelError::Unknown(format!("Parse error: {}", e)))?;
            let choice = &data["choices"][0]["message"];
            let content = choice["content"].as_str().unwrap_or("").to_string();
            let input_tokens = data["usage"]["prompt_tokens"].as_u64().unwrap_or(0);
            let output_tokens = data["usage"]["completion_tokens"].as_u64().unwrap_or(0);
            let model = data["model"].as_str().unwrap_or(&self.model).to_string();
            let tool_calls = parse_tool_calls(choice)?;
            Ok(ModelResponse::new(
                content,
                tool_calls,
                input_tokens,
                output_tokens,
                model,
            ))
        } else {
            let err_text = response.text().await.unwrap_or_default();
            match status.as_u16() {
                401 => Err(ModelError::Authentication(err_text)),
                429 => Err(ModelError::RateLimit(err_text)),
                s if s >= 500 => Err(ModelError::Provider(err_text)),
                _ => Err(ModelError::Unknown(format!(
                    "HTTP {}: {}",
                    status, err_text
                ))),
            }
        }
    }

    async fn count_tokens(&self, text: &str) -> Result<u64, ModelError> {
        Ok((text.len() as u64).div_ceil(4))
    }
}

fn parse_tool_calls(message: &serde_json::Value) -> Result<Vec<ToolCall>, ModelError> {
    let Some(calls) = message.get("tool_calls").and_then(|v| v.as_array()) else {
        return Ok(vec![]);
    };

    calls
        .iter()
        .map(|call| {
            let function = call.get("function").ok_or_else(|| {
                ModelError::InvalidRequest("tool call missing function payload".to_string())
            })?;
            let name = function
                .get("name")
                .and_then(|v| v.as_str())
                .ok_or_else(|| {
                    ModelError::InvalidRequest("tool call missing function name".to_string())
                })?
                .to_string();
            let arguments = parse_arguments(function.get("arguments"))?;
            let id = call.get("id").and_then(|v| v.as_str()).map(str::to_string);
            Ok(ToolCall::new(name, arguments, id))
        })
        .collect()
}

fn parse_arguments(
    value: Option<&serde_json::Value>,
) -> Result<HashMap<String, serde_json::Value>, ModelError> {
    match value {
        None | Some(serde_json::Value::Null) => Ok(HashMap::new()),
        Some(serde_json::Value::Object(map)) => Ok(map.clone().into_iter().collect()),
        Some(serde_json::Value::String(raw)) if raw.trim().is_empty() => Ok(HashMap::new()),
        Some(serde_json::Value::String(raw)) => {
            let parsed: serde_json::Value = serde_json::from_str(raw).map_err(|e| {
                ModelError::InvalidRequest(format!("invalid tool arguments JSON: {e}"))
            })?;
            match parsed {
                serde_json::Value::Object(map) => Ok(map.into_iter().collect()),
                _ => Err(ModelError::InvalidRequest(
                    "tool arguments JSON must decode to an object".to_string(),
                )),
            }
        }
        Some(_) => Err(ModelError::InvalidRequest(
            "tool call arguments must be an object or JSON object string".to_string(),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_openai_compatible_tool_calls() {
        let message = serde_json::json!({
            "content": null,
            "tool_calls": [{
                "id": "call-1",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": "{\"path\":\"Cargo.toml\"}"
                }
            }]
        });

        let calls = parse_tool_calls(&message).unwrap();
        assert_eq!(calls.len(), 1);
        assert_eq!(calls[0].name, "read_file");
        assert_eq!(calls[0].id.as_deref(), Some("call-1"));
        assert_eq!(
            calls[0].arguments.get("path"),
            Some(&serde_json::Value::String("Cargo.toml".to_string()))
        );
    }

    #[test]
    fn invalid_tool_arguments_fail_closed() {
        let message = serde_json::json!({
            "tool_calls": [{
                "function": {
                    "name": "read_file",
                    "arguments": "[\"not\", \"an\", \"object\"]"
                }
            }]
        });

        let err = parse_tool_calls(&message).unwrap_err();
        assert!(matches!(err, ModelError::InvalidRequest(_)));
    }

    #[test]
    fn config_selects_only_supported_providers() {
        let mut config = ForgeConfig::defaults();
        config.provider = "openrouter".to_string();
        config.api_key = "test-key".to_string();
        config.base_url = "https://openrouter.ai/api/v1/".to_string();
        let provider = DeepSeekProvider::from_config(&config).unwrap();
        assert_eq!(provider.base_url, "https://openrouter.ai/api/v1");

        config.provider = "unknown".to_string();
        let err = DeepSeekProvider::from_config(&config).unwrap_err();
        assert!(matches!(err, ModelError::InvalidRequest(_)));
    }
}

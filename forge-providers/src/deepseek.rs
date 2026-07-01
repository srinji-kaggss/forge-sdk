use std::collections::HashMap;
use async_trait::async_trait;
use forge_core::port::{ModelError, ModelPort, ModelResponse, ToolSpec};

pub struct DeepSeekProvider {
    client: reqwest::Client,
    api_key: String,
    model: String,
}

impl DeepSeekProvider {
    pub fn new(model: String) -> Self {
        dotenvy::dotenv().ok();
        let api_key = std::env::var("DEEPSEEK_API_KEY")
            .expect("DEEPSEEK_API_KEY must be set in environment or .env file");
        let model = if model.is_empty() { "deepseek-chat".to_string() } else { model };
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");
        Self { client, api_key, model }
    }
}

#[async_trait]
impl ModelPort for DeepSeekProvider {
    async fn generate(&self, system: &str, messages: &[HashMap<String, String>]) -> Result<ModelResponse, ModelError> {
        self.generate_with_tools(system, messages, &[]).await
    }

    async fn generate_with_tools(&self, system: &str, messages: &[HashMap<String, String>], tools: &[ToolSpec]) -> Result<ModelResponse, ModelError> {
        let url = "https://api.deepseek.com/chat/completions";
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
            body["tools"] = serde_json::json!(tools.iter().map(|t| {
                serde_json::json!({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                })
            }).collect::<Vec<_>>());
        }

        let response = self.client.post(url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&body)
            .send()
            .await
            .map_err(|e| {
                if e.is_timeout() { ModelError::Timeout(e.to_string()) }
                else { ModelError::Unknown(e.to_string()) }
            })?;

        let status = response.status();
        if status.is_success() {
            let data: serde_json::Value = response.json().await
                .map_err(|e| ModelError::Unknown(format!("Parse error: {}", e)))?;
            let choice = &data["choices"][0]["message"];
            let content = choice["content"].as_str().unwrap_or("").to_string();
            let input_tokens = data["usage"]["prompt_tokens"].as_u64().unwrap_or(0);
            let output_tokens = data["usage"]["completion_tokens"].as_u64().unwrap_or(0);
            let model = data["model"].as_str().unwrap_or(&self.model).to_string();
            Ok(ModelResponse::new(content, vec![], input_tokens, output_tokens, model))
        } else {
            let err_text = response.text().await.unwrap_or_default();
            match status.as_u16() {
                401 => Err(ModelError::Authentication(err_text)),
                429 => Err(ModelError::RateLimit(err_text)),
                s if s >= 500 => Err(ModelError::Provider(err_text)),
                _ => Err(ModelError::Unknown(format!("HTTP {}: {}", status, err_text))),
            }
        }
    }

    async fn count_tokens(&self, text: &str) -> Result<u64, ModelError> {
        Ok((text.len() as u64 + 3) / 4)
    }
}

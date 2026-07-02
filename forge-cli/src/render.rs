use std::str::FromStr;

/// Supported output formats
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OutputFormat {
    Text,
    Json,
    StreamJson,
}

impl FromStr for OutputFormat {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "text" => Ok(OutputFormat::Text),
            "json" => Ok(OutputFormat::Json),
            "stream-json" => Ok(OutputFormat::StreamJson),
            other => Err(format!(
                "Unknown output format: '{other}'. Use: text, json, or stream-json"
            )),
        }
    }
}

impl OutputFormat {
    pub fn render(&self, value: &serde_json::Value) -> String {
        match self {
            OutputFormat::Json | OutputFormat::StreamJson => serde_json::to_string_pretty(value)
                .unwrap_or_else(|e| format!("Serialization error: {e}")),
            OutputFormat::Text => {
                format!("{value:}")
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_output_format_parse() {
        assert_eq!("text".parse::<OutputFormat>().unwrap(), OutputFormat::Text);
        assert_eq!("json".parse::<OutputFormat>().unwrap(), OutputFormat::Json);
        assert_eq!(
            "stream-json".parse::<OutputFormat>().unwrap(),
            OutputFormat::StreamJson
        );
        assert!("xml".parse::<OutputFormat>().is_err());
    }

    #[test]
    fn test_render_json() {
        let fmt = OutputFormat::Json;
        let out = fmt.render(&serde_json::json!("hello"));
        assert!(out.contains("hello"));
    }
}

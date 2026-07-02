use std::fmt;
use std::time::SystemTime;

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// EpisodeOutcome — 3-discriminator enum with self-describing Display
// ---------------------------------------------------------------------------

/// The outcome of a recorded episode.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum EpisodeOutcome {
    /// The episode completed successfully.
    Success,
    /// The episode failed.
    Failure,
    /// The episode completed partially (some goals met, some missed).
    Partial,
}

impl fmt::Display for EpisodeOutcome {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Success => write!(f, "success"),
            Self::Failure => write!(f, "failure"),
            Self::Partial => write!(f, "partial"),
        }
    }
}

// ---------------------------------------------------------------------------
// Episode — a recorded task execution with outcome
// ---------------------------------------------------------------------------

/// A recorded task execution with outcome — ported from Python
/// `forge_sdk.harness.learning.Episode`.
///
/// Episodes are the raw material for learning. Each one captures:
/// - What the agent was asked to do
/// - What it actually did (steps, tools used)
/// - Whether it succeeded and why
/// - What it should learn from this
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Episode {
    /// Unique identifier for this episode.
    pub id: String,
    /// The task description the agent was asked to perform.
    pub task: String,
    /// The outcome of the episode.
    pub outcome: EpisodeOutcome,
    /// Ordered list of steps the agent took during execution.
    pub steps: Vec<serde_json::Value>,
    /// Names of tools that were used during the episode.
    pub tools_used: Vec<String>,
    /// Number of tokens consumed during execution.
    pub tokens_used: u64,
    /// Wall-clock duration of execution in milliseconds.
    pub duration_ms: f64,
    /// Error message if the episode failed.
    pub error: Option<String>,
    /// What the agent should learn from this episode.
    pub lesson: Option<String>,
    /// Domain/topic this episode belongs to.
    pub domain: String,
    /// Unix timestamp (seconds since epoch) when the episode was recorded.
    pub timestamp: f64,
    /// Generation counter for the episode (used in evolutionary learning).
    pub generation: u32,
}

impl Episode {
    /// Create a new episode with default values.
    ///
    /// Defaults:
    /// - `outcome`: `EpisodeOutcome::Success`
    /// - `steps`: empty vec
    /// - `tools_used`: empty vec
    /// - `tokens_used`: `0`
    /// - `duration_ms`: `0.0`
    /// - `error`: `None`
    /// - `lesson`: `None`
    /// - `domain`: `"general"`
    /// - `timestamp`: current unix epoch time via `SystemTime::now()`
    /// - `generation`: `0`
    pub fn new(id: impl Into<String>, task: impl Into<String>) -> Self {
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        Self {
            id: id.into(),
            task: task.into(),
            outcome: EpisodeOutcome::Success,
            steps: Vec::new(),
            tools_used: Vec::new(),
            tokens_used: 0,
            duration_ms: 0.0,
            error: None,
            lesson: None,
            domain: "general".to_string(),
            timestamp: now,
            generation: 0,
        }
    }

    /// Returns `true` if the outcome is `EpisodeOutcome::Success`.
    pub fn success(&self) -> bool {
        self.outcome == EpisodeOutcome::Success
    }

    /// Serialize this episode into a JSON value.
    ///
    /// All fields are included verbatim via Serde serialization.
    pub fn to_json(&self) -> serde_json::Value {
        serde_json::to_value(self).unwrap_or(serde_json::Value::Null)
    }

    /// Deserialize an episode from a JSON value with lenient defaults.
    ///
    /// Missing fields are filled with the same defaults used in
    /// [`Episode::new`]. If the value is not an object, a default
    /// episode is returned.
    pub fn from_json(value: &serde_json::Value) -> Self {
        let obj = match value.as_object() {
            Some(o) => o,
            None => return Self::new("", ""),
        };

        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64();

        Self {
            id: obj
                .get("id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            task: obj
                .get("task")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            outcome: obj
                .get("outcome")
                .and_then(|v| serde_json::from_value::<EpisodeOutcome>(v.clone()).ok())
                .unwrap_or(EpisodeOutcome::Success),
            steps: obj
                .get("steps")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default(),
            tools_used: obj
                .get("tools_used")
                .and_then(|v| serde_json::from_value::<Vec<String>>(v.clone()).ok())
                .unwrap_or_default(),
            tokens_used: obj.get("tokens_used").and_then(|v| v.as_u64()).unwrap_or(0),
            duration_ms: obj
                .get("duration_ms")
                .and_then(|v| v.as_f64())
                .unwrap_or(0.0),
            error: obj.get("error").and_then(|v| v.as_str()).map(String::from),
            lesson: obj.get("lesson").and_then(|v| v.as_str()).map(String::from),
            domain: obj
                .get("domain")
                .and_then(|v| v.as_str())
                .unwrap_or("general")
                .to_string(),
            timestamp: obj.get("timestamp").and_then(|v| v.as_f64()).unwrap_or(now),
            generation: obj
                .get("generation")
                .and_then(|v| v.as_u64())
                .map(|v| v as u32)
                .unwrap_or(0),
        }
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_episode_new() {
        let ep = Episode::new("ep-1", "test task");

        assert_eq!(ep.id, "ep-1");
        assert_eq!(ep.task, "test task");
        assert_eq!(ep.outcome, EpisodeOutcome::Success);
        assert!(ep.steps.is_empty());
        assert!(ep.tools_used.is_empty());
        assert_eq!(ep.tokens_used, 0);
        assert_eq!(ep.duration_ms, 0.0);
        assert!(ep.error.is_none());
        assert!(ep.lesson.is_none());
        assert_eq!(ep.domain, "general");
        assert!(ep.timestamp > 0.0);
        assert_eq!(ep.generation, 0);
    }

    #[test]
    fn test_episode_success() {
        let success = Episode::new("s1", "do something");
        assert!(success.success());
        assert_eq!(success.outcome, EpisodeOutcome::Success);

        let mut failure = Episode::new("f1", "do something risky");
        failure.outcome = EpisodeOutcome::Failure;
        assert!(!failure.success());
        assert_eq!(failure.outcome, EpisodeOutcome::Failure);

        let mut partial = Episode::new("p1", "do something partially");
        partial.outcome = EpisodeOutcome::Partial;
        assert!(!partial.success());
        assert_eq!(partial.outcome, EpisodeOutcome::Partial);
    }

    #[test]
    fn test_episode_json_round_trip() {
        let mut ep = Episode::new("rt-1", "round trip test");
        ep.outcome = EpisodeOutcome::Partial;
        ep.tokens_used = 1500;
        ep.duration_ms = 3200.5;
        ep.tools_used = vec!["bash".into(), "read".into()];
        ep.steps = vec![serde_json::json!({"action": "read_file", "target": "src/main.rs"})];
        ep.error = Some("timeout after 30s".into());
        ep.lesson = Some("add retry logic".into());
        ep.domain = "development".into();
        ep.generation = 3;

        let json = ep.to_json();
        let restored = Episode::from_json(&json);

        assert_eq!(restored.id, ep.id);
        assert_eq!(restored.task, ep.task);
        assert_eq!(restored.outcome, ep.outcome);
        assert_eq!(restored.steps, ep.steps);
        assert_eq!(restored.tools_used, ep.tools_used);
        assert_eq!(restored.tokens_used, ep.tokens_used);
        assert!((restored.duration_ms - ep.duration_ms).abs() < f64::EPSILON);
        assert_eq!(restored.error, ep.error);
        assert_eq!(restored.lesson, ep.lesson);
        assert_eq!(restored.domain, ep.domain);
        assert!((restored.timestamp - ep.timestamp).abs() < f64::EPSILON);
        assert_eq!(restored.generation, ep.generation);
    }

    #[test]
    fn test_episode_json_round_trip_minimal() {
        let ep = Episode::new("min", "minimal");
        let json = ep.to_json();
        let restored = Episode::from_json(&json);

        assert_eq!(restored.id, "min");
        assert_eq!(restored.task, "minimal");
        assert_eq!(restored.outcome, EpisodeOutcome::Success);
        assert!(restored.steps.is_empty());
        assert_eq!(restored.domain, "general");
        assert_eq!(restored.generation, 0);
    }

    #[test]
    fn test_episode_from_json_lenient() {
        let json = serde_json::json!({
            "id": "lenient-1",
            "task": "lenient task"
        });
        let ep = Episode::from_json(&json);

        assert_eq!(ep.id, "lenient-1");
        assert_eq!(ep.task, "lenient task");
        assert_eq!(ep.outcome, EpisodeOutcome::Success);
        assert!(ep.steps.is_empty());
        assert!(ep.tools_used.is_empty());
        assert_eq!(ep.tokens_used, 0);
        assert_eq!(ep.duration_ms, 0.0);
        assert!(ep.error.is_none());
        assert!(ep.lesson.is_none());
        assert_eq!(ep.domain, "general");
        assert!(ep.timestamp > 0.0);
        assert_eq!(ep.generation, 0);
    }

    #[test]
    fn test_episode_from_json_non_object() {
        let ep = Episode::from_json(&serde_json::json!("not_an_object"));
        assert_eq!(ep.id, "");
        assert_eq!(ep.task, "");
    }

    #[test]
    fn test_episode_outcome_display() {
        assert_eq!(EpisodeOutcome::Success.to_string(), "success");
        assert_eq!(EpisodeOutcome::Failure.to_string(), "failure");
        assert_eq!(EpisodeOutcome::Partial.to_string(), "partial");
    }
}

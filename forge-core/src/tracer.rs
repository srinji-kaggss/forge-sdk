use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SpanKind { Llm, Tool, Agent, Internal }

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum SpanStatus { Ok, Error, Unset }

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpanEvent {
    pub name: String,
    pub timestamp_ms: i64,
    pub attributes: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub span_id: String,
    pub trace_id: String,
    pub parent_span_id: Option<String>,
    pub name: String,
    pub kind: SpanKind,
    pub start_time_ms: i64,
    pub end_time_ms: Option<i64>,
    pub attributes: HashMap<String, serde_json::Value>,
    pub events: Vec<SpanEvent>,
    pub status: SpanStatus,
}

impl Span {
    pub fn finish(&mut self, status: SpanStatus) {
        self.end_time_ms = Some(SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as i64);
        self.status = status;
    }

    pub fn add_event(&mut self, name: &str, attributes: HashMap<String, serde_json::Value>) {
        self.events.push(SpanEvent {
            name: name.to_string(),
            timestamp_ms: SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as i64,
            attributes,
        });
    }

    pub fn duration_ms(&self) -> Option<i64> {
        self.end_time_ms.map(|e| e - self.start_time_ms)
    }
}

pub struct Tracer {
    pub spans: Vec<Span>,
}

impl Tracer {
    pub fn new() -> Self { Self { spans: Vec::new() } }

    pub fn start_span(&mut self, name: &str, kind: SpanKind, trace_id: &str, parent_span_id: Option<String>) -> Span {
        let span = Span {
            span_id: Uuid::new_v4().to_string(),
            trace_id: trace_id.to_string(),
            parent_span_id,
            name: name.to_string(),
            kind,
            start_time_ms: SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis() as i64,
            end_time_ms: None,
            attributes: HashMap::new(),
            events: vec![],
            status: SpanStatus::Unset,
        };
        self.spans.push(span.clone());
        span
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_span_finish_sets_end_time() {
        let mut span = Span {
            span_id: "test".into(),
            trace_id: "trace".into(),
            parent_span_id: None,
            name: "test".into(),
            kind: SpanKind::Llm,
            start_time_ms: 0,
            end_time_ms: None,
            attributes: HashMap::new(),
            events: vec![],
            status: SpanStatus::Unset,
        };
        assert!(span.duration_ms().is_none());
        span.finish(SpanStatus::Ok);
        assert!(span.duration_ms().is_some());
        assert_eq!(span.status, SpanStatus::Ok);
    }

    #[test]
    fn test_span_add_event() {
        let mut span = Span {
            span_id: "test".into(),
            trace_id: "trace".into(),
            parent_span_id: None,
            name: "test".into(),
            kind: SpanKind::Agent,
            start_time_ms: 0,
            end_time_ms: None,
            attributes: HashMap::new(),
            events: vec![],
            status: SpanStatus::Unset,
        };
        span.add_event("test_event", HashMap::new());
        assert_eq!(span.events.len(), 1);
        assert_eq!(span.events[0].name, "test_event");
    }

    #[test]
    fn test_tracer_start_span() {
        let mut tracer = Tracer::new();
        let span = tracer.start_span("op", SpanKind::Tool, "trace-1", None);
        assert_eq!(span.name, "op");
        assert_eq!(span.kind, SpanKind::Tool);
        assert_eq!(tracer.spans.len(), 1);
    }

    #[test]
    fn test_span_kind_serde() {
        let kinds = vec![SpanKind::Llm, SpanKind::Tool, SpanKind::Agent, SpanKind::Internal];
        for k in kinds {
            let json = serde_json::to_string(&k).unwrap();
            let back: SpanKind = serde_json::from_str(&json).unwrap();
            assert_eq!(back, k);
        }
    }
}

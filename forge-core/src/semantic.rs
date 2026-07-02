use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// SemanticLabel — 8 interpretation-plane discriminators
// ---------------------------------------------------------------------------

/// The 8 semantic labels that classify what forge is doing in the
/// interpretation plane.
///
/// Every `MeaningFrame` carries exactly one label so that downstream
/// consumers (routing, audit, UI) can categorise intent without
/// string matching.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SemanticLabel {
    /// Generating new code from a specification or prompt.
    CodeSynthesis,
    /// Reading and understanding existing code.
    CodeUnderstanding,
    /// Analysing a bug, error, or crash.
    DebugAnalysis,
    /// Restructuring code without changing behaviour.
    Refactoring,
    /// High-level system or component architecture.
    ArchitectureDesign,
    /// Producing or updating documentation.
    Documentation,
    /// Generating unit / integration / property tests.
    TestGeneration,
    /// Analysing or updating dependencies.
    DependencyAnalysis,
}

// ---------------------------------------------------------------------------
// MeaningFrame
// ---------------------------------------------------------------------------

/// A frame that attaches semantic intent to a span of work.
///
/// `MeaningFrame` is the basic unit of forge's interpretation plane: it
/// pairs a `SemanticLabel` with a confidence score, a piece of evidence
/// that justifies the label, and an optional source-location span.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MeaningFrame {
    /// The semantic category.
    pub label: SemanticLabel,
    /// Confidence in [0.0, 1.0] that this label is correct.
    pub confidence: f32,
    /// Human-readable evidence string that justifies the label.
    pub evidence: String,
    /// Optional file path where the labelled work occurs.
    pub span_file: Option<String>,
    /// Optional (start_line, end_line) span within `span_file`.
    pub span_lines: Option<(u32, u32)>,
}

impl MeaningFrame {
    /// Create a new `MeaningFrame` with the given label, confidence, and
    /// evidence.  `span_file` and `span_lines` default to `None`.
    pub fn new(label: SemanticLabel, confidence: f32, evidence: String) -> Self {
        Self {
            label,
            confidence,
            evidence,
            span_file: None,
            span_lines: None,
        }
    }

    /// Returns `true` when `confidence >= threshold`.
    ///
    /// The default threshold used by forge's interpretation plane is `0.6`.
    pub fn confidence_threshold(&self, threshold: f32) -> bool {
        self.confidence >= threshold
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_semantic_label_8_variants() {
        // All 8 variants must exist and each must have a unique discriminant.
        let labels = [
            SemanticLabel::CodeSynthesis,
            SemanticLabel::CodeUnderstanding,
            SemanticLabel::DebugAnalysis,
            SemanticLabel::Refactoring,
            SemanticLabel::ArchitectureDesign,
            SemanticLabel::Documentation,
            SemanticLabel::TestGeneration,
            SemanticLabel::DependencyAnalysis,
        ];
        assert_eq!(labels.len(), 8);

        // Verify uniqueness by collecting discriminant values.
        let mut discriminants: Vec<isize> = labels.iter().map(|l| *l as isize).collect();
        discriminants.sort();
        discriminants.dedup();
        assert_eq!(discriminants.len(), 8, "each variant must have a unique discriminant");
    }

    #[test]
    fn test_meaning_frame_round_trip() {
        let original = MeaningFrame {
            label: SemanticLabel::Refactoring,
            confidence: 0.85,
            evidence: "Method exceeds cyclomatic complexity threshold.".into(),
            span_file: Some("src/parser.rs".into()),
            span_lines: Some((42, 89)),
        };

        let json = serde_json::to_string(&original).expect("serialize");
        let deserialized: MeaningFrame = serde_json::from_str(&json).expect("deserialize");

        assert_eq!(original, deserialized);
    }

    #[test]
    fn test_confidence_threshold() {
        let frame = MeaningFrame {
            label: SemanticLabel::CodeSynthesis,
            confidence: 0.6,
            evidence: "test".into(),
            span_file: None,
            span_lines: None,
        };
        // Exactly at threshold.
        assert!(frame.confidence_threshold(0.6));
        // Above threshold.
        assert!(frame.confidence_threshold(0.5));
        // Below threshold.
        assert!(!frame.confidence_threshold(0.61));
        // Zero threshold – everything passes.
        assert!(frame.confidence_threshold(0.0));
        // Very high threshold fails.
        assert!(!frame.confidence_threshold(1.0));
    }

    #[test]
    fn test_meaning_frame_new() {
        let frame = MeaningFrame::new(
            SemanticLabel::TestGeneration,
            0.73,
            "No tests exist for this module.".into(),
        );

        assert_eq!(frame.label, SemanticLabel::TestGeneration);
        assert!((frame.confidence - 0.73).abs() < f32::EPSILON);
        assert_eq!(frame.evidence, "No tests exist for this module.");
        // span_file and span_lines MUST default to None.
        assert!(frame.span_file.is_none());
        assert!(frame.span_lines.is_none());
    }
}

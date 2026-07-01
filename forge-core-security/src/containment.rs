use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Tainted / Trusted — compile-time taint tracking
// ---------------------------------------------------------------------------
//
// SPEC-SECURITY-003 §3.2. These newtypes prevent accidentally passing untrusted
// data (e.g., raw model output, user file content) into contexts that require
// validated input (e.g., prompt construction, command arguments).
//
// `Tainted<T>` has no public constructor except from raw I/O sources.
// `Trusted<T>` is the ONLY thing prompt-construction or command-construction
// should accept — the transformation Tainted → Trusted goes through `contain()`.

/// A value originating from an untrusted source (model output, user file, network).
///
/// No `From<T>` impl for arbitrary construction — only raw-I/O entry points
/// produce `Tainted` values. To use the inner value safely, call `contain()`
/// which returns a `ContainmentResult`. Only a `Trusted<T>` can be extracted
/// from a `ContainmentResult::Safe{...}` branch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tainted<T>(T);

impl<T> Tainted<T> {
    /// Wrap a value as tainted. **Only call from raw-I/O boundary points.**
    ///
    /// This is intentionally `pub(crate)` to enforce the constructor discipline:
    /// only I/O modules within forge-core-security can produce `Tainted` values;
    /// everything else receives them and must call `contain()`.
    pub(crate) fn new(value: T) -> Self {
        Self(value)
    }

    /// Run containment analysis on this tainted value.
    ///
    /// Returns `ContainmentResult::Safe` if the value passes all configured
    /// containment checks (e.g., no dangerous patterns, within risk threshold).
    /// Returns `ContainmentResult::Quarantined` if the value is rejected.
    ///
    /// This is the ONLY way to extract a `Trusted<T>` from a `Tainted<T>`.
    pub fn contain(self) -> ContainmentResult<T> {
        // Phase 0: basic pass-through with minimum risk score.
        // Phase 1+ will add pattern-based classification (shell metacharacters,
        // path traversals, prompt injection signatures).
        //
        // The risk_score here is a placeholder (0.0 = no detectable risk).
        // Real scoring will use regex patterns, entropy analysis, and LLM-as-judge.
        ContainmentResult::Safe {
            value: Trusted(self.0),
            category: Category::Unknown,
            risk_score: 0.0,
        }
    }
}

/// A value that has passed containment analysis and is trusted for consumption.
///
/// Prompt construction, command construction, and other sensitive consumers
/// MUST accept `Trusted<T>`, not raw `T`. The type system enforces that
/// untrusted data goes through `Tainted → contain() → Trusted` before use.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trusted<T>(T);

impl<T> Trusted<T> {
    /// Construct a Trusted value directly from a known-safe value.
    ///
    /// **Only use in tests or when the value is trusted by construction**
    /// (e.g., a hardcoded configuration string, a literal constant).
    /// The standard path is `Tainted → contain() → Trusted`.
    pub fn new_internal(value: T) -> Self {
        Self(value)
    }

    /// Borrow the trusted inner value.
    pub fn as_inner(&self) -> &T {
        &self.0
    }

    /// Consume and return the trusted inner value.
    pub fn into_inner(self) -> T {
        self.0
    }
}

// ---------------------------------------------------------------------------
// ContainmentResult — outcome of containment analysis
// ---------------------------------------------------------------------------

/// The outcome of running containment analysis on a `Tainted` value.
///
/// # Invariants
/// - `Quarantined` carries NO text from the original value — nothing to leak.
/// - `Safe` carries the `Trusted<T>` wrapper that prompt-construction enforces.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ContainmentResult<T> {
    /// Value passed containment checks and is now trusted.
    Safe {
        value: Trusted<T>,
        category: Category,
        risk_score: f32,
    },
    /// Value was rejected — quarantined, no inner value accessible.
    Quarantined {
        risk_score: f32,
    },
}

impl<T> ContainmentResult<T> {
    /// Returns the risk score (0.0–1.0), regardless of variant.
    pub fn risk_score(&self) -> f32 {
        match self {
            Self::Safe { risk_score, .. } | Self::Quarantined { risk_score } => *risk_score,
        }
    }

    /// Returns `true` if the value passed containment.
    pub fn is_safe(&self) -> bool {
        matches!(self, Self::Safe { .. })
    }

    /// Returns `true` if the value was quarantined.
    pub fn is_quarantined(&self) -> bool {
        matches!(self, Self::Quarantined { .. })
    }
}

// ---------------------------------------------------------------------------
// Category — containment classification
// ---------------------------------------------------------------------------

/// The classification of a contained value's risk category.
///
/// Closed enum — adding a new variant requires updating all match sites.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Category {
    /// No specific risk pattern detected.
    Unknown,
    /// Value contains timeout-related patterns.
    TimeoutHandling,
    /// Value contains permission-related patterns.
    PermissionErrors,
    /// Value contains shell metacharacters.
    ShellInjection,
    /// Value contains path traversal attempts ("../").
    PathTraversal,
    /// Value resembles a prompt injection.
    PromptInjection,
    /// Value contains code that would be executed.
    CodeExecution,
    /// Value from a network source.
    NetworkOrigin,
}


// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_taint_then_contain() {
        let tainted = Tainted::new("user input; rm -rf /".to_string());
        let result = tainted.contain();
        assert!(result.is_safe());
        assert!(result.risk_score() >= 0.0);
    }

    #[test]
    fn test_trusted_extraction() {
        let tainted = Tainted::new("safe_string".to_string());
        let result = tainted.contain();
        match result {
            ContainmentResult::Safe { value, .. } => {
                assert_eq!(value.into_inner(), "safe_string");
            }
            ContainmentResult::Quarantined { .. } => {
                panic!("Expected Safe but got Quarantined");
            }
        }
    }

    #[test]
    fn test_tainted_no_public_constructor() {
        let tainted = Tainted::new(42u64);
        assert_eq!(tainted.contain().is_safe(), true);
    }

    #[test]
    fn test_containment_result_quarantined_no_value() {
        let q: ContainmentResult<String> = ContainmentResult::Quarantined { risk_score: 0.95 };
        assert!(q.is_quarantined());
        assert_eq!(q.risk_score(), 0.95);
    }

    #[test]
    fn test_category_serialization() {
        let c = Category::ShellInjection;
        let json = serde_json::to_string(&c).unwrap();
        assert_eq!(json, "\"ShellInjection\"");
        let back: Category = serde_json::from_str(&json).unwrap();
        assert_eq!(back, Category::ShellInjection);
    }
}

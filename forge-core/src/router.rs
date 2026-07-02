use std::collections::HashSet;
use std::time::Duration;

use tokio::time::sleep;

use crate::port::{ModelResponse, ToolSpec};
use crate::result::FailureReason;

type ModelCaller =
    dyn Fn(&str, &[ToolSpec], &str) -> Result<ModelResponse, RouteFailure> + Send + Sync;

// ---------------------------------------------------------------------------
// RouteFailure — discriminators for the model-caller closure
// ---------------------------------------------------------------------------

/// Errors returned by the model-caller closure, distinguishing
/// rate-limit, not-found, and other model errors so that
/// `AutoRouter` can apply the correct backoff / dead-model logic.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RouteFailure {
    /// The provider returned a rate-limit error with a suggested
    /// retry-after duration in seconds.
    RateLimited { retry_after_seconds: u64 },
    /// The model was not found (e.g. 404). Models that return this
    /// are marked dead for the remainder of the session.
    NotFound,
    /// Any other model error that is not recoverable by retry.
    Other(String),
}

// ---------------------------------------------------------------------------
// AutoRouter
// ---------------------------------------------------------------------------

/// A model fallback router with rate-limit backoff and dead-model tracking.
///
/// `AutoRouter` holds an ordered list of model-id candidates and a
/// mutable set of models that have returned `NotFound` during this
/// session. The `dispatch` method tries each candidate in order,
/// applying rate-limit backoff (one retry per model) and skipping
/// dead models entirely.
pub struct AutoRouter {
    /// Ordered list of model IDs to try as fallbacks.
    candidates: Vec<String>,
    /// Models that returned `NotFound` — never retried this session.
    dead_this_session: HashSet<String>,
    /// Model-caller closure: `(prompt, tools, model_id) -> Result<ModelResponse, RouteFailure>`
    caller: Box<ModelCaller>,
}

impl AutoRouter {
    /// Create a new `AutoRouter` with the given candidate model IDs
    /// and a caller closure that performs the actual model invocation.
    pub fn new(candidates: Vec<String>, caller: Box<ModelCaller>) -> Self {
        Self {
            candidates,
            dead_this_session: HashSet::new(),
            caller,
        }
    }

    /// Try each candidate model in order:
    ///
    /// 1. **`RouteFailure::RateLimited`** — sleep `retry_after_seconds`,
    ///    then retry the same model **once**. If the retry also fails
    ///    (any route failure), fall through to the next candidate.
    ///
    /// 2. **`RouteFailure::NotFound`** — mark the model as dead for this
    ///    session and try the next candidate immediately (no retry).
    ///
    /// 3. **`RouteFailure::Other`** — fall through to the next candidate
    ///    immediately.
    ///
    /// On success returns `Ok((ModelResponse, model_used_string))` with the
    /// model that actually served the request.
    ///
    /// If all candidates are exhausted returns
    /// `Err(FailureReason::ModelError("all models exhausted"))`.
    pub async fn dispatch(
        &mut self,
        prompt: &str,
        tools: &[ToolSpec],
    ) -> Result<(ModelResponse, String), FailureReason> {
        for model in &self.candidates {
            // Skip models that have been marked dead this session.
            if self.dead_this_session.contains(model) {
                continue;
            }

            // -- first attempt -------------------------------------------------
            match (self.caller)(prompt, tools, model) {
                Ok(response) => return Ok((response, model.clone())),

                Err(RouteFailure::RateLimited {
                    retry_after_seconds,
                }) => {
                    // Sleep once, then retry the same model exactly once.
                    sleep(Duration::from_secs(retry_after_seconds)).await;
                    match (self.caller)(prompt, tools, model) {
                        Ok(response) => return Ok((response, model.clone())),
                        Err(_) => {
                            // Retry failed — fall through to next candidate.
                            continue;
                        }
                    }
                }

                Err(RouteFailure::NotFound) => {
                    // Mark dead, try next candidate immediately.
                    self.dead_this_session.insert(model.clone());
                    continue;
                }

                Err(RouteFailure::Other(_)) => {
                    // Non-recoverable. Fall through to next candidate.
                    continue;
                }
            }
        }

        Err(FailureReason::ModelError(
            "all models exhausted".to_string(),
        ))
    }

    // -- test helpers -------------------------------------------------------

    /// Return a reference to the dead-model set (for testing).
    #[doc(hidden)]
    pub fn dead_models(&self) -> &HashSet<String> {
        &self.dead_this_session
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -- helpers ------------------------------------------------------------

    fn make_response(model: &str) -> ModelResponse {
        ModelResponse {
            content: "ok".into(),
            tool_calls: vec![],
            input_tokens: 10,
            output_tokens: 5,
            model: model.into(),
        }
    }

    fn no_tools() -> Vec<ToolSpec> {
        vec![]
    }

    // -- test: NotFound advances to next candidate --------------------------

    #[tokio::test]
    async fn test_route_not_found() {
        let candidates = vec!["model-a".into(), "model-b".into()];
        let caller = Box::new(
            |_prompt: &str, _tools: &[ToolSpec], model: &str| match model {
                "model-a" => Err(RouteFailure::NotFound),
                "model-b" => Ok(make_response("model-b")),
                _ => panic!("unexpected model: {model}"),
            },
        );

        let mut router = AutoRouter::new(candidates, caller);
        let (resp, used) = router.dispatch("hello", &no_tools()).await.unwrap();

        assert_eq!(used, "model-b");
        assert_eq!(resp.content, "ok");
        // model-a should be marked dead
        assert!(router.dead_models().contains("model-a"));
        assert!(!router.dead_models().contains("model-b"));
    }

    // -- test: rate-limit, sleep, retry, succeed on retry -------------------

    #[tokio::test]
    async fn test_route_rate_limit_then_succeed() {
        use std::sync::atomic::{AtomicU8, Ordering};
        use std::sync::Arc;

        let call_count = Arc::new(AtomicU8::new(0));
        let count = Arc::clone(&call_count);

        let candidates = vec!["model-a".into()];
        let caller = Box::new(move |_prompt: &str, _tools: &[ToolSpec], model: &str| {
            let n = count.fetch_add(1, Ordering::SeqCst);
            match n {
                0 => Err(RouteFailure::RateLimited {
                    retry_after_seconds: 0,
                }),
                1 => Ok(make_response(model)),
                _ => panic!("unexpected call #{n}"),
            }
        });

        let mut router = AutoRouter::new(candidates, caller);
        let (resp, used) = router.dispatch("hello", &no_tools()).await.unwrap();

        assert_eq!(used, "model-a");
        assert_eq!(resp.content, "ok");
        assert_eq!(call_count.load(Ordering::SeqCst), 2);
    }

    // -- test: all candidates exhausted -------------------------------------

    #[tokio::test]
    async fn test_route_all_exhausted() {
        let candidates = vec!["model-a".into(), "model-b".into()];
        let caller = Box::new(
            |_prompt: &str, _tools: &[ToolSpec], model: &str| match model {
                "model-a" => Err(RouteFailure::Other("bad request".into())),
                "model-b" => Err(RouteFailure::Other("server error".into())),
                _ => panic!("unexpected model: {model}"),
            },
        );

        let mut router = AutoRouter::new(candidates, caller);
        let err = router.dispatch("hello", &no_tools()).await.unwrap_err();

        assert_eq!(
            err,
            FailureReason::ModelError("all models exhausted".into())
        );
    }

    // -- test: model name surfaced in Ok tuple ------------------------------

    #[tokio::test]
    async fn test_route_model_name_surfaced() {
        let candidates = vec!["claude-sonnet-4".into()];
        let caller =
            Box::new(|_prompt: &str, _tools: &[ToolSpec], model: &str| Ok(make_response(model)));

        let mut router = AutoRouter::new(candidates, caller);
        let (resp, used) = router.dispatch("hello", &no_tools()).await.unwrap();

        assert_eq!(used, "claude-sonnet-4");
        assert_eq!(resp.model, "claude-sonnet-4");
    }

    // -- test: NotFound models are never retried ----------------------------

    #[tokio::test]
    async fn test_dead_this_session() {
        use std::sync::atomic::{AtomicU8, Ordering};
        use std::sync::Arc;

        let call_count = Arc::new(AtomicU8::new(0));
        let count = Arc::clone(&call_count);

        // model-a fails with NotFound on first call.
        // model-b succeeds.
        let candidates = vec!["model-a".into(), "model-b".into()];
        let caller = Box::new(move |_prompt: &str, _tools: &[ToolSpec], model: &str| {
            count.fetch_add(1, Ordering::SeqCst);
            match model {
                "model-a" => Err(RouteFailure::NotFound),
                "model-b" => Ok(make_response("model-b")),
                _ => panic!("unexpected model: {model}"),
            }
        });

        let mut router = AutoRouter::new(candidates, caller);

        // First dispatch — model-a fails NotFound, model-b succeeds.
        let (_resp, used) = router.dispatch("hello", &no_tools()).await.unwrap();
        assert_eq!(used, "model-b");
        assert_eq!(call_count.load(Ordering::SeqCst), 2); // a then b

        // Second dispatch — model-a is dead, should go straight to model-b.
        // With dead tracking, model-b is the only model called (+1).
        let (_resp, used2) = router.dispatch("hello again", &no_tools()).await.unwrap();
        assert_eq!(used2, "model-b");
        // Call count should be 3 (a, b from first; then just b from second)
        assert_eq!(call_count.load(Ordering::SeqCst), 3);
    }
}

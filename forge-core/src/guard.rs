use crate::context::AgentContext;
use crate::result::FailureReason;

#[derive(Debug, Clone)]
pub struct LoopGuard {
    max_steps: u32,
    max_tokens: u64,
    max_cost: f64,
    convergence_threshold: u32,
    step_count: u32,
    total_tokens: u64,
    total_cost: f64,
    convergence_nudges: u32,
}

impl LoopGuard {
    pub fn new(ctx: &AgentContext) -> Self {
        Self {
            max_steps: ctx.max_steps,
            max_tokens: ctx.max_tokens,
            max_cost: ctx.max_cost,
            convergence_threshold: 3,
            step_count: ctx.step_count,
            total_tokens: 0,
            total_cost: 0.0,
            convergence_nudges: 0,
        }
    }

    pub fn check(&mut self, step_tokens: u64, step_cost: f64) -> Result<(), FailureReason> {
        self.step_count += 1;
        self.total_tokens += step_tokens;
        self.total_cost += step_cost;
        if self.step_count > self.max_steps {
            return Err(FailureReason::MaxStepsReached);
        }
        if self.max_tokens > 0 && self.total_tokens > self.max_tokens {
            return Err(FailureReason::UsageLimitExceeded);
        }
        if self.max_cost > 0.0 && self.total_cost > self.max_cost {
            return Err(FailureReason::UsageLimitExceeded);
        }
        Ok(())
    }

    pub fn nudge(&mut self) -> Result<(), FailureReason> {
        self.convergence_nudges += 1;
        if self.convergence_nudges > self.convergence_threshold {
            return Err(FailureReason::ConvergenceFailure {
                nudges: self.convergence_nudges,
                detail: format!(
                    "Model not converging after {} nudges",
                    self.convergence_nudges
                ),
            });
        }
        Ok(())
    }

    pub fn step_count(&self) -> u32 {
        self.step_count
    }
    pub fn total_tokens(&self) -> u64 {
        self.total_tokens
    }
    pub fn total_cost(&self) -> f64 {
        self.total_cost
    }
    pub fn convergence_nudges(&self) -> u32 {
        self.convergence_nudges
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn make_ctx(max_steps: u32, max_tokens: u64, max_cost: f64) -> AgentContext {
        AgentContext::new(
            "test",
            "/tmp",
            max_steps,
            max_tokens,
            max_cost,
            "trace-1",
            "run-1",
            Some("session-1".into()),
            "model-1",
            "provider-1",
            HashMap::new(),
            vec![],
            0,
        )
    }

    #[test]
    fn test_loop_guard_steps() {
        let ctx = make_ctx(3, 0, 0.0);
        let mut guard = LoopGuard::new(&ctx);
        assert_eq!(guard.step_count(), 0);
        assert!(guard.check(0, 0.0).is_ok());
        assert!(guard.check(0, 0.0).is_ok());
        assert!(guard.check(0, 0.0).is_ok());
        assert_eq!(guard.check(0, 0.0), Err(FailureReason::MaxStepsReached));
    }

    #[test]
    fn test_loop_guard_token_limit() {
        let ctx = make_ctx(100, 50, 0.0);
        let mut guard = LoopGuard::new(&ctx);
        assert!(guard.check(30, 0.0).is_ok());
        assert!(guard.check(20, 0.0).is_ok());
        assert_eq!(guard.check(10, 0.0), Err(FailureReason::UsageLimitExceeded));
    }

    #[test]
    fn test_loop_guard_cost_limit() {
        let ctx = make_ctx(100, 0, 1.0);
        let mut guard = LoopGuard::new(&ctx);
        assert!(guard.check(0, 0.6).is_ok());
        assert!(guard.check(0, 0.4).is_ok());
        assert_eq!(guard.check(0, 0.1), Err(FailureReason::UsageLimitExceeded));
    }

    #[test]
    fn test_convergence_nudge() {
        let ctx = make_ctx(100, 0, 0.0);
        let mut guard = LoopGuard::new(&ctx);
        assert!(guard.nudge().is_ok());
        assert!(guard.nudge().is_ok());
        assert!(guard.nudge().is_ok());
        assert_eq!(guard.convergence_nudges(), 3);
        match guard.nudge() {
            Err(FailureReason::ConvergenceFailure { nudges, .. }) => assert_eq!(nudges, 4),
            _ => panic!("expected ConvergenceFailure"),
        }
    }
}

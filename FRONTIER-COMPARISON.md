# Frontier AI Agent Frameworks — Comparison Against forge-sdk

**Date:** 2026-06-30 | **Scope:** 6 frontier frameworks vs forge-sdk architecture

---

## 1. Framework Summary Table

| Pattern | forge-sdk | LangGraph | Claude Agent SDK | OpenAI Agents SDK | CrewAI | AutoGen | Pydantic AI |
|---|---|---|---|---|---|---|---|
| **Architecture** | ReAct loop (for-loop) | StateGraph (Pregel runtime) | query() async generator | Responses API + tool loop | Crew/Process (sequential/hierarchical) | ConversableAgent + GroupChat | pydantic-graph FSM |
| **State Management** | In-memory AgentContext + messages list | TypedDict + reducers + checkpointing | JSONL session files on disk | Conversations API (hosted) | In-memory task outputs | Conversation history as state | RunContext + message history |
| **Tool Definition** | ToolSpec dataclass + registry | @tool decorator or ToolNode | Built-in 20+ tools + custom | Function tools (JSON schema) | @tool decorator | Function registration | @agent.tool decorator + Pydantic models |
| **Error Recovery** | LoopGuard (hash-based repeat detection) | Conditional edges + retry policies | Hook system (PreToolUse/PostToolUse) | Automatic retries + guardrails | Retry delegator + error handling | Conversation-based retry | ModelRetry + validation error feedback |
| **Human-in-the-Loop** | None | Interrupt/resume + breakpoint nodes | Permission modes (ask/bypass/dontAsk) | Handoff objects | HumanInputAgent | UserProxyAgent | Deferred tools + approval |
| **Streaming** | complete_stream() returns list[ModelChunk] | Token/state/node-level streaming | Async generator (every intermediate msg) | Native streaming | Limited | Limited (v0.4 improving) | run_stream() + run_stream_events() |
| **Verification** | Verifier pipeline (syntactic/AST/entity/semantic) | Custom node-based checks | Hooks + evaluation | Guardrails framework | Task output validation | Conversation-based validation | Pydantic output validation + retries |
| **Type Safety** | dataclasses (untyped schema dicts) | TypedDict state schema | TypeScript + Python typed | Pydantic models | Pydantic models | Generic messages | Full generic types Agent[Deps, Output] |
| **Context Management** | Unbounded message list (MEDIUM-004 documented) | State reducers (append-only lists) | Session compaction + subagent isolation | Thread auto-truncation | Task output chaining | Conversation window management | Message history with compaction |
| **Multi-Agent** | Single agent | Graph-based subgraphs | Subagents via Agent tool | Agents-as-tools / parallel | Crew hierarchical/sequential | GroupChat with speaker selection | Multi-agent via graph composition |
| **Persistence** | SQLite audit log (hash-chain) | Checkpoint DB (SQLite/Postgres) | JSONL on disk | Hosted (API-managed) | In-memory (enterprise: persistent) | In-memory | In-memory + durable execution (Temporal) |
| **Observability** | Tracer → JSONL spans | LangSmith integration | OpenTelemetry traces | Built-in tracing | Tracing + monitoring | OpenTelemetry | Pydantic Logfire |

---

## 2. Key Patterns forge-sdk Is Missing

### 2.1 Durable State Persistence (Checkpoints)

**What others do:** LangGraph checkpoints state at every node execution. If the server restarts mid-workflow, it picks up exactly where it left off. Pydantic AI integrates with Temporal for durable execution.

**What forge-sdk does:** AgentContext is an in-memory dataclass. Crash = total state loss. The `messages` list grows unbounded (MEDIUM-004).

**Gap severity:** HIGH — production agents running multi-hour tasks lose everything on crash.

**LangGraph pattern:**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=memory)

# State persists across restarts
config = {"configurable": {"thread_id": "agent-run-42"}}
result = graph.invoke({"messages": [user_msg]}, config)
```

**Pydantic AI pattern:**
```python
from pydantic_ai import Agent
from pydantic_ai.durable_exec import temporal

# Agent state survives process crashes
agent = Agent('openai:gpt-5.2')
async with temporal.run(agent, task_id="my-task") as run:
    result = await run.next("Do something complex")
    # If process crashes, resume with:
    # await temporal.resume("my-task")
```

### 2.2 Structured Output with Automatic Retry

**What others do:** Pydantic AI validates LLM output against a Pydantic model. If validation fails, it feeds the error back to the model and retries automatically — with configurable retry limits.

**What forge-sdk does:** `_parse_response()` does raw JSON parsing with no schema validation. If the model returns garbage, it falls back to treating the entire response as a finish action.

**Gap severity:** HIGH — no guarantee the model's output matches expected schema.

**Pydantic AI pattern:**
```python
from pydantic import BaseModel
from pydantic_ai import Agent

class CodeOutput(BaseModel):
    file_path: str
    code: str
    explanation: str

agent = Agent('openai:gpt-5.2', output_type=CodeOutput)
result = agent.run_sync("Fix the auth bug")
# result.output is a validated CodeOutput instance
# If the LLM returns invalid JSON, Pydantic AI retries with the error
```

### 2.3 Dependency Injection for Tools

**What others do:** Pydantic AI passes typed dependencies through `RunContext` — tools, system prompts, and validators all receive the same DI container. This makes testing trivial (swap mock deps) and keeps tools decoupled from global state.

**What forge-sdk does:** Tools receive raw `dict` kwargs. No typed context injection. The `ToolSpec.handler` is `Callable[..., Awaitable[ToolResult]]` — no dependency channel.

**Gap severity:** MEDIUM — makes testing harder, couples tools to module-level imports.

**Pydantic AI pattern:**
```python
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext

@dataclass
class MyDeps:
    db: DatabaseConn
    api_key: str

agent = Agent('openai:gpt-5.2', deps_type=MyDeps)

@agent.tool
async def get_customer(ctx: RunContext[MyDeps], customer_id: int) -> str:
    # ctx.deps is typed MyDeps — IDE autocomplete works
    customer = await ctx.deps.db.get_customer(customer_id)
    return f"Customer: {customer.name}"
```

### 2.4 Human-in-the-Loop Patterns

**What others do:**
- LangGraph: `interrupt()` node that pauses execution, persists state, and resumes when human approves
- Claude Agent SDK: Permission modes (`ask`, `bypassPermissions`, `dontAsk`) + `canUseTool` callback
- Pydantic AI: Deferred tools that require explicit approval before execution
- AutoGen: `UserProxyAgent` with `human_input_mode` (NEVER/ALWAYS/TERMINATE)

**What forge-sdk does:** No HITL support. Agent runs autonomously until max_steps.

**Gap severity:** MEDIUM — acceptable for coding agents, but limits production use cases.

**LangGraph pattern:**
```python
def human_review(state):
    result = interrupt("Please review and approve this plan")
    return {"approved": result["approved"]}

graph.add_node("review", human_review)
graph.add_edge("plan", "review")
```

### 2.5 Parallel Tool Calls

**What others do:** OpenAI and Anthropic both support returning multiple tool calls in a single response. The runtime executes them concurrently and returns all results at once.

**What forge-sdk does:** Single tool call per step. Sequential only.

**Gap severity:** MEDIUM — 3x latency penalty when reading multiple independent files.

**OpenAI pattern:**
```python
# Model returns multiple tool_calls in one response
response = client.chat.completions.create(
    model="gpt-4o",
    tools=[...],
    messages=[...],
)
# response.choices[0].message.tool_calls may contain 3+ calls
# Execute all in parallel with asyncio.gather
results = await asyncio.gather(*[execute(tc) for tc in tool_calls])
```

### 2.6 Graph-Based Workflow Composition

**What others do:** LangGraph models workflows as directed graphs. Nodes are computation steps, edges define control flow. Supports conditional branching, cycles, parallel execution, and subgraphs.

**What forge-sdk does:** Linear for-loop. No branching, no conditional routing, no subgraph composition.

**Gap severity:** LOW for single-agent coding, HIGH for complex workflows.

**LangGraph pattern:**
```python
from langgraph.graph import StateGraph

graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("write", write_node)
graph.add_node("review", review_node)

# Conditional routing
graph.add_conditional_edges(
    "review",
    lambda state: "publish" if state["approved"] else "revise",
    {"publish": "publish_node", "revise": "write"}
)
```

### 2.7 Subagent Isolation and Delegation

**What others do:** Claude Agent SDK spawns subagents with isolated context windows, separate system prompts, restricted tool sets, and independent model choices. The parent only sees the final result.

**What forge-sdk does:** Single agent. No subagent spawning. No context isolation.

**Gap severity:** LOW for simple tasks, HIGH when tasks require parallel investigation.

**Claude Agent SDK pattern:**
```python
agents={
    "code-reviewer": AgentDefinition(
        description="Expert code review specialist.",
        prompt="You are a code review specialist.",
        tools=["Read", "Grep", "Glob"],  # read-only!
        model="sonnet",
    ),
}
```

### 2.8 Hook System for Lifecycle Control

**What others do:** Claude Agent SDK provides hooks at `PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd` — each can deny, modify, or log. Pydantic AI has a similar hooks system.

**What forge-sdk does:** No lifecycle hooks. Tool execution is fire-and-forget.

**Gap severity:** MEDIUM — makes auditing and guardrails harder to implement.

### 2.9 Session Management and Forking

**What others do:** Claude Agent SDK supports continue/resume/fork of sessions. Pydantic AI supports conversation history passing across runs.

**What forge-sdk does:** Each `arun()` starts fresh. No session persistence, no resume, no fork.

**Gap severity:** LOW for single-shot tasks, MEDIUM for interactive workflows.

### 2.10 Usage Limits and Cost Guardrails

**What others do:** Pydantic AI has `UsageLimits(request_limit=N, output_tokens_limit=N, tool_calls_limit=N)`. LangSmith tracks costs per run.

**What forge-sdk does:** `LoopGuard` prevents repeated calls but doesn't limit total tokens, requests, or cost. The `total_cost_usd` is tracked but not enforced.

**Gap severity:** MEDIUM — runaway agent loops can burn significant tokens.

**Pydantic AI pattern:**
```python
from pydantic_ai import UsageLimits

result = agent.run_sync(
    "Complex task",
    usage_limits=UsageLimits(
        request_limit=10,
        output_tokens_limit=50000,
        tool_calls_limit=20,
    ),
)
```

---

## 3. Patterns forge-sdk Does Better

### 3.1 Verification Pipeline (INV-201/202/203)

**forge-sdk advantage:** forge-sdk has a formal verification pipeline with multiple gates (syntactic, AST parse, entity validation, shell dry-run, semantic check). The `Verifier` class runs deterministic checks. `INV-203` ensures the model that writes code does NOT grade it (separate verifier). `INV-207` uses an LLM for semantic alignment checking.

**What others lack:** Most frameworks trust the model's self-assessment or provide ad-hoc validation. LangGraph has no built-in verification pipeline. Claude Agent SDK relies on hooks. Pydantic AI validates output schema but not semantic correctness.

### 3.2 Audit Trail with Hash-Chain Integrity

**forge-sdk advantage:** The `AuditLog` (SQLite) provides append-only, hash-chained audit records. The `DaemonEventSink` bridges to the lgwks daemon with crash-safe WAL. Every tool call and LLM call is traced with typed spans.

**What others lack:** LangGraph uses LangSmith (external SaaS). Claude Agent SDK uses OpenTelemetry (exported elsewhere). Most frameworks don't have built-in tamper-evident audit logs.

### 3.3 LoopGuard with Semantic Analysis

**forge-sdk advantage:** `LoopGuard` detects repeated identical tool calls (hash-based). Beyond that, `SemanticCheck` (INV-207) catches "shallow edits" — syntactically valid but semantically wrong changes. The false-green detection (`_task_implies_edits`) catches cases where the agent completes without making expected changes.

**What others lack:** Most frameworks have simple max-iteration limits. None have semantic alignment checking of the output against the task intent.

### 3.4 AI-Native Error Messages

**forge-sdk advantage:** `ToolResult.as_message` formats errors for AI consumption — includes candidates, suggestions, and recovery guidance. The `_execute_tool` method returns structured error messages with available tool lists.

**What others lack:** Most frameworks return raw exception strings to the model. Claude Agent SDK and LangGraph don't specifically optimize error messages for model consumption.

### 3.5 Model-Agnostic Protocol Design

**forge-sdk advantage:** `ModelPort` is a Python Protocol (structural subtyping). Any class with `complete()` and `complete_stream()` methods works. The `ProviderRegistry` allows runtime model swapping. Edge-portable (JSON-serializable, subprocess-isolated).

**What others do:** LangGraph and Pydantic AI also support multiple providers, but through provider-specific adapters rather than a single protocol. Claude Agent SDK is locked to Anthropic.

### 3.6 Trace-First Observability

**forge-sdk advantage:** Every LLM call and tool call produces a typed `Span` with structured attributes (gen_ai.system, gen_ai.request.model, tool.name, etc.). Spans export to JSONL. The `Tracer` class manages span lifecycle with parent-child relationships.

**What others do:** LangGraph integrates with LangSmith (SaaS). Claude Agent SDK uses OpenTelemetry. CrewAI has basic tracing. forge-sdk's tracer is self-contained and edge-portable.

---

## 4. Specific Gaps with Code Examples

### 4.1 Gap: No Checkpoint/Persistence Layer

**forge-sdk (current):**
```python
# State is lost on crash
context = AgentContext(task="Fix auth.py", cwd="/repo")
result = agent.run(context)  # If process dies here, everything is lost
```

**LangGraph (target pattern):**
```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string("checkpoints.db")
graph = builder.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "run-42"}}
# State survives restarts
for event in graph.stream({"messages": [msg]}, config):
    print(event)
# After crash, resume with same thread_id
```

### 4.2 Gap: No Structured Output Validation

**forge-sdk (current):**
```python
def _parse_response(self, content: str) -> dict[str, Any]:
    # Raw JSON parsing, no schema validation
    try:
        return json.loads(content[start:end])
    except (json.JSONDecodeError, ValueError):
        # Falls back to treating entire response as finish
        return {"thought": content, "action": "finish", ...}
```

**Pydantic AI (target pattern):**
```python
from pydantic import BaseModel
from pydantic_ai import Agent

class AgentAction(BaseModel):
    thought: str
    action: str
    action_input: dict

agent = Agent('openai:gpt-5.2', output_type=AgentAction)
# Validation happens automatically
# Invalid output → retry with error feedback
```

### 4.3 Gap: No Human-in-the-Loop

**forge-sdk (current):**
```python
# Agent runs autonomously until max_steps
# No way to pause, approve, or intervene
for step_num in range(1, context.max_steps + 1):
    response = self._model.complete(messages, temperature=0.0)
    # ... execute tool without any approval gate
```

**Claude Agent SDK (target pattern):**
```python
async for message in query(
    prompt="Fix the auth bug",
    options=ClaudeAgentOptions(
        permission_mode="ask",  # Pause for approval on writes
        allowed_tools=["Read", "Edit", "Bash"],
    ),
):
    if hasattr(message, "result"):
        print(message.result)
```

### 4.4 Gap: Unbounded Context Growth

**forge-sdk (current):**
```python
# MEDIUM-004: Messages list grows forever
messages.append({"role": "assistant", "content": response.content})
messages.append({"role": "user", "content": f"Tool output:\n{observation}"})
# After 50 steps with large tool outputs, this exceeds context window
```

**Claude Agent SDK (target pattern):**
```python
# Session compaction happens automatically
# Subagent isolation prevents context bloating
# Max turns configurable per subagent
AgentDefinition(
    maxTurns=10,  # Hard cap on turns
    tools=["Read"],  # Restricted tool set
)
```

### 4.5 Gap: No Parallel Tool Execution

**forge-sdk (current):**
```python
# Sequential: one tool per step
for step_num in range(1, context.max_steps + 1):
    response = self._model.complete(messages)
    parsed = self._parse_response(response.content)
    observation = await self._execute_tool(parsed["action"], parsed["action_input"])
    # Must wait for each tool before next step
```

**OpenAI Agents SDK (target pattern):**
```python
# Model can request multiple tools in one response
# Runtime executes them concurrently
async def run_agent():
    result = await Runner.run(
        agent,
        messages,
        max_turns=10,
    )
    # Multiple tool calls executed in parallel internally
```

### 4.6 Gap: No Dependency Injection

**forge-sdk (current):**
```python
def my_tool(args: dict) -> ToolResult:
    # Must import dependencies at module level
    # No way to inject mocks for testing
    db = get_database()  # Global import
    return ToolResult(success=True, output="...")
```

**Pydantic AI (target pattern):**
```python
@agent.tool
async def my_tool(ctx: RunContext[MyDeps], query: str) -> str:
    # ctx.deps is typed, injectable, testable
    return await ctx.deps.db.query(query)

# Testing: inject mock deps
result = agent.run_sync("test", deps=MockDeps())
```

---

## 5. Recommended Priority for forge-sdk

| Priority | Gap | Effort | Impact |
|---|---|---|---|
| P0 | Structured output with retry | Low | High — prevents malformed actions |
| P0 | Usage limits (request/token/cost caps) | Low | High — prevents runaway loops |
| P1 | Checkpoint/persistence | Medium | High — crash recovery |
| P1 | Human-in-the-loop gates | Medium | High — production safety |
| P2 | Parallel tool calls | Medium | Medium — latency improvement |
| P2 | Dependency injection | Low | Medium — testability |
| P2 | Context window management | Medium | Medium — long-running tasks |
| P3 | Hook system | Medium | Low — can be added incrementally |
| P3 | Session resume/fork | Medium | Low — nice-to-have |
| P3 | Graph-based workflows | High | Low — single-agent focus doesn't need it |

---

## 6. References

- LangGraph docs: https://docs.langchain.com/oss/python/langgraph
- Claude Agent SDK: https://docs.anthropic.com/en/docs/claude-code/sdk
- OpenAI Agents SDK: https://developers.openai.com/docs/guides/agents-sdk
- CrewAI: https://crewai.com
- AutoGen: https://microsoft.github.io/autogen/stable/
- Pydantic AI: https://pydantic.dev/docs/ai/overview/
- forge-sdk source: `/Users/srinji/forge/src/forge_sdk/`

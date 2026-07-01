"""Regression test for a live-reproduced bug: Gemini/Vertex responses with a
literal (unescaped) newline inside a JSON string value fail strict
json.loads(), so every parse strategy returns None and the response is
marked __parse_failed__ even though the JSON is a single well-formed object.

Found while dogfooding a real forge run (gemini-2.5-flash via Vertex,
reviewing semantic-memory-brain): the model's `"thought"` field contained a
literal "\\n\\n" character instead of an escaped "\\n" sequence. forge told it
"Your last response could not be parsed", and the model — whose JSON was
structurally fine from its own perspective — just re-emitted the identical
response, burning a step for zero new progress (traced at
.forge/traces/071410beadf343149c0dc711e8f40b70.jsonl, steps 3-4).

Fix: json.loads(..., strict=False) in every parse-strategy call site. This
only relaxes control-character handling inside string literals; it does not
change what counts as valid JSON structure.

Run with: pytest tests/test_parse_control_chars.py -v
"""

from __future__ import annotations

from forge_sdk.agents.react import FirstValidJsonStrategy, FullJsonStrategy, _unwrap_nested_finish

# Exact shape captured from the live trace: a literal newline (not "\\n")
# inside the "thought" string value.
_RAW_WITH_LITERAL_NEWLINE = (
    '{"thought": "I\'ve read `AGENTS.md`.\n\nNext, I will read `README.md`.", '
    '"action": "read_file", "action_input": {"path": "README.md"}}'
)


def test_full_json_strategy_tolerates_literal_newline_in_string():
    strategy = FullJsonStrategy()
    assert strategy.applies(_RAW_WITH_LITERAL_NEWLINE)

    result = strategy.execute(_RAW_WITH_LITERAL_NEWLINE)

    assert result is not None
    assert result["action"] == "read_file"
    assert result["action_input"] == {"path": "README.md"}


def test_first_valid_json_strategy_tolerates_literal_newline_in_string():
    strategy = FirstValidJsonStrategy()

    result = strategy.execute(_RAW_WITH_LITERAL_NEWLINE)

    assert result is not None
    assert result["action"] == "read_file"


def test_unwrap_nested_finish_tolerates_literal_newline_in_string():
    wrapped = {
        "action": "finish",
        "action_input": {"output": f"Done. {_RAW_WITH_LITERAL_NEWLINE}"},
    }

    result = _unwrap_nested_finish(wrapped)

    assert result is not None
    assert result["action"] == "read_file"


def test_full_json_strategy_still_rejects_genuinely_broken_json():
    """The relaxed strict=False must not turn actual structural breakage into
    a false pass — a truncated/unbalanced object should still fail."""
    strategy = FullJsonStrategy()

    result = strategy.execute('{"thought": "no closing quote, "action": "finish"}')

    assert result is None

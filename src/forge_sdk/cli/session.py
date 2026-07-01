"""L5b Session Recovery — checkpoint save/restore for agent runs.

H3: Every user-affecting surface has a file-backed recovery path.
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_CHECKPOINT_DIR = Path.home() / ".forge" / "checkpoints"


@dataclass
class SessionState:
    session_id: str = ""
    task: str = ""
    model: str = ""
    step_count: int = 0
    tool_calls_made: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    checkpoint_step: int = 0
    timestamp: float = 0.0
    extra: dict = field(default_factory=dict)


def checkpoint_save(
    state: SessionState,
    checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR,
    max_checkpoints: int = 10,
) -> Path:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    state.timestamp = time.time()

    filename = f"{state.session_id}.json"
    filepath = checkpoint_dir / filename

    with open(filepath, "w") as f:
        json.dump(asdict(state), f, indent=2)

    # Prune old checkpoints
    checkpoints = sorted(checkpoint_dir.glob("*.json"), key=os.path.getmtime)
    while len(checkpoints) > max_checkpoints:
        checkpoints[0].unlink()
        checkpoints = checkpoints[1:]

    return filepath


def checkpoint_restore(
    session_id: str, checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR
) -> SessionState | None:
    filepath = checkpoint_dir / f"{session_id}.json"
    if not filepath.exists():
        # Try partial match
        matches = list(checkpoint_dir.glob(f"{session_id}*.json"))
        if matches:
            filepath = max(matches, key=os.path.getmtime)
        else:
            return None

    with open(filepath) as f:
        data = json.load(f)

    return SessionState(**data)


def list_checkpoints(checkpoint_dir: Path = DEFAULT_CHECKPOINT_DIR) -> list[dict]:
    if not checkpoint_dir.exists():
        return []

    results = []
    for fp in sorted(checkpoint_dir.glob("*.json"), key=os.path.getmtime, reverse=True):
        try:
            with open(fp) as f:
                data = json.load(f)
            results.append(
                {
                    "session_id": data.get("session_id", fp.stem),
                    "task": data.get("task", "")[:80],
                    "steps": data.get("step_count", 0),
                    "timestamp": data.get("timestamp", 0),
                    "file": str(fp),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return results

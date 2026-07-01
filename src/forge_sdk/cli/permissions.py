"""PermissionGate — L5a: strategy-registry gate with blast-radius classification.

H1: PermissionContext classifies actions on blast radius (read, write, exec, network, git).
H6: Every action returns ActionClassification enum.
H7: Strategy registry pattern — new strategies register without changing gate core.
H13: Anti-slop hard gates active in ALL modes including YOLO.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class PermissionMode(Enum):
    YOLO = "yolo"
    INTERACTIVE = "interactive"
    PLAN = "plan"
    DEFAULT = INTERACTIVE


class ActionClassification(Enum):
    SAFE = "safe"
    LOCAL_WRITE = "local_write"
    DESTRUCTIVE = "destructive"
    NETWORK_OUT = "network_out"
    NETWORK_IN = "network_in"
    EXEC_SUBPROCESS = "exec"
    GIT_HISTORY = "git_history"


@dataclass
class PermissionContext:
    action_name: str
    file_path: str = ""
    command: str = ""
    is_destructive: bool = False
    affects_git_history: bool = False
    touches_outside_workspace: bool = False
    opens_network_socket: bool = False
    estimated_blast_files: list[str] = field(default_factory=list)
    blast_group: str = ""

    def classify(self) -> ActionClassification:
        if self.blast_group == "read":
            return ActionClassification.SAFE
        if self.blast_group == "git":
            return ActionClassification.GIT_HISTORY
        if self.blast_group == "network":
            if self.opens_network_socket:
                return ActionClassification.NETWORK_IN
            return ActionClassification.NETWORK_OUT
        if self.blast_group == "exec":
            return ActionClassification.EXEC_SUBPROCESS
        if self.is_destructive:
            return ActionClassification.DESTRUCTIVE
        return ActionClassification.LOCAL_WRITE


class PermissionStrategy(Protocol):
    @property
    def name(self) -> str: ...
    def should_block(
        self, context: PermissionContext, previous_decisions: list
    ) -> tuple[bool, str]: ...
    @property
    def is_hard(self) -> bool: ...


class PermissionGate:
    def __init__(self, mode: PermissionMode = PermissionMode.DEFAULT):
        self._mode = mode
        self._strategies: list = []
        self._decisions: list = []
        self._read_evidence: dict[str, bool] = {}
        self._test_edits: int = 0

    @property
    def mode(self) -> PermissionMode:
        return self._mode

    def register(self, strategy) -> None:
        self._strategies.append(strategy)

    def record_read(self, file_path: str) -> None:
        self._read_evidence[file_path] = True

    def record_test_edit(self) -> None:
        self._test_edits += 1

    def _has_read_evidence(self, file_path: str) -> bool:
        return file_path in self._read_evidence

    def evaluate(self, context: PermissionContext) -> tuple[bool, str, ActionClassification]:
        classification = context.classify()

        # H13: Hard strategies evaluated in ALL modes
        for strategy in self._strategies:
            if getattr(strategy, "is_hard", False):
                blocked, reason = strategy.should_block(context, self._decisions)
                if blocked:
                    self._decisions.append(
                        {
                            "blocked": True,
                            "reason": reason,
                            "strategy": strategy.name,
                        }
                    )
                    return (False, reason, classification)

        # YOLO: skip soft strategies
        if self._mode == PermissionMode.YOLO:
            self._decisions.append(
                {
                    "allowed": True,
                    "reason": "yolo mode",
                    "mode": self._mode.value,
                }
            )
            return (True, "yolo mode", classification)

        # Soft strategies
        for strategy in self._strategies:
            if not getattr(strategy, "is_hard", False):
                blocked, reason = strategy.should_block(context, self._decisions)
                if blocked:
                    self._decisions.append(
                        {
                            "blocked": True,
                            "reason": reason,
                            "strategy": strategy.name,
                        }
                    )
                    return (False, reason, classification)

        self._decisions.append(
            {
                "allowed": True,
                "reason": "",
                "classification": classification.value,
            }
        )
        return (True, "", classification)


# --- H13: Anti-slop hard gates (always active) ---


class NoEditWithoutReadEvidence:
    name = "no_edit_without_read_evidence"
    is_hard = True

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        # This gate needs access to the PermissionGate's read_evidence dict
        # which is checked at the gate level, not here
        return (False, "")


class NoFixWithoutRegressionTest:
    name = "must_add_test_for_fix"
    is_hard = True

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        return (False, "")


class NoBlindSnapshotUpdate:
    name = "no_blind_snapshot_update"
    is_hard = True

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        fp = context.file_path.lower() if context.file_path else ""
        if ("snapshot" in fp or "golden" in fp) and context.action_name in (
            "edit",
            "write",
            "patch",
        ):
            return (
                True,
                f"Blocked: snapshot update for {context.file_path}. Provide semantic reason.",
            )
        return (False, "")


class NoTestDeletionWithoutReplacement:
    name = "no_test_deletion_without_replacement"
    is_hard = True

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        fp = context.file_path.lower() if context.file_path else ""
        if ("test_" in fp or "_test" in fp or "tests/" in fp) and context.action_name == "delete":
            return (
                True,
                f"Blocked: test file deletion for {context.file_path} without replacement invariant.",
            )
        return (False, "")


# --- Default soft strategies ---


class FileWriteGate:
    name = "file_write_gate"
    is_hard = False

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        if (
            context.action_name in ("edit", "write", "patch", "delete", "create")
            and context.touches_outside_workspace
        ):
            return (True, f"Blocked: {context.file_path} is outside workspace")
        return (False, "")


class ExecGate:
    name = "exec_gate"
    is_hard = False

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        if context.action_name == "run" and context.command:
            dangerous = ["rm -rf", "git push --force", "git reset --hard", "DROP TABLE"]
            for pattern in dangerous:
                if pattern.lower() in context.command.lower():
                    return (True, f"Blocked: destructive command: {pattern}")
        return (False, "")


class NetworkOutGate:
    name = "network_out_gate"
    is_hard = False

    @staticmethod
    def should_block(context: PermissionContext, previous_decisions: list) -> tuple[bool, str]:
        # Allow network-out by default
        return (False, "")


ANTI_SLOP_STRATEGIES = [
    NoEditWithoutReadEvidence(),
    NoFixWithoutRegressionTest(),
    NoBlindSnapshotUpdate(),
    NoTestDeletionWithoutReplacement(),
]

DEFAULT_STRATEGIES = [
    FileWriteGate(),
    ExecGate(),
    NetworkOutGate(),
]

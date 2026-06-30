"""Policy Kernel — L4: tool authorization by risk classification.

Typed tool leases with TTL. Policy-mechanism separation.
Only the policy kernel grants permissions — the model may reason, but the harness authorizes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(Enum):
    LOW = "low"        # read-only, no side effects
    MEDIUM = "medium"  # write to workspace, reversible
    HIGH = "high"      # exec shell, network, irreversible
    CRITICAL = "critical"  # system-level, requires human approval


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    EXEC = "exec"
    NETWORK = "network"
    MERGE = "merge"
    MEMORY_WRITE = "memory_write"


@dataclass(frozen=True)
class ToolLease:
    """A typed permission grant for a specific tool invocation."""

    tool_id: str
    permissions: tuple[Permission, ...]
    risk: RiskLevel
    ttl_seconds: float = 300.0
    granted_at: float = field(default_factory=time.time)
    scope: str = ""  # e.g. "workspace", "repo:/path/to/repo"

    @property
    def is_expired(self) -> bool:
        return time.time() > self.granted_at + self.ttl_seconds


@dataclass
class PolicyDecision:
    """Result of a policy check."""

    allowed: bool
    lease: ToolLease | None = None
    reason: str = ""


class PolicyKernel:
    """L4: grants/denies tools by risk. Policy-mechanism separation."""

    def __init__(self) -> None:
        self._leases: dict[str, ToolLease] = {}
        self._risk_rules: dict[str, RiskLevel] = {}
        self._denied_tools: set[str] = set()

    def register_tool_risk(self, tool_id: str, risk: RiskLevel) -> None:
        """Register the risk level for a tool."""
        self._risk_rules[tool_id] = risk

    def deny_tool(self, tool_id: str) -> None:
        """Blacklist a tool entirely."""
        self._denied_tools.add(tool_id)

    def request_lease(
        self,
        tool_id: str,
        requested_permissions: tuple[Permission, ...],
        ttl_seconds: float = 300.0,
        scope: str = "",
    ) -> PolicyDecision:
        """Request a tool lease. Returns PolicyDecision with allowed=True/False."""
        if tool_id in self._denied_tools:
            return PolicyDecision(allowed=False, reason=f"Tool '{tool_id}' is blacklisted")

        risk = self._risk_rules.get(tool_id, RiskLevel.MEDIUM)

        # Critical tools need explicit approval (human gate)
        if risk == RiskLevel.CRITICAL:
            return PolicyDecision(
                allowed=False,
                reason=f"Tool '{tool_id}' requires CRITICAL approval (human gate)",
            )

        lease = ToolLease(
            tool_id=tool_id,
            permissions=requested_permissions,
            risk=risk,
            ttl_seconds=ttl_seconds,
            scope=scope,
        )
        self._leases[tool_id] = lease
        return PolicyDecision(allowed=True, lease=lease, reason=f"Lease granted (risk={risk.value})")

    def check_lease(self, tool_id: str) -> PolicyDecision:
        """Check if an existing lease is still valid."""
        lease = self._leases.get(tool_id)
        if lease is None:
            return PolicyDecision(allowed=False, reason=f"No lease for '{tool_id}'")
        if lease.is_expired:
            del self._leases[tool_id]
            return PolicyDecision(allowed=False, reason=f"Lease for '{tool_id}' expired")
        return PolicyDecision(allowed=True, lease=lease)

    def revoke_lease(self, tool_id: str) -> bool:
        """Revoke a lease."""
        if tool_id in self._leases:
            del self._leases[tool_id]
            return True
        return False

    def active_leases(self) -> list[ToolLease]:
        """Return all non-expired leases."""
        now = time.time()
        return [
            l for l in self._leases.values()
            if now <= l.granted_at + l.ttl_seconds
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "active_leases": len(self.active_leases()),
            "total_leases_granted": len(self._leases),
            "denied_tools": list(self._denied_tools),
            "risk_rules": {k: v.value for k, v in self._risk_rules.items()},
        }

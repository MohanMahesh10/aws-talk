"""Deterministic policy engine.

AI understands receipts. This code decides approval routing.
Thresholds live here — not in prompts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# Easy to change. Do not bury these numbers in prompts.
# Bands: first rule is [0, max), later bounded rules are (prev, max], last is open.
POLICY_VERSIONS: dict[str, dict[str, Any]] = {
    "v1": {
        "name": "Standard travel policy",
        "rules": [
            {"max": 10000, "approver": "MANAGER", "reason": "Claim is below ₹10,000 threshold"},
            {"max": 50000, "approver": "CFO", "reason": "Claim exceeds ₹10,000 threshold"},
            {"max": None, "approver": "CFO + Finance", "reason": "Claim exceeds ₹50,000 threshold"},
        ],
    },
    "v2": {
        "name": "Delegated BU review",
        "rules": [
            {"max": 10000, "approver": "MANAGER", "reason": "Claim is below ₹10,000 threshold"},
            {"max": 50000, "approver": "BU_HEAD", "reason": "Claim is ₹10,000–₹50,000 — BU Head approval (v2)"},
            {"max": None, "approver": "CFO", "reason": "Claim exceeds ₹50,000 threshold — CFO (v2)"},
        ],
    },
}


@dataclass(frozen=True)
class PolicyDecision:
    approver: str
    reason: str
    version: str
    total_amount: float
    cached: bool = False


class PolicyEngine:
    """Pure functions. No LLM. Same input → same output."""

    def __init__(self, versions: dict[str, dict[str, Any]] | None = None) -> None:
        self.versions = versions or POLICY_VERSIONS

    def determine_approval(self, total_amount: float, version: str = "v1") -> PolicyDecision:
        """Route a claim total to the required approver."""
        if total_amount < 0:
            raise ValueError("total_amount cannot be negative")
        spec = self.versions.get(version)
        if spec is None:
            raise ValueError(f"Unknown policy version: {version}")

        rules = spec["rules"]
        for idx, rule in enumerate(rules):
            ceiling = rule["max"]
            if ceiling is None:
                return self._decision(rule, version, total_amount)
            if idx == 0 and total_amount < ceiling:
                return self._decision(rule, version, total_amount)
            if idx > 0 and total_amount <= ceiling:
                return self._decision(rule, version, total_amount)

        last = rules[-1]
        return self._decision(last, version, total_amount)

    def _decision(self, rule: dict[str, Any], version: str, total_amount: float) -> PolicyDecision:
        return PolicyDecision(
            approver=rule["approver"],
            reason=rule["reason"],
            version=version,
            total_amount=total_amount,
        )

    def required_roles(self, approver: str) -> list[str]:
        """Split compound approvers into individual roles."""
        parts = [p.strip() for p in approver.replace("+", ",").split(",")]
        mapping = {
            "MANAGER": "MANAGER",
            "CFO": "CFO",
            "FINANCE": "FINANCE",
            "BU_HEAD": "BU_HEAD",
            "BU HEAD": "BU_HEAD",
        }
        roles: list[str] = []
        for part in parts:
            key = part.upper()
            if key in mapping:
                roles.append(mapping[key])
            elif "FINANCE" in key:
                roles.append("FINANCE")
            elif "CFO" in key:
                roles.append("CFO")
            elif "BU" in key:
                roles.append("BU_HEAD")
            elif "MANAGER" in key:
                roles.append("MANAGER")
        seen: set[str] = set()
        out: list[str] = []
        for role in roles:
            if role not in seen:
                seen.add(role)
                out.append(role)
        return out or ["MANAGER"]


_ENGINE = PolicyEngine()


def determine_approval(total_amount: float, version: str = "v1") -> PolicyDecision:
    return _ENGINE.determine_approval(total_amount, version)

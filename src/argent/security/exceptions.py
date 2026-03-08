"""Custom exceptions for the ARG security layer — The Guard.

These exceptions are raised by security policy validators when a payload
violates a configured security rule.
"""

from __future__ import annotations


class SecurityViolationError(Exception):
    """Raised when a SecurityValidator detects a policy violation.

    Attributes:
        policy_name: Name of the policy that detected the violation.
        reason: Human-readable description of why the payload was rejected.
    """

    def __init__(self, policy_name: str, reason: str) -> None:
        self.policy_name = policy_name
        self.reason = reason
        super().__init__(f"[{policy_name}] {reason}")

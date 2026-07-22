"""Base classes for sensitivity detection rules."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class RuleSeverity(StrEnum):
    """Severity levels for detection rules.

    Scoring:
    - LOW (10 pts): Full names, job titles
    - MEDIUM (50 pts): Emails, phone numbers, addresses
    - HIGH (100 pts): Passwords, API keys
    - CRITICAL (1000 pts): Credit cards, SSN, bank accounts

    Classification:
    - Score < 50: PUBLIC (auto-approve)
    - 50 <= Score < 100: SENSITIVE (needs approval)
    - Score >= 100: CRITICAL (never auto-approve)
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RuleMatch:
    """Result when a detection rule matches.

    Immutable dataclass (frozen=True) for thread safety.
    """

    rule_name: str
    severity: RuleSeverity
    matched_text: str | None = None
    confidence: float = 1.0


class SensitivityRule(ABC):
    """Abstract base class for sensitivity detection rules.

    All detection rules must inherit from this and implement evaluate().

    Rules are evaluated sequentially. Each rule:
    - Returns None if content doesn't match
    - Returns RuleMatch if content matches (with severity level)

    Multiple matches can occur (e.g., email + phone in same text).
    """

    def __init__(self, name: str, enabled: bool = True):
        """Initialize rule.

        Args:
            name: Unique rule identifier (used in logs and UI)
            enabled: Whether rule is active (can be toggled at runtime)
        """
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def evaluate(self, content: str) -> RuleMatch | None:
        """Evaluate content against this rule.

        Args:
            content: Memory content to analyze (normalized, validated)

        Returns:
            RuleMatch if rule matches, None if no match

        Note:
            - Implementation must be fast (no expensive operations)
            - Should handle edge cases gracefully
            - Should never raise exceptions (use try/except internally)
        """
        pass

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} name={self.name} {status}>"

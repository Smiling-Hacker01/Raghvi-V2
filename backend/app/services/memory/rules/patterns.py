"""Regex-based sensitivity detection rules."""

import re
from re import Pattern

from .base import RuleMatch, RuleSeverity, SensitivityRule


class PatternRule(SensitivityRule):
    """Base class for regex pattern-based detection rules.

    Compiles regex once at init time (cached for performance).
    """

    def __init__(
        self,
        name: str,
        pattern: str,
        severity: RuleSeverity,
        enabled: bool = True,
        flags: int = re.IGNORECASE | re.UNICODE,
    ):
        """Initialize pattern rule.

        Args:
            name: Rule identifier
            pattern: Regex pattern string
            severity: Severity if matched
            enabled: Whether rule is active
            flags: Regex compilation flags
        """
        super().__init__(name, enabled)
        self.pattern: Pattern[str] = re.compile(pattern, flags)
        self.severity = severity

    def evaluate(self, content: str) -> RuleMatch | None:
        """Evaluate content against regex pattern."""
        if not self.enabled:
            return None

        try:
            match = self.pattern.search(content)
            if not match:
                return None

            return RuleMatch(
                rule_name=self.name,
                severity=self.severity,
                matched_text="[REDACTED]",
                confidence=1.0,
            )
        except Exception as e:
            # Log but don't crash
            import logging

            logging.warning(f"Error in PatternRule {self.name}: {e}")
            return None


class CreditCardRule(SensitivityRule):
    """Detect credit card numbers using Luhn algorithm validation.

    Checks:
    - Visa: 13 or 16 digits starting with 4
    - Mastercard: 16 digits starting with 5
    - Amex: 15 digits starting with 3
    - Discover: 16 digits starting with 6

    Uses Luhn algorithm to reduce false positives.
    """

    def __init__(self, name: str = "credit_card", enabled: bool = True):
        """Initialize credit card rule."""
        super().__init__(name, enabled)
        # Pattern for card-like sequences (with optional formatting)
        self.pattern = re.compile(
            r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            re.IGNORECASE | re.UNICODE,
        )

    def evaluate(self, content: str) -> RuleMatch | None:
        """Detect credit cards using Luhn algorithm."""
        if not self.enabled:
            return None

        try:
            matches = self.pattern.findall(content)
            for match in matches:
                # Remove formatting characters
                card_num = re.sub(r"[-\s]", "", match)
                if self._luhn_check(card_num):
                    return RuleMatch(
                        rule_name=self.name,
                        severity=RuleSeverity.CRITICAL,
                        matched_text="[REDACTED]",
                        confidence=0.99,
                    )
            return None
        except Exception as e:
            import logging

            logging.warning(f"Error in CreditCardRule: {e}")
            return None

    @staticmethod
    def _luhn_check(card_number: str) -> bool:
        """Validate credit card using Luhn algorithm.

        Args:
            card_number: String of digits to validate

        Returns:
            True if passes Luhn check, False otherwise
        """
        try:
            # Extract digits only
            digits = [int(d) for d in card_number if d.isdigit()]

            # Valid card length: 13-19 digits
            if not (13 <= len(digits) <= 19):
                return False

            # Luhn algorithm
            total = 0
            for i, digit in enumerate(reversed(digits)):
                # Double every second digit from right
                if i % 2 == 1:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                total += digit

            # Valid if total is divisible by 10
            return total % 10 == 0
        except (ValueError, IndexError, TypeError):
            return False


class KeywordRule(SensitivityRule):
    """Detect sensitive keywords (password, API key, secret, token, etc.).

    Looks for patterns like:
    - password: secret123
    - api_key = abc123
    - token: xyz789
    - secret = value
    """

    def __init__(
        self,
        name: str = "sensitive_keywords",
        enabled: bool = True,
    ):
        """Initialize keyword rule."""
        super().__init__(name, enabled)
        # Patterns and their severities
        self.keyword_patterns = [
            (r"\bpassword\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bpwd\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bpasswd\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bapi\s*key\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bapi_key\s*[:=]", RuleSeverity.CRITICAL),
            (r"\btoken\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bprivate\s*key\s*[:=]", RuleSeverity.CRITICAL),
            (r"\bsecret\s*[:=]", RuleSeverity.CRITICAL),
        ]
        # Compile patterns once
        self.patterns = [
            (re.compile(pattern, re.IGNORECASE), severity)
            for pattern, severity in self.keyword_patterns
        ]

    def evaluate(self, content: str) -> RuleMatch | None:
        """Detect sensitive keywords."""
        if not self.enabled:
            return None

        try:
            for pattern, severity in self.patterns:
                if pattern.search(content):
                    return RuleMatch(
                        rule_name=self.name,
                        severity=severity,
                        matched_text="[REDACTED]",
                        confidence=1.0,
                    )
            return None
        except Exception as e:
            import logging

            logging.warning(f"Error in KeywordRule: {e}")
            return None


# Standard rules loaded by default
STANDARD_RULES = [
    # CRITICAL severity (1000 points)
    PatternRule(
        name="ssn",
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        severity=RuleSeverity.CRITICAL,
    ),
    PatternRule(
        name="bank_account",
        pattern=r"\b\d{3}-\d{2}-\d{5}\b",
        severity=RuleSeverity.CRITICAL,
    ),
    CreditCardRule(),
    KeywordRule(),
    # MEDIUM severity (50 points)
    PatternRule(
        name="email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        severity=RuleSeverity.MEDIUM,
    ),
    PatternRule(
        name="phone",
        pattern=r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
        severity=RuleSeverity.MEDIUM,
    ),
    PatternRule(
        name="home_address",
        pattern=r"\b\d+\s+[A-Z][a-z]+\s+(?:St|Ave|Blvd|Rd|Dr|Ln|Ct|Way),?\s+[A-Z][a-z]+,?\s+[A-Z]{2}\s*\d{5}\b",
        severity=RuleSeverity.MEDIUM,
    ),
]

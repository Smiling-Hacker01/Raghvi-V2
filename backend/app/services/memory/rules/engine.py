"""Configurable sensitivity detection engine with score-based classification."""

import logging
from dataclasses import dataclass

from .base import RuleMatch, RuleSeverity, SensitivityRule
from .patterns import STANDARD_RULES

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineConfig:
    """Configuration for sensitivity detection engine.

    Thresholds (based on total score from all matched rules):
    - < public_threshold: PUBLIC (auto-approve)
    - < sensitive_threshold: SENSITIVE (needs approval)
    - >= sensitive_threshold: CRITICAL (never auto-approve)
    """

    public_threshold: int = 50
    sensitive_threshold: int = 100
    min_content_length: int = 3
    max_content_length: int = 5000


@dataclass
class DetectionScore:
    """Result of sensitivity analysis."""

    total_score: int
    matched_rules: list[RuleMatch]
    is_sensitive: bool
    requires_approval: bool
    severity_level: str  # "public", "sensitive", "critical"
    reason: str


class SensitivityEngine:
    """Configurable rules-based sensitivity detection engine.

    Features:
    - Pluggable rule system
    - Score-based severity classification
    - Runtime rule enable/disable
    - Extensible for custom rules
    - Fast pattern matching

    Usage:
        engine = SensitivityEngine()
        result = engine.analyze("My email is test@example.com")

        if result.requires_approval:
            # Flag for user approval
        else:
            # Auto-approve
    """

    def __init__(
        self,
        rules: list[SensitivityRule] | None = None,
        config: EngineConfig | None = None,
    ):
        """Initialize engine.

        Args:
            rules: List of rules (uses STANDARD_RULES if None)
            config: Configuration (uses defaults if None)
        """
        self.rules = rules or STANDARD_RULES
        self.config = config or EngineConfig()

        logger.info(
            f"SensitivityEngine initialized: {len(self.rules)} rules, "
            f"thresholds: public={self.config.public_threshold}, "
            f"sensitive={self.config.sensitive_threshold}"
        )

    def _validate_content(self, content: str) -> str:
        """Validate and normalize content.

        Args:
            content: Memory content to validate

        Returns:
            Normalized content

        Raises:
            ValueError: If content is invalid
        """
        if content is None:
            raise ValueError("Content cannot be None")

        # Convert to string if needed
        content_str = str(content).strip()

        if not content_str:
            raise ValueError("Content cannot be empty or whitespace-only")

        if len(content_str) < self.config.min_content_length:
            raise ValueError(
                f"Content must be at least {self.config.min_content_length} characters"
            )

        if len(content_str) > self.config.max_content_length:
            raise ValueError(
                f"Content exceeds maximum length of {self.config.max_content_length} characters"
            )

        return content_str

    def _calculate_score(self, matched_rules: list[RuleMatch]) -> int:
        """Calculate total sensitivity score.

        Severity to score mapping:
        - LOW: 10 points
        - MEDIUM: 50 points
        - HIGH: 100 points
        - CRITICAL: 1000 points

        Final score is adjusted by confidence (0.0 to 1.0).
        """
        severity_scores = {
            RuleSeverity.LOW: 10,
            RuleSeverity.MEDIUM: 50,
            RuleSeverity.HIGH: 100,
            RuleSeverity.CRITICAL: 1000,
        }

        total = 0
        for match in matched_rules:
            base_score = severity_scores.get(match.severity, 0)
            # Adjust for confidence
            adjusted_score = int(base_score * match.confidence)
            total += adjusted_score
            logger.debug(
                f"Rule '{match.rule_name}': {match.severity} "
                f"({base_score} × {match.confidence} = {adjusted_score})"
            )

        return total

    def _classify_score(self, score: int) -> tuple[str, bool, bool]:
        """Classify score into severity level.

        Args:
            score: Total score from all matched rules

        Returns:
            Tuple of (severity_level, is_sensitive, requires_approval)
        """
        if score >= self.config.sensitive_threshold:
            # CRITICAL: Never auto-approve
            return ("critical", True, True)
        elif score >= self.config.public_threshold:
            # SENSITIVE: Requires user approval
            return ("sensitive", True, True)
        else:
            # PUBLIC: Auto-approve
            return ("public", False, False)

    def analyze(self, content: str) -> DetectionScore:
        """Analyze content for sensitivity.

        Args:
            content: Memory content to analyze

        Returns:
            DetectionScore with classification and details

        Raises:
            ValueError: If content is invalid
        """
        # Validate input
        normalized = self._validate_content(content)
        logger.debug(f"Analyzing content: {len(normalized)} chars")

        # Run all enabled rules
        matched_rules: list[RuleMatch] = []
        for rule in self.rules:
            try:
                match = rule.evaluate(normalized)
                if match:
                    matched_rules.append(match)
                    logger.debug(
                        f"Rule '{rule.name}' matched "
                        f"(severity={match.severity}, confidence={match.confidence})"
                    )
            except Exception as e:
                logger.error(f"Error in rule '{rule.name}': {e}", exc_info=True)
                # Don't fail entire detection on single rule error

        # Calculate total score
        score = self._calculate_score(matched_rules)

        # Classify into severity level
        severity_level, is_sensitive, requires_approval = self._classify_score(score)

        # Build explanation for user
        if matched_rules:
            rule_names = ", ".join(set(r.rule_name for r in matched_rules))
            if requires_approval:
                reason = f"Detected: {rule_names} — requires your approval"
            else:
                reason = f"Detected: {rule_names}"
        else:
            reason = ""

        result = DetectionScore(
            total_score=score,
            matched_rules=matched_rules,
            is_sensitive=is_sensitive,
            requires_approval=requires_approval,
            severity_level=severity_level,
            reason=reason,
        )

        logger.info(
            f"Analysis complete: severity={severity_level}, score={score}, "
            f"rules_matched={len(matched_rules)}, requires_approval={requires_approval}"
        )

        return result

    def add_rule(self, rule: SensitivityRule) -> None:
        """Add a new rule to the engine at runtime.

        Args:
            rule: Rule instance to add
        """
        if any(r.name == rule.name for r in self.rules):
            logger.warning(f"Rule '{rule.name}' already exists, skipping")
            return

        self.rules.append(rule)
        logger.info(f"Rule '{rule.name}' added to engine")

    def disable_rule(self, rule_name: str) -> None:
        """Disable a rule by name.

        Args:
            rule_name: Name of rule to disable
        """
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info(f"Rule '{rule_name}' disabled")
                return
        logger.warning(f"Rule '{rule_name}' not found")

    def enable_rule(self, rule_name: str) -> None:
        """Enable a rule by name.

        Args:
            rule_name: Name of rule to enable
        """
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info(f"Rule '{rule_name}' enabled")
                return
        logger.warning(f"Rule '{rule_name}' not found")

    def get_rule(self, rule_name: str) -> SensitivityRule | None:
        """Get a rule by name.

        Args:
            rule_name: Name of rule to retrieve

        Returns:
            Rule if found, None otherwise
        """
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None


# Global singleton engine instance
_default_engine: SensitivityEngine | None = None


def get_sensitivity_engine(
    rules: list[SensitivityRule] | None = None,
    config: EngineConfig | None = None,
) -> SensitivityEngine:
    """Get or create default sensitivity engine (singleton).

    Args:
        rules: Override default rules (creates new instance if provided)
        config: Override default config (creates new instance if provided)

    Returns:
        SensitivityEngine instance
    """
    global _default_engine

    if rules or config or not _default_engine:
        _default_engine = SensitivityEngine(rules, config)

    return _default_engine


def reset_engine() -> None:
    """Reset the default engine instance.

    Useful for testing with different configurations.
    """
    global _default_engine
    _default_engine = None

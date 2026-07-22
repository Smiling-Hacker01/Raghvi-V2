"""Tests for sensitivity detection engine."""

import pytest

from app.services.memory.rules.base import RuleSeverity
from app.services.memory.rules.engine import (
    EngineConfig,
    SensitivityEngine,
    get_sensitivity_engine,
    reset_engine,
)
from app.services.memory.rules.patterns import PatternRule


class TestSensitivityEngine:
    """Tests for SensitivityEngine."""

    def setup_method(self):
        """Reset engine before each test."""
        reset_engine()

    def test_public_content_no_approval(self):
        """Test that public content is auto-approved."""
        engine = SensitivityEngine()

        public_examples = [
            "I'm a software engineer at Google",
            "I love hiking and photography",
            "I'm learning Rust and Python",
            "My favorite food is sushi",
            "I live in California",
        ]

        for content in public_examples:
            result = engine.analyze(content)
            assert result.severity_level == "public", f"Failed for: {content}"
            assert not result.is_sensitive
            assert not result.requires_approval

    def test_email_requires_approval(self):
        """Test that email addresses are flagged as sensitive."""
        engine = SensitivityEngine()
        result = engine.analyze("My email is alice@example.com")

        assert result.severity_level == "sensitive"
        assert result.is_sensitive
        assert result.requires_approval
        assert any(r.rule_name == "email" for r in result.matched_rules)

    def test_phone_requires_approval(self):
        """Test that phone numbers are flagged as sensitive."""
        engine = SensitivityEngine()
        result = engine.analyze("My phone is +1-415-555-1234")

        assert result.severity_level == "sensitive"
        assert result.is_sensitive
        assert result.requires_approval
        assert any(r.rule_name == "phone" for r in result.matched_rules)

    def test_password_never_approved(self):
        """Test that passwords are critical and never auto-approved."""
        engine = SensitivityEngine()
        result = engine.analyze("password: MySecret123")

        assert result.severity_level == "critical"
        assert result.is_sensitive
        assert result.requires_approval
        assert result.total_score >= 1000

    def test_credit_card_never_approved(self):
        """Test that credit cards are flagged as critical."""
        engine = SensitivityEngine()
        result = engine.analyze("My card: 4111-1111-1111-1111")

        assert result.severity_level == "critical"
        assert result.is_sensitive
        assert result.requires_approval
        assert any(r.rule_name == "credit_card" for r in result.matched_rules)

    def test_ssn_never_approved(self):
        """Test that SSN is critical."""
        engine = SensitivityEngine()
        result = engine.analyze("My SSN: 123-45-6789")

        assert result.severity_level == "critical"
        assert result.requires_approval
        assert any(r.rule_name == "ssn" for r in result.matched_rules)

    def test_multiple_detections(self):
        """Test detection of multiple sensitive items."""
        engine = SensitivityEngine()
        result = engine.analyze("Email: alice@example.com, Phone: 415-555-1234")

        assert result.is_sensitive
        assert len(result.matched_rules) >= 2
        assert result.total_score >= 50

    def test_invalid_content_raises_error(self):
        """Test that invalid content raises ValueError."""
        engine = SensitivityEngine()

        invalid_inputs = [None, "", "   ", "ab", "x" * 6000]

        for invalid in invalid_inputs:
            with pytest.raises(ValueError):
                engine.analyze(invalid)

    def test_custom_rules(self):
        """Test custom rule integration."""
        custom_rule = PatternRule(
            name="company_secret",
            pattern=r"\bCONFIDENTIAL\b",
            severity=RuleSeverity.HIGH,
        )

        engine = SensitivityEngine(rules=[custom_rule])
        result = engine.analyze("This is CONFIDENTIAL information")

        assert result.is_sensitive
        assert result.requires_approval

    def test_disable_rule(self):
        """Test disabling a rule."""
        engine = SensitivityEngine()

        # Email initially detected
        result1 = engine.analyze("test@example.com")
        assert result1.is_sensitive

        # Disable email rule
        engine.disable_rule("email")

        # Now email should not be detected
        result2 = engine.analyze("test@example.com")
        assert not result2.is_sensitive

    def test_enable_rule(self):
        """Test enabling a disabled rule."""
        engine = SensitivityEngine()
        engine.disable_rule("email")

        engine.enable_rule("email")

        result = engine.analyze("test@example.com")
        assert result.is_sensitive

    def test_custom_thresholds(self):
        """Test custom score thresholds."""
        config = EngineConfig(
            public_threshold=10,
            sensitive_threshold=50,
        )
        engine = SensitivityEngine(config=config)

        # Email (50 points) now triggers CRITICAL threshold
        result = engine.analyze("Email: test@example.com")
        assert result.severity_level == "critical"

    def test_score_calculation(self):
        """Test that scores are calculated correctly."""
        engine = SensitivityEngine()

        public = engine.analyze("I love hiking")
        assert public.total_score < 50

        sensitive = engine.analyze("Email: test@example.com")
        assert 50 <= sensitive.total_score < 100

        critical = engine.analyze("password: secret")
        assert critical.total_score >= 100

    def test_singleton_pattern(self):
        """Test that get_sensitivity_engine returns singleton."""
        engine1 = get_sensitivity_engine()
        engine2 = get_sensitivity_engine()

        assert engine1 is engine2

    def test_reset_engine(self):
        """Test resetting the engine."""
        engine1 = get_sensitivity_engine()
        reset_engine()
        engine2 = get_sensitivity_engine()

        assert engine1 is not engine2

    def test_reason_generated_for_user(self):
        """Test that user-friendly reason is generated."""
        engine = SensitivityEngine()
        result = engine.analyze("My email: alice@example.com")

        assert result.reason
        assert "email" in result.reason.lower()

    def test_rule_repr_and_get_rule(self):
        """Test rule repr and get_rule methods."""
        engine = SensitivityEngine()
        rule = engine.get_rule("email")
        assert rule is not None
        assert "email" in repr(rule)
        assert "enabled" in repr(rule)

        rule.enabled = False
        assert "disabled" in repr(rule)

        assert engine.get_rule("non_existent_rule") is None

    def test_add_duplicate_rule(self):
        """Test adding duplicate rule is handled gracefully."""
        engine = SensitivityEngine()
        custom_rule = PatternRule(name="email", pattern=r"test", severity=RuleSeverity.LOW)
        engine.add_rule(custom_rule)  # Already exists, should skip

    def test_toggle_non_existent_rule(self):
        """Test enabling/disabling a rule that does not exist."""
        engine = SensitivityEngine()
        engine.disable_rule("unknown_rule")
        engine.enable_rule("unknown_rule")

    def test_rule_exception_handling(self):
        """Test that a failing rule does not crash the entire engine."""

        class FaultyRule(PatternRule):
            def evaluate(self, content: str):
                raise RuntimeError("Faulty rule error")

        faulty = FaultyRule(name="faulty", pattern=r"test", severity=RuleSeverity.LOW)
        engine = SensitivityEngine(rules=[faulty])
        result = engine.analyze("Testing content with faulty rule")
        assert result.severity_level == "public"

    def test_luhn_check_edge_cases(self):
        """Test Luhn algorithm edge cases."""
        from app.services.memory.rules.patterns import CreditCardRule

        card_rule = CreditCardRule()
        assert not card_rule._luhn_check("123")  # Too short
        assert not card_rule._luhn_check("1" * 25)  # Too long
        assert not card_rule._luhn_check("invalid_digits")

        # Test credit card rule disabled
        card_rule.enabled = False
        assert card_rule.evaluate("My card: 4111-1111-1111-1111") is None

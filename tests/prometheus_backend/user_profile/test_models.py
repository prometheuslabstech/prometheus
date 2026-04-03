import pytest

from prometheus_backend.content_processing.models import AlertCategory
from prometheus_backend.models.content import ContentTheme
from prometheus_backend.user_profile.models import (
    Channel,
    InvestmentFramework,
    FRAMEWORK_METADATA,
    NotificationPreferences,
    UserEvaluatorConfig,
    UserProfile,
)


def make_profile(**overrides) -> UserProfile:
    defaults = dict(
        id="user-1",
        followed_stocks=["NVDA", "AAPL"],
        followed_themes=[ContentTheme.TECHNOLOGY],
        interest_reasons={"NVDA": "Primary AI infrastructure exposure"},
        investment_framework=InvestmentFramework.VALUE,
    )
    return UserProfile(**{**defaults, **overrides})


class TestInvestmentFramework:
    def test_all_frameworks_have_metadata(self):
        for framework in InvestmentFramework:
            assert framework in FRAMEWORK_METADATA

    def test_metadata_has_description(self):
        for framework in InvestmentFramework:
            assert FRAMEWORK_METADATA[framework].description

    def test_frameworks_with_notable_investors(self):
        assert FRAMEWORK_METADATA[InvestmentFramework.VALUE].notable_investors
        assert FRAMEWORK_METADATA[InvestmentFramework.MACRO].notable_investors

    def test_momentum_has_no_notable_investors(self):
        assert FRAMEWORK_METADATA[InvestmentFramework.MOMENTUM].notable_investors == []


class TestUserEvaluatorConfig:
    def test_defaults(self):
        config = UserEvaluatorConfig()
        assert config.push_threshold == 0.75
        assert config.suppression_window_days == 7
        assert config.source_trust == {}

    def test_default_category_weights_covers_all_categories(self):
        config = UserEvaluatorConfig()
        assert set(config.category_weights.keys()) == set(AlertCategory)

    def test_default_category_weights_are_one(self):
        config = UserEvaluatorConfig()
        assert all(w == 1.0 for w in config.category_weights.values())

    def test_custom_weights(self):
        weights = {c: 0.5 for c in AlertCategory}
        config = UserEvaluatorConfig(category_weights=weights)
        assert all(w == 0.5 for w in config.category_weights.values())


class TestNotificationPreferences:
    def test_defaults(self):
        prefs = NotificationPreferences()
        assert prefs.push_enabled is False
        assert prefs.channels == [Channel.EMAIL]
        assert prefs.digest_schedule == "Monday 09:00"


class TestUserProfile:
    def test_creation(self):
        profile = make_profile()
        assert profile.id == "user-1"
        assert profile.investment_framework == InvestmentFramework.VALUE

    def test_default_notification_prefs(self):
        profile = make_profile()
        assert profile.notification_prefs.push_enabled is False

    def test_default_evaluator_config(self):
        profile = make_profile()
        assert profile.evaluator_config.push_threshold == 0.75

    def test_serialization_round_trip(self):
        profile = make_profile()
        restored = UserProfile.model_validate_json(profile.model_dump_json())
        assert restored == profile

    def test_followed_stocks_and_themes(self):
        profile = make_profile()
        assert "NVDA" in profile.followed_stocks
        assert ContentTheme.TECHNOLOGY in profile.followed_themes

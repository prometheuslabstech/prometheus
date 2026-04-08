from prometheus_backend.content_processing.models import AlertCategory
from prometheus_backend.user_profile.framework_defaults import default_evaluator_config
from prometheus_backend.user_profile.models import InvestmentFramework


class TestDefaultEvaluatorConfig:
    def test_all_frameworks_have_defaults(self):
        for framework in InvestmentFramework:
            config = default_evaluator_config(framework)
            assert config is not None

    def test_config_covers_all_categories(self):
        for framework in InvestmentFramework:
            config = default_evaluator_config(framework)
            assert set(config.category_weights.keys()) == set(AlertCategory)

    def test_weights_are_positive(self):
        for framework in InvestmentFramework:
            config = default_evaluator_config(framework)
            assert all(w > 0 for w in config.category_weights.values())

    def test_value_prioritises_company_narrative_shift(self):
        config = default_evaluator_config(InvestmentFramework.VALUE)
        assert (
            config.category_weights[AlertCategory.COMPANY_NARRATIVE_SHIFT]
            > config.category_weights[AlertCategory.TECHNOLOGY_INFLECTION]
        )

    def test_macro_prioritises_macro_impact(self):
        config = default_evaluator_config(InvestmentFramework.MACRO)
        assert (
            config.category_weights[AlertCategory.MACRO_IMPACT]
            > config.category_weights[AlertCategory.COMPANY_NARRATIVE_SHIFT]
        )

    def test_disruptive_growth_prioritises_technology_inflection(self):
        config = default_evaluator_config(InvestmentFramework.DISRUPTIVE_GROWTH)
        assert (
            config.category_weights[AlertCategory.TECHNOLOGY_INFLECTION]
            > config.category_weights[AlertCategory.MACRO_IMPACT]
        )

    def test_default_push_threshold_unchanged(self):
        for framework in InvestmentFramework:
            config = default_evaluator_config(framework)
            assert config.push_threshold == 0.75

    def test_configs_are_independent(self):
        value_config = default_evaluator_config(InvestmentFramework.VALUE)
        macro_config = default_evaluator_config(InvestmentFramework.MACRO)
        assert (
            value_config.category_weights[AlertCategory.MACRO_IMPACT]
            != macro_config.category_weights[AlertCategory.MACRO_IMPACT]
        )

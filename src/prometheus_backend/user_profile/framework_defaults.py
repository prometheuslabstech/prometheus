from prometheus_backend.content_processing.models import AlertCategory
from prometheus_backend.user_profile.models import InvestmentFramework, UserEvaluatorConfig

_C = AlertCategory

_FRAMEWORK_WEIGHTS: dict[InvestmentFramework, dict[AlertCategory, float]] = {
    InvestmentFramework.VALUE: {
        _C.COMPANY_NARRATIVE_SHIFT: 1.5,   # moat erosion and management changes are critical
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.3,  # competitive dynamics matter for moat assessment
        _C.REGULATION_POLICY: 1.2,
        _C.MACRO_IMPACT: 0.9,
        _C.TECHNOLOGY_INFLECTION: 0.8,      # less relevant for traditional value holdings
        _C.EMERGING_SIGNAL: 0.7,
    },
    InvestmentFramework.GARP: {
        _C.COMPANY_NARRATIVE_SHIFT: 1.4,    # earnings trajectory changes are key
        _C.TECHNOLOGY_INFLECTION: 1.2,
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.2,
        _C.REGULATION_POLICY: 1.0,
        _C.EMERGING_SIGNAL: 1.0,
        _C.MACRO_IMPACT: 0.9,
    },
    InvestmentFramework.DISRUPTIVE_GROWTH: {
        _C.TECHNOLOGY_INFLECTION: 1.8,      # primary signal for disruptive growth investors
        _C.EMERGING_SIGNAL: 1.5,
        _C.REGULATION_POLICY: 1.3,          # regulatory risk is high for disruptors
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.3,
        _C.COMPANY_NARRATIVE_SHIFT: 1.0,
        _C.MACRO_IMPACT: 0.8,               # macro is secondary to innovation signals
    },
    InvestmentFramework.MACRO: {
        _C.MACRO_IMPACT: 1.8,               # central to macro investing
        _C.REGULATION_POLICY: 1.5,
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.2,
        _C.EMERGING_SIGNAL: 1.0,
        _C.TECHNOLOGY_INFLECTION: 0.9,
        _C.COMPANY_NARRATIVE_SHIFT: 0.7,    # individual company stories are secondary
    },
    InvestmentFramework.MOMENTUM: {
        _C.COMPANY_NARRATIVE_SHIFT: 1.5,    # catalysts that drive price action
        _C.EMERGING_SIGNAL: 1.4,
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.2,
        _C.MACRO_IMPACT: 1.1,
        _C.TECHNOLOGY_INFLECTION: 1.1,
        _C.REGULATION_POLICY: 0.9,
    },
    InvestmentFramework.INCOME: {
        _C.REGULATION_POLICY: 1.4,          # dividend tax policy, interest rate decisions
        _C.COMPANY_NARRATIVE_SHIFT: 1.3,    # dividend cuts or payout changes
        _C.MACRO_IMPACT: 1.3,
        _C.INDUSTRY_STRUCTURE_CHANGE: 1.0,
        _C.TECHNOLOGY_INFLECTION: 0.7,
        _C.EMERGING_SIGNAL: 0.7,
    },
}


def default_evaluator_config(framework: InvestmentFramework) -> UserEvaluatorConfig:
    """Return the default UserEvaluatorConfig for a given investment framework."""
    return UserEvaluatorConfig(category_weights=_FRAMEWORK_WEIGHTS[framework])

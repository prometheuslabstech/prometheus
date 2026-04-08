import json
from unittest.mock import MagicMock

from prometheus_backend.models.content import ContentTheme
from prometheus_backend.user_profile.builder import generate_interest_reasons
from prometheus_backend.user_profile.models import InvestmentFramework

STOCKS = ["NVDA", "AAPL"]
THEMES = [ContentTheme.TECHNOLOGY]
FRAMEWORK = InvestmentFramework.VALUE
USER_CONTEXT = (
    "I hold NVDA as my primary AI infrastructure play — I'm watching GPU margin trends. "
    "AAPL is a quality compounder with an unmatched ecosystem moat. "
    "Technology is my core theme given secular digitisation tailwinds."
)

MOCK_REASONS = {
    "NVDA": "Primary AI infrastructure exposure; monitoring GPU margin expansion as data center demand accelerates.",
    "AAPL": "Quality compounder with a durable ecosystem moat; low churn and services growth are key signals.",
    "technology": "Core secular theme underpinning most holdings; tracking digitisation adoption across sectors.",
}


def make_mock_gemini(reasons: dict = MOCK_REASONS) -> MagicMock:
    mock = MagicMock()
    mock.converse.return_value = json.dumps(reasons)
    return mock


class TestGenerateInterestReasons:
    def test_returns_dict_with_all_keys(self):
        result = generate_interest_reasons(
            framework=FRAMEWORK,
            stocks=STOCKS,
            themes=THEMES,
            user_context=USER_CONTEXT,
            gemini=make_mock_gemini(),
        )
        assert set(result.keys()) == {"NVDA", "AAPL", "technology"}

    def test_reasons_are_strings(self):
        result = generate_interest_reasons(
            framework=FRAMEWORK,
            stocks=STOCKS,
            themes=THEMES,
            user_context=USER_CONTEXT,
            gemini=make_mock_gemini(),
        )
        assert all(isinstance(v, str) for v in result.values())

    def test_passes_framework_description_to_prompt(self):
        gemini = make_mock_gemini()
        generate_interest_reasons(
            framework=InvestmentFramework.MACRO,
            stocks=STOCKS,
            themes=THEMES,
            user_context=USER_CONTEXT,
            gemini=gemini,
        )
        call_kwargs = gemini.converse.call_args.kwargs
        user_msg = call_kwargs.get("user_message", "")
        assert "macro" in user_msg.lower() or "central bank" in user_msg.lower()

    def test_theme_values_used_as_keys(self):
        result = generate_interest_reasons(
            framework=FRAMEWORK,
            stocks=STOCKS,
            themes=THEMES,
            user_context=USER_CONTEXT,
            gemini=make_mock_gemini(),
        )
        assert "technology" in result

import json

from prometheus_backend.models.content import ContentTheme
from prometheus_backend.prompts.profile_builder_prompt import SYSTEM_INSTRUCTION, user_message
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.user_profile.models import FRAMEWORK_METADATA, InvestmentFramework


def generate_interest_reasons(
    framework: InvestmentFramework,
    stocks: list[str],
    themes: list[ContentTheme],
    user_context: str,
    gemini: GeminiClient,
) -> dict[str, str]:
    """Synthesize the user's expressed views into per-holding interest reasons.

    Args:
        framework: The user's selected investment framework.
        stocks: Stock tickers the user follows (e.g. ["NVDA", "AAPL"]).
        themes: Content themes the user follows.
        user_context: Free-form text from the profile interview capturing the
            user's views on why they hold each stock and theme.
        gemini: Initialized GeminiClient.

    Returns:
        A dict mapping each stock/theme key to a concise reason string.
    """
    metadata = FRAMEWORK_METADATA[framework]
    theme_values = [t.value for t in themes]

    prompt = user_message(
        framework_description=metadata.description,
        stocks=stocks,
        themes=theme_values,
        user_context=user_context,
    )

    raw = gemini.converse(user_message=prompt, system_prompt=SYSTEM_INSTRUCTION)
    # Strip markdown code fences if Gemini wraps the JSON output
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.rsplit("```", 1)[0].strip()
    return json.loads(stripped)

"""Prometheus Profile MCP Server."""

import json
import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

from prometheus_backend.config import settings
from prometheus_backend.models.content import ContentTheme
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.user_profile.builder import generate_interest_reasons
from prometheus_backend.user_profile.framework_defaults import default_evaluator_config
from prometheus_backend.user_profile.models import (
    FRAMEWORK_METADATA,
    InvestmentFramework,
    UserProfile,
)
from prometheus_backend.user_profile.repository import LocalUserProfileRepository

logger = logging.getLogger(__name__)

_repo = LocalUserProfileRepository()


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Yield a GeminiClient. AWS/KMS already initialized by main.py entrypoint."""
    yield GeminiClient(api_key=settings.gemini_api_key)


mcp = FastMCP(
    "prometheus-profile",
    instructions=(
        "User profile management tools for Prometheus. "
        "Use these tools to build, retrieve, and update investor profiles. "
        "Profiles capture followed stocks, themes, investment framework, and "
        "the reasoning behind each holding — which drives personalized alert evaluation."
    ),
    lifespan=lifespan,
)


@mcp.tool()
async def list_investment_frameworks() -> str:
    """List available investment frameworks with descriptions and notable investors.

    Call this first when building a user profile so the user can select
    the framework that best matches their investment philosophy.
    Returns a JSON array of framework options.
    """
    options = []
    for framework in InvestmentFramework:
        meta = FRAMEWORK_METADATA[framework]
        options.append(
            {
                "id": framework.value,
                "description": meta.description,
                "notable_investors": meta.notable_investors,
            }
        )
    return json.dumps(options, indent=2)


@mcp.tool()
async def generate_profile_interest_reasons(
    framework: str,
    stocks: list[str],
    themes: list[str],
    user_context: str,
    ctx: Context | None = None,
) -> str:
    """Synthesize interview answers into structured per-holding interest reasons.

    After conducting the profile interview, call this tool with the user's
    expressed views to generate concise, structured reasons for each holding.
    These reasons drive the relevance scoring in alert evaluation.

    Args:
        framework: Investment framework id (from list_investment_frameworks).
        stocks: Stock tickers the user follows (e.g. ["NVDA", "AAPL"]).
        themes: Content theme ids the user follows (e.g. ["technology", "energy"]).
        user_context: The user's expressed views collected during the interview —
            why they hold each stock and theme, what signals they watch.
    """
    assert ctx is not None, "Context is required"
    gemini: GeminiClient = ctx.request_context.lifespan_context

    reasons = generate_interest_reasons(
        framework=InvestmentFramework(framework),
        stocks=stocks,
        themes=[ContentTheme(t) for t in themes],
        user_context=user_context,
        gemini=gemini,
    )
    return json.dumps(reasons, indent=2)


@mcp.tool()
async def save_user_profile(
    user_id: str,
    framework: str,
    stocks: list[str],
    themes: list[str],
    interest_reasons: str,
) -> str:
    """Save or update a user profile.

    Call this after generate_profile_interest_reasons to persist the profile.
    Seeds the evaluator config with framework-appropriate category weights.

    Args:
        user_id: Unique identifier for the user.
        framework: Investment framework id (from list_investment_frameworks).
        stocks: Stock tickers the user follows.
        themes: Content theme ids the user follows.
        interest_reasons: JSON object mapping stock/theme keys to reason strings,
            as returned by generate_profile_interest_reasons.
    """
    selected_framework = InvestmentFramework(framework)
    profile = UserProfile(
        id=user_id,
        followed_stocks=stocks,
        followed_themes=[ContentTheme(t) for t in themes],
        interest_reasons=json.loads(interest_reasons),
        investment_framework=selected_framework,
        evaluator_config=default_evaluator_config(selected_framework),
    )
    _repo.put(profile)
    logger.info("Saved profile for user_id=%s framework=%s", user_id, framework)
    return json.dumps({"status": "saved", "user_id": user_id})


@mcp.tool()
async def get_user_profile(user_id: str) -> str:
    """Retrieve an existing user profile by user ID.

    Returns the full profile as JSON, or an error if not found.

    Args:
        user_id: Unique identifier for the user.
    """
    profile = _repo.get(user_id)
    if profile is None:
        return json.dumps({"error": f"No profile found for user_id={user_id}"})
    return profile.model_dump_json(indent=2)


def main() -> None:
    """Run the Profile MCP server."""
    logger.info("Starting Prometheus Profile MCP server")
    mcp.run()


if __name__ == "__main__":
    main()

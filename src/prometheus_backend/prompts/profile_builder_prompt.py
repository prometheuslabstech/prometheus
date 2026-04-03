"""Prompts for the user profile builder — interest_reasons synthesis."""

SYSTEM_INSTRUCTION = """\
You are a financial profile analyst helping to articulate an investor's reasoning \
for each of their holdings and themes of interest. \
Given the investor's framework and their expressed views, extract a concise investment \
thesis for each stock or theme. \
Each reason should be 1-2 sentences capturing why this holding matters to them — \
their thesis, what signals they watch, or what risk they are tracking. \
Be precise and grounded in what the investor actually said. Do not invent reasoning.\
"""


def user_message(
    framework_description: str,
    stocks: list[str],
    themes: list[str],
    user_context: str,
) -> str:
    holdings = stocks + themes
    return (
        f"Investment framework: {framework_description}\n\n"
        f"Holdings and themes to reason about: {', '.join(holdings)}\n\n"
        f"Investor's expressed views:\n{user_context}\n\n"
        f"Extract a concise investment reason for each of the following keys: "
        f"{', '.join(holdings)}. "
        f"Return a JSON object mapping each key exactly as given to a reason string."
    )

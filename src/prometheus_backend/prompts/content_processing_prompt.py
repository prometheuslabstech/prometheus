"""Prompts for the content processing job."""

SYSTEM_INSTRUCTION = """\
You are a financial content analyst. \
Extract structured metadata from the provided article. \
Be precise and conservative — only include entities and themes clearly supported by the content.\
"""


def user_message(raw_content: str) -> str:
    return f"Analyze the following article content and extract structured metadata:\n\n{raw_content}"

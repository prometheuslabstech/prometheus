"""Helpers for parsing AWS Bedrock Converse API responses."""


def parse_converse_response(response: dict) -> str:
    """Extract text content from a Bedrock Converse API response.

    Args:
        response: The raw response dict from the Converse API.

    Returns:
        The text content from the first content block.
    """
    result: str = response["output"]["message"]["content"][0]["text"]
    return result

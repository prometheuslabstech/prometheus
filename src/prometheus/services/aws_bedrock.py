"""Common Bedrock Converse API logic."""

from botocore.client import BaseClient  # type: ignore[import-untyped]

DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def converse(
    client: BaseClient,
    user_message: str,
    system_prompt: str,
    model_id: str = DEFAULT_MODEL_ID,
    max_tokens: int = 1024,
) -> str:
    """Call Bedrock Converse API and return the response text.

    Args:
        client: Bedrock Runtime boto3 client.
        user_message: The user message to send.
        system_prompt: The system prompt to guide the model.
        model_id: Bedrock model ID to invoke.
        max_tokens: Maximum tokens in the response.

    Returns:
        The text content from the model response.
    """
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[
            {
                "role": "user",
                "content": [{"text": user_message}],
            },
        ],
        inferenceConfig={"maxTokens": max_tokens},
    )

    result: str = response["output"]["message"]["content"][0]["text"]
    return result

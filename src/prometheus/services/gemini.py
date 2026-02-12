"""Gemini API client for LLM access."""

import os
from typing import Optional

from google import genai
from google.genai.types import GenerateContentResponse

DEFAULT_MODEL_ID = "gemini-2.0-flash"


class GeminiClient:
    """Client for interacting with Google's Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model_id: str = DEFAULT_MODEL_ID):
        """Initialize the Gemini client.

        Args:
            api_key: Gemini API key. If not provided, reads from GEMINI_API_KEY
                     or GOOGLE_API_KEY environment variable.
            model_id: The Gemini model to use.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Provide it directly or set "
                "GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
            )
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = model_id

    def converse(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int = 1024,
    ) -> str:
        """Send a message to Gemini and return the response text.

        Args:
            user_message: The user message to send.
            system_prompt: The system prompt to guide the model.
            max_tokens: Maximum tokens in the response.

        Returns:
            The text content from the model response.
        """
        response: GenerateContentResponse = self.client.models.generate_content(
            model=self.model_id,
            contents=user_message,
            config={
                "system_instruction": system_prompt,
                "max_output_tokens": max_tokens,
            },
        )
        return response.text


def converse(
    client: GeminiClient,
    user_message: str,
    system_prompt: str,
    max_tokens: int = 1024,
) -> str:
    """Call Gemini API and return the response text.

    This function provides a similar interface to the Bedrock converse function.

    Args:
        client: GeminiClient instance.
        user_message: The user message to send.
        system_prompt: The system prompt to guide the model.
        max_tokens: Maximum tokens in the response.

    Returns:
        The text content from the model response.
    """
    return client.converse(
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
    )

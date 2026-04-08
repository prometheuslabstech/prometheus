"""
Prometheus application settings.

Stage-based configuration — set STAGE=dev (default) or STAGE=prod.

Dev:  provide GEMINI_API_KEY and TAVILY_API_KEY directly in .env or environment.
      AWS credentials are not required.

Prod: API keys are KMS-encrypted; AWS credentials must be available to boto3
      (env vars, ~/.aws/credentials, or IAM role).
"""

import base64
import os
from enum import Enum
from typing import Optional, Union

from appdevcommons.kms_encryptor import KMSEncryptor  # type: ignore[import-untyped]
from pydantic_settings import BaseSettings, SettingsConfigDict

from prometheus_backend.dagger.aws import AWSClients


class Stage(str, Enum):
    DEV = "dev"
    PROD = "prod"


class DevSettings(BaseSettings):
    """Dev settings — API keys supplied directly via environment / .env file."""

    stage: Stage = Stage.DEV
    aws_region: str = "us-west-2"

    gemini_api_key: str = ""
    tavily_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def init_aws(self) -> None:
        """No-op — AWS is not required in dev."""
        pass


class ProdSettings(BaseSettings):
    """Prod settings — API keys decrypted from AWS KMS at runtime."""

    stage: Stage = Stage.PROD
    aws_region: str = "us-west-2"
    kms_key_arn: str = (
        "arn:aws:kms:us-west-2:792341830430:key/f46115bb-774a-4777-ab66-29903da24381"
    )

    encrypted_tavily_api_key: str = (
        "AQICAHg7rDJp72oZrIfl2vnBxkvlcidlgcJm7juguFV/iuWU+AHpeNXM1+xDGzIOkq3hyxr0AAAAiDCBhQYJKoZIhvcNAQcGoHgwdgIBADBxBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDHVB7aMFakksi489HAIBEIBEEyuVc/n9WUT/u9P2nsnQl/h7jBidNJKmCssSymJIZFlgUTnhUyw4bvsrmUJYRcVfoXIGYdcFZRXWzxqYVZBHPYuJQDU="
    )
    encrypted_gemini_api_key: str = (
        "AQICAHg7rDJp72oZrIfl2vnBxkvlcidlgcJm7juguFV/iuWU+AEV3H++a4lvm7YgbGSkh4ZoAAAAhjCBgwYJKoZIhvcNAQcGoHYwdAIBADBvBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDHFXBeKWFqtCVn6LowIBEIBC+dNo4VUUtu4Txd1SSjSOs/laMm9xuXLALC4WKe88kzuIgmaOEFpYrFCn/YkfSOjHAVEnwhPfW+lXIPKB75xErGqn"
    )

    _aws_clients: Optional[AWSClients] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def init_aws(self) -> None:
        """Initialize AWS clients for KMS decryption. Must be called before accessing API keys."""
        aws_clients = AWSClients(region_name=self.aws_region)
        aws_clients.initialize()
        self._aws_clients = aws_clients

    @staticmethod
    def _kms_decrypt(encrypted_value: str, aws_clients: AWSClients, kms_key_arn: str) -> str:
        kms_client = aws_clients.get_kms_client()
        ciphertext_blob = base64.b64decode(encrypted_value)
        plaintext_bytes = KMSEncryptor.decrypt(
            ciphertext=ciphertext_blob, kms_key_arn=kms_key_arn, kms_client=kms_client
        )
        return plaintext_bytes.decode("utf-8")

    @property
    def gemini_api_key(self) -> str:
        """Gemini API key, decrypted via KMS."""
        assert self._aws_clients is not None, "Call init_aws() before accessing API keys"
        return self._kms_decrypt(
            self.encrypted_gemini_api_key, self._aws_clients, self.kms_key_arn
        )

    @property
    def tavily_api_key(self) -> str:
        """Tavily API key, decrypted via KMS."""
        assert self._aws_clients is not None, "Call init_aws() before accessing API keys"
        return self._kms_decrypt(
            self.encrypted_tavily_api_key, self._aws_clients, self.kms_key_arn
        )


AppSettings = Union[DevSettings, ProdSettings]


def _load_settings() -> AppSettings:
    stage = os.getenv("STAGE", Stage.DEV).lower()
    if stage == Stage.PROD:
        return ProdSettings()
    return DevSettings()


settings: AppSettings = _load_settings()

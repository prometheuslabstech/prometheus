import base64
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from appdevcommons.kms_encryptor import KMSEncryptor  # type: ignore[import-untyped]
from prometheus_backend.dagger.aws import AWSClients


class Settings(BaseSettings):
    """
    Application settings.

    AWS credentials are NOT stored here - they are resolved by boto3 from:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - IAM roles (when running on EC2/ECS/Lambda)
    - AWS credentials file (~/.aws/credentials)
    """

    # AWS
    aws_region: str = "us-west-2"
    kms_key_arn: str = "arn:aws:kms:us-west-2:792341830430:key/f46115bb-774a-4777-ab66-29903da24381"

    encrypted_tavily_api_key: str = "AQICAHg7rDJp72oZrIfl2vnBxkvlcidlgcJm7juguFV/iuWU+AHpeNXM1+xDGzIOkq3hyxr0AAAAiDCBhQYJKoZIhvcNAQcGoHgwdgIBADBxBgkqhkiG9w0BBwEwHgYJYIZIAWUDBAEuMBEEDHVB7aMFakksi489HAIBEIBEEyuVc/n9WUT/u9P2nsnQl/h7jBidNJKmCssSymJIZFlgUTnhUyw4bvsrmUJYRcVfoXIGYdcFZRXWzxqYVZBHPYuJQDU="

    _aws_clients: Optional[AWSClients] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    def set_aws_clients(self, aws_clients: AWSClients) -> None:
        """Set AWS clients instance for decryption."""
        self._aws_clients = aws_clients

    @staticmethod
    def decrypt_value(encrypted_value: str, aws_clients: AWSClients, kms_key_arn: str) -> str:
        """
        Decrypt a value using AWS KMS via KMSEncryptor from appdevcommons.

        Args:
            encrypted_value: Base64-encoded encrypted value (CiphertextBlob as string)
            aws_clients: Initialized AWSClients instance
            kms_key_arn: KMS key ARN to use for decryption

        Returns:
            Decrypted plaintext value as string
        """
        kms_client = aws_clients.get_kms_client()
        ciphertext_blob = base64.b64decode(encrypted_value)
        plaintext_bytes = KMSEncryptor.decrypt(
            ciphertext=ciphertext_blob, kms_key_arn=kms_key_arn, kms_client=kms_client
        )
        return plaintext_bytes.decode("utf-8")

    @property
    def tavily_api_key(self) -> str:
        """Decrypted Tavily API key."""
        assert self._aws_clients is not None, "AWS clients must be initialized"
        return self.decrypt_value(
            self.encrypted_tavily_api_key, self._aws_clients, self.kms_key_arn
        )


settings = Settings()

from pathlib import Path

from prometheus_backend.storage.repository_base import LocalJsonlRepository
from prometheus_backend.user_profile.models import UserProfile

DEFAULT_FILE_PATH = Path(__file__).parent.parent.parent.parent / "data" / "user_profiles.jsonl"


class LocalUserProfileRepository(LocalJsonlRepository[UserProfile]):
    def __init__(self, file_path: Path = DEFAULT_FILE_PATH) -> None:
        super().__init__(UserProfile, file_path)

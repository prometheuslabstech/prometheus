import pytest

from prometheus_backend.models.content import ContentTheme
from prometheus_backend.user_profile.models import InvestmentFramework, UserProfile
from prometheus_backend.user_profile.repository import LocalUserProfileRepository


def make_profile(id: str = "user-1", framework: InvestmentFramework = InvestmentFramework.VALUE) -> UserProfile:
    return UserProfile(
        id=id,
        followed_stocks=["NVDA"],
        followed_themes=[ContentTheme.TECHNOLOGY],
        interest_reasons={"NVDA": "AI infrastructure exposure"},
        investment_framework=framework,
    )


@pytest.fixture
def repo(tmp_path):
    return LocalUserProfileRepository(file_path=tmp_path / "user_profiles.jsonl")


class TestLocalUserProfileRepository:
    def test_put_and_get(self, repo):
        profile = make_profile()
        repo.put(profile)
        assert repo.get("user-1") == profile

    def test_get_returns_none_for_missing(self, repo):
        assert repo.get("nonexistent") is None

    def test_put_overwrites_existing(self, repo):
        profile = make_profile()
        repo.put(profile)
        updated = profile.model_copy(update={"followed_stocks": ["AAPL"]})
        repo.put(updated)
        assert repo.get("user-1").followed_stocks == ["AAPL"]

    def test_list_returns_all(self, repo):
        repo.put(make_profile("user-1"))
        repo.put(make_profile("user-2"))
        assert len(repo.list()) == 2

    def test_list_empty_when_no_profiles(self, repo):
        assert repo.list() == []

    def test_delete_removes_profile(self, repo):
        repo.put(make_profile())
        repo.delete("user-1")
        assert repo.get("user-1") is None

    def test_delete_nonexistent_is_safe(self, repo):
        repo.delete("nonexistent")

    def test_round_trip_preserves_framework(self, repo):
        profile = make_profile(framework=InvestmentFramework.MACRO)
        repo.put(profile)
        assert repo.get("user-1").investment_framework == InvestmentFramework.MACRO

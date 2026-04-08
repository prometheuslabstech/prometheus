from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from prometheus_backend.content_processing.models import AlertCategory
from prometheus_backend.models.content import ContentTheme


class InvestmentFramework(str, Enum):
    VALUE = "value"
    GARP = "garp"
    DISRUPTIVE_GROWTH = "disruptive_growth"
    MACRO = "macro"
    MOMENTUM = "momentum"
    INCOME = "income"


@dataclass
class FrameworkMetadata:
    description: str
    notable_investors: list[str]


FRAMEWORK_METADATA: dict[InvestmentFramework, FrameworkMetadata] = {
    InvestmentFramework.VALUE: FrameworkMetadata(
        description="Intrinsic value, margin of safety, long-term fundamentals",
        notable_investors=["Buffett", "Munger", "Graham"],
    ),
    InvestmentFramework.GARP: FrameworkMetadata(
        description="Growth at a reasonable price — strong earnings growth without overpaying",
        notable_investors=["Lynch", "Neff"],
    ),
    InvestmentFramework.DISRUPTIVE_GROWTH: FrameworkMetadata(
        description="Transformative innovation, TAM expansion, multi-year disruption horizons",
        notable_investors=["Wood", "Druckenmiller"],
    ),
    InvestmentFramework.MACRO: FrameworkMetadata(
        description="Big-picture cycles — central bank policy, debt dynamics, global capital flows",
        notable_investors=["Dalio", "Soros", "Rogers"],
    ),
    InvestmentFramework.MOMENTUM: FrameworkMetadata(
        description="Trend-following, sector rotation, price and volume signals",
        notable_investors=[],
    ),
    InvestmentFramework.INCOME: FrameworkMetadata(
        description="Dividend yield, payout consistency, defensive sectors",
        notable_investors=[],
    ),
}


class UserEvaluatorConfig(BaseModel):
    push_threshold: float = 0.75
    category_weights: dict[AlertCategory, float] = Field(
        default_factory=lambda: {c: 1.0 for c in AlertCategory}
    )
    source_trust: dict[str, float] = Field(default_factory=dict)
    suppression_window_days: int = 7


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"


class NotificationPreferences(BaseModel):
    push_enabled: bool = False
    channels: list[Channel] = Field(default_factory=lambda: [Channel.EMAIL])
    digest_schedule: str = "Monday 09:00"


class UserProfile(BaseModel):
    id: str
    followed_stocks: list[str]
    followed_themes: list[ContentTheme]
    interest_reasons: dict[str, str]
    investment_framework: InvestmentFramework
    notification_prefs: NotificationPreferences = Field(
        default_factory=NotificationPreferences
    )
    evaluator_config: UserEvaluatorConfig = Field(
        default_factory=UserEvaluatorConfig
    )

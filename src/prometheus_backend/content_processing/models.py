from enum import Enum


class AlertCategory(str, Enum):
    COMPANY_NARRATIVE_SHIFT = "company_narrative_shift"
    INDUSTRY_STRUCTURE_CHANGE = "industry_structure_change"
    REGULATION_POLICY = "regulation_policy"
    TECHNOLOGY_INFLECTION = "technology_inflection"
    MACRO_IMPACT = "macro_impact"
    EMERGING_SIGNAL = "emerging_signal"

"""Performance test cases for extract_research_keywords."""

import json
from unittest.mock import MagicMock, patch

import pytest

from prometheus.servers.analysis import extract_research_keywords

# Test data for extract_research_keywords performance evaluation
TEST_CASES = [
    # Case 1: Simple, clear keywords across categories
    {
        "name": "basic_multi_category",
        "text": """
            Apple (AAPL) reported Q4 earnings beating EPS estimates. The Fed signaled
            a potential rate cut amid falling CPI. Investors remain bullish on tech stocks.
        """,
        "expected": {
            "securities": ["AAPL", "Apple"],
            "financial_terms": ["earnings", "EPS"],
            "policy_and_regulation": ["Fed", "rate cut"],
            "economic_indicators": ["CPI"],
            "market_sentiment": ["bullish"],
        },
    },
    # Case 2: Heavy securities focus
    {
        "name": "securities_heavy",
        "text": """
            The S&P 500 (SPY) and Nasdaq (QQQ) hit all-time highs as Tesla (TSLA),
            Microsoft (MSFT), and NVIDIA (NVDA) led gains. The Dow Jones Industrial
            Average lagged behind.
        """,
        "expected": {
            "securities": ["SPY", "QQQ", "TSLA", "MSFT", "NVDA"],
            "financial_terms": [],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": ["gains"],
        },
    },
    # Case 3: Policy and economic focus
    {
        "name": "macro_economic",
        "text": """
            The Federal Reserve's FOMC meeting concluded with hawkish commentary on
            quantitative tightening. Nonfarm payrolls exceeded expectations while
            unemployment remained at 3.7%. GDP growth showed resilience despite
            inflation concerns.
        """,
        "expected": {
            "securities": [],
            "financial_terms": [],
            "policy_and_regulation": [
                "Federal Reserve",
                "FOMC",
                "quantitative tightening",
                "hawkish",
            ],
            "economic_indicators": ["nonfarm payrolls", "unemployment", "GDP", "inflation"],
            "market_sentiment": ["hawkish"],
        },
    },
    # Case 4: Earnings report style
    {
        "name": "earnings_report",
        "text": """
            Amazon (AMZN) Q3 Results: Revenue of $143.1B (+13% YoY), EBITDA margin
            expanded to 15.3%. Free cash flow improved to $21.4B. Management raised
            full-year guidance. P/E ratio now at 45x with market cap exceeding $1.5T.
            The company announced a $10B buyback program.
        """,
        "expected": {
            "securities": ["AMZN", "Amazon"],
            "financial_terms": [
                "revenue",
                "EBITDA",
                "margin",
                "free cash flow",
                "guidance",
                "P/E",
                "market cap",
                "buyback",
            ],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": [],
        },
    },
    # Case 5: Market volatility and sentiment
    {
        "name": "market_sentiment",
        "text": """
            Markets experienced a sharp sell-off as fear gripped investors. The VIX
            spiked indicating extreme volatility. Analysts warn of a potential correction
            after months of euphoria. Risk-off sentiment dominated with investors fleeing
            to safe havens. Some see capitulation as a buying opportunity.
        """,
        "expected": {
            "securities": ["VIX"],
            "financial_terms": [],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": [
                "sell-off",
                "fear",
                "volatility",
                "correction",
                "euphoria",
                "risk-off",
                "capitulation",
            ],
        },
    },
    # Case 6: Complex mixed content (real-world style)
    {
        "name": "complex_mixed",
        "text": """
            JPMorgan (JPM) CEO Jamie Dimon warned of headwinds from rising interest rates
            as the Fed maintains its hawkish stance. The bank reported ROE of 15% and
            raised dividend yield to 2.8%. Treasury yields climbed following strong
            retail sales data and elevated PPI readings. Despite uncertainty, momentum
            in financial stocks remains strong with JPM trading at 12x earnings.
        """,
        "expected": {
            "securities": ["JPM", "JPMorgan"],
            "financial_terms": ["ROE", "dividend", "yield", "earnings"],
            "policy_and_regulation": ["Fed", "interest rates", "Treasury"],
            "economic_indicators": ["retail sales", "PPI"],
            "market_sentiment": ["headwinds", "hawkish", "uncertainty", "momentum"],
        },
    },
    # Case 7: Abbreviated/jargon heavy
    {
        "name": "jargon_heavy",
        "text": """
            FCF conversion improved QoQ. D/E ratio decreased to 0.8x. Short interest
            in the stock fell to 5%. Options activity surged with calls outpacing puts.
            The company's ROA and ROE both exceeded sector averages.
        """,
        "expected": {
            "securities": [],
            "financial_terms": ["FCF", "D/E", "short interest", "options", "ROA", "ROE"],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": [],
        },
    },
    # Case 8: Empty/minimal content
    {
        "name": "minimal_content",
        "text": "The weather was nice today and people went to the park.",
        "expected": {
            "securities": [],
            "financial_terms": [],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": [],
        },
    },
    # Case 9: Implied terms (not explicitly stated)
    {
        "name": "implied_terms",
        "text": """
            Investors are pricing in a 75bp move at the next meeting. The central bank
            faces a tough choice between fighting prices and supporting employment.
            Bond traders see yields moving higher.
        """,
        "expected": {
            "securities": [],
            "financial_terms": ["yield", "bonds"],
            "policy_and_regulation": ["central bank", "interest rate"],
            "economic_indicators": ["inflation", "unemployment"],
            "market_sentiment": [],
        },
    },
    # Case 10: Regulatory focus
    {
        "name": "regulatory",
        "text": """
            The SEC launched an investigation into the company's accounting practices.
            Antitrust concerns mount as regulators scrutinize the proposed merger.
            New Dodd-Frank amendments could impact bank capital requirements.
            Tariff threats weigh on semiconductor stocks.
        """,
        "expected": {
            "securities": [],
            "financial_terms": [],
            "policy_and_regulation": ["SEC", "antitrust", "regulation", "Dodd-Frank", "tariff"],
            "economic_indicators": [],
            "market_sentiment": [],
        },
    },
]


def calculate_category_score(expected: list[str], actual: list[str]) -> dict:
    """Calculate precision, recall, and F1 score for a single category.

    Args:
        expected: List of expected keywords (case-insensitive matching)
        actual: List of actual keywords from the extractor

    Returns:
        Dictionary with precision, recall, f1, and match details
    """
    if not expected and not actual:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "matches": [], "missing": [], "extra": []}

    expected_lower = {e.lower() for e in expected}
    actual_lower = {a.lower() for a in actual}

    matches = expected_lower & actual_lower
    missing = expected_lower - actual_lower
    extra = actual_lower - expected_lower

    precision = len(matches) / len(actual_lower) if actual_lower else 0.0
    recall = len(matches) / len(expected_lower) if expected_lower else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matches": list(matches),
        "missing": list(missing),
        "extra": list(extra),
    }


def evaluate_extraction(expected: dict, actual: dict) -> dict:
    """Evaluate extraction results against expected output.

    Args:
        expected: Expected keywords by category
        actual: Actual extracted keywords by category

    Returns:
        Dictionary with per-category and overall scores
    """
    categories = [
        "securities",
        "financial_terms",
        "policy_and_regulation",
        "economic_indicators",
        "market_sentiment",
    ]

    results = {}
    total_precision = 0.0
    total_recall = 0.0
    total_f1 = 0.0

    for category in categories:
        expected_list = expected.get(category, [])
        actual_list = actual.get(category, [])
        results[category] = calculate_category_score(expected_list, actual_list)
        total_precision += results[category]["precision"]
        total_recall += results[category]["recall"]
        total_f1 += results[category]["f1"]

    results["overall"] = {
        "precision": total_precision / len(categories),
        "recall": total_recall / len(categories),
        "f1": total_f1 / len(categories),
    }

    return results


def print_evaluation_report(test_case: dict, actual: dict, scores: dict) -> None:
    """Print a detailed evaluation report for a test case."""
    print(f"\n{'=' * 60}")
    print(f"Test Case: {test_case['name']}")
    print(f"{'=' * 60}")
    print(f"Input text: {test_case['text'][:100].strip()}...")
    print(f"\nOverall Scores: P={scores['overall']['precision']:.2f} "
          f"R={scores['overall']['recall']:.2f} F1={scores['overall']['f1']:.2f}")

    for category in ["securities", "financial_terms", "policy_and_regulation",
                     "economic_indicators", "market_sentiment"]:
        cat_scores = scores[category]
        print(f"\n  {category}:")
        print(f"    Expected: {test_case['expected'].get(category, [])}")
        print(f"    Actual:   {actual.get(category, [])}")
        print(f"    Scores:   P={cat_scores['precision']:.2f} R={cat_scores['recall']:.2f} F1={cat_scores['f1']:.2f}")
        if cat_scores["missing"]:
            print(f"    Missing:  {cat_scores['missing']}")
        if cat_scores["extra"]:
            print(f"    Extra:    {cat_scores['extra']}")


class TestExtractKeywordsPerformance:
    """Performance tests for extract_research_keywords."""

    @pytest.fixture
    def mock_ctx(self):
        """Create a mock context for testing."""
        mock = MagicMock()
        mock_bedrock = MagicMock()
        mock.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
            mock_bedrock
        )
        return mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: tc["name"])
    async def test_extraction_structure(self, test_case, mock_ctx):
        """Test that extraction returns valid JSON with required keys."""
        mock_response = json.dumps(test_case["expected"])

        with patch("prometheus.servers.analysis.converse", return_value=mock_response):
            result = await extract_research_keywords(test_case["text"], ctx=mock_ctx)

        parsed = json.loads(result)
        required_keys = {
            "securities",
            "financial_terms",
            "policy_and_regulation",
            "economic_indicators",
            "market_sentiment",
        }
        assert required_keys <= set(parsed.keys()), f"Missing keys in response"

    @pytest.mark.asyncio
    async def test_evaluation_framework(self, mock_ctx):
        """Test the evaluation framework with a known result."""
        expected = {
            "securities": ["AAPL"],
            "financial_terms": ["EPS", "revenue"],
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": ["bullish"],
        }
        actual = {
            "securities": ["AAPL", "MSFT"],  # 1 match, 1 extra
            "financial_terms": ["EPS"],  # 1 match, 1 missing
            "policy_and_regulation": [],
            "economic_indicators": [],
            "market_sentiment": ["bullish"],
        }

        scores = evaluate_extraction(expected, actual)

        # securities: precision=0.5 (1/2), recall=1.0 (1/1)
        assert scores["securities"]["precision"] == 0.5
        assert scores["securities"]["recall"] == 1.0

        # financial_terms: precision=1.0 (1/1), recall=0.5 (1/2)
        assert scores["financial_terms"]["precision"] == 1.0
        assert scores["financial_terms"]["recall"] == 0.5

        # market_sentiment: precision=1.0, recall=1.0
        assert scores["market_sentiment"]["precision"] == 1.0
        assert scores["market_sentiment"]["recall"] == 1.0


# Utility function for manual testing with real Bedrock calls
async def run_performance_evaluation():
    """Run performance evaluation against real Bedrock API.

    This function is for manual testing and requires AWS credentials.
    Run with: python -c "import asyncio; from tests.test_extract_keywords_performance import run_performance_evaluation; asyncio.run(run_performance_evaluation())"
    """
    from prometheus.dagger.aws import AWSClients
    from prometheus.services.aws_bedrock import converse
    from prometheus.prompts.extract_research_keywords_prompt import (
        EXTRACT_RESEARCH_KEYWORDS_PROMPT,
    )

    clients = AWSClients()
    clients.initialize()
    bedrock = clients.get_bedrock_runtime_client()

    all_scores = []

    for test_case in TEST_CASES:
        print(f"\nProcessing: {test_case['name']}...")

        result = converse(
            client=bedrock,
            user_message=test_case["text"],
            system_prompt=EXTRACT_RESEARCH_KEYWORDS_PROMPT,
        )

        try:
            actual = json.loads(result)
        except json.JSONDecodeError:
            print(f"  ERROR: Invalid JSON response: {result[:100]}")
            continue

        scores = evaluate_extraction(test_case["expected"], actual)
        all_scores.append(scores["overall"]["f1"])
        print_evaluation_report(test_case, actual, scores)

    if all_scores:
        avg_f1 = sum(all_scores) / len(all_scores)
        print(f"\n{'=' * 60}")
        print(f"OVERALL AVERAGE F1 SCORE: {avg_f1:.2f}")
        print(f"{'=' * 60}")

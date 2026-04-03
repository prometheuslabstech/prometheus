from prometheus_backend.news_aggregator.helpers.page_fetch_job_helper import strip_preamble

# Trimmed but representative preamble from a real Yahoo Finance fetch.
_PREAMBLE = (
    "Oops, something went wrong\n\n"
    "[Skip to navigation](#navigation-container)  [Skip to right column](#right-rail) \n\n"
    "* [Today's news](https://www.yahoo.com/news/)\n"
    "* [Markets](https://finance.yahoo.com/markets/)\n"
    "* [My Portfolio](https://finance.yahoo.com/portfolios/)\n\n"
    "© 2026 All rights reserved.\n\n"
    "# Yahoo Finance\n\n"
    " [Yahoo Finance](https://finance.yahoo.com/)\n\n"
    "[Mail](https://mail.yahoo.com/)\n\n"
    "[Sign in](https://login.yahoo.com/?.lang=en-US&src=finance)\n\n"
)

_ARTICLE = (
    "# Analysts Remain Bullish on SailPoint (SAIL) Amid Strong Q4 and Full-Year Results\n\n"
    "Faheem Tahir\n\n"
    "SailPoint, Inc. (NASDAQ:SAIL) continues to retain the confidence of over 90% of covering "
    "analysts, who maintain bullish ratings on the stock, as of March 27, 2026.\n\n"
    "The earnings report featured 28% YoY growth in total ARR, taking the total to $1.125 billion."
)

_FULL_CONTENT = _PREAMBLE + _ARTICLE


def test_strips_preamble_and_returns_article():
    result = strip_preamble(_FULL_CONTENT)
    assert result == _ARTICLE
    assert "Oops, something went wrong" not in result
    assert "Skip to navigation" not in result
    assert "Sign in" not in result


def test_returns_content_unchanged_when_no_marker_present():
    clean_content = (
        "# Analysts Remain Bullish on SailPoint (SAIL)\n\n"
        "SailPoint reported strong Q4 results with 28% ARR growth."
    )
    result = strip_preamble(clean_content)
    assert result == clean_content


def test_returns_content_unchanged_when_marker_present_but_no_article_heading():
    malformed = (
        "Oops, something went wrong\n\n"
        "# Yahoo Finance\n\n"
        "[Sign in](https://login.yahoo.com/)\n\n"
        "Some text with no article heading following."
    )
    result = strip_preamble(malformed)
    assert result == malformed

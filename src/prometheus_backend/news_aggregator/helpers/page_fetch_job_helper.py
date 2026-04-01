_YAHOO_FINANCE_SECTION_MARKER = "\n# Yahoo Finance\n"


def strip_preamble(content: str) -> str:
    """Strip Yahoo Finance bot-detection preamble from fetched page content.

    Yahoo Finance's SSR HTML includes an "Oops, something went wrong" error
    overlay and full site navigation before the article body when fetched
    without JavaScript. The actual article starts at the first H1 heading
    after the "# Yahoo Finance" section marker.
    """
    section_idx = content.find(_YAHOO_FINANCE_SECTION_MARKER)
    if section_idx == -1:
        return content
    after_section = section_idx + len(_YAHOO_FINANCE_SECTION_MARKER)
    article_heading_idx = content.find("\n# ", after_section)
    if article_heading_idx == -1:
        return content
    return content[article_heading_idx:].lstrip()

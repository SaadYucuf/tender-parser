from app.parsers.base import GenericSearchParser, SearchEndpoint


class UngmParser(GenericSearchParser):
    source_name = "UNGM"
    base_url = "https://www.ungm.org/Public/Notice"
    country_filter = "uzbekistan"
    max_keywords = 12
    endpoints = [
        SearchEndpoint(
            "https://www.ungm.org/Public/Notice",
            "Title",
            {"Country": "UZB", "Status": "Active"},
        )
    ]

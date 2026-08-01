from app.parsers.base import GenericSearchParser, SearchEndpoint


class UnopsParser(GenericSearchParser):
    source_name = "UNOPS eSourcing"
    base_url = "https://esourcing.unops.org"
    country_filter = "uzbekistan"
    max_keywords = 12
    endpoints = [
        SearchEndpoint("https://esourcing.unops.org/Notice/NoticeSearch", "searchText", {"country": "Uzbekistan"})
    ]

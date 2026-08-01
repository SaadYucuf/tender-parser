from app.parsers.base import GenericSearchParser, SearchEndpoint


class UzmedimpexParser(GenericSearchParser):
    source_name = "O'zmedimpeks"
    base_url = "https://uzmedimpex.uz"
    endpoints = [
        SearchEndpoint("https://gov.uz/uzmedimpex/search", "q"),
        SearchEndpoint("https://uzmedimpex.uz/search", "q"),
        SearchEndpoint("https://uzmedimpex.uz/tenders", "q"),
    ]

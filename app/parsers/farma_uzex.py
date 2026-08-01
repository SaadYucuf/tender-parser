from app.parsers.base import GenericSearchParser, SearchEndpoint


class FarmaUzexParser(GenericSearchParser):
    source_name = "Farma UZEX"
    base_url = "https://farma.uzex.uz"
    endpoints = [
        SearchEndpoint("https://farma.uzex.uz/search", "search"),
        SearchEndpoint("https://farma.uzex.uz/lot/list", "filter"),
    ]

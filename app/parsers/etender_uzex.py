from app.parsers.base import GenericSearchParser, SearchEndpoint


class EtenderUzexParser(GenericSearchParser):
    source_name = "eTender UZEX"
    base_url = "https://etender.uzex.uz"
    endpoints = [
        SearchEndpoint("https://etender.uzex.uz/search", "search"),
        SearchEndpoint("https://etender.uzex.uz/lot/list", "filter"),
    ]

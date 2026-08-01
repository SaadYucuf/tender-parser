from app.parsers.base import GenericSearchParser, SearchEndpoint


class XaridUzexParser(GenericSearchParser):
    source_name = "Xarid UZEX"
    base_url = "https://xarid.uzex.uz"
    endpoints = [
        SearchEndpoint("https://xarid.uzex.uz/search", "search"),
        SearchEndpoint("https://xarid.uzex.uz/lot/list", "filter"),
    ]

from app.parsers.base import GenericSearchParser, SearchEndpoint


class GovSsvParser(GenericSearchParser):
    source_name = "SSV"
    base_url = "https://gov.uz/oz/ssv"
    endpoints = [
        SearchEndpoint("https://gov.uz/oz/ssv/search", "q"),
        SearchEndpoint("https://gov.uz/uz/ssv/search", "q"),
        SearchEndpoint("https://gov.uz/ru/ssv/search", "q"),
    ]

from app.parsers.base import GenericSearchParser, SearchEndpoint


class XaridMfParser(GenericSearchParser):
    source_name = "Xarid MF"
    base_url = "https://xarid.mf.uz"
    endpoints = [
        SearchEndpoint("https://xarid.mf.uz/search", "q"),
        SearchEndpoint("https://xarid-mf.imv.uz/search", "q"),
    ]

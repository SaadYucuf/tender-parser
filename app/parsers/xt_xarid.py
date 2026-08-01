from app.parsers.base import GenericSearchParser, SearchEndpoint


class XtXaridParser(GenericSearchParser):
    source_name = "XT-Xarid"
    base_url = "https://xt-xarid.uz"
    endpoints = [SearchEndpoint("https://xt-xarid.uz/search", "q")]

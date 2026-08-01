from app.parsers.etender_uzex import EtenderUzexParser
from app.parsers.farma_uzex import FarmaUzexParser
from app.parsers.generic import ConfiguredGenericParser
from app.parsers.gov_portal import GovPortalParser
from app.parsers.gov_ssv import GovSsvParser
from app.parsers.ungm import UngmParser
from app.parsers.unops import UnopsParser
from app.parsers.uzmedimpex import UzmedimpexParser
from app.parsers.xarid_mf import XaridMfParser
from app.parsers.xarid_uzex import XaridUzexParser
from app.parsers.xt_xarid import XtXaridParser
from app.sources import SourceConfig, load_source_configs


PARSER_BY_ID = {
    "farma_uzex": FarmaUzexParser,
    "xarid_uzex": XaridUzexParser,
    "etender_uzex": EtenderUzexParser,
    "xarid_mf": XaridMfParser,
    "xt_xarid": XtXaridParser,
    "gov_ssv": GovSsvParser,
    "uzmedimpex": UzmedimpexParser,
    "ungm": UngmParser,
    "unops": UnopsParser,
}


def build_parser(config: SourceConfig):
    parser_cls = PARSER_BY_ID.get(config.id)
    if parser_cls is None:
        if config.parser.endswith("gov_portal"):
            parser = GovPortalParser(config)
        else:
            parser = ConfiguredGenericParser(config)
    else:
        parser = parser_cls()
        parser.config = config
        parser.source_name = config.name
        parser.base_url = str(config.base_url)
        if getattr(parser, "endpoints", None) and config.entry_urls:
            from app.parsers.base import SearchEndpoint

            parser.endpoints = [SearchEndpoint(str(url), "q") for url in config.entry_urls]
            parser.direct_pages_only = True
    return parser


def build_parsers(config_path: str = "config/sources.yaml"):
    return [build_parser(config) for config in load_source_configs(config_path)]


__all__ = [
    "EtenderUzexParser",
    "FarmaUzexParser",
    "ConfiguredGenericParser",
    "GovPortalParser",
    "GovSsvParser",
    "UngmParser",
    "UnopsParser",
    "UzmedimpexParser",
    "XaridMfParser",
    "XaridUzexParser",
    "XtXaridParser",
    "build_parsers",
]

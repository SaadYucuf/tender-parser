from app.parsers.etender_uzex import EtenderUzexParser
from app.parsers.farma_uzex import FarmaUzexParser
from app.parsers.gov_ssv import GovSsvParser
from app.parsers.ungm import UngmParser
from app.parsers.unops import UnopsParser
from app.parsers.uzmedimpex import UzmedimpexParser
from app.parsers.xarid_mf import XaridMfParser
from app.parsers.xarid_uzex import XaridUzexParser
from app.parsers.xt_xarid import XtXaridParser


def build_parsers():
    return [
        EtenderUzexParser(),
        XaridUzexParser(),
        GovSsvParser(),
        UzmedimpexParser(),
        UngmParser(),
        UnopsParser(),
        FarmaUzexParser(),
        XtXaridParser(),
        XaridMfParser(),
    ]


__all__ = [
    "EtenderUzexParser",
    "FarmaUzexParser",
    "GovSsvParser",
    "UngmParser",
    "UnopsParser",
    "UzmedimpexParser",
    "XaridMfParser",
    "XaridUzexParser",
    "XtXaridParser",
    "build_parsers",
]

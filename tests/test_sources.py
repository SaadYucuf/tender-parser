from app.parsers import build_parsers
from app.sources import load_source_configs


def test_sources_are_loaded_in_priority_order():
    configs = load_source_configs()

    assert len(configs) >= 22
    assert configs[0].id == "farma_uzex"
    assert configs[0].priority == "critical"
    assert configs[8].id == "unops"
    assert configs[-1].priority == "low"


def test_build_parsers_uses_source_config_names_and_urls():
    parsers = build_parsers()

    assert len(parsers) >= 22
    assert parsers[0].source_name == "UZFARM / Farma UZEX"
    assert parsers[2].source_name == "eTender UZEX"
    assert parsers[2].base_url.rstrip("/") == "https://etender.uzex.uz"

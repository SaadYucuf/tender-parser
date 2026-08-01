from app.parsers.etender_uzex import EtenderUzexParser
from app.services.telegram import format_daily_report
from app.utils.relevance import looks_medically_relevant


def test_generic_parser_extracts_tender_from_html_block():
    html = """
    <html><body>
      <article class="tender-card">
        <a href="/lot/123">Supply of medical equipment and MRI scanner</a>
        <p>Customer: O'zmedimpeks</p>
        <p>Deadline: 20.08.2026 15:00</p>
        <p>Amount: 100000 USD</p>
        <p>Status: Active</p>
      </article>
    </body></html>
    """

    records = EtenderUzexParser().parse_html(html, "https://etender.uzex.uz/search")

    assert len(records) == 1
    assert records[0].title == "Supply of medical equipment and MRI scanner"
    assert str(records[0].source_url) == "https://etender.uzex.uz/lot/123"
    assert records[0].deadline is not None


def test_etender_api_item_to_record():
    item = {
        "id": 502640,
        "display_no": "26120012502640",
        "name": "MRI va tibbiy uskunalar yetkazib berish",
        "start_date": "2026-07-16T08:10:17",
        "end_date": "2026-08-03T08:10:17",
        "cost": 490960000.0,
        "seller_name": "O'zmedimpeks",
        "region_name": "Toshkent shahri",
        "currency_codeabc": "UZS",
    }

    record = EtenderUzexParser()._item_to_record(item)

    assert record is not None
    assert record.source == "eTender UZEX"
    assert record.tender_number == "26120012502640"
    assert str(record.source_url) == "https://etender.uzex.uz/lot/502640"
    assert record.deadline is not None


def test_relevance_filter_rejects_generic_process_terms_only():
    text = "Konditsionerlar yetkazib berish. Kafolat xizmati va tender ta'minoti talab qilinadi."
    assert looks_medically_relevant(text) is False


def test_relevance_filter_rejects_hospital_furniture_purchase():
    text = "Farg'ona viloyat tibbiyot markazi uchun ofis mebeli va kantselyariya buyumlari xaridi"
    assert looks_medically_relevant(text) is False


def test_relevance_filter_accepts_specific_device_name():
    text = "1.5 Tesla MRI tizimini yetkazib berish, o'rnatish va ishga tushirish"
    assert looks_medically_relevant(text) is True


def test_relevance_filter_accepts_two_weak_medical_terms_together():
    text = "Shifoxona jihozlari va laboratoriya uskunalari yetkazib berish tenderi"
    assert looks_medically_relevant(text) is True


def test_daily_report_includes_source_links():
    text = format_daily_report(
        {"sources_checked": 1, "found": 2, "new_active": 0},
        [],
        [("eTender UZEX", "https://etender.uzex.uz")],
    )

    assert "Tekshirilgan manbalar" in text
    assert "https://etender.uzex.uz" in text

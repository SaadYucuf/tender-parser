from app.parsers.etender_uzex import EtenderUzexParser


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

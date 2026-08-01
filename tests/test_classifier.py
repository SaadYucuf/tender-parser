from app.models.schemas import Category, TenderRecord
from app.services.classifier import TenderClassifier


def test_classifier_detects_diagnostic_equipment():
    record = TenderRecord(
        source="test",
        title="Supply, installation and commissioning of 1.5 Tesla MRI system",
        source_url="https://example.com/tender/1",
    )

    classified = TenderClassifier().classify(record)

    assert classified.category == Category.DIAGNOSTIC_EQUIPMENT
    assert classified.relevance_score >= 70


def test_classifier_marks_unrelated_low_score():
    record = TenderRecord(source="test", title="Office furniture and stationery", source_url="https://example.com/tender/2")

    classified = TenderClassifier().classify(record)

    assert classified.category == Category.NOT_RELEVANT
    assert classified.relevance_score < 70

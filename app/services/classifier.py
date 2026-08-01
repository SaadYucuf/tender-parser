from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.schemas import Category, TenderRecord


CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.DIAGNOSTIC_EQUIPMENT: [
        "mri", "mrt", "мрт", "кт", "ct", "computed tomography", "ангиограф", "angiography",
        "рентген", "x-ray", "ultrasound", "uzi", "узи", "диагност",
    ],
    Category.LABORATORY_EQUIPMENT: [
        "лаборатор", "laboratory", "analizator", "анализатор", "pcr", "пцр", "hplc", "gc",
        "центрифуг", "microscope", "микроскоп", "reagent", "реагент", "spectrometer",
    ],
    Category.MEDICAL_CONSUMABLES: [
        "расход", "consumable", "syringe", "шприц", "катетер", "catheter", "implant",
        "стерил", "disposable", "однораз", "sarf material",
    ],
    Category.AMBULANCE_TRANSPORT: [
        "ambulance", "скорой помощи", "tez yordam", "санитар transport", "mobile clinic", "mobil klinika",
    ],
    Category.HOSPITAL_INFRASTRUCTURE: [
        "shifoxona qurilishi", "reconstruction", "реконструкц", "medical gas", "tibbiy gaz",
        "кислород", "oxygen supply", "sterile zone", "laboratoriya xonalari",
    ],
    Category.INSTALLATION_COMMISSIONING: [
        "installation", "commissioning", "o'rnatish", "o‘rnatish", "монтаж", "пусконалад",
        "ishga tushirish",
    ],
    Category.MEDICAL_EQUIPMENT: [
        "medical equipment", "medical devices", "медицинское оборудование", "медицинская техника",
        "tibbiy texnika", "tibbiy uskunalar", "defibrillator", "дефибриллятор", "ventilator",
        "ивл", "наркоз", "patient monitor", "bemor monitor", "infusion pump", "syringe pump",
        "hemodialysis", "гемодиализ", "autoclave", "автоклав", "sterilizer",
    ],
    Category.PHARMACEUTICALS: ["pharmaceutical", "лекарств", "dori vosita", "фармацевт"],
}

NEGATIVE_KEYWORDS = ["furniture", "office", "канцеляр", "food", "oziq-ovqat", "топливо", "fuel"]
ACTIVE_STATUSES = {"active", "open", "published", "прием предложений", "активный", "qabul qilinmoqda"}
CLOSED_STATUSES = {"closed", "cancelled", "canceled", "completed", "awarded", "archive", "bekor", "закрыт", "отменен", "отменён"}


class TenderClassifier:
    def classify(self, record: TenderRecord) -> TenderRecord:
        text = self._record_text(record)
        category, score = self._score(text)
        record.category = category
        record.relevance_score = score
        record.description = record.description or self._short_description(record, category)
        record.required_documents = record.required_documents or self._extract_requirements(text)
        record.bid_security = record.bid_security or self._flag(text, ["bid security", "tender security", "банковская гарантия", "залог", "обеспечение"])
        record.manufacturer_authorization = record.manufacturer_authorization or self._flag(
            text, ["manufacturer authorization", "авторизац", "ishlab chiqaruvchi avtorizatsiyasi"]
        )
        record.delivery_requirements = record.delivery_requirements or self._flag(text, ["delivery", "installation", "commissioning", "yetkazib", "монтаж"])
        return record

    def is_active_status(self, status: str | None) -> bool:
        if not status:
            return True
        normalized = status.lower()
        if any(value in normalized for value in CLOSED_STATUSES):
            return False
        return any(value in normalized for value in ACTIVE_STATUSES) or True

    def _score(self, text: str) -> tuple[Category, int]:
        negative_hits = self._count_hits(text, NEGATIVE_KEYWORDS)
        best_category = Category.NOT_RELEVANT
        best_hits = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            if category in {Category.INSTALLATION_COMMISSIONING, Category.PHARMACEUTICALS}:
                continue
            hits = self._count_hits(text, keywords)
            if hits > best_hits:
                best_category = category
                best_hits = hits

        pharma_hits = self._count_hits(text, CATEGORY_KEYWORDS[Category.PHARMACEUTICALS])
        if pharma_hits > best_hits and best_hits == 0:
            return Category.PHARMACEUTICALS, min(69, 35 + pharma_hits * 10)
        install_hits = self._count_hits(text, CATEGORY_KEYWORDS[Category.INSTALLATION_COMMISSIONING])
        if best_hits == 0 and install_hits:
            return Category.INSTALLATION_COMMISSIONING, min(100, 55 + install_hits * 12 - negative_hits * 15)
        if best_hits == 0:
            return Category.NOT_RELEVANT, max(0, 20 - negative_hits * 10)
        score = min(100, 55 + best_hits * 12 - negative_hits * 15)
        if best_category in {Category.DIAGNOSTIC_EQUIPMENT, Category.LABORATORY_EQUIPMENT}:
            score = min(100, score + 5)
        return best_category, max(0, score)

    def _record_text(self, record: TenderRecord) -> str:
        parts: Iterable[str | None] = [
            record.title,
            record.lot_name,
            record.customer,
            record.description,
            record.status,
            record.raw_text,
        ]
        return " ".join(part for part in parts if part).lower()

    def _count_hits(self, text: str, keywords: list[str]) -> int:
        return sum(1 for keyword in keywords if re.search(re.escape(keyword.lower()), text))

    def _short_description(self, record: TenderRecord, category: Category) -> str:
        return f"{record.title[:220]} ({category}). Manbadagi ma'lumot asosida avtomatik klassifikatsiya qilindi."

    def _extract_requirements(self, text: str) -> list[str]:
        checks = [
            ("ishlab chiqaruvchi avtorizatsiyasi", ["manufacturer authorization", "авторизац"]),
            ("o'rnatish va commissioning", ["installation", "commissioning", "монтаж", "пусконалад"]),
            ("kafolat va servis", ["warranty", "service", "гарант", "сервис"]),
            ("bid security", ["bid security", "tender security", "обеспечение", "залог"]),
            ("texnik trening", ["training", "обучение", "trening"]),
        ]
        return [label for label, keys in checks if any(key in text for key in keys)]

    def _flag(self, text: str, keys: list[str]) -> str | None:
        return "Talab qilinishi mumkin, hujjatda qo'lda tekshiring" if any(key in text for key in keys) else None

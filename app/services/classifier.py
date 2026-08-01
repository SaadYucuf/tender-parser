from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.schemas import Category, TenderRecord
from app.utils.relevance import NEGATIVE_KEYWORDS as SHARED_NEGATIVE_KEYWORDS
from app.utils.relevance import STRONG_DEVICE_KEYWORDS as SHARED_STRONG_DEVICE_KEYWORDS


CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.DIAGNOSTIC_EQUIPMENT: [
        "mri", "mrt", "мрт", "кт", "ct scanner", "computed tomography", "ангиограф", "angiography",
        "рентген", "x-ray", "ultrasound", "uzi", "узи", "диагностическое оборудование",
        "diagnostic equipment", "diagnostika uskunalari", "magnit-rezonans tomografiya",
        "kompyuter tomografiyasi", "rentgen apparati", "mammograf", "c-arm", "flyuorograf",
        "densitometr", "uzi apparati", "doppler apparati", "магнитно-резонансный томограф",
        "компьютерный томограф", "рентген аппарат", "маммограф", "флюорограф", "денситометр",
        "узи аппарат", "допплер", "mri scanner", "x-ray machine", "mammography unit",
        "angiography system", "fluoroscopy", "bone densitometer", "ultrasound machine",
        "doppler system",
    ],
    Category.LABORATORY_EQUIPMENT: [
        "лаборатор", "laboratory", "analizator", "анализатор", "pcr", "пцр", "hplc", "gc",
        "центрифуг", "microscope", "микроскоп", "reagent", "реагент", "spectrometer",
        "biokimyo analizatori", "gematologik analizator", "immunoferment analizatori",
        "pcr qurilmasi", "real-time pcr", "hplc tizimi", "gaz xromatografi", "sentrifuga",
        "mikroskop", "laboratoriya muzlatgichi", "termostat", "inkubator", "gaz analizatori",
        "spektrofotometr", "reagentlar to'plami", "tibbiy diagnostika to'plamlari",
        "биохимический анализатор", "гематологический анализатор", "ифа анализатор",
        "пцр аппарат", "пцр в реальном времени", "вэжх система", "газовый хроматограф",
        "лабораторный холодильник", "газоанализатор", "спектрофотометр", "набор реагентов",
        "диагностические наборы", "biochemistry analyzer", "hematology analyzer",
        "elisa analyzer", "pcr device", "gas chromatograph", "centrifuge", "lab freezer",
        "gas analyzer", "spectrophotometer", "reagent kit", "diagnostic test kit",
    ],
    Category.MEDICAL_CONSUMABLES: [
        "расход", "consumable", "syringe", "шприц", "катетер", "catheter", "implant",
        "стерил", "disposable", "однораз", "sarf material", "tibbiy kateter",
        "jarrohlik asboblari", "ortopedik plastinka", "steril xalat", "steril qo'lqop",
        "bir martalik tibbiy niqob", "shovlar", "медицинский катетер",
        "хирургический инструмент", "ортопедическая пластина", "стерильный халат",
        "стерильные перчатки", "одноразовая медицинская маска", "хирургический шовный материал",
        "medical catheter", "surgical instrument", "orthopedic plate", "sterile gown",
        "sterile gloves", "disposable medical mask", "surgical suture",
    ],
    Category.AMBULANCE_TRANSPORT: [
        "ambulance", "скорой помощи", "tez yordam", "санитар transport", "mobile clinic", "mobil klinika",
        "sanitar transport", "санитарный транспорт", "мобильная клиника",
    ],
    Category.HOSPITAL_INFRASTRUCTURE: [
        "shifoxona qurilishi", "reconstruction", "реконструкц", "medical gas", "tibbiy gaz",
        "кислород", "oxygen supply", "sterile zone", "laboratoriya xonalari",
        "tibbiy gaz tizimi", "markazlashtirilgan kislorod ta'minoti", "steril zona",
        "laboratoriya xonasini jihozlash", "operatsion blokni jihozlash",
        "tibbiyot markazini rekonstruksiya qilish", "система медицинских газов",
        "централизованное кислородоснабжение", "стерильная зона", "оснащение лаборатории",
        "оснащение операционного блока", "строительство больницы",
        "реконструкция медицинского центра", "medical gas system", "central oxygen supply",
        "laboratory room fitout", "operating block equipping", "hospital construction",
        "medical center reconstruction",
    ],
    Category.INSTALLATION_COMMISSIONING: [
        "installation", "commissioning", "o'rnatish", "o‘rnatish", "монтаж", "пусконалад",
        "ishga tushirish", "yetkazib berish va o'rnatish", "поставка и монтаж",
        "installation and commissioning of medical equipment",
    ],
    Category.MEDICAL_EQUIPMENT: [
        "medical equipment", "medical devices", "медицинское оборудование", "медицинская техника",
        "медицинская аппаратура", "медицинские изделия", "tibbiy texnika", "tibbiy uskunalar",
        "tibbiy jihoz", "tibbiy apparat", "defibrillator", "дефибриллятор", "ventilator",
        "ивл", "наркоз", "patient monitor", "bemor monitor", "infusion pump", "syringe pump",
        "hemodialysis", "гемодиализ", "autoclave", "автоклав", "sterilizer",
        "sun'iy nafas apparati", "narkoz apparati", "elektrokardiograf", "eeg apparati",
        "emg apparati", "endoskop", "laparoskop tizimi", "operatsion stol",
        "jarrohlik chirog'i", "gemodializ apparati", "infuzion nasos", "shprits nasosi",
        "kislorod kontsentratori", "avtoklav", "sterilizator", "аппарат ивл",
        "наркозный аппарат", "электрокардиограф", "ээг аппарат", "эмг аппарат",
        "эндоскоп", "лапароскопическая стойка", "операционный стол", "хирургический светильник",
        "аппарат для гемодиализа", "монитор пациента", "инфузионный насос", "шприцевой насос",
        "кислородный концентратор", "anesthesia machine", "ecg machine", "eeg device",
        "emg device", "laparoscopy tower", "operating table", "surgical light",
        "dialysis machine", "oxygen concentrator",
    ],
    Category.PHARMACEUTICALS: ["pharmaceutical", "лекарств", "dori vosita", "фармацевт", "фармпродукция", "farmatsevtika"],
}

NEGATIVE_KEYWORDS = SHARED_NEGATIVE_KEYWORDS
STRONG_DEVICE_KEYWORDS = list(dict.fromkeys(SHARED_STRONG_DEVICE_KEYWORDS))


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
            return Category.INSTALLATION_COMMISSIONING, min(69, 45 + install_hits * 8 - negative_hits * 15)
        if best_hits == 0:
            return Category.NOT_RELEVANT, max(0, 20 - negative_hits * 10)
        score = min(100, 55 + best_hits * 12 - negative_hits * 15)
        if best_category in {Category.DIAGNOSTIC_EQUIPMENT, Category.LABORATORY_EQUIPMENT}:
            score = min(100, score + 5)
        if self._count_hits(text, STRONG_DEVICE_KEYWORDS):
            score = max(score, 82)
        return best_category, max(0, score)

    def _record_text(self, record: TenderRecord) -> str:
        parts: Iterable[str | None] = [
            record.title,
            record.lot_name,
            record.description,
            record.status,
            record.raw_text,
        ]
        return " ".join(part for part in parts if part).lower()

    def _count_hits(self, text: str, keywords: list[str]) -> int:
        hits = 0
        for keyword in keywords:
            lowered = keyword.lower()
            if len(lowered) <= 3 or lowered in {"mri", "mrt", "uzi", "мрт", "кт"}:
                pattern = rf"(?<![\w]){re.escape(lowered)}(?![\w])"
            else:
                pattern = re.escape(lowered)
            if re.search(pattern, text):
                hits += 1
        return hits

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

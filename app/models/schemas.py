from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class Category(StrEnum):
    MEDICAL_EQUIPMENT = "Medical Equipment"
    LABORATORY_EQUIPMENT = "Laboratory Equipment"
    DIAGNOSTIC_EQUIPMENT = "Diagnostic Equipment"
    MEDICAL_CONSUMABLES = "Medical Consumables"
    HOSPITAL_INFRASTRUCTURE = "Hospital Infrastructure"
    AMBULANCE_TRANSPORT = "Ambulance and Medical Transport"
    INSTALLATION_COMMISSIONING = "Installation and Commissioning"
    PHARMACEUTICALS = "Pharmaceuticals"
    NOT_RELEVANT = "Not Relevant"


class TenderRecord(BaseModel):
    external_id: str | None = None
    source: str
    tender_number: str | None = None
    lot_number: str | None = None
    title: str
    lot_name: str | None = None
    customer: str | None = None
    customer_region: str | None = None
    category: Category = Category.NOT_RELEVANT
    amount: float | None = None
    currency: str | None = None
    published_at: datetime | None = None
    deadline: datetime | None = None
    status: str | None = None
    language: str | None = None
    source_url: HttpUrl | str
    description: str | None = None
    required_documents: list[str] = Field(default_factory=list)
    bid_security: str | None = None
    manufacturer_authorization: str | None = None
    delivery_requirements: str | None = None
    relevance_score: int = 0
    raw_text: str | None = None
    content_hash: str | None = None
    dedupe_key: str | None = None
    verified_source: bool = True

"""Search endpoint query keywords.

This list is used only for search requests. Parser-level medical relevance is
checked by ``app.utils.relevance.looks_medically_relevant`` so generic process
terms like warranty, maintenance, bid security, and installation do not cause
unrelated public procurement notices to pass the first filter.
"""

from __future__ import annotations

from app.utils.relevance import STRONG_DEVICE_KEYWORDS, WEAK_MEDICAL_KEYWORDS

KEYWORDS: list[str] = list(dict.fromkeys(WEAK_MEDICAL_KEYWORDS + STRONG_DEVICE_KEYWORDS))

"""Explainable volunteer match domain model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Match:
    id: str
    requestId: str
    volunteerId: str
    score: float
    reasons: list[str]
    createdAt: datetime

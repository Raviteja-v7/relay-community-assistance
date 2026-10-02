"""Community account and volunteer availability model."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class UserRole(StrEnum):
    REQUESTER = "REQUESTER"
    VOLUNTEER = "VOLUNTEER"
    COORDINATOR = "COORDINATOR"


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"


@dataclass
class User:
    id: str
    name: str
    role: UserRole
    location: dict[str, Any]
    skills: list[str] = field(default_factory=list)
    availability: Availability = Availability.OFFLINE
    activeRequests: int = 0
    createdAt: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "location": self.location,
            "skills": self.skills,
            "availability": self.availability.value,
            "activeRequests": self.activeRequests,
            "createdAt": self.createdAt.isoformat().replace("+00:00", "Z") if self.createdAt else None,
        }

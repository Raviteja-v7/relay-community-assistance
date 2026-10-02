"""Persisted profile for the authenticated Cognito account."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommunityProfile:
    id: str
    name: str
    roles: list[str]
    createdAt: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "roles": list(self.roles),
            "createdAt": self.createdAt.isoformat().replace("+00:00", "Z"),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CommunityProfile":
        return cls(
            id=data["id"],
            name=data["name"],
            roles=list(data.get("roles", ["REQUESTER"])),
            createdAt=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")),
        )

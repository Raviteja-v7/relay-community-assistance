"""Community assistance request and lifecycle values."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

class RequestStatus(StrEnum):
    REQUESTED = "REQUESTED"
    CLAIMED = "CLAIMED"
    IN_PROGRESS = "IN_PROGRESS"
    VOLUNTEER_COMPLETED = "VOLUNTEER_COMPLETED"
    REQUESTER_CONFIRMED = "REQUESTER_CONFIRMED"
    RESOLVED = "RESOLVED"


@dataclass
class AssistanceRequest:
    id: str
    description: str
    category: str
    urgency: str
    location: dict[str, Any]
    peopleAffected: int
    status: RequestStatus
    createdAt: datetime
    summary: str | None = None
    requiredSkills: list[str] = field(default_factory=list)
    mobilityNeeds: str = "unknown"
    isStructured: bool = False
    # Cognito subject of the creator. Optional only for records created before auth.
    requesterId: str | None = None
    claimedBy: str | None = None
    volunteerCompletedAt: datetime | None = None
    requesterConfirmedAt: datetime | None = None
    statusHistory: list[str] = field(default_factory=list)
    resolvedAt: datetime | None = None

    def to_dict(self, include_private: bool = False) -> dict[str, Any]:
        created_at = self.createdAt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        resolved_at = (
            self.resolvedAt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if self.resolvedAt
            else None
        )
        def timestamp(value: datetime | None) -> str | None:
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if value else None
        result = {
            "id": self.id,
            "description": self.description,
            "category": self.category,
            "urgency": self.urgency,
            "location": self.location,
            "peopleAffected": self.peopleAffected,
            "status": self.status.value,
            "createdAt": created_at,
            "summary": self.summary,
            "requiredSkills": self.requiredSkills,
            "mobilityNeeds": self.mobilityNeeds,
            "isStructured": self.isStructured,
            "claimedBy": self.claimedBy,
            "volunteerCompletedAt": timestamp(self.volunteerCompletedAt),
            "requesterConfirmedAt": timestamp(self.requesterConfirmedAt),
            "statusHistory": list(self.statusHistory),
            "resolvedAt": resolved_at,
        }
        if include_private and self.requesterId is not None:
            result["requesterId"] = self.requesterId
        return result

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "AssistanceRequest":
        created_at = datetime.fromisoformat(item["createdAt"].replace("Z", "+00:00"))
        return cls(
            id=item["id"],
            description=item["description"],
            category=item["category"],
            urgency=item["urgency"],
            location=item["location"],
            peopleAffected=int(item["peopleAffected"]),
            status=RequestStatus(item["status"]),
            createdAt=created_at,
            summary=item.get("summary"),
            requiredSkills=item.get("requiredSkills", []),
            mobilityNeeds=item.get("mobilityNeeds", "unknown"),
            isStructured=item.get("isStructured", False),
            requesterId=item.get("requesterId"),
            claimedBy=item.get("claimedBy"),
            volunteerCompletedAt=(
                datetime.fromisoformat(item["volunteerCompletedAt"].replace("Z", "+00:00"))
                if item.get("volunteerCompletedAt") else None
            ),
            requesterConfirmedAt=(
                datetime.fromisoformat(item["requesterConfirmedAt"].replace("Z", "+00:00"))
                if item.get("requesterConfirmedAt") else None
            ),
            statusHistory=item.get("statusHistory", []),
            resolvedAt=(
                datetime.fromisoformat(item["resolvedAt"].replace("Z", "+00:00"))
                if item.get("resolvedAt")
                else None
            ),
        )

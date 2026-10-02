"""Volunteer repository protocol and deterministic local demo roster."""

from datetime import datetime, timezone
from typing import Protocol

from app.models.user import Availability, User, UserRole


class VolunteerRepository(Protocol):
    def get(self, volunteer_id: str) -> User | None: ...

    def list(self) -> list[User]: ...

    def update(self, volunteer: User) -> User: ...
    def save(self, volunteer: User) -> User: ...


class InMemoryVolunteerRepository:
    """Small seeded volunteer roster for local/demo use only."""

    def __init__(self, volunteers: list[User] | None = None) -> None:
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._volunteers = {
            volunteer.id: volunteer
            for volunteer in (volunteers if volunteers is not None else [
                User(
                    id="volunteer-a",
                    name="Maya Rao",
                    role=UserRole.VOLUNTEER,
                    location={"label": "Block C", "latitude": 17.4000, "longitude": 78.4000},
                    skills=["pharmacy_pickup", "general_help", "food_delivery"],
                    availability=Availability.AVAILABLE,
                    createdAt=created_at,
                ),
                User(
                    id="volunteer-b",
                    name="Arjun Mehta",
                    role=UserRole.VOLUNTEER,
                    location={"label": "Oakwood", "latitude": 17.4080, "longitude": 78.4120},
                    skills=["transport", "general_help", "mobility_assistance"],
                    availability=Availability.AVAILABLE,
                    createdAt=created_at,
                ),
                User(
                    id="volunteer-c",
                    name="Leela Nair",
                    role=UserRole.VOLUNTEER,
                    location={"label": "Block C", "latitude": 17.4010, "longitude": 78.4010},
                    skills=["pharmacy_pickup", "general_help"],
                    availability=Availability.OFFLINE,
                    createdAt=created_at,
                ),
            ])
        }

    def get(self, volunteer_id: str) -> User | None:
        return self._volunteers.get(volunteer_id)

    def list(self) -> list[User]:
        return sorted(self._volunteers.values(), key=lambda item: item.id)

    def update(self, volunteer: User) -> User:
        if volunteer.id not in self._volunteers:
            raise KeyError(volunteer.id)
        self._volunteers[volunteer.id] = volunteer
        return volunteer

    def save(self, volunteer: User) -> User:
        self._volunteers[volunteer.id] = volunteer
        return volunteer

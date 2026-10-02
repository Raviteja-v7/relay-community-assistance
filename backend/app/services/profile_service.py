"""Validation and application rules for Cognito-owned profiles."""

from datetime import datetime, timezone
from typing import Any

from app.models.profile import CommunityProfile
from app.models.user import Availability, User, UserRole
from app.repositories.profile_repository import ProfileRepository
from app.repositories.volunteer_repository import VolunteerRepository

ROLES = {"REQUESTER", "VOLUNTEER"}
SKILLS = {
    "pharmacy_pickup", "transport", "mobility_assistance", "food_delivery",
    "water_delivery", "general_help",
}


class ProfileValidationError(ValueError):
    pass


class ProfileNotFoundError(LookupError):
    pass


class ProfileService:
    def __init__(self, profiles: ProfileRepository, volunteers: VolunteerRepository) -> None:
        self.profiles = profiles
        self.volunteers = volunteers

    def get_profile(self, subject: str) -> CommunityProfile:
        profile = self.profiles.get(subject)
        if profile is None:
            raise ProfileNotFoundError(subject)
        return profile

    def save_profile(self, subject: str, payload: Any) -> CommunityProfile:
        if not isinstance(payload, dict):
            raise ProfileValidationError("Request body must be a JSON object")
        name = payload.get("name")
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            raise ProfileValidationError("name must contain 2 to 80 characters")
        roles = payload.get("roles", ["REQUESTER"])
        if not isinstance(roles, list) or not roles or any(not isinstance(role, str) or role not in ROLES for role in roles):
            raise ProfileValidationError("roles may contain REQUESTER and VOLUNTEER")
        current = self.profiles.get(subject)
        profile = CommunityProfile(
            id=subject,
            name=name.strip(),
            roles=sorted(set(roles) | {"REQUESTER"}),
            createdAt=current.createdAt if current else datetime.now(timezone.utc),
        )
        saved = self.profiles.save(profile)
        existing_volunteer = self.volunteers.get(subject)
        if existing_volunteer:
            existing_volunteer.name = saved.name
            if "VOLUNTEER" not in saved.roles:
                existing_volunteer.availability = Availability.OFFLINE
            self.volunteers.save(existing_volunteer)
        return saved

    def get_volunteer(self, subject: str) -> User:
        profile = self.get_profile(subject)
        if "VOLUNTEER" not in profile.roles:
            raise ProfileValidationError("Add the VOLUNTEER role to your account first")
        volunteer = self.volunteers.get(subject)
        if volunteer is None:
            raise ProfileNotFoundError(subject)
        return volunteer

    def save_volunteer(self, subject: str, payload: Any) -> User:
        profile = self.get_profile(subject)
        if "VOLUNTEER" not in profile.roles:
            raise ProfileValidationError("Add the VOLUNTEER role to your account first")
        if not isinstance(payload, dict):
            raise ProfileValidationError("Request body must be a JSON object")
        skills = payload.get("skills", [])
        if not isinstance(skills, list) or any(not isinstance(skill, str) or skill not in SKILLS for skill in skills):
            raise ProfileValidationError("skills contains an unsupported value")
        availability_value = payload.get("availability", "OFFLINE")
        try:
            availability = Availability(availability_value)
        except (ValueError, TypeError):
            raise ProfileValidationError("availability must be AVAILABLE, BUSY, or OFFLINE") from None
        location = payload.get("location", {})
        if not isinstance(location, dict):
            raise ProfileValidationError("location must be an object")
        label = location.get("label", "Location not shared")
        if not isinstance(label, str) or len(label.strip()) > 120:
            raise ProfileValidationError("location.label must be text up to 120 characters")
        normalized = {"label": label.strip() or "Location not shared"}
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if (latitude is None) != (longitude is None):
            raise ProfileValidationError("Both coordinates are required for distance matching")
        if latitude is not None:
            if (isinstance(latitude, bool) or not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90
                    or isinstance(longitude, bool) or not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180):
                raise ProfileValidationError("Coordinates are invalid")
            # About 100 m precision at the equator; raw input is not retained.
            normalized.update(latitude=round(latitude, 3), longitude=round(longitude, 3))
        existing = self.volunteers.get(subject)
        if existing and existing.activeRequests > 0 and availability == Availability.AVAILABLE:
            availability = Availability.BUSY
        volunteer = User(
            id=subject,
            name=profile.name,
            role=UserRole.VOLUNTEER,
            location=normalized,
            skills=sorted(set(skills)),
            availability=availability,
            activeRequests=existing.activeRequests if existing else 0,
            createdAt=profile.createdAt,
        )
        return self.volunteers.save(volunteer)

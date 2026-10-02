"""Request validation, structuring, matching orchestration, and lifecycle rules."""

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from app.models.request import AssistanceRequest, RequestStatus
from app.models.user import Availability, UserRole
from app.repositories.request_repository import RequestRepository
from app.repositories.volunteer_repository import VolunteerRepository
from app.services.matching_service import MatchingService
from app.services.request_structuring_service import (
    ALLOWED_CATEGORIES,
    ALLOWED_URGENCY,
    RequestStructuringService,
    RequestStructuringError,
    StructuredRequest,
    validate_structured_output,
)


TRANSITIONS = {
    RequestStatus.REQUESTED: RequestStatus.CLAIMED,
    RequestStatus.CLAIMED: RequestStatus.IN_PROGRESS,
    RequestStatus.IN_PROGRESS: RequestStatus.RESOLVED,
}
AUTHENTICATED_TRANSITIONS = {
    RequestStatus.REQUESTED: RequestStatus.CLAIMED,
    RequestStatus.CLAIMED: RequestStatus.IN_PROGRESS,
    RequestStatus.IN_PROGRESS: RequestStatus.VOLUNTEER_COMPLETED,
}


class RequestValidationError(ValueError):
    """Input cannot form a valid assistance request."""


class RequestNotFoundError(LookupError):
    """The requested item does not exist."""


class InvalidStatusTransition(ValueError):
    """Requested lifecycle change is not allowed."""


class RequestAlreadyClaimedError(InvalidStatusTransition):
    """A request has already been claimed."""


class VolunteerNotFoundError(LookupError):
    """The selected volunteer does not exist."""


class VolunteerUnavailableError(InvalidStatusTransition):
    """A volunteer must be available to claim a request."""


class VolunteerRepositoryUnavailableError(RuntimeError):
    """Volunteer persistence is not configured for this environment."""


class RequestStructuringFailure(RuntimeError):
    """The configured structuring service failed to produce valid output."""


class RequestService:
    """Application service depending on storage and intelligence interfaces."""

    def __init__(
        self,
        repository: RequestRepository,
        id_factory: Callable[[], str] = lambda: str(uuid4()),
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        structuring_service: RequestStructuringService | None = None,
        volunteer_repository: VolunteerRepository | None = None,
        matching_service: MatchingService | None = None,
    ) -> None:
        self.repository = repository
        self._id_factory = id_factory
        self._clock = clock
        self.structuring_service = structuring_service
        self.volunteer_repository = volunteer_repository
        self.matching_service = matching_service or MatchingService()

    @staticmethod
    def validate(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RequestValidationError("Request body must be a JSON object")

        description = payload.get("description")
        if not isinstance(description, str) or not description.strip():
            raise RequestValidationError("description is required")
        description = description.strip()
        if len(description) > 1000:
            raise RequestValidationError("description must be 1000 characters or fewer")

        category = payload.get("category")
        if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
            raise RequestValidationError(f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")

        urgency = payload.get("urgency")
        if not isinstance(urgency, str) or urgency not in ALLOWED_URGENCY:
            raise RequestValidationError(f"urgency must be one of: {', '.join(sorted(ALLOWED_URGENCY))}")

        location = payload.get("location")
        if location is None:
            location = {"label": "Location not shared"}
        if not isinstance(location, dict):
            raise RequestValidationError("location must be an object")
        label = location.get("label", "Location not shared")
        if not isinstance(label, str):
            raise RequestValidationError("location.label must be text")
        normalized_location: dict[str, Any] = {"label": label.strip() or "Location not shared"}
        for coordinate in ("latitude", "longitude"):
            if coordinate in location and location[coordinate] is not None:
                value = location[coordinate]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise RequestValidationError(f"location.{coordinate} must be a number")
                lower, upper = (-90, 90) if coordinate == "latitude" else (-180, 180)
                if not lower <= value <= upper:
                    raise RequestValidationError(f"location.{coordinate} is out of range")
                # Persist only neighborhood-level precision (about 100 m).
                normalized_location[coordinate] = round(value, 3)

        people_affected = payload.get("peopleAffected")
        if isinstance(people_affected, bool) or not isinstance(people_affected, int) or people_affected < 1:
            raise RequestValidationError("peopleAffected must be a positive whole number")

        return {
            "description": description,
            "category": category,
            "urgency": urgency,
            "location": normalized_location,
            "peopleAffected": people_affected,
        }

    def structure_description(self, description: Any) -> StructuredRequest:
        if not isinstance(description, str) or not description.strip():
            raise RequestValidationError("description is required")
        if len(description.strip()) > 1000:
            raise RequestValidationError("description must be 1000 characters or fewer")
        if self.structuring_service is None:
            raise RuntimeError("Request structuring service is not configured")
        try:
            return self.structuring_service.structure(description.strip())
        except RequestStructuringError as exc:
            raise RequestStructuringFailure("Request details could not be structured safely") from exc
        except Exception as exc:
            raise RequestStructuringFailure("Request details could not be structured safely") from exc

    def create_request(self, payload: Any, requester_id: str | None = None) -> AssistanceRequest:
        fields = self.validate(payload)
        structured_keys = {"requiredSkills", "mobilityNeeds", "summary"}
        is_structured = any(key in payload for key in structured_keys)
        structured = None
        if is_structured:
            try:
                structured = validate_structured_output({
                    "category": fields["category"],
                    "urgency": fields["urgency"],
                    "peopleAffected": fields["peopleAffected"],
                    "requiredSkills": payload.get("requiredSkills"),
                    "mobilityNeeds": payload.get("mobilityNeeds"),
                    "summary": payload.get("summary"),
                })
            except RequestStructuringError as exc:
                raise RequestValidationError(str(exc)) from exc

        request = AssistanceRequest(
            id=self._id_factory(),
            **fields,
            status=RequestStatus.REQUESTED,
            createdAt=self._clock().astimezone(timezone.utc),
            summary=structured.summary if structured else None,
            requiredSkills=structured.requiredSkills if structured else [],
            mobilityNeeds=structured.mobilityNeeds if structured else "unknown",
            isStructured=structured is not None,
            requesterId=requester_id,
            statusHistory=[RequestStatus.REQUESTED.value],
        )
        return self.repository.create(request)

    def list_requests(self) -> list[AssistanceRequest]:
        return self.repository.list()

    def get_request(self, request_id: str) -> AssistanceRequest:
        request = self.repository.get(request_id)
        if request is None:
            raise RequestNotFoundError(request_id)
        return request

    def find_matches(self, request_id: str) -> list[dict[str, Any]]:
        request = self.get_request(request_id)
        if request.status != RequestStatus.REQUESTED:
            raise InvalidStatusTransition("Only open requests can be matched")
        if not request.isStructured:
            structured = self.structure_description(request.description)
            request.category = structured.category
            request.urgency = structured.urgency
            request.peopleAffected = structured.peopleAffected
            request.requiredSkills = structured.requiredSkills
            request.mobilityNeeds = structured.mobilityNeeds
            request.summary = structured.summary
            request.isStructured = True
            request = self.repository.update(request)
        if self.volunteer_repository is None:
            raise VolunteerRepositoryUnavailableError("Volunteer repository is not configured")
        return self.matching_service.match(request, self.volunteer_repository.list())

    def claim_request(self, request_id: str, volunteer_id: Any) -> AssistanceRequest:
        if self.volunteer_repository is None:
            raise VolunteerRepositoryUnavailableError("Volunteer repository is not configured")
        request = self.get_request(request_id)
        if request.status == RequestStatus.RESOLVED:
            raise InvalidStatusTransition("A resolved request cannot be claimed")
        if request.status == RequestStatus.CLAIMED:
            raise RequestAlreadyClaimedError("This request has already been claimed")
        if request.status != RequestStatus.REQUESTED:
            raise InvalidStatusTransition(f"Cannot claim a request in {request.status.value} status")
        if not isinstance(volunteer_id, str) or not volunteer_id:
            raise RequestValidationError("volunteerId is required")
        if request.requesterId is not None and request.requesterId == volunteer_id:
            raise RequestAuthorizationError("A requester cannot claim their own request")
        volunteer = self.volunteer_repository.get(volunteer_id)
        if volunteer is None or volunteer.role != UserRole.VOLUNTEER:
            raise VolunteerNotFoundError(volunteer_id)
        if volunteer.availability != Availability.AVAILABLE:
            raise VolunteerUnavailableError("Only available volunteers can claim a request")

        volunteer.activeRequests += 1
        if volunteer.activeRequests > 0:
            volunteer.availability = Availability.BUSY
        request.status = RequestStatus.CLAIMED
        request.claimedBy = volunteer.id
        if not request.statusHistory:
            request.statusHistory = [RequestStatus.REQUESTED.value]
        request.statusHistory.append(RequestStatus.CLAIMED.value)
        self.repository.update(request)
        self.volunteer_repository.update(volunteer)
        return request

    def update_status(self, request_id: str, target: Any, actor_id: str | None = None) -> AssistanceRequest:
        request = self.get_request(request_id)
        if actor_id is not None and request.claimedBy != actor_id:
            raise RequestAuthorizationError("Only the volunteer who claimed this request can update its status")
        try:
            next_status = RequestStatus(target)
        except (ValueError, TypeError):
            raise RequestValidationError("status must be IN_PROGRESS or RESOLVED") from None
        transitions = AUTHENTICATED_TRANSITIONS if request.requesterId is not None else TRANSITIONS
        expected = transitions.get(request.status)
        if next_status == RequestStatus.CLAIMED and request.status == RequestStatus.REQUESTED:
            raise InvalidStatusTransition("Use the claim endpoint to claim a request")
        if next_status != expected:
            raise InvalidStatusTransition(f"Cannot change status from {request.status.value} to {next_status.value}")
        request.status = next_status
        if not request.statusHistory:
            request.statusHistory = [RequestStatus.REQUESTED.value]
        request.statusHistory.append(next_status.value)
        if next_status == RequestStatus.VOLUNTEER_COMPLETED:
            request.volunteerCompletedAt = self._clock().astimezone(timezone.utc)
        if next_status == RequestStatus.RESOLVED:
            request.resolvedAt = self._clock().astimezone(timezone.utc)
        self.repository.update(request)
        if next_status == RequestStatus.RESOLVED and request.claimedBy and self.volunteer_repository:
            volunteer = self.volunteer_repository.get(request.claimedBy)
            if volunteer:
                volunteer.activeRequests = max(0, volunteer.activeRequests - 1)
                if volunteer.activeRequests == 0 and volunteer.availability == Availability.BUSY:
                    volunteer.availability = Availability.AVAILABLE
                self.volunteer_repository.update(volunteer)
        return request

    def confirm_request(self, request_id: str, requester_id: str) -> AssistanceRequest:
        request = self.get_request(request_id)
        if not request.requesterId or request.requesterId != requester_id:
            raise RequestAuthorizationError("Only the requester can confirm that help was received")
        if request.status != RequestStatus.VOLUNTEER_COMPLETED:
            raise InvalidStatusTransition("Only volunteer-completed requests can be confirmed")
        now = self._clock().astimezone(timezone.utc)
        request.requesterConfirmedAt = now
        request.status = RequestStatus.RESOLVED
        if not request.statusHistory:
            request.statusHistory = [RequestStatus.REQUESTED.value]
        request.statusHistory.extend([
            RequestStatus.REQUESTER_CONFIRMED.value,
            RequestStatus.RESOLVED.value,
        ])
        request.resolvedAt = now
        self.repository.update(request)
        if request.claimedBy and self.volunteer_repository:
            volunteer = self.volunteer_repository.get(request.claimedBy)
            if volunteer:
                volunteer.activeRequests = max(0, volunteer.activeRequests - 1)
                if volunteer.activeRequests == 0 and volunteer.availability == Availability.BUSY:
                    volunteer.availability = Availability.AVAILABLE
                self.volunteer_repository.update(volunteer)
        return request


class RequestAuthorizationError(PermissionError):
    """The authenticated user is not allowed to perform this request action."""

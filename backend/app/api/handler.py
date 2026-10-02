"""API Gateway-compatible HTTP adapter for the Relay request API."""

import json
import os
from typing import Any

from app.repositories.request_repository import InMemoryRequestRepository
from app.repositories.volunteer_repository import InMemoryVolunteerRepository
from app.repositories.profile_repository import InMemoryProfileRepository, DynamoDBProfileRepository
from app.repositories.trust_repository import InMemoryTrustRepository, DynamoDBTrustRepository
from app.services.request_service import (
    InvalidStatusTransition,
    RequestNotFoundError,
    RequestAuthorizationError,
    RequestService,
    RequestStructuringFailure,
    RequestValidationError,
    VolunteerNotFoundError,
    VolunteerRepositoryUnavailableError,
)
from app.services.request_structuring_service import (
    BedrockRequestStructuringService,
    LocalRequestStructuringService,
)
from app.services.profile_service import ProfileService, ProfileNotFoundError, ProfileValidationError


_service: RequestService | None = None
_profile_service: ProfileService | None = None
_trust_repository: Any = None


def get_service() -> RequestService:
    global _service
    if _service is None:
        storage = os.environ.get("RELAY_STORAGE", "memory").lower()
        if storage == "memory":
            repository = InMemoryRequestRepository()
            volunteer_repository = InMemoryVolunteerRepository()
        elif storage == "dynamodb":
            from app.repositories.dynamodb_request_repository import DynamoDBRequestRepository
            from app.repositories.dynamodb_volunteer_repository import DynamoDBVolunteerRepository

            repository = DynamoDBRequestRepository()
            volunteer_repository = DynamoDBVolunteerRepository(
                table_name=os.environ.get("RELAY_REQUESTS_TABLE")
            )
        else:
            raise RuntimeError("RELAY_STORAGE must be 'memory' or 'dynamodb'")
        structuring_mode = os.environ.get("RELAY_REQUEST_STRUCTURING", "local").lower()
        if structuring_mode == "local":
            structuring_service = LocalRequestStructuringService()
        elif structuring_mode == "bedrock":
            structuring_service = BedrockRequestStructuringService()
        else:
            raise RuntimeError("RELAY_REQUEST_STRUCTURING must be 'local' or 'bedrock'")
        _service = RequestService(
            repository,
            structuring_service=structuring_service,
            volunteer_repository=volunteer_repository,
        )
    return _service


def get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        service = get_service()
        if os.environ.get("RELAY_STORAGE", "memory").lower() == "dynamodb":
            profiles = DynamoDBProfileRepository()
        else:
            profiles = InMemoryProfileRepository()
        _profile_service = ProfileService(profiles, service.volunteer_repository)
    return _profile_service


def set_service(service: RequestService | None) -> None:
    """Replace the process service (primarily useful for tests/local setup)."""
    global _service
    _service = service
    set_profile_service(None)
    set_trust_repository(None)


def set_profile_service(service: ProfileService | None) -> None:
    global _profile_service
    _profile_service = service


def get_trust_repository() -> Any:
    global _trust_repository
    if _trust_repository is None:
        if os.environ.get("RELAY_STORAGE", "memory").lower() == "dynamodb":
            _trust_repository = DynamoDBTrustRepository()
        else:
            _trust_repository = InMemoryTrustRepository()
    return _trust_repository


def set_trust_repository(repository: Any) -> None:
    global _trust_repository
    _trust_repository = repository


def _response(status_code: int, data: Any = None) -> dict[str, Any]:
    headers = {
        "content-type": "application/json; charset=utf-8",
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET,POST,PUT,PATCH,OPTIONS",
        "access-control-allow-headers": "content-type,authorization",
    }
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": "" if status_code == 204 else json.dumps(data, separators=(",", ":")),
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Handle API Gateway HTTP API v2 and REST API proxy events."""
    del context
    http = event.get("requestContext", {}).get("http", {})
    method = str(http.get("method") or event.get("httpMethod") or "GET").upper()
    path = event.get("rawPath") or event.get("path") or "/"
    if path.startswith("/api/"):
        path = path[4:]
    elif path == "/api":
        path = "/"
    if path != "/":
        path = path.rstrip("/")

    if method == "OPTIONS":
        return _response(204)
    if method == "GET" and path == "/health":
        return _response(200, {"status": "ok"})

    principal_id = _principal_id(event)
    if principal_id is None:
        return _response(401, {"error": "unauthorized", "message": "A valid sign-in is required"})

    try:
        service = get_service()
        profile_service = get_profile_service()
        segments = [segment for segment in path.split("/") if segment]
        if method == "GET" and segments == ["me"]:
            return _response(200, profile_service.get_profile(principal_id).to_dict())
        if method == "PUT" and segments == ["me"]:
            payload = _parse_body(event.get("body"))
            return _response(200, profile_service.save_profile(principal_id, payload).to_dict())
        if method == "GET" and segments == ["me", "volunteer"]:
            return _response(200, _public_volunteer(profile_service.get_volunteer(principal_id), is_self=True))
        if method == "PUT" and segments == ["me", "volunteer"]:
            payload = _parse_body(event.get("body"))
            return _response(200, _public_volunteer(profile_service.save_volunteer(principal_id, payload), is_self=True))
        if method == "GET" and segments == ["me", "blocks"]:
            return _response(200, {"userIds": sorted(get_trust_repository().blocked_users(principal_id))})
        if len(segments) == 3 and segments[0] == "users" and segments[2] == "block":
            target_id = segments[1]
            if target_id == principal_id:
                raise RequestValidationError("You cannot block your own account")
            if method == "POST":
                get_trust_repository().block(principal_id, target_id)
                return _response(201, {"blockedUserId": target_id})
            if method == "DELETE":
                get_trust_repository().unblock(principal_id, target_id)
                return _response(204)
        if method == "POST" and segments == ["reports"]:
            payload = _parse_body(event.get("body"))
            if not isinstance(payload, dict):
                raise RequestValidationError("Request body must be a JSON object")
            target_type, target_id = payload.get("targetType"), payload.get("targetId")
            reason, details = payload.get("reason", "other"), payload.get("details", "")
            if (not isinstance(target_type, str) or target_type not in {"REQUEST", "USER"}
                    or not isinstance(target_id, str) or not target_id or len(target_id) > 128):
                raise RequestValidationError("targetType and targetId are required")
            if target_type == "REQUEST":
                service.get_request(target_id)
            else:
                if target_id == principal_id:
                    raise RequestValidationError("You cannot report your own account")
                volunteer = service.volunteer_repository.get(target_id) if service.volunteer_repository else None
                if profile_service.profiles.get(target_id) is None and volunteer is None:
                    raise ProfileNotFoundError(target_id)
            if not isinstance(reason, str) or reason not in {"inappropriate", "safety_concern", "spam", "other"}:
                raise RequestValidationError("reason must be inappropriate, safety_concern, spam, or other")
            if not isinstance(details, str) or len(details) > 500:
                raise RequestValidationError("details must be text up to 500 characters")
            report = get_trust_repository().report(principal_id, target_type, target_id, reason, details.strip())
            return _response(201, {"id": report["id"], "createdAt": report["createdAt"]})
        if method == "POST" and segments == ["requests"]:
            payload = _parse_body(event.get("body"))
            request = service.create_request(payload, requester_id=principal_id)
            return _response(201, _public_request(request, principal_id))

        if method == "POST" and segments == ["requests", "structure"]:
            payload = _parse_body(event.get("body"))
            if not isinstance(payload, dict):
                raise RequestValidationError("Request body must be a JSON object")
            return _response(200, service.structure_description(payload.get("description")).to_dict())

        if method == "GET" and segments == ["requests"]:
            return _response(200, {"requests": [_public_request(item, principal_id) for item in service.list_requests()]})

        if method == "GET" and segments == ["volunteers"]:
            if service.volunteer_repository is None:
                return _response(200, {"volunteers": []})
            return _response(200, {"volunteers": [_public_volunteer(item) for item in service.volunteer_repository.list()]})

        if method == "GET" and len(segments) == 2 and segments[0] == "requests":
            request_id = segments[1]
            return _response(200, _public_request(service.get_request(request_id), principal_id))

        if method == "POST" and len(segments) == 3 and segments[0] == "requests" and segments[2] == "matches":
            matches = service.find_matches(segments[1])
            request = service.get_request(segments[1])
            matches = [match for match in matches if match["volunteerId"] != request.requesterId]
            if request.requesterId:
                trust_repository = get_trust_repository()
                matches = [match for match in matches if not trust_repository.is_blocked_either_way(request.requesterId, match["volunteerId"])]
            return _response(200, {"requestId": segments[1], "matches": matches})

        if method == "POST" and len(segments) == 3 and segments[0] == "requests" and segments[2] == "claim":
            payload = _parse_body(event.get("body"))
            if not isinstance(payload, dict):
                raise RequestValidationError("Request body must be a JSON object")
            # The authenticated Cognito subject is authoritative. Ignore any supplied ID.
            request = service.claim_request(segments[1], principal_id)
            return _response(200, _public_request(request, principal_id))

        if method == "POST" and len(segments) == 3 and segments[0] == "requests" and segments[2] == "confirm":
            request = service.confirm_request(segments[1], principal_id)
            return _response(200, _public_request(request, principal_id))

        if method == "PATCH" and len(segments) == 3 and segments[0] == "requests" and segments[2] == "status":
            payload = _parse_body(event.get("body"))
            if not isinstance(payload, dict):
                raise RequestValidationError("Request body must be a JSON object")
            request = service.update_status(segments[1], payload.get("status"), actor_id=principal_id)
            return _response(200, _public_request(request, principal_id))
        return _response(404, {"error": "not_found", "message": "Route not found"})
    except RequestValidationError as exc:
        return _response(400, {"error": "validation_error", "message": str(exc)})
    except RequestAuthorizationError as exc:
        return _response(403, {"error": "forbidden", "message": str(exc)})
    except ProfileValidationError as exc:
        return _response(400, {"error": "validation_error", "message": str(exc)})
    except ProfileNotFoundError:
        return _response(404, {"error": "profile_not_found", "message": "Profile not found"})
    except RequestNotFoundError:
        return _response(404, {"error": "not_found", "message": "Request not found"})
    except InvalidStatusTransition as exc:
        return _response(409, {"error": "invalid_status_transition", "message": str(exc)})
    except VolunteerNotFoundError:
        return _response(404, {"error": "volunteer_not_found", "message": "Volunteer not found"})
    except RequestStructuringFailure as exc:
        return _response(502, {"error": "request_structuring_failed", "message": str(exc)})
    except VolunteerRepositoryUnavailableError as exc:
        return _response(503, {"error": "volunteer_repository_unavailable", "message": str(exc)})
    except Exception:
        return _response(500, {"error": "internal_error", "message": "Unable to process this request"})


def _parse_body(body: Any) -> Any:
    if not isinstance(body, str):
        raise RequestValidationError("Request body must contain JSON")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RequestValidationError("Request body must contain valid JSON") from exc


def _principal_id(event: dict[str, Any]) -> str | None:
    """Read identity only from API Gateway's verified JWT authorizer context."""
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    claims = (authorizer.get("jwt") or {}).get("claims") or authorizer.get("claims") or {}
    subject = claims.get("sub") if isinstance(claims, dict) else None
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    # Explicit local-only identity support; never enabled by the AWS Lambda config.
    if os.environ.get("RELAY_LOCAL_AUTH", "false").lower() == "true" and os.environ.get("RELAY_STORAGE", "memory").lower() == "memory":
        headers = event.get("headers") or {}
        local_subject = next((value for key, value in headers.items() if key.lower() == "x-relay-local-sub"), None)
        if isinstance(local_subject, str) and local_subject and len(local_subject) <= 128:
            return local_subject
    return None


def _public_volunteer(volunteer: Any, is_self: bool = False) -> dict[str, Any]:
    """Serialize only fields intended for matching and public profile display."""
    return {
        "id": volunteer.id,
        "name": volunteer.name,
        "role": volunteer.role.value,
        "location": {"label": volunteer.location.get("label", "Location not shared") if is_self else "Approximate area shared"},
        "skills": volunteer.skills,
        "availability": volunteer.availability.value,
        "activeRequests": volunteer.activeRequests,
        "createdAt": volunteer.createdAt.isoformat().replace("+00:00", "Z") if volunteer.createdAt else None,
    }


def _public_request(request: Any, principal_id: str | None = None) -> dict[str, Any]:
    """Never return private coordinates or the account subject from a request."""
    result = request.to_dict()
    is_requester = bool(request.requesterId and request.requesterId == principal_id)
    result["location"] = {
        "label": request.location.get("label", "Location not shared") if is_requester else "Approximate area shared"
    }
    result.pop("claimedBy", None)
    result["isRequester"] = is_requester
    result["isClaimedByYou"] = bool(request.claimedBy and request.claimedBy == principal_id)
    if not result["isRequester"]:
        # Keep user narratives, model summaries, labels, and exact location requester-only.
        public_summary = f"{request.category.title()} assistance requested."
        result["description"] = public_summary
        result["summary"] = public_summary
    return result

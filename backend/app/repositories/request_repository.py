"""Repository protocol and local in-memory implementation."""

from typing import Protocol

from app.models.request import AssistanceRequest


class RequestRepository(Protocol):
    """Persistence contract consumed by application services."""

    def create(self, request: AssistanceRequest) -> AssistanceRequest: ...

    def get(self, request_id: str) -> AssistanceRequest | None: ...

    def list(self) -> list[AssistanceRequest]: ...

    def update(self, request: AssistanceRequest) -> AssistanceRequest: ...


class InMemoryRequestRepository:
    """Process-local repository for development and tests."""

    def __init__(self) -> None:
        self._requests: dict[str, AssistanceRequest] = {}

    def create(self, request: AssistanceRequest) -> AssistanceRequest:
        if request.id in self._requests:
            raise ValueError(f"Request {request.id} already exists")
        self._requests[request.id] = request
        return request

    def get(self, request_id: str) -> AssistanceRequest | None:
        return self._requests.get(request_id)

    def list(self) -> list[AssistanceRequest]:
        return sorted(self._requests.values(), key=lambda item: item.createdAt, reverse=True)

    def update(self, request: AssistanceRequest) -> AssistanceRequest:
        if request.id not in self._requests:
            raise KeyError(request.id)
        self._requests[request.id] = request
        return request

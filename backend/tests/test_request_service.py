import unittest
from datetime import datetime, timezone

from app.models.request import RequestStatus
from app.repositories.request_repository import InMemoryRequestRepository
from app.repositories.volunteer_repository import InMemoryVolunteerRepository
from app.services.request_service import (
    InvalidStatusTransition,
    RequestNotFoundError,
    RequestService,
    RequestValidationError,
)


VALID_INPUT = {
    "description": "Please bring drinking water",
    "category": "water",
    "urgency": "high",
    "location": {"label": "Block C", "latitude": 17.4, "longitude": 78.4},
    "peopleAffected": 2,
}


class RequestServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryRequestRepository()
        self.service = RequestService(
            self.repository,
            id_factory=lambda: "request-123",
            clock=lambda: datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            volunteer_repository=InMemoryVolunteerRepository(),
        )

    def test_validation_accepts_valid_input_and_trims_fields(self):
        result = self.service.validate({**VALID_INPUT, "description": "  Need water  ", "location": {"label": " Block C "}})
        self.assertEqual(result["description"], "Need water")
        self.assertEqual(result["location"], {"label": "Block C"})

    def test_validation_rejects_missing_description(self):
        payload = {**VALID_INPUT, "description": " "}
        with self.assertRaisesRegex(RequestValidationError, "description is required"):
            self.service.validate(payload)

    def test_validation_rejects_unknown_category_and_urgency(self):
        for field, value in (("category", "housing"), ("urgency", "critical")):
            with self.subTest(field=field), self.assertRaises(RequestValidationError):
                self.service.validate({**VALID_INPUT, field: value})

    def test_validation_rejects_invalid_location_and_people_count(self):
        cases = [
            {**VALID_INPUT, "location": {"label": "Block C", "latitude": 95}},
            {**VALID_INPUT, "peopleAffected": True},
            {**VALID_INPUT, "peopleAffected": 0},
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(RequestValidationError):
                self.service.validate(payload)

    def test_creation_generates_id_timestamp_and_requested_status(self):
        request = self.service.create_request(VALID_INPUT)
        self.assertEqual(request.id, "request-123")
        self.assertEqual(request.status, RequestStatus.REQUESTED)
        self.assertEqual(request.createdAt.isoformat(), "2026-01-02T03:04:05+00:00")
        self.assertEqual(self.repository.get(request.id), request)

    def test_status_transitions_follow_lifecycle(self):
        request = self.service.create_request(VALID_INPUT)
        self.service.claim_request(request.id, "volunteer-a")
        for status in ("IN_PROGRESS", "RESOLVED"):
            request = self.service.update_status(request.id, status)
            self.assertEqual(request.status.value, status)

    def test_status_transition_cannot_skip_a_step_or_reopen(self):
        request = self.service.create_request(VALID_INPUT)
        with self.assertRaises(InvalidStatusTransition):
            self.service.update_status(request.id, "IN_PROGRESS")
        with self.assertRaises(InvalidStatusTransition):
            self.service.update_status(request.id, "CLAIMED")
        with self.assertRaises(InvalidStatusTransition):
            self.service.update_status(request.id, "RESOLVED")

    def test_unknown_request_raises_not_found(self):
        with self.assertRaises(RequestNotFoundError):
            self.service.get_request("missing")


class InMemoryRepositoryTests(unittest.TestCase):
    def test_create_get_list_and_update(self):
        repository = InMemoryRequestRepository()
        service = RequestService(repository)
        created = service.create_request(VALID_INPUT)
        self.assertEqual(repository.get(created.id).id, created.id)
        self.assertEqual([item.id for item in repository.list()], [created.id])
        created.status = RequestStatus.CLAIMED
        repository.update(created)
        self.assertEqual(repository.get(created.id).status, RequestStatus.CLAIMED)

    def test_update_missing_item_raises_key_error(self):
        repository = InMemoryRequestRepository()
        service = RequestService(repository)
        request = service.create_request(VALID_INPUT)
        repository._requests.clear()
        with self.assertRaises(KeyError):
            repository.update(request)


if __name__ == "__main__":
    unittest.main()

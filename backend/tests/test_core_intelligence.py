import unittest
from datetime import datetime, timezone

from app.models.request import AssistanceRequest, RequestStatus
from app.models.user import Availability, User, UserRole
from app.repositories.request_repository import InMemoryRequestRepository
from app.repositories.volunteer_repository import InMemoryVolunteerRepository
from app.services.matching_service import MatchingService
from app.services.request_service import (
    InvalidStatusTransition,
    RequestAlreadyClaimedError,
    RequestService,
    VolunteerUnavailableError,
)
from app.services.request_structuring_service import (
    BedrockRequestStructuringService,
    LocalRequestStructuringService,
    RequestStructuringError,
    validate_structured_output,
)


class RequestStructuringTests(unittest.TestCase):
    def test_local_rules_structure_pharmacy_need(self):
        result = LocalRequestStructuringService().structure({
            "description": "My elderly parents need someone to pick up their prescription from the pharmacy."
        })
        self.assertEqual(result.category, "pharmacy")
        self.assertEqual(result.urgency, "high")
        self.assertEqual(result.peopleAffected, 2)
        self.assertEqual(result.requiredSkills, ["pharmacy_pickup", "mobility_assistance"])
        self.assertEqual(result.mobilityNeeds, "limited")
        self.assertEqual(result.summary, "Pharmacy pickup needed for two elderly people.")

    def test_invalid_category_and_skill_rejected(self):
        good = {
            "category": "water", "urgency": "normal", "peopleAffected": 1,
            "requiredSkills": ["water_delivery"], "mobilityNeeds": "none", "summary": "Water delivery needed.",
        }
        for field, value in (("category", "emergency"), ("requiredSkills", ["admin_override"])):
            with self.subTest(field=field), self.assertRaises(RequestStructuringError):
                validate_structured_output({**good, field: value})

    def test_bedrock_response_parsing_validates_tool_schema_boundary(self):
        response = {"output": {"message": {"content": [{"toolUse": {
            "name": "structure_assistance_request",
            "input": {
                "category": "pharmacy", "urgency": "high", "peopleAffected": 2,
                "requiredSkills": ["pharmacy_pickup"], "mobilityNeeds": "limited",
                "summary": "Pharmacy pickup needed for two people.",
            },
        }}]}}}
        parsed = BedrockRequestStructuringService.parse_response(response)
        self.assertEqual(parsed.category, "pharmacy")

        response["output"]["message"]["content"][0]["toolUse"]["input"]["category"] = "medical_emergency"
        with self.assertRaises(RequestStructuringError):
            BedrockRequestStructuringService.parse_response(response)

    def test_bedrock_service_sends_forced_tool_schema_without_real_call(self):
        class FakeClient:
            def __init__(self):
                self.kwargs = None

            def converse(self, **kwargs):
                self.kwargs = kwargs
                return {"output": {"message": {"content": [{"toolUse": {
                    "name": "structure_assistance_request",
                    "input": {
                        "category": "other", "urgency": "normal", "peopleAffected": 1,
                        "requiredSkills": ["general_help"], "mobilityNeeds": "none", "summary": "General help needed.",
                    },
                }}]}}}

        client = FakeClient()
        service = BedrockRequestStructuringService(client=client, model_id="configured-test-model")
        result = service.structure("Need help with a small task")
        self.assertEqual(result.category, "other")
        self.assertEqual(client.kwargs["modelId"], "configured-test-model")
        self.assertEqual(client.kwargs["toolConfig"]["toolChoice"], {"tool": {"name": service.TOOL_NAME}})


def volunteer(
    volunteer_id, *, skills=(), latitude=0, longitude=0, availability=Availability.AVAILABLE, active=0
):
    return User(
        id=volunteer_id,
        name=volunteer_id.title(),
        role=UserRole.VOLUNTEER,
        location={"label": "Neighborhood", "latitude": latitude, "longitude": longitude},
        skills=list(skills),
        availability=availability,
        activeRequests=active,
    )


def structured_request(urgency="normal", skills=None, location=None):
    return AssistanceRequest(
        id="request-1", description="Need help", category="other", urgency=urgency,
        location=location or {"label": "Neighborhood", "latitude": 0, "longitude": 0},
        peopleAffected=1, status=RequestStatus.REQUESTED, createdAt=datetime.now(timezone.utc),
        summary="Help needed", requiredSkills=skills or ["general_help"], mobilityNeeds="none", isStructured=True,
    )


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.matcher = MatchingService()

    def test_skill_matching_awards_weighted_points(self):
        result = self.matcher.match(structured_request(skills=["pharmacy_pickup", "general_help"]), [
            volunteer("both", skills=["pharmacy_pickup", "general_help"]),
            volunteer("one", skills=["pharmacy_pickup"]),
        ])
        self.assertEqual(result[0]["scoreBreakdown"]["skillMatch"], 40)
        self.assertEqual(result[1]["scoreBreakdown"]["skillMatch"], 20)

    def test_busy_and_offline_volunteers_are_not_returned(self):
        result = self.matcher.match(structured_request(), [
            volunteer("available", skills=["general_help"]),
            volunteer("busy", skills=["general_help"], availability=Availability.BUSY),
            volunteer("offline", skills=["general_help"], availability=Availability.OFFLINE),
        ])
        self.assertEqual([item["volunteerId"] for item in result], ["available"])

    def test_proximity_uses_haversine_distance_and_points(self):
        result = self.matcher.match(structured_request(), [
            volunteer("near", skills=["general_help"], longitude=0.005),
            volunteer("far", skills=["general_help"], longitude=0.05),
        ])
        by_id = {item["volunteerId"]: item for item in result}
        self.assertGreater(by_id["near"]["distanceKm"], 0)
        self.assertGreater(by_id["near"]["scoreBreakdown"]["proximity"], by_id["far"]["scoreBreakdown"]["proximity"])
        self.assertTrue(any("Approximately" in reason for reason in by_id["near"]["reasons"]))

    def test_missing_coordinates_do_not_claim_distance(self):
        result = self.matcher.match(
            structured_request(location={"label": "Block C"}),
            [volunteer("near", skills=["general_help"])],
        )[0]
        self.assertIsNone(result["distanceKm"])
        self.assertEqual(result["scoreBreakdown"]["proximity"], 0)
        self.assertTrue(any("Distance unavailable" in reason for reason in result["reasons"]))

    def test_workload_scoring(self):
        result = self.matcher.match(structured_request(), [
            volunteer("free", skills=["general_help"], active=0),
            volunteer("loaded", skills=["general_help"], active=3),
        ])
        by_id = {item["volunteerId"]: item for item in result}
        self.assertEqual(by_id["free"]["scoreBreakdown"]["workload"], 10)
        self.assertEqual(by_id["loaded"]["scoreBreakdown"]["workload"], 4)

    def test_urgency_suitability_points(self):
        candidates = [volunteer("one-active", skills=["general_help"], active=1)]
        normal = self.matcher.match(structured_request("normal"), candidates)[0]
        urgent = self.matcher.match(structured_request("urgent"), candidates)[0]
        self.assertEqual(normal["scoreBreakdown"]["urgencySuitability"], 5)
        self.assertEqual(urgent["scoreBreakdown"]["urgencySuitability"], 3)

    def test_match_results_sort_by_highest_score(self):
        result = self.matcher.match(structured_request(skills=["pharmacy_pickup"]), [
            volunteer("far-general", skills=["general_help"], longitude=0.05),
            volunteer("near-pharmacy", skills=["pharmacy_pickup"], longitude=0.002),
        ])
        self.assertEqual(result[0]["volunteerId"], "near-pharmacy")
        self.assertGreaterEqual(result[0]["score"], result[1]["score"])


class ClaimWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.requests = InMemoryRequestRepository()
        self.volunteers = InMemoryVolunteerRepository([
            volunteer("ready", skills=["general_help"]),
            volunteer("away", skills=["general_help"], availability=Availability.OFFLINE),
        ])
        self.service = RequestService(
            self.requests,
            id_factory=lambda: "claimable",
            structuring_service=LocalRequestStructuringService(),
            volunteer_repository=self.volunteers,
        )
        self.request = self.service.create_request({
            "description": "Need a hand",
            "category": "other",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
        })

    def test_claim_success_updates_request_and_volunteer(self):
        claimed = self.service.claim_request(self.request.id, "ready")
        volunteer_record = self.volunteers.get("ready")
        self.assertEqual(claimed.status, RequestStatus.CLAIMED)
        self.assertEqual(claimed.claimedBy, "ready")
        self.assertEqual(volunteer_record.activeRequests, 1)
        self.assertEqual(volunteer_record.availability, Availability.BUSY)

    def test_duplicate_claim_rejected(self):
        self.service.claim_request(self.request.id, "ready")
        with self.assertRaises(RequestAlreadyClaimedError):
            self.service.claim_request(self.request.id, "ready")

    def test_unavailable_volunteer_cannot_claim(self):
        with self.assertRaises(VolunteerUnavailableError):
            self.service.claim_request(self.request.id, "away")

    def test_invalid_status_transition_rejected_and_completion_releases_volunteer(self):
        with self.assertRaises(InvalidStatusTransition):
            self.service.update_status(self.request.id, "IN_PROGRESS")
        self.service.claim_request(self.request.id, "ready")
        self.service.update_status(self.request.id, "IN_PROGRESS")
        resolved = self.service.update_status(self.request.id, "RESOLVED")
        self.assertEqual(resolved.status, RequestStatus.RESOLVED)
        self.assertIsNotNone(resolved.resolvedAt)
        self.assertEqual(self.volunteers.get("ready").activeRequests, 0)
        self.assertEqual(self.volunteers.get("ready").availability, Availability.AVAILABLE)

    def test_resolved_request_cannot_be_claimed(self):
        self.service.claim_request(self.request.id, "ready")
        self.service.update_status(self.request.id, "IN_PROGRESS")
        self.service.update_status(self.request.id, "RESOLVED")
        with self.assertRaises(InvalidStatusTransition):
            self.service.claim_request(self.request.id, "ready")


if __name__ == "__main__":
    unittest.main()

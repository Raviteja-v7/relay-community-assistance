import json
import os
import unittest
from unittest.mock import patch

from app.api.handler import handler, set_service, set_profile_service, set_trust_repository, get_trust_repository
from app.repositories.request_repository import InMemoryRequestRepository
from app.repositories.volunteer_repository import InMemoryVolunteerRepository
from app.services.request_service import RequestService
from app.services.request_structuring_service import LocalRequestStructuringService
from app.repositories.profile_repository import InMemoryProfileRepository
from app.services.profile_service import ProfileService
from app.repositories.trust_repository import InMemoryTrustRepository


class RequestApiTests(unittest.TestCase):
    def setUp(self):
        service = RequestService(
            InMemoryRequestRepository(),
            id_factory=lambda: "api-request-1",
            structuring_service=LocalRequestStructuringService(),
            volunteer_repository=InMemoryVolunteerRepository(),
        )
        set_service(service)
        set_profile_service(ProfileService(InMemoryProfileRepository(), service.volunteer_repository))
        set_trust_repository(InMemoryTrustRepository())

    def tearDown(self):
        set_service(None)

    @staticmethod
    def call(method, path, body=None, principal="test-requester"):
        return handler({
            "httpMethod": method,
            "path": path,
            "body": json.dumps(body) if body is not None else None,
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": principal}}}},
        })

    def test_health(self):
        result = self.call("GET", "/health")
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"]), {"status": "ok"})

    def test_create_list_detail_and_status_workflow(self):
        payload = {
            "description": "Need help carrying water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 2,
        }
        created = self.call("POST", "/requests", payload)
        self.assertEqual(created["statusCode"], 201)
        request = json.loads(created["body"])
        self.assertEqual(request["status"], "REQUESTED")
        self.assertTrue(request["createdAt"].endswith("Z"))
        self.assertNotIn("latitude", request["location"])
        self.assertNotIn("longitude", request["location"])

        listed = self.call("GET", "/requests")
        self.assertEqual(json.loads(listed["body"])["requests"][0]["id"], request["id"])
        detail = self.call("GET", f"/requests/{request['id']}")
        self.assertEqual(json.loads(detail["body"])["id"], request["id"])
        self.assertNotIn("latitude", json.loads(detail["body"])["location"])
        claimed = self.call("POST", f"/requests/{request['id']}/claim", {"volunteerId": "somebody-else"}, "volunteer-a")
        self.assertEqual(json.loads(claimed["body"])["status"], "CLAIMED")
        from app.api.handler import get_service
        self.assertEqual(get_service().get_request(request["id"]).claimedBy, "volunteer-a")
        patched = self.call("PATCH", f"/requests/{request['id']}/status", {"status": "IN_PROGRESS"}, "volunteer-a")
        self.assertEqual(json.loads(patched["body"])["status"], "IN_PROGRESS")

    def test_structure_and_match_endpoints(self):
        structured = self.call("POST", "/requests/structure", {
            "description": "My elderly parents need a prescription pickup from the pharmacy",
        })
        self.assertEqual(structured["statusCode"], 200)
        self.assertEqual(json.loads(structured["body"])["category"], "pharmacy")

        created = self.call("POST", "/requests", {
            "description": "My elderly parents need a prescription pickup from the pharmacy",
            "category": "pharmacy",
            "urgency": "high",
            "location": {"label": "Block C", "latitude": 17.4, "longitude": 78.4},
            "peopleAffected": 2,
            **json.loads(structured["body"]),
        })
        request_id = json.loads(created["body"])["id"]
        matches = self.call("POST", f"/requests/{request_id}/matches", {})
        body = json.loads(matches["body"])
        self.assertEqual(matches["statusCode"], 200)
        self.assertEqual(body["matches"][0]["volunteerId"], "volunteer-a")
        self.assertEqual(body["matches"][0]["availability"], "AVAILABLE")
        self.assertIn("scoreBreakdown", body["matches"][0])
        self.assertTrue(body["matches"][0]["reasons"])

    def test_duplicate_claim_returns_conflict(self):
        self.call("POST", "/requests", {
            "description": "Need water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
        })
        self.call("POST", "/requests/api-request-1/claim", {"volunteerId": "volunteer-a"}, "volunteer-a")
        duplicate = self.call("POST", "/requests/api-request-1/claim", {"volunteerId": "volunteer-b"}, "volunteer-b")
        self.assertEqual(duplicate["statusCode"], 409)

    def test_missing_principal_is_rejected_but_health_is_public(self):
        private = handler({"httpMethod": "GET", "path": "/requests"})
        self.assertEqual(private["statusCode"], 401)
        self.assertEqual(self.call("GET", "/health").get("statusCode"), 200)

    def test_local_identity_header_is_disabled_outside_memory_mode(self):
        from app.api.handler import _principal_id
        event = {"headers": {"x-relay-local-sub": "forged-sub"}}
        with patch.dict(os.environ, {"RELAY_LOCAL_AUTH": "true", "RELAY_STORAGE": "memory"}):
            self.assertEqual(_principal_id(event), "forged-sub")
        with patch.dict(os.environ, {"RELAY_LOCAL_AUTH": "true", "RELAY_STORAGE": "dynamodb"}):
            self.assertIsNone(_principal_id(event))

    def test_requester_cannot_claim_own_request(self):
        self.call("POST", "/requests", {
            "description": "Need help",
            "category": "other",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
        }, "volunteer-a")
        claim = self.call("POST", "/requests/api-request-1/claim", {}, "volunteer-a")
        self.assertEqual(claim["statusCode"], 403)

    def test_requester_id_from_body_is_ignored_and_not_returned(self):
        created = self.call("POST", "/requests", {
            "description": "Need water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
            "requesterId": "forged-user",
        }, "real-subject")
        self.assertEqual(created["statusCode"], 201)
        body = json.loads(created["body"])
        self.assertNotIn("requesterId", body)
        from app.api.handler import get_service
        self.assertEqual(get_service().get_request(body["id"]).requesterId, "real-subject")

    def test_request_coordinates_are_rounded_in_storage_and_redacted_from_lists(self):
        created = self.call("POST", "/requests", {
            "description": "Need water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "North neighborhood", "latitude": 17.40049, "longitude": 78.40049},
            "peopleAffected": 1,
        })
        from app.api.handler import get_service
        stored = get_service().get_request(json.loads(created["body"])["id"])
        self.assertEqual(stored.location["latitude"], 17.4)
        self.assertEqual(stored.location["longitude"], 78.4)
        listed = json.loads(self.call("GET", "/requests")["body"])["requests"][0]
        self.assertEqual(listed["location"], {"label": "North neighborhood"})
        other_view = json.loads(self.call("GET", "/requests", principal="neighbor-sub")["body"])["requests"][0]
        self.assertEqual(other_view["location"], {"label": "Approximate area shared"})
        self.assertNotEqual(other_view["description"], stored.description)

    def test_only_claiming_principal_can_update_status(self):
        self.call("POST", "/requests", {
            "description": "Need water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
        })
        self.call("POST", "/requests/api-request-1/claim", {}, "volunteer-a")
        denied = self.call("PATCH", "/requests/api-request-1/status", {"status": "IN_PROGRESS"}, "volunteer-b")
        self.assertEqual(denied["statusCode"], 403)
        allowed = self.call("PATCH", "/requests/api-request-1/status", {"status": "IN_PROGRESS"}, "volunteer-a")
        self.assertEqual(allowed["statusCode"], 200)

    def test_profile_and_volunteer_profile_are_owned_by_authenticated_subject(self):
        saved = self.call("PUT", "/me", {"name": "Sam Neighbor", "roles": ["REQUESTER", "VOLUNTEER"], "id": "forged"}, "account-sub")
        profile = json.loads(saved["body"])
        self.assertEqual(profile["id"], "account-sub")
        self.assertEqual(profile["name"], "Sam Neighbor")
        self.assertNotIn("forged", profile.values())
        volunteer = self.call("PUT", "/me/volunteer", {
            "location": {"label": "Oakwood", "latitude": 17.40049, "longitude": 78.40049},
            "skills": ["general_help"],
            "availability": "AVAILABLE",
            "id": "other-account",
        }, "account-sub")
        volunteer_body = json.loads(volunteer["body"])
        self.assertEqual(volunteer_body["id"], "account-sub")
        self.assertNotIn("latitude", volunteer_body["location"])
        from app.api.handler import get_profile_service
        stored_volunteer = get_profile_service().volunteers.get("account-sub")
        self.assertEqual(stored_volunteer.location["latitude"], 17.4)
        stored = self.call("GET", "/volunteers")
        public_volunteer = next(item for item in json.loads(stored["body"])["volunteers"] if item["id"] == "account-sub")
        self.assertNotIn("latitude", public_volunteer["location"])
        self.assertEqual(public_volunteer["location"]["label"], "Approximate area shared")

    def test_volunteer_profile_requires_volunteer_role(self):
        self.call("PUT", "/me", {"name": "Requester", "roles": ["REQUESTER"]}, "requester-sub")
        result = self.call("PUT", "/me/volunteer", {"skills": [], "availability": "OFFLINE"}, "requester-sub")
        self.assertEqual(result["statusCode"], 400)

    def test_two_sided_completion_requires_volunteer_then_requester_confirmation(self):
        self.call("POST", "/requests", {
            "description": "Need water",
            "category": "water",
            "urgency": "normal",
            "location": {"label": "Block C"},
            "peopleAffected": 1,
        }, "requester-sub")
        self.call("POST", "/requests/api-request-1/claim", {}, "volunteer-a")
        self.call("PATCH", "/requests/api-request-1/status", {"status": "IN_PROGRESS"}, "volunteer-a")
        too_early = self.call("POST", "/requests/api-request-1/confirm", {}, "requester-sub")
        self.assertEqual(too_early["statusCode"], 409)
        done = self.call("PATCH", "/requests/api-request-1/status", {"status": "VOLUNTEER_COMPLETED"}, "volunteer-a")
        self.assertEqual(json.loads(done["body"])["status"], "VOLUNTEER_COMPLETED")
        wrong_requester = self.call("POST", "/requests/api-request-1/confirm", {}, "another-sub")
        self.assertEqual(wrong_requester["statusCode"], 403)
        confirmed = self.call("POST", "/requests/api-request-1/confirm", {}, "requester-sub")
        body = json.loads(confirmed["body"])
        self.assertEqual(body["status"], "RESOLVED")
        self.assertEqual(body["statusHistory"][-2:], ["REQUESTER_CONFIRMED", "RESOLVED"])

    def test_block_controls_matching_and_report_is_persisted(self):
        self.call("PUT", "/me", {"name": "Requester", "roles": ["REQUESTER"]}, "requester-sub")
        self.call("POST", "/requests", {
            "description": "My parent needs a pharmacy pickup",
            "category": "pharmacy",
            "urgency": "high",
            "location": {"label": "Block C", "latitude": 17.4, "longitude": 78.4},
            "peopleAffected": 1,
            "requiredSkills": ["pharmacy_pickup"],
            "mobilityNeeds": "unknown",
            "summary": "Pharmacy pickup",
        }, "requester-sub")
        matches = self.call("POST", "/requests/api-request-1/matches", {}, "requester-sub")
        self.assertTrue(json.loads(matches["body"])["matches"])
        first_volunteer = json.loads(matches["body"])["matches"][0]["volunteerId"]
        self.call("POST", f"/users/{first_volunteer}/block", {}, "requester-sub")
        filtered = self.call("POST", "/requests/api-request-1/matches", {}, "requester-sub")
        self.assertNotIn(first_volunteer, [item["volunteerId"] for item in json.loads(filtered["body"])["matches"]])
        remaining = json.loads(filtered["body"])["matches"]
        if remaining:
            get_trust_repository().block(remaining[0]["volunteerId"], "requester-sub")
            filtered_reverse = self.call("POST", "/requests/api-request-1/matches", {}, "requester-sub")
            self.assertNotIn(remaining[0]["volunteerId"], [item["volunteerId"] for item in json.loads(filtered_reverse["body"])["matches"]])
        report = self.call("POST", "/reports", {
            "targetType": "REQUEST", "targetId": "api-request-1",
            "reason": "safety_concern", "details": "Please review this post",
        }, "requester-sub")
        self.assertEqual(report["statusCode"], 201)
        self.assertTrue(json.loads(report["body"])["id"])
        self.assertEqual(self.call("GET", "/me/blocks", principal="requester-sub")["statusCode"], 200)

    def test_invalid_create_returns_bad_request(self):
        result = self.call("POST", "/requests", {"description": "Missing required fields"})
        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(json.loads(result["body"])["error"], "validation_error")

    def test_missing_request_returns_not_found(self):
        result = self.call("GET", "/requests/no-such-request")
        self.assertEqual(result["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()

"""Transparent volunteer scoring with straight-line Haversine proximity."""

import math
from typing import Any, Iterable

from app.models.user import Availability, User, UserRole


class MatchingService:
    """Rank available volunteers using a documented, deterministic score."""

    def match(self, request: Any, volunteers: Iterable[User]) -> list[dict[str, Any]]:
        results = []
        required_skills = list(getattr(request, "requiredSkills", []) or [])
        for volunteer in volunteers:
            if volunteer.role != UserRole.VOLUNTEER or volunteer.availability != Availability.AVAILABLE:
                continue

            skill_matches = sorted(set(required_skills).intersection(volunteer.skills))
            skill_score = round(40 * len(skill_matches) / len(required_skills)) if required_skills else 20
            distance = self.haversine_km(request.location, volunteer.location)
            proximity_score = self._proximity_points(distance)
            workload_score = max(0, 10 - 2 * max(0, volunteer.activeRequests))
            urgency_score, urgency_reason = self._urgency_points(request.urgency, volunteer.activeRequests)
            availability_score = 20
            total = skill_score + availability_score + proximity_score + workload_score + urgency_score

            reasons = []
            if skill_matches:
                reasons.extend(f"Has the required {skill.replace('_', ' ')} skill" for skill in skill_matches)
            else:
                reasons.append("No specific required skill matched")
            reasons.append("Available now")
            if distance is None:
                reasons.append("Distance unavailable because coordinates are not provided")
            else:
                reasons.append(f"Approximately {distance:.1f} km away")
            reasons.append("No active requests" if volunteer.activeRequests == 0 else f"{volunteer.activeRequests} active request(s)")
            reasons.append(urgency_reason)

            results.append({
                "volunteerId": volunteer.id,
                "name": volunteer.name,
                "availability": volunteer.availability.value,
                "score": total,
                "reasons": reasons,
                "distanceKm": round(distance, 2) if distance is not None else None,
                "scoreBreakdown": {
                    "skillMatch": skill_score,
                    "availability": availability_score,
                    "proximity": proximity_score,
                    "workload": workload_score,
                    "urgencySuitability": urgency_score,
                },
            })

        return sorted(
            results,
            key=lambda item: (
                -item["score"],
                item["distanceKm"] if item["distanceKm"] is not None else float("inf"),
                item["name"].casefold(),
                item["volunteerId"],
            ),
        )

    @staticmethod
    def haversine_km(origin: dict[str, Any], destination: dict[str, Any]) -> float | None:
        keys = ("latitude", "longitude")
        if any(key not in origin or key not in destination for key in keys):
            return None
        values = [origin[key] for key in keys] + [destination[key] for key in keys]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
            return None
        latitude_a, longitude_a, latitude_b, longitude_b = map(math.radians, values)
        delta_latitude = latitude_b - latitude_a
        delta_longitude = longitude_b - longitude_a
        haversine = (
            math.sin(delta_latitude / 2) ** 2
            + math.cos(latitude_a) * math.cos(latitude_b) * math.sin(delta_longitude / 2) ** 2
        )
        haversine = min(1.0, max(0.0, haversine))
        angle = 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))
        return 6371.0088 * angle

    @staticmethod
    def _proximity_points(distance_km: float | None) -> int:
        if distance_km is None:
            return 0
        if distance_km <= 1:
            return 25
        if distance_km <= 5:
            return 20
        if distance_km <= 10:
            return 15
        if distance_km <= 25:
            return 8
        return 0

    @staticmethod
    def _urgency_points(urgency: str, active_requests: int) -> tuple[int, str]:
        workload = max(0, active_requests)
        if urgency == "urgent":
            points = 5 if workload == 0 else 3 if workload == 1 else 0
            return points, "Urgent requests favor volunteers with very low workload"
        if urgency == "high":
            points = 5 if workload <= 1 else 3 if workload <= 3 else 0
            return points, "High urgency is balanced against current workload"
        return 5, "Workload is suitable for a normal urgency request"

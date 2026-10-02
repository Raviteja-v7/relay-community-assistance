"""Authenticated account profile persistence."""

import os
from datetime import datetime, timezone
from typing import Protocol

from app.models.profile import CommunityProfile


class ProfileRepository(Protocol):
    def get(self, subject: str) -> CommunityProfile | None: ...
    def save(self, profile: CommunityProfile) -> CommunityProfile: ...


class InMemoryProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, CommunityProfile] = {}

    def get(self, subject: str) -> CommunityProfile | None:
        return self._profiles.get(subject)

    def save(self, profile: CommunityProfile) -> CommunityProfile:
        self._profiles[profile.id] = profile
        return profile


class DynamoDBProfileRepository:
    def __init__(self, table_name: str | None = None, region_name: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install backend dependencies to use DynamoDB storage") from exc
        resolved = table_name or os.environ.get("RELAY_REQUESTS_TABLE")
        if not resolved:
            raise RuntimeError("RELAY_REQUESTS_TABLE must be set for DynamoDB storage")
        self._table = boto3.resource("dynamodb", region_name=region_name or os.environ.get("AWS_REGION")).Table(resolved)

    def get(self, subject: str) -> CommunityProfile | None:
        item = self._table.get_item(Key={"PK": f"USER#{subject}"}).get("Item")
        if not item:
            return None
        item.pop("PK", None)
        return CommunityProfile.from_dict(item)

    def save(self, profile: CommunityProfile) -> CommunityProfile:
        existing = self.get(profile.id)
        if existing:
            profile.createdAt = existing.createdAt
        elif profile.createdAt is None:
            profile.createdAt = datetime.now(timezone.utc)
        self._table.put_item(
            Item={"PK": f"USER#{profile.id}", **profile.to_dict()},
        )
        return profile

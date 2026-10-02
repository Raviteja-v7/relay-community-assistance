"""DynamoDB adapter for demo volunteer data, sharing the single Relay table."""

import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.user import Availability, User, UserRole


class DynamoDBVolunteerRepository:
    """Persist the deterministic demo roster so Lambda instances share claims."""

    def __init__(self, table_name: str | None = None, region_name: str | None = None) -> None:
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr
        except ImportError as exc:
            raise RuntimeError("Install backend dependencies to use DynamoDB storage") from exc

        resolved_table = table_name or os.environ.get("RELAY_REQUESTS_TABLE")
        if not resolved_table:
            raise RuntimeError("RELAY_REQUESTS_TABLE must be set for DynamoDB storage")
        self._table = boto3.resource(
            "dynamodb", region_name=region_name or os.environ.get("AWS_REGION")
        ).Table(resolved_table)
        self._attr = Attr

    @staticmethod
    def _normalize(value: Any) -> Any:
        if isinstance(value, float):
            return Decimal(str(value))
        if isinstance(value, list):
            return [DynamoDBVolunteerRepository._normalize(entry) for entry in value]
        if isinstance(value, dict):
            return {key: DynamoDBVolunteerRepository._normalize(entry) for key, entry in value.items()}
        return value

    @staticmethod
    def _user(item: dict[str, Any]) -> User:
        def normalize(value: Any) -> Any:
            if isinstance(value, Decimal):
                return int(value) if value == value.to_integral_value() else float(value)
            if isinstance(value, list):
                return [normalize(entry) for entry in value]
            if isinstance(value, dict):
                return {key: normalize(entry) for key, entry in value.items()}
            return value

        data = normalize({key: value for key, value in item.items() if key != "PK"})
        created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")) if data.get("createdAt") else None
        return User(
            id=data["id"],
            name=data["name"],
            role=UserRole(data["role"]),
            location=data["location"],
            skills=data.get("skills", []),
            availability=Availability(data["availability"]),
            activeRequests=int(data.get("activeRequests", 0)),
            createdAt=created_at,
        )

    def get(self, volunteer_id: str) -> User | None:
        result = self._table.get_item(Key={"PK": f"VOLUNTEER#{volunteer_id}"})
        item = result.get("Item")
        return self._user(item) if item else None

    def list(self) -> list[User]:
        paginator = self._table.meta.client.get_paginator("scan")
        items = [
            item
            for page in paginator.paginate(
                TableName=self._table.name,
                FilterExpression=self._attr("PK").begins_with("VOLUNTEER#"),
            )
            for item in page.get("Items", [])
        ]
        return sorted((self._user(item) for item in items), key=lambda item: item.id)

    def update(self, volunteer: User) -> User:
        self._table.put_item(
            Item={"PK": f"VOLUNTEER#{volunteer.id}", **self._normalize(volunteer.to_dict())},
            ConditionExpression=self._attr("PK").exists(),
        )
        return volunteer

    def save(self, volunteer: User) -> User:
        self._table.put_item(
            Item={"PK": f"VOLUNTEER#{volunteer.id}", **self._normalize(volunteer.to_dict())},
        )
        return volunteer

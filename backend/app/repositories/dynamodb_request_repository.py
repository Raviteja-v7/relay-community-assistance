"""DynamoDB adapter for the request repository protocol.

Each request is stored as one item in a single table, keyed by PK. The adapter
does not assume DynamoDB geospatial query support; location matching remains an
application concern. Future GSIs can be added without changing the service API.
"""

import os
from decimal import Decimal
from typing import Any

from app.models.request import AssistanceRequest


class DynamoDBRequestRepository:
    def __init__(self, table_name: str | None = None, region_name: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install backend dependencies to use DynamoDB storage") from exc

        resolved_table = table_name or os.environ.get("RELAY_REQUESTS_TABLE")
        if not resolved_table:
            raise RuntimeError("RELAY_REQUESTS_TABLE must be set for DynamoDB storage")
        self._table = boto3.resource(
            "dynamodb", region_name=region_name or os.environ.get("AWS_REGION")
        ).Table(resolved_table)

    @staticmethod
    def _item(request: AssistanceRequest) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, float):
                return Decimal(str(value))
            if isinstance(value, list):
                return [normalize(entry) for entry in value]
            if isinstance(value, dict):
                return {key: normalize(entry) for key, entry in value.items()}
            return value

        return normalize({"PK": f"REQUEST#{request.id}", **request.to_dict(include_private=True)})

    @staticmethod
    def _request(item: dict[str, Any]) -> AssistanceRequest:
        def normalize(value: Any) -> Any:
            if isinstance(value, Decimal):
                return int(value) if value == value.to_integral_value() else float(value)
            if isinstance(value, list):
                return [normalize(entry) for entry in value]
            if isinstance(value, dict):
                return {key: normalize(entry) for key, entry in value.items()}
            return value

        data = normalize({key: value for key, value in item.items() if key != "PK"})
        return AssistanceRequest.from_dict(data)

    def create(self, request: AssistanceRequest) -> AssistanceRequest:
        from boto3.dynamodb.conditions import Attr

        self._table.put_item(
            Item=self._item(request),
            ConditionExpression=Attr("PK").not_exists(),
        )
        return request

    def get(self, request_id: str) -> AssistanceRequest | None:
        result = self._table.get_item(Key={"PK": f"REQUEST#{request_id}"})
        item = result.get("Item")
        return self._request(item) if item else None

    def list(self) -> list[AssistanceRequest]:
        from boto3.dynamodb.conditions import Attr

        paginator = self._table.meta.client.get_paginator("scan")
        items = [
            item
            for page in paginator.paginate(
                TableName=self._table.name,
                FilterExpression=Attr("PK").begins_with("REQUEST#"),
            )
            for item in page.get("Items", [])
        ]
        requests = [self._request(item) for item in items]
        return sorted(requests, key=lambda item: item.createdAt, reverse=True)

    def update(self, request: AssistanceRequest) -> AssistanceRequest:
        from boto3.dynamodb.conditions import Attr

        self._table.put_item(
            Item=self._item(request),
            ConditionExpression=Attr("PK").exists(),
        )
        return request

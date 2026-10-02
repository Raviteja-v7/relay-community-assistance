"""Persistence for user blocks and safety reports."""

import os
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4


class TrustRepository(Protocol):
    def block(self, blocker: str, blocked: str) -> None: ...
    def unblock(self, blocker: str, blocked: str) -> None: ...
    def blocked_users(self, blocker: str) -> set[str]: ...
    def is_blocked_either_way(self, first: str, second: str) -> bool: ...
    def report(self, reporter: str, target_type: str, target_id: str, reason: str, details: str) -> dict: ...


class InMemoryTrustRepository:
    def __init__(self) -> None:
        self.blocks: set[tuple[str, str]] = set()
        self.reports: list[dict] = []

    def block(self, blocker: str, blocked: str) -> None:
        self.blocks.add((blocker, blocked))

    def unblock(self, blocker: str, blocked: str) -> None:
        self.blocks.discard((blocker, blocked))

    def blocked_users(self, blocker: str) -> set[str]:
        return {blocked for owner, blocked in self.blocks if owner == blocker}

    def is_blocked_either_way(self, first: str, second: str) -> bool:
        return (first, second) in self.blocks or (second, first) in self.blocks

    def report(self, reporter: str, target_type: str, target_id: str, reason: str, details: str) -> dict:
        item = {
            "id": str(uuid4()), "reporterId": reporter, "targetType": target_type,
            "targetId": target_id, "reason": reason, "details": details,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self.reports.append(item)
        return item


class DynamoDBTrustRepository:
    def __init__(self, table_name: str | None = None, region_name: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install backend dependencies to use DynamoDB storage") from exc
        name = table_name or os.environ.get("RELAY_REQUESTS_TABLE")
        if not name:
            raise RuntimeError("RELAY_REQUESTS_TABLE must be set for DynamoDB storage")
        self._table = boto3.resource("dynamodb", region_name=region_name or os.environ.get("AWS_REGION")).Table(name)

    def block(self, blocker: str, blocked: str) -> None:
        self._table.put_item(Item={"PK": f"BLOCK#{blocker}#{blocked}", "blockerId": blocker, "blockedId": blocked})

    def unblock(self, blocker: str, blocked: str) -> None:
        self._table.delete_item(Key={"PK": f"BLOCK#{blocker}#{blocked}"})

    def blocked_users(self, blocker: str) -> set[str]:
        from boto3.dynamodb.conditions import Attr
        result = self._table.scan(FilterExpression=Attr("blockerId").eq(blocker))
        return {item["blockedId"] for item in result.get("Items", []) if "blockedId" in item}

    def is_blocked_either_way(self, first: str, second: str) -> bool:
        for blocker, blocked in ((first, second), (second, first)):
            if self._table.get_item(Key={"PK": f"BLOCK#{blocker}#{blocked}"}).get("Item"):
                return True
        return False

    def report(self, reporter: str, target_type: str, target_id: str, reason: str, details: str) -> dict:
        item = {
            "PK": f"REPORT#{uuid4()}", "reporterId": reporter, "targetType": target_type,
            "targetId": target_id, "reason": reason, "details": details,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._table.put_item(Item=item)
        return {"id": item["PK"].removeprefix("REPORT#"), **{k: v for k, v in item.items() if k != "PK"}}

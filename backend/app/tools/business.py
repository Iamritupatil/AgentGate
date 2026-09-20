"""Exactly five internal operations. Authorization is a later, separate layer."""

from dataclasses import asdict
from typing import Any

from app.domain.storage import BusinessStore


class BusinessTools:
    def __init__(self, store: BusinessStore) -> None:
        self._store = store

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        return asdict(self._store.lookup_order(order_id))

    def lookup_customer(self, customer_id: str) -> dict[str, Any]:
        return asdict(self._store.lookup_customer(customer_id))

    def refund_order(self, order_id: str, amount: int) -> dict[str, Any]:
        # The store validates and commits atomically before success is returned.
        receipt = self._store.refund_order(order_id, amount)
        return {"status": "refunded", **asdict(receipt)}

    def send_email(self, customer_id: str, subject: str, body: str) -> dict[str, Any]:
        receipt = self._store.record_email(customer_id, subject, body)
        return {"status": "recorded", "delivered": False, **asdict(receipt)}

    def export_customers(self) -> list[dict[str, Any]]:
        # Internal domain tests only until Cedar guards this data-release action.
        return [asdict(customer) for customer in self._store.export_customers()]

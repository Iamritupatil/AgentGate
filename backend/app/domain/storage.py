"""Storage contract shared by internal tools and future persistence adapters."""

from typing import Protocol

from app.domain.models import Customer, Order, RecordedEmail, Refund, StoreSnapshot


class BusinessStore(Protocol):
    def lookup_order(self, order_id: str) -> Order: ...

    def lookup_customer(self, customer_id: str) -> Customer: ...

    def refund_order(self, order_id: str, amount: int) -> Refund:
        """Atomically validate payment/amount/prior refund, then commit once.

        Reject invalid, unpaid, over-refund and already-refunded requests with
        DomainError and zero state change. Concurrent requests have one winner.
        This contract does not grant policy authorization.
        """
        ...

    def record_email(self, customer_id: str, subject: str, body: str) -> RecordedEmail:
        """Record a valid local demo message; never send it over a network."""
        ...

    def export_customers(self) -> tuple[Customer, ...]: ...

    def snapshot(self) -> StoreSnapshot:
        """Return a consistent immutable view, with no writable storage aliases."""
        ...

    def reset(self) -> None:
        """Atomically restore initial fixtures and empty the action records."""
        ...

"""Immutable records; returned snapshots cannot change stored business state."""

from dataclasses import dataclass
from typing import Literal

from app.domain.errors import DomainError, require_identifier, require_money, require_text


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: str
    name: str
    email: str

    def __post_init__(self) -> None:
        require_identifier(self.customer_id, "customer_id")
        require_text(self.name, "name")
        require_text(self.email, "email")


@dataclass(frozen=True, slots=True)
class Order:
    order_id: str
    customer_id: str
    amount: int
    payment_status: Literal["paid", "unpaid"]
    shipping_status: Literal["lost", "in_transit", "delivered"]
    refunded_amount: int = 0
    currency: Literal["INR"] = "INR"

    def __post_init__(self) -> None:
        require_identifier(self.order_id, "order_id")
        require_identifier(self.customer_id, "customer_id")
        require_money(self.amount, "amount")
        require_money(self.refunded_amount, "refunded_amount", allow_zero=True)
        if self.payment_status not in ("paid", "unpaid"):
            raise DomainError("INVALID_ARGUMENT", "Unknown payment status.")
        if self.shipping_status not in ("lost", "in_transit", "delivered"):
            raise DomainError("INVALID_ARGUMENT", "Unknown shipping status.")
        if self.currency != "INR":
            raise DomainError("INVALID_ARGUMENT", "The demo stores whole INR only.")
        if self.refunded_amount > self.amount:
            raise DomainError("INVALID_ARGUMENT", "Refunded amount exceeds the order total.")
        if self.payment_status == "unpaid" and self.refunded_amount:
            raise DomainError("INVALID_ARGUMENT", "An unpaid order cannot already be refunded.")


@dataclass(frozen=True, slots=True)
class Refund:
    refund_id: str
    order_id: str
    amount: int
    currency: Literal["INR"] = "INR"


@dataclass(frozen=True, slots=True)
class RecordedEmail:
    email_id: str
    customer_id: str
    to: str
    subject: str
    body: str


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    customers: tuple[Customer, ...]
    orders: tuple[Order, ...]
    refunds: tuple[Refund, ...] = ()
    emails: tuple[RecordedEmail, ...] = ()

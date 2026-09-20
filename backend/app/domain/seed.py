"""Fictional, deterministic demo fixtures. No real customer data."""

from dataclasses import dataclass

from app.domain.errors import DomainError
from app.domain.models import Customer, Order


@dataclass(frozen=True, slots=True)
class SeedData:
    customers: tuple[Customer, ...]
    orders: tuple[Order, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.customers, tuple) or not all(isinstance(item, Customer) for item in self.customers):
            raise DomainError("INVALID_SEED", "Seed customers must be a tuple of Customer records.")
        if not isinstance(self.orders, tuple) or not all(isinstance(item, Order) for item in self.orders):
            raise DomainError("INVALID_SEED", "Seed orders must be a tuple of Order records.")
        customer_ids = {item.customer_id for item in self.customers}
        order_ids = {item.order_id for item in self.orders}
        if len(customer_ids) != len(self.customers) or len(order_ids) != len(self.orders):
            raise DomainError("INVALID_SEED", "Duplicate customer or order identifiers in seed.")
        if any(order.customer_id not in customer_ids for order in self.orders):
            raise DomainError("INVALID_SEED", "Every seeded order must reference a seeded customer.")
        if any(order.refunded_amount for order in self.orders):
            raise DomainError("INVALID_SEED", "Initial fixtures must not contain unrecorded refunds.")


def demo_seed() -> SeedData:
    return SeedData(
        customers=(
            Customer("CUS-1001", "Asha Rao", "asha@agentgate.example"),
            Customer("CUS-1002", "Dev Mehta", "dev@agentgate.example"),
            Customer("CUS-1003", "Mira Shah", "mira@agentgate.example"),
        ),
        orders=(
            Order("ORD-1001", "CUS-1001", 799, "paid", "lost"),
            Order("ORD-1002", "CUS-1002", 8499, "paid", "lost"),
            Order("ORD-1003", "CUS-1003", 25000, "paid", "lost"),
        ),
    )

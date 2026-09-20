"""Single-process demo store. All business state commits under one shared lock."""

from dataclasses import replace
from threading import Lock

from app.domain.errors import DomainError, require_identifier, require_money, require_text
from app.domain.models import Customer, Order, RecordedEmail, Refund, StoreSnapshot
from app.domain.seed import SeedData, demo_seed


class InMemoryStore:
    def __init__(self, seed: SeedData | None = None) -> None:
        fixtures = seed if seed is not None else demo_seed()
        if not isinstance(fixtures, SeedData):
            raise DomainError("INVALID_SEED", "Expected validated SeedData.")
        self._initial = StoreSnapshot(
            customers=tuple(sorted(fixtures.customers, key=lambda item: item.customer_id)),
            orders=tuple(sorted(fixtures.orders, key=lambda item: item.order_id)),
        )
        self._state = self._initial
        self._lock = Lock()

    def _find_order(self, order_id: str) -> Order:
        # Private finders are called only while holding the store lock.
        for order in self._state.orders:
            if order.order_id == order_id:
                return order
        raise DomainError("NOT_FOUND", f"Order {order_id!r} does not exist.")

    def _find_customer(self, customer_id: str) -> Customer:
        for customer in self._state.customers:
            if customer.customer_id == customer_id:
                return customer
        raise DomainError("NOT_FOUND", f"Customer {customer_id!r} does not exist.")

    def lookup_order(self, order_id: str) -> Order:
        require_identifier(order_id, "order_id")
        with self._lock:
            return self._find_order(order_id)

    def lookup_customer(self, customer_id: str) -> Customer:
        require_identifier(customer_id, "customer_id")
        with self._lock:
            return self._find_customer(customer_id)

    def refund_order(self, order_id: str, amount: int) -> Refund:
        require_identifier(order_id, "order_id")
        require_money(amount, "amount")
        with self._lock:
            order = self._find_order(order_id)
            if order.payment_status != "paid":
                raise DomainError("UNPAID_ORDER", "Only paid orders can be refunded.")
            if order.refunded_amount:
                raise DomainError("ALREADY_REFUNDED", "This demo permits only one refund per order.")
            if amount > order.amount:
                raise DomainError("OVER_REFUND", "Refund exceeds the paid order total.")

            updated_order = replace(order, refunded_amount=amount)
            refund = Refund(f"RFD-{len(self._state.refunds) + 1:04d}", order_id, amount)
            # Construct everything before the one state assignment. Failed validation
            # cannot leave a changed order without its matching refund record.
            next_state = replace(
                self._state,
                orders=tuple(updated_order if item.order_id == order_id else item for item in self._state.orders),
                refunds=(*self._state.refunds, refund),
            )
            self._state = next_state
            return refund

    def record_email(self, customer_id: str, subject: str, body: str) -> RecordedEmail:
        require_identifier(customer_id, "customer_id")
        require_text(subject, "subject")
        require_text(body, "body")
        with self._lock:
            customer = self._find_customer(customer_id)
            email = RecordedEmail(
                email_id=f"EMAIL-{len(self._state.emails) + 1:04d}",
                customer_id=customer_id,
                to=customer.email,
                subject=subject,
                body=body,
            )
            self._state = replace(self._state, emails=(*self._state.emails, email))
            return email

    def export_customers(self) -> tuple[Customer, ...]:
        with self._lock:
            return self._state.customers

    def snapshot(self) -> StoreSnapshot:
        with self._lock:
            return self._state

    def reset(self) -> None:
        with self._lock:
            self._state = self._initial

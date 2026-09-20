from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from threading import Barrier

import pytest

from app.domain.errors import DomainError
from app.domain.memory import InMemoryStore
from app.domain.models import Order
from app.domain.seed import demo_seed


def test_seed_construction_is_repeatable():
    assert demo_seed() == demo_seed()
    assert InMemoryStore().snapshot() == InMemoryStore().snapshot()


@pytest.mark.parametrize("change", ["duplicate_customer", "duplicate_order", "orphan_order", "existing_refund"])
def test_invalid_seed_is_rejected(change):
    seed = demo_seed()
    with pytest.raises(DomainError) as error:
        if change == "duplicate_customer":
            replace(seed, customers=(*seed.customers, seed.customers[0]))
        elif change == "duplicate_order":
            replace(seed, orders=(*seed.orders, seed.orders[0]))
        elif change == "orphan_order":
            replace(seed, orders=(replace(seed.orders[0], customer_id="CUS-MISSING"),))
        else:
            replace(seed, orders=(replace(seed.orders[0], refunded_amount=1),))
    assert error.value.code == "INVALID_SEED"


@pytest.mark.parametrize("changes", [
    {"amount": True}, {"amount": 0}, {"amount": 799.0},
    {"refunded_amount": -1}, {"refunded_amount": 800},
    {"payment_status": "unpaid", "refunded_amount": 1},
    {"currency": "USD"}, {"payment_status": "unknown"}, {"shipping_status": "unknown"},
])
def test_invalid_order_state_cannot_enter_storage(changes):
    with pytest.raises(DomainError):
        replace(demo_seed().orders[0], **changes)


def test_snapshots_and_records_are_immutable_and_stable_after_later_writes():
    store = InMemoryStore()
    before = store.snapshot()
    with pytest.raises(FrozenInstanceError):
        before.orders[0].refunded_amount = 799
    with pytest.raises(FrozenInstanceError):
        before.customers[0].email = "changed@example.invalid"
    with pytest.raises(FrozenInstanceError):
        before.orders = ()
    store.refund_order("ORD-1001", 799)
    assert before.orders[0].refunded_amount == 0
    assert before.refunds == ()


def test_custom_fixture_reset_and_export_order():
    seed = demo_seed()
    custom = replace(seed, customers=tuple(reversed(seed.customers)), orders=(seed.orders[1],))
    store = InMemoryStore(custom)
    initial = store.snapshot()
    assert [customer.customer_id for customer in store.export_customers()] == ["CUS-1001", "CUS-1002", "CUS-1003"]
    store.refund_order("ORD-1002", 8499)
    store.reset()
    assert store.snapshot() == initial
    with pytest.raises(DomainError):
        store.lookup_order("ORD-1001")


def test_store_itself_rejects_invalid_refund_without_tool_wrapper():
    store = InMemoryStore()
    before = store.snapshot()
    with pytest.raises(DomainError):
        store.refund_order("ORD-1001", True)
    assert store.snapshot() == before


@pytest.mark.parametrize("order_id,amount", [("ORD-1002", 8499), ("ORD-1003", 25000)])
def test_domain_validity_is_separate_from_future_policy_authority(order_id, amount):
    # These internal calls prove no fake policy thresholds live in the domain.
    # Future authorization will require approval / deny before invoking them.
    store = InMemoryStore()
    assert store.refund_order(order_id, amount).amount == amount


def test_refund_record_construction_failure_leaves_state_unchanged(monkeypatch):
    store = InMemoryStore()
    initial = store.snapshot()

    def fail(*args):
        raise RuntimeError("Cannot construct refund record")

    monkeypatch.setattr("app.domain.memory.Refund", fail)
    with pytest.raises(RuntimeError, match="Cannot construct refund record"):
        store.refund_order("ORD-1001", 799)
    assert store.snapshot() == initial


def test_concurrent_different_orders_do_not_lose_refund_records():
    store = InMemoryStore()
    barrier = Barrier(3)

    def refund(order: Order):
        barrier.wait(timeout=10)
        return store.refund_order(order.order_id, order.amount)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(refund, demo_seed().orders))
    assert len({receipt.refund_id for receipt in results}) == 3
    state = store.snapshot()
    assert len(state.refunds) == 3
    assert all(order.refunded_amount == order.amount for order in state.orders)


def test_concurrent_reset_and_refund_never_split_order_and_receipt():
    store = InMemoryStore()
    barrier = Barrier(2)

    def reset():
        barrier.wait(timeout=10)
        store.reset()

    def refund():
        barrier.wait(timeout=10)
        store.refund_order("ORD-1001", 799)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reset), pool.submit(refund)]
        for future in futures:
            future.result(timeout=10)
    state = store.snapshot()
    # Whichever operation acquires the lock last, the complete snapshot agrees.
    assert state.orders[0].refunded_amount == sum(item.amount for item in state.refunds)
    assert len(state.refunds) <= 1


def test_concurrent_recorded_emails_have_unique_ids_and_all_bodies():
    store = InMemoryStore()
    barrier = Barrier(6)

    def record(index):
        barrier.wait(timeout=10)
        return store.record_email("CUS-1001", "Demo", f"Message {index}")

    with ThreadPoolExecutor(max_workers=6) as pool:
        emails = list(pool.map(record, range(6)))
    assert len({email.email_id for email in emails}) == 6
    assert {email.body for email in store.snapshot().emails} == {f"Message {index}" for index in range(6)}

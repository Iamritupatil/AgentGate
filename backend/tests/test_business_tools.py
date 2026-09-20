from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest

from app.domain.errors import DomainError
from app.domain.memory import InMemoryStore
from app.domain.seed import demo_seed
from app.tools.business import BusinessTools


@pytest.fixture
def store():
    return InMemoryStore()


@pytest.fixture
def tools(store):
    return BusinessTools(store)


def test_exactly_five_business_operations():
    assert {name for name in vars(BusinessTools) if not name.startswith("_")} == {
        "lookup_order", "lookup_customer", "refund_order", "send_email", "export_customers"
    }


@pytest.mark.parametrize("order_id,amount", [("ORD-1001", 799), ("ORD-1002", 8499), ("ORD-1003", 25000)])
def test_seeded_lookups_are_consistent(tools, store, order_id, amount):
    before = store.snapshot()
    order = tools.lookup_order(order_id)
    customer = tools.lookup_customer(order["customer_id"])
    assert order == {
        "order_id": order_id,
        "customer_id": customer["customer_id"],
        "amount": amount,
        "currency": "INR",
        "payment_status": "paid",
        "shipping_status": "lost",
        "refunded_amount": 0,
    }
    assert customer["email"].endswith(".example")
    assert store.snapshot() == before


def test_successful_refund_changes_only_the_target_order_once(tools, store):
    before = store.snapshot()
    receipt = tools.refund_order("ORD-1001", 799)
    after = store.snapshot()
    assert receipt == {
        "status": "refunded", "refund_id": "RFD-0001",
        "order_id": "ORD-1001", "amount": 799, "currency": "INR",
    }
    assert tools.lookup_order("ORD-1001")["refunded_amount"] == 799
    assert len(after.refunds) == 1
    assert after.orders[1:] == before.orders[1:]
    assert after.customers == before.customers
    assert after.emails == before.emails


@pytest.mark.parametrize("amount", [1, 798, 799])
def test_positive_refund_up_to_order_total_is_valid(tools, amount):
    assert tools.refund_order("ORD-1001", amount)["amount"] == amount
    assert tools.lookup_order("ORD-1001")["refunded_amount"] == amount


@pytest.mark.parametrize("first,second", [(799, 799), (100, 100), (100, 699)])
def test_second_refund_including_partial_topup_is_rejected(tools, store, first, second):
    tools.refund_order("ORD-1001", first)
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        tools.refund_order("ORD-1001", second)
    assert error.value.code == "ALREADY_REFUNDED"
    assert store.snapshot() == before


@pytest.mark.parametrize("amount", [800, 25000])
def test_over_refund_leaves_all_business_state_unchanged(tools, store, amount):
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        tools.refund_order("ORD-1001", amount)
    assert error.value.code == "OVER_REFUND"
    assert store.snapshot() == before


@pytest.mark.parametrize("amount", [0, -1, True, False, 799.0, 1.5, "799", None, [], {}])
def test_invalid_money_is_never_coerced_or_recorded(tools, store, amount):
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        tools.refund_order("ORD-1001", amount)
    assert error.value.code == "INVALID_ARGUMENT"
    assert store.snapshot() == before


def test_unpaid_order_cannot_be_refunded():
    seed = demo_seed()
    unpaid = replace(seed.orders[0], payment_status="unpaid")
    store = InMemoryStore(replace(seed, orders=(unpaid, *seed.orders[1:])))
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        BusinessTools(store).refund_order("ORD-1001", 799)
    assert error.value.code == "UNPAID_ORDER"
    assert store.snapshot() == before


@pytest.mark.parametrize("method,args", [
    ("lookup_order", ("ORD-MISSING",)),
    ("lookup_customer", ("CUS-MISSING",)),
    ("refund_order", ("ORD-MISSING", 799)),
    ("send_email", ("CUS-MISSING", "Subject", "Body")),
])
def test_missing_record_does_not_invent_success(tools, store, method, args):
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        getattr(tools, method)(*args)
    assert error.value.code == "NOT_FOUND"
    assert store.snapshot() == before


@pytest.mark.parametrize("record_id", [None, True, 1001, "", " ", " ORD-1001 "])
def test_invalid_identifiers_do_not_mutate(tools, store, record_id):
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        tools.refund_order(record_id, 799)
    assert error.value.code == "INVALID_ARGUMENT"
    assert store.snapshot() == before


def test_email_is_recorded_locally_without_claiming_delivery(tools, store, monkeypatch):
    def reject_network(*args, **kwargs):
        raise AssertionError("Demo email must not use network transport")

    monkeypatch.setattr("socket.socket.connect", reject_network)
    before = store.snapshot()
    result = tools.send_email("CUS-1001", "Your lost order", "We are investigating ORD-1001.")
    after = store.snapshot()
    assert result == {
        "status": "recorded", "delivered": False, "email_id": "EMAIL-0001",
        "customer_id": "CUS-1001", "to": "asha@agentgate.example",
        "subject": "Your lost order", "body": "We are investigating ORD-1001.",
    }
    assert len(after.emails) == 1
    assert after.emails[0].body == result["body"]
    assert after.orders == before.orders
    assert after.customers == before.customers
    assert after.refunds == before.refunds


@pytest.mark.parametrize("subject,body", [("", "Body"), (" ", "Body"), (None, "Body"), ("Subject", ""), ("Subject", 7)])
def test_invalid_email_is_not_recorded(tools, store, subject, body):
    before = store.snapshot()
    with pytest.raises(DomainError) as error:
        tools.send_email("CUS-1001", subject, body)
    assert error.value.code == "INVALID_ARGUMENT"
    assert store.snapshot() == before


def test_export_and_lookups_return_detached_data(tools, store):
    before = store.snapshot()
    exported = tools.export_customers()
    assert [customer["customer_id"] for customer in exported] == ["CUS-1001", "CUS-1002", "CUS-1003"]
    assert exported[0] == tools.lookup_customer("CUS-1001")
    exported[0]["email"] = "changed@invalid.example"
    exported.clear()
    tools.lookup_customer("CUS-1001")["name"] = "Changed"
    tools.lookup_order("ORD-1001")["amount"] = 1
    assert store.snapshot() == before


def test_reset_restores_exact_seed_and_clears_recorded_actions(tools, store):
    initial = store.snapshot()
    tools.refund_order("ORD-1001", 799)
    tools.send_email("CUS-1002", "Demo", "Recorded only.")
    store.reset()
    assert store.snapshot() == initial
    store.reset()
    assert store.snapshot() == initial
    assert tools.refund_order("ORD-1001", 799)["refund_id"] == "RFD-0001"
    assert tools.send_email("CUS-1001", "Again", "Fresh demo.")["email_id"] == "EMAIL-0001"


def test_separate_stores_do_not_share_business_state():
    first, second = InMemoryStore(), InMemoryStore()
    initial = second.snapshot()
    BusinessTools(first).refund_order("ORD-1001", 799)
    BusinessTools(first).send_email("CUS-1001", "Test", "Only in first store.")
    assert second.snapshot() == initial


def test_concurrent_refunds_have_one_winner_even_through_separate_tool_instances(store):
    barrier = Barrier(8)

    def attempt(_):
        barrier.wait(timeout=10)
        try:
            return BusinessTools(store).refund_order("ORD-1001", 799)["status"]
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert outcomes.count("refunded") == 1
    assert outcomes.count("ALREADY_REFUNDED") == 7
    assert store.lookup_order("ORD-1001").refunded_amount == 799
    assert len(store.snapshot().refunds) == 1


def test_storage_failure_is_not_reported_as_tool_success(store, monkeypatch):
    def fail(*args):
        raise RuntimeError("Storage unavailable")

    monkeypatch.setattr(store, "refund_order", fail)
    with pytest.raises(RuntimeError, match="Storage unavailable"):
        BusinessTools(store).refund_order("ORD-1001", 799)

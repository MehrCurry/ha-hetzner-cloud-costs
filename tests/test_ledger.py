from datetime import UTC, datetime, timedelta
from decimal import Decimal

from custom_components.hetzner_cloud_costs.ledger import CostLedger

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)


def test_new_server_accrues_one_hour_immediately():
    ledger = CostLedger()
    snapshot = ledger.update({1: (NOW, Decimal("0.006"))}, NOW)
    assert snapshot.rate == Decimal("0.006")
    assert snapshot.total_cost == Decimal("0.006")  # first started hour, billed in full
    assert snapshot.active_count == 1


def test_running_server_accrues_by_started_hour_not_elapsed_time():
    ledger = CostLedger()
    ledger.update({1: (NOW, Decimal("0.006"))}, NOW)
    later = NOW + timedelta(minutes=90)  # into the 2nd started hour
    snapshot = ledger.update({1: (NOW, Decimal("0.006"))}, later)
    assert snapshot.total_cost == Decimal("0.012")
    assert snapshot.active_count == 1


def test_disappeared_server_is_booked_from_last_seen_rounded_up():
    ledger = CostLedger()
    ledger.update({1: (NOW, Decimal("0.006"))}, NOW)
    last_seen = NOW + timedelta(minutes=5)
    ledger.update({1: (NOW, Decimal("0.006"))}, last_seen)
    # next poll: server is gone
    snapshot = ledger.update({}, last_seen + timedelta(minutes=5))
    assert snapshot.total_cost == Decimal("0.006")  # booked 1 started hour
    assert snapshot.active_count == 0
    assert snapshot.rate == Decimal("0")


def test_booked_cost_survives_across_updates():
    ledger = CostLedger()
    ledger.update({1: (NOW, Decimal("0.006"))}, NOW)
    ledger.update({}, NOW + timedelta(minutes=10))  # server 1 booked
    snapshot = ledger.update({2: (NOW, Decimal("0.01"))}, NOW + timedelta(minutes=20))
    assert snapshot.total_cost == Decimal("0.006") + Decimal("0.01")


def test_round_trip_serialization():
    ledger = CostLedger()
    ledger.update({1: (NOW, Decimal("0.006"))}, NOW)
    restored = CostLedger.from_dict(ledger.to_dict())
    snapshot = restored.update({1: (NOW, Decimal("0.006"))}, NOW)
    assert snapshot.active_count == 1
    assert snapshot.rate == Decimal("0.006")

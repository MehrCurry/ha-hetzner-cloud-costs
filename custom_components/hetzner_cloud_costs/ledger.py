"""Billing-exact cost ledger for Hetzner Cloud servers.

Plain Python, no Home Assistant imports, so it can be unit tested in
isolation. Hetzner bills per started hour from server creation
(docs.hetzner.com/cloud/billing/faq): any partial hour, even the first,
counts as a full billed hour.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class ServerSnapshot:
    created: datetime
    price_hourly: Decimal
    last_seen: datetime


@dataclass
class CostSnapshot:
    rate: Decimal
    total_cost: Decimal
    active_count: int
    started_total: int


def _billed_hours(created: datetime, until: datetime) -> int:
    seconds = max((until - created).total_seconds(), 0)
    return max(math.ceil(seconds / 3600), 1)


class CostLedger:
    """Tracks running servers and books cost when they disappear.

    A server missing from a poll is assumed deleted between polls (the
    Hetzner API only lists servers that still exist, there is no delete
    timestamp). Its final cost is booked using the last time it was seen,
    rounded up to the next full hour from creation.
    """

    def __init__(self) -> None:
        self._open: dict[int, ServerSnapshot] = {}
        self._booked_total = Decimal("0")
        self._started_total = 0

    def update(
        self, current: dict[int, tuple[datetime, Decimal]], now: datetime
    ) -> CostSnapshot:
        for server_id in list(self._open):
            if server_id not in current:
                snapshot = self._open.pop(server_id)
                hours = _billed_hours(snapshot.created, snapshot.last_seen)
                self._booked_total += hours * snapshot.price_hourly

        for server_id, (created, price_hourly) in current.items():
            existing = self._open.get(server_id)
            if existing is None:
                self._open[server_id] = ServerSnapshot(created, price_hourly, now)
                self._started_total += 1
            else:
                existing.last_seen = now
                existing.price_hourly = price_hourly

        rate = sum((s.price_hourly for s in self._open.values()), Decimal("0"))
        accrued = sum(
            (
                _billed_hours(s.created, now) * s.price_hourly
                for s in self._open.values()
            ),
            Decimal("0"),
        )
        return CostSnapshot(
            rate=rate,
            total_cost=self._booked_total + accrued,
            active_count=len(self._open),
            started_total=self._started_total,
        )

    def to_dict(self) -> dict:
        return {
            "booked_total": str(self._booked_total),
            "started_total": self._started_total,
            "open": {
                str(server_id): {
                    "created": s.created.isoformat(),
                    "price_hourly": str(s.price_hourly),
                    "last_seen": s.last_seen.isoformat(),
                }
                for server_id, s in self._open.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> CostLedger:
        ledger = cls()
        ledger._booked_total = Decimal(data.get("booked_total", "0"))
        ledger._started_total = data.get("started_total", 0)
        for server_id, s in data.get("open", {}).items():
            ledger._open[int(server_id)] = ServerSnapshot(
                created=datetime.fromisoformat(s["created"]),
                price_hourly=Decimal(s["price_hourly"]),
                last_seen=datetime.fromisoformat(s["last_seen"]),
            )
        return ledger

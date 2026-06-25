import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    account_id  TEXT NOT NULL,
    total_value TEXT,
    currency    TEXT,
    positions   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_account_ts
    ON portfolio_snapshots(account_id, timestamp);
"""


class SnapshotStorage:
    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)

    async def init(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.executescript(CREATE_TABLE)
            await db.commit()

    async def insert(
        self,
        account_id: str,
        total_value: str | None,
        currency: str | None,
        positions: list[dict],
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO portfolio_snapshots "
                "(timestamp, account_id, total_value, currency, positions) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, account_id, total_value, currency, json.dumps(positions, ensure_ascii=False)),
            )
            await db.commit()

    async def get_history(self, account_id: str, limit: int = 20) -> list[dict]:
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT timestamp, total_value, currency, positions "
                "FROM portfolio_snapshots "
                "WHERE account_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (account_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [
            {
                "timestamp": r["timestamp"],
                "total_value": r["total_value"],
                "currency": r["currency"],
                "positions": json.loads(r["positions"]),
            }
            for r in rows
        ]

    async def get_summary(self, account_id: str, days: int = 7) -> dict:
        """Return first and last snapshot in the window + per-position delta."""
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row

            # boundary: oldest snapshot within `days` days
            since = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            from datetime import timedelta
            since = since - timedelta(days=days - 1)
            since_iso = since.isoformat()

            async with db.execute(
                "SELECT timestamp, total_value, currency, positions "
                "FROM portfolio_snapshots "
                "WHERE account_id = ? AND timestamp >= ? "
                "ORDER BY timestamp ASC LIMIT 1",
                (account_id, since_iso),
            ) as cur:
                first_row = await cur.fetchone()

            async with db.execute(
                "SELECT timestamp, total_value, currency, positions "
                "FROM portfolio_snapshots "
                "WHERE account_id = ? "
                "ORDER BY timestamp DESC LIMIT 1",
                (account_id,),
            ) as cur:
                last_row = await cur.fetchone()

            async with db.execute(
                "SELECT COUNT(*) as cnt FROM portfolio_snapshots WHERE account_id = ? AND timestamp >= ?",
                (account_id, since_iso),
            ) as cur:
                count_row = await cur.fetchone()

        if not last_row:
            return {"error": "No snapshots found. Run trigger_snapshot first."}

        last = {
            "timestamp": last_row["timestamp"],
            "total_value": last_row["total_value"],
            "currency": last_row["currency"],
            "positions": json.loads(last_row["positions"]),
        }

        result: dict = {
            "account_id": account_id,
            "period_days": days,
            "snapshots_in_period": count_row["cnt"] if count_row else 0,
            "latest": {
                "timestamp": last["timestamp"],
                "total_value": last["total_value"],
                "currency": last["currency"],
            },
        }

        if first_row and first_row["timestamp"] != last_row["timestamp"]:
            first = {
                "timestamp": first_row["timestamp"],
                "total_value": first_row["total_value"],
                "positions": json.loads(first_row["positions"]),
            }
            result["oldest_in_period"] = {
                "timestamp": first["timestamp"],
                "total_value": first["total_value"],
            }
            # total value delta
            try:
                from decimal import Decimal
                v_last = Decimal(last["total_value"].split()[0])
                v_first = Decimal(first["total_value"].split()[0])
                delta = v_last - v_first
                delta_pct = (delta / v_first * 100).quantize(Decimal("0.01"))
                result["total_delta"] = f"{delta:+.2f} {last['currency']}"
                result["total_delta_pct"] = f"{delta_pct:+.2f}%"
            except Exception:
                result["total_delta"] = "n/a"

            # per-position delta
            first_pos = {p["figi"]: p for p in first["positions"] if p.get("figi")}
            last_pos = last["positions"]
            position_deltas = []
            for p in last_pos:
                figi = p.get("figi")
                if not figi:
                    continue
                try:
                    from decimal import Decimal
                    ey_last = Decimal(p.get("expected_yield") or "0")
                    fp = first_pos.get(figi)
                    ey_first = Decimal(fp.get("expected_yield") or "0") if fp else Decimal("0")
                    position_deltas.append(
                        {
                            "ticker": p.get("ticker") or figi,
                            "instrument_type": p.get("instrument_type"),
                            "expected_yield_now": str(ey_last),
                            "expected_yield_delta": f"{ey_last - ey_first:+.6f}",
                            "current_price": p.get("current_price"),
                        }
                    )
                except Exception:
                    continue
            result["positions"] = sorted(
                position_deltas,
                key=lambda x: float(x["expected_yield_delta"]),
                reverse=True,
            )
        else:
            result["note"] = "Only one snapshot available; collect more to see delta."
            result["positions"] = [
                {
                    "ticker": p.get("ticker") or p.get("figi"),
                    "instrument_type": p.get("instrument_type"),
                    "expected_yield_now": p.get("expected_yield"),
                    "current_price": p.get("current_price"),
                }
                for p in last["positions"]
            ]

        return result

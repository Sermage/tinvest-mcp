import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from tinvest_mcp.storage import SnapshotStorage
from tinvest_mcp.tinvest.client import TInvestClient

log = logging.getLogger(__name__)


async def _collect_all_accounts(client: TInvestClient, storage: SnapshotStorage) -> None:
    """Snapshot all accessible accounts. Called by scheduler and manual trigger."""
    from tinvest_mcp.tools.accounts import get_accounts
    from tinvest_mcp.tools.portfolio import get_portfolio

    try:
        accounts = await get_accounts(client)
    except Exception as exc:
        log.error("scheduler: failed to fetch accounts", exc_info=exc)
        return

    for acc in accounts:
        aid = acc["id"]
        try:
            portfolio = await get_portfolio(client, aid)
            total_raw = portfolio.get("total_amount_portfolio") or ""
            parts = total_raw.split()
            total_value = parts[0] if parts else None
            currency = parts[1] if len(parts) > 1 else None
            await storage.insert(aid, total_value, currency, portfolio.get("positions", []))
            log.info("scheduler: snapshot saved", extra={"account_id": aid, "total": total_raw})
        except Exception as exc:
            log.error("scheduler: failed to snapshot account %s", aid, exc_info=exc)


def build_scheduler(
    client: TInvestClient,
    storage: SnapshotStorage,
    interval_minutes: int,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _collect_all_accounts,
        trigger=IntervalTrigger(minutes=interval_minutes),
        args=[client, storage],
        id="portfolio_snapshot",
        name=f"Portfolio snapshot every {interval_minutes}m",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler

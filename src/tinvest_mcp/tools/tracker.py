from tinvest_mcp.scheduler import _collect_all_accounts
from tinvest_mcp.storage import SnapshotStorage
from tinvest_mcp.tinvest.client import TInvestClient


async def trigger_snapshot(client: TInvestClient, storage: SnapshotStorage) -> dict:
    """Immediately collect a portfolio snapshot for all accounts."""
    await _collect_all_accounts(client, storage)
    return {"status": "ok", "message": "Snapshot collected for all accounts."}


async def get_portfolio_history(
    storage: SnapshotStorage, account_id: str, limit: int = 10
) -> list[dict]:
    return await storage.get_history(account_id, limit)


async def get_portfolio_summary(
    storage: SnapshotStorage, account_id: str, days: int = 7
) -> dict:
    return await storage.get_summary(account_id, days)

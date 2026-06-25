import logging
from contextlib import asynccontextmanager
from typing import Literal

import structlog
from mcp.server.fastmcp import FastMCP

from mcp.server.transport_security import TransportSecuritySettings

from tinvest_mcp.config import Settings, load_settings
from tinvest_mcp.scheduler import build_scheduler
from tinvest_mcp.storage import SnapshotStorage
from tinvest_mcp.tinvest.client import TInvestClient, make_http_client
from tinvest_mcp.tools import accounts as accounts_tool
from tinvest_mcp.tools import instruments as instruments_tool
from tinvest_mcp.tools import market_data as market_data_tool
from tinvest_mcp.tools import operations as operations_tool
from tinvest_mcp.tools import portfolio as portfolio_tool
from tinvest_mcp.tools import positions as positions_tool
from tinvest_mcp.tools import tracker as tracker_tool

InstrumentKind = Literal[
    "INSTRUMENT_TYPE_UNSPECIFIED",
    "INSTRUMENT_TYPE_BOND",
    "INSTRUMENT_TYPE_SHARE",
    "INSTRUMENT_TYPE_CURRENCY",
    "INSTRUMENT_TYPE_ETF",
    "INSTRUMENT_TYPE_FUTURES",
    "INSTRUMENT_TYPE_SP",
    "INSTRUMENT_TYPE_OPTION",
    "INSTRUMENT_TYPE_CLEARING_CERTIFICATE",
    "INSTRUMENT_TYPE_INDEX",
    "INSTRUMENT_TYPE_COMMODITY",
]

CandleInterval = Literal[
    "CANDLE_INTERVAL_1_MIN",
    "CANDLE_INTERVAL_5_MIN",
    "CANDLE_INTERVAL_15_MIN",
    "CANDLE_INTERVAL_HOUR",
    "CANDLE_INTERVAL_DAY",
    "CANDLE_INTERVAL_2_MIN",
    "CANDLE_INTERVAL_3_MIN",
    "CANDLE_INTERVAL_10_MIN",
    "CANDLE_INTERVAL_30_MIN",
    "CANDLE_INTERVAL_2_HOUR",
    "CANDLE_INTERVAL_4_HOUR",
    "CANDLE_INTERVAL_WEEK",
    "CANDLE_INTERVAL_MONTH",
]

OperationState = Literal[
    "OPERATION_STATE_UNSPECIFIED",
    "OPERATION_STATE_EXECUTED",
    "OPERATION_STATE_CANCELED",
    "OPERATION_STATE_PROGRESS",
]


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )


def _transport_security(settings: Settings) -> TransportSecuritySettings | None:
    if settings.transport != "http":
        return None
    allowed: list[str] = ["localhost", "localhost:*", "127.0.0.1", "127.0.0.1:*"]
    if settings.http_host and settings.http_host not in ("0.0.0.0", "127.0.0.1"):
        allowed += [settings.http_host, f"{settings.http_host}:*"]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed,
    )


def build_server(settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_: FastMCP):
        # init storage
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        storage = SnapshotStorage(settings.db_path)
        await storage.init()

        # init HTTP client + T-Invest client
        http = make_http_client(settings)
        client = TInvestClient(settings, http)

        # start scheduler
        scheduler = build_scheduler(client, storage, settings.snapshot_interval)
        scheduler.start()

        try:
            yield {"client": client, "storage": storage}
        finally:
            scheduler.shutdown(wait=False)
            await http.aclose()

    mcp = FastMCP(
        "tinvest-mcp",
        lifespan=lifespan,
        transport_security=_transport_security(settings),
    )

    def _client() -> TInvestClient:
        return mcp.get_context().request_context.lifespan_context["client"]

    def _storage() -> SnapshotStorage:
        return mcp.get_context().request_context.lifespan_context["storage"]

    # ── read-only market/portfolio tools ──────────────────────────────────────

    @mcp.tool(
        name="get_accounts",
        description="List T-Invest accounts available for the configured token.",
    )
    async def get_accounts() -> list[dict]:
        return await accounts_tool.get_accounts(_client())

    @mcp.tool(
        name="get_portfolio",
        description="Get portfolio (totals, positions with current price and yield) for an account.",
    )
    async def get_portfolio(account_id: str) -> dict:
        return await portfolio_tool.get_portfolio(_client(), account_id)

    @mcp.tool(
        name="get_positions",
        description="Get raw positions (money, securities, futures, options) for an account.",
    )
    async def get_positions(account_id: str) -> dict:
        return await positions_tool.get_positions(_client(), account_id)

    @mcp.tool(
        name="get_operations",
        description=(
            "Get account operations between two timestamps (ISO 8601 with Z, e.g. "
            "2025-01-01T00:00:00Z). State defaults to EXECUTED. Optional FIGI filter."
        ),
    )
    async def get_operations(
        account_id: str,
        from_: str,
        to: str,
        state: OperationState = "OPERATION_STATE_EXECUTED",
        figi: str | None = None,
    ) -> list[dict]:
        return await operations_tool.get_operations(
            _client(), account_id, from_, to, state, figi
        )

    @mcp.tool(
        name="find_instrument",
        description="Search instruments by ticker, ISIN, FIGI, or name.",
    )
    async def find_instrument(
        query: str,
        instrument_kind: InstrumentKind | None = None,
        api_trade_available_flag: bool | None = None,
    ) -> list[dict]:
        return await instruments_tool.find_instrument(
            _client(), query, instrument_kind, api_trade_available_flag
        )

    @mcp.tool(
        name="get_last_prices",
        description="Latest prices for given FIGI list or instrument UID list.",
    )
    async def get_last_prices(
        figi: list[str] | None = None,
        instrument_id: list[str] | None = None,
    ) -> list[dict]:
        return await market_data_tool.get_last_prices(_client(), figi, instrument_id)

    @mcp.tool(
        name="get_candles",
        description=(
            "OHLCV candles between two timestamps for a FIGI or instrument UID. "
            "Pick interval matching the date range (longer ranges require coarser intervals)."
        ),
    )
    async def get_candles(
        from_: str,
        to: str,
        interval: CandleInterval,
        figi: str | None = None,
        instrument_id: str | None = None,
    ) -> list[dict]:
        return await market_data_tool.get_candles(
            _client(), from_, to, interval, figi, instrument_id
        )

    # ── snapshot / tracker tools ──────────────────────────────────────────────

    @mcp.tool(
        name="trigger_snapshot",
        description=(
            "Immediately collect a portfolio snapshot for all accounts and save to DB. "
            "The scheduler does this automatically every TINVEST_SNAPSHOT_INTERVAL minutes "
            "(default 60). Use this tool to force a snapshot right now."
        ),
    )
    async def trigger_snapshot() -> dict:
        return await tracker_tool.trigger_snapshot(_client(), _storage())

    @mcp.tool(
        name="get_portfolio_history",
        description=(
            "Return the last N snapshots for an account from the local SQLite DB. "
            "Each entry has timestamp, total_value, currency, and positions."
        ),
    )
    async def get_portfolio_history(account_id: str, limit: int = 10) -> list[dict]:
        return await tracker_tool.get_portfolio_history(_storage(), account_id, limit)

    @mcp.tool(
        name="get_portfolio_summary",
        description=(
            "Return an aggregated portfolio summary for an account over the last N days. "
            "Includes total value now vs. start of period, delta in RUB/%, "
            "and per-position expected yield delta (sorted best to worst)."
        ),
    )
    async def get_portfolio_summary(account_id: str, days: int = 7) -> dict:
        return await tracker_tool.get_portfolio_summary(_storage(), account_id, days)

    return mcp


def _run_http(server: FastMCP, settings: Settings) -> None:
    import uvicorn
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if settings.mcp_token:
                auth = request.headers.get("Authorization", "")
                if auth != f"Bearer {settings.mcp_token}":
                    return Response("Unauthorized", status_code=401)
            return await call_next(request)

    app = server.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    uvicorn.run(app, host=settings.http_host, port=settings.http_port, log_level="info")


def main() -> None:
    _configure_logging()
    settings = load_settings()
    server = build_server(settings)
    if settings.transport == "http":
        _run_http(server, settings)
    else:
        server.run()


if __name__ == "__main__":
    main()

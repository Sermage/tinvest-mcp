import logging
from contextlib import asynccontextmanager
from typing import Literal

import structlog
from mcp.server.fastmcp import FastMCP

from tinvest_mcp.config import Settings, load_settings
from tinvest_mcp.tinvest.client import TInvestClient, make_http_client
from tinvest_mcp.tools import accounts as accounts_tool
from tinvest_mcp.tools import instruments as instruments_tool
from tinvest_mcp.tools import market_data as market_data_tool
from tinvest_mcp.tools import operations as operations_tool
from tinvest_mcp.tools import portfolio as portfolio_tool
from tinvest_mcp.tools import positions as positions_tool

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


def build_server(settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_: FastMCP):
        http = make_http_client(settings)
        try:
            yield {"client": TInvestClient(settings, http)}
        finally:
            await http.aclose()

    mcp = FastMCP("tinvest-mcp", lifespan=lifespan)

    def _client() -> TInvestClient:
        return mcp.get_context().request_context.lifespan_context["client"]

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

    return mcp


def main() -> None:
    _configure_logging()
    settings = load_settings()
    server = build_server(settings)
    server.run()


if __name__ == "__main__":
    main()

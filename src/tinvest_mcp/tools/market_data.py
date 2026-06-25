from tinvest_mcp.tinvest.client import TInvestClient
from tinvest_mcp.tinvest.money import quotation_to_decimal


async def get_last_prices(
    client: TInvestClient,
    figi: list[str] | None = None,
    instrument_id: list[str] | None = None,
) -> list[dict]:
    body: dict = {}
    if figi:
        body["figi"] = figi
    if instrument_id:
        body["instrumentId"] = instrument_id
    data = await client.call("MarketDataService", "GetLastPrices", body)
    return [
        {
            "figi": p.get("figi"),
            "instrument_uid": p.get("instrumentUid"),
            "price": str(quotation_to_decimal(p.get("price"))),
            "time": p.get("time"),
            "last_price_type": p.get("lastPriceType"),
        }
        for p in data.get("lastPrices", [])
    ]


async def get_candles(
    client: TInvestClient,
    from_: str,
    to: str,
    interval: str,
    figi: str | None = None,
    instrument_id: str | None = None,
) -> list[dict]:
    body: dict = {"from": from_, "to": to, "interval": interval}
    if figi:
        body["figi"] = figi
    if instrument_id:
        body["instrumentId"] = instrument_id
    data = await client.call("MarketDataService", "GetCandles", body)
    return [
        {
            "time": c.get("time"),
            "open": str(quotation_to_decimal(c.get("open"))),
            "high": str(quotation_to_decimal(c.get("high"))),
            "low": str(quotation_to_decimal(c.get("low"))),
            "close": str(quotation_to_decimal(c.get("close"))),
            "volume": c.get("volume"),
            "is_complete": c.get("isComplete"),
        }
        for c in data.get("candles", [])
    ]

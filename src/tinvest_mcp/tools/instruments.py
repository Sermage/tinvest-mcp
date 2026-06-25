from tinvest_mcp.tinvest.client import TInvestClient


async def find_instrument(
    client: TInvestClient,
    query: str,
    instrument_kind: str | None = None,
    api_trade_available_flag: bool | None = None,
) -> list[dict]:
    body: dict = {"query": query}
    if instrument_kind:
        body["instrumentKind"] = instrument_kind
    if api_trade_available_flag is not None:
        body["apiTradeAvailableFlag"] = api_trade_available_flag
    data = await client.call("InstrumentsService", "FindInstrument", body)
    return [
        {
            "figi": i.get("figi"),
            "ticker": i.get("ticker"),
            "class_code": i.get("classCode"),
            "isin": i.get("isin"),
            "instrument_type": i.get("instrumentType"),
            "instrument_kind": i.get("instrumentKind"),
            "name": i.get("name"),
            "uid": i.get("uid"),
            "position_uid": i.get("positionUid"),
            "api_trade_available_flag": i.get("apiTradeAvailableFlag"),
            "for_qual_investor_flag": i.get("forQualInvestorFlag"),
        }
        for i in data.get("instruments", [])
    ]

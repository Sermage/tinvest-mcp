from tinvest_mcp.tinvest.client import TInvestClient
from tinvest_mcp.tinvest.money import money_to_str, quotation_to_decimal


def _position(p: dict) -> dict:
    return {
        "figi": p.get("figi"),
        "instrument_type": p.get("instrumentType"),
        "instrument_uid": p.get("instrumentUid"),
        "ticker": p.get("ticker"),
        "quantity": str(quotation_to_decimal(p.get("quantity"))),
        "average_position_price": money_to_str(p.get("averagePositionPrice")),
        "current_price": money_to_str(p.get("currentPrice")),
        "current_nkd": money_to_str(p.get("currentNkd")),
        "expected_yield": str(quotation_to_decimal(p.get("expectedYield"))),
    }


async def get_portfolio(client: TInvestClient, account_id: str) -> dict:
    data = await client.call(
        "OperationsService", "GetPortfolio", {"accountId": account_id}
    )
    return {
        "account_id": account_id,
        "total_amount_portfolio": money_to_str(data.get("totalAmountPortfolio")),
        "total_amount_shares": money_to_str(data.get("totalAmountShares")),
        "total_amount_bonds": money_to_str(data.get("totalAmountBonds")),
        "total_amount_etf": money_to_str(data.get("totalAmountEtf")),
        "total_amount_currencies": money_to_str(data.get("totalAmountCurrencies")),
        "total_amount_futures": money_to_str(data.get("totalAmountFutures")),
        "expected_yield": str(quotation_to_decimal(data.get("expectedYield"))),
        "positions": [_position(p) for p in data.get("positions", [])],
    }

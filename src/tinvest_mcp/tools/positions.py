from tinvest_mcp.tinvest.client import TInvestClient
from tinvest_mcp.tinvest.money import money_to_str, quotation_to_decimal


async def get_positions(client: TInvestClient, account_id: str) -> dict:
    data = await client.call(
        "OperationsService", "GetPositions", {"accountId": account_id}
    )
    return {
        "account_id": account_id,
        "money": [money_to_str(m) for m in data.get("money", [])],
        "blocked": [money_to_str(m) for m in data.get("blocked", [])],
        "securities": [
            {
                "figi": s.get("figi"),
                "instrument_type": s.get("instrumentType"),
                "balance": s.get("balance"),
                "blocked": s.get("blocked"),
            }
            for s in data.get("securities", [])
        ],
        "limits_loading_in_progress": data.get("limitsLoadingInProgress"),
        "futures": [
            {
                "figi": f.get("figi"),
                "balance": f.get("balance"),
                "blocked": f.get("blocked"),
            }
            for f in data.get("futures", [])
        ],
        "options": [
            {
                "figi": o.get("figi"),
                "balance": o.get("balance"),
                "blocked": o.get("blocked"),
            }
            for o in data.get("options", [])
        ],
    }

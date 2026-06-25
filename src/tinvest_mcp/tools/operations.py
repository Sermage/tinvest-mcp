from tinvest_mcp.tinvest.client import TInvestClient
from tinvest_mcp.tinvest.money import money_to_str

OPERATION_STATE_DEFAULT = "OPERATION_STATE_EXECUTED"


async def get_operations(
    client: TInvestClient,
    account_id: str,
    from_: str,
    to: str,
    state: str = OPERATION_STATE_DEFAULT,
    figi: str | None = None,
) -> list[dict]:
    body: dict = {
        "accountId": account_id,
        "from": from_,
        "to": to,
        "state": state,
    }
    if figi:
        body["figi"] = figi
    data = await client.call("OperationsService", "GetOperations", body)
    return [
        {
            "id": op.get("id"),
            "parent_operation_id": op.get("parentOperationId"),
            "date": op.get("date"),
            "type": op.get("operationType"),
            "type_text": op.get("type"),
            "state": op.get("state"),
            "payment": money_to_str(op.get("payment")),
            "price": money_to_str(op.get("price")),
            "quantity": op.get("quantity"),
            "quantity_rest": op.get("quantityRest"),
            "figi": op.get("figi"),
            "instrument_type": op.get("instrumentType"),
            "currency": op.get("currency"),
        }
        for op in data.get("operations", [])
    ]

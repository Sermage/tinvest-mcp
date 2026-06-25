from tinvest_mcp.tinvest.client import TInvestClient


async def get_accounts(client: TInvestClient) -> list[dict]:
    data = await client.call("UsersService", "GetAccounts")
    return [
        {
            "id": acc.get("id"),
            "type": acc.get("type"),
            "name": acc.get("name"),
            "status": acc.get("status"),
            "access_level": acc.get("accessLevel"),
            "opened_date": acc.get("openedDate"),
            "closed_date": acc.get("closedDate"),
        }
        for acc in data.get("accounts", [])
    ]

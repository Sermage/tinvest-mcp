from typing import Any

import httpx

from tinvest_mcp.config import Settings

PROD_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"
SANDBOX_BASE_URL = "https://invest-public-api.tinkoff.ru/rest"
SERVICE_PREFIX = "tinkoff.public.invest.api.contract.v1"


class TInvestError(RuntimeError):
    def __init__(self, status_code: int, payload: Any) -> None:
        super().__init__(f"T-Invest API error {status_code}: {payload}")
        self.status_code = status_code
        self.payload = payload


class TInvestClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def call(self, service: str, method: str, body: dict | None = None) -> dict:
        url = f"{PROD_BASE_URL}/{SERVICE_PREFIX}.{service}/{method}"
        response = await self._http.post(url, json=body or {})
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise TInvestError(response.status_code, payload)
        return response.json()


def make_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {settings.token}",
            "Content-Type": "application/json",
            "x-app-name": settings.app_name,
        },
        timeout=httpx.Timeout(30.0, connect=10.0),
    )

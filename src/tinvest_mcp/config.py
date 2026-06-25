from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        env_prefix="TINVEST_",
        extra="ignore",
    )

    token: str = Field(..., description="T-Invest API token")
    sandbox: bool = Field(False, description="Use sandbox endpoint")
    readonly: bool = Field(True, description="Block any order-placing tools")
    app_name: str = Field("tinvest-mcp", description="x-app-name header value")
    snapshot_interval: int = Field(60, description="Portfolio snapshot interval in minutes")
    db_path: Path = Field(
        default_factory=lambda: _PROJECT_ROOT / "data" / "snapshots.db",
        description="Path to SQLite database file",
    )
    transport: str = Field("stdio", description="MCP transport: stdio or http")
    http_port: int = Field(8000, description="HTTP transport port")
    mcp_token: str = Field("", description="Bearer token for HTTP transport auth")


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

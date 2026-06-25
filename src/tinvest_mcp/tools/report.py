"""Pipeline tool: fetch portfolio → aggregate → save HTML report."""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from tinvest_mcp.storage import SnapshotStorage
from tinvest_mcp.tinvest.client import TInvestClient
from tinvest_mcp.tools import portfolio as portfolio_tool


# ── Step 1: search ────────────────────────────────────────────────────────────

async def _fetch(client: TInvestClient, account_id: str) -> dict:
    return await portfolio_tool.get_portfolio(client, account_id)


# ── Step 2: summarize ─────────────────────────────────────────────────────────

def _to_decimal(value: str | None) -> Decimal:
    try:
        return Decimal(str(value).split()[0]) if value else Decimal(0)
    except InvalidOperation:
        return Decimal(0)


def _aggregate(raw: dict) -> dict:
    positions = raw.get("positions", [])

    by_type: dict[str, list[dict]] = {}
    for p in positions:
        kind = p.get("instrument_type", "unknown")
        by_type.setdefault(kind, []).append(p)

    rows = []
    total_yield = Decimal(0)
    for p in positions:
        qty = _to_decimal(p.get("quantity"))
        price = _to_decimal(p.get("current_price"))
        avg = _to_decimal(p.get("average_position_price"))
        yld = _to_decimal(p.get("expected_yield"))
        market_value = qty * price
        total_yield += yld
        rows.append(
            {
                "ticker": p.get("ticker") or p.get("figi", "—"),
                "type": p.get("instrument_type", "—"),
                "qty": float(qty),
                "avg_price": float(avg),
                "current_price": float(price),
                "market_value": float(market_value),
                "expected_yield": float(yld),
            }
        )

    rows.sort(key=lambda r: r["expected_yield"], reverse=True)

    return {
        "account_id": raw["account_id"],
        "total_portfolio": raw.get("total_amount_portfolio", "—"),
        "total_bonds": raw.get("total_amount_bonds", "—"),
        "total_shares": raw.get("total_amount_shares", "—"),
        "total_etf": raw.get("total_amount_etf", "—"),
        "total_currencies": raw.get("total_amount_currencies", "—"),
        "expected_yield_total": raw.get("expected_yield", "0"),
        "positions": rows,
        "type_counts": {k: len(v) for k, v in by_type.items()},
    }


# ── Step 3: save to file ──────────────────────────────────────────────────────

def _render_html(summary: dict, generated_at: str) -> str:
    def row_class(yld: float) -> str:
        if yld > 0:
            return "pos"
        if yld < 0:
            return "neg"
        return ""

    rows_html = ""
    for p in summary["positions"]:
        cls = row_class(p["expected_yield"])
        sign = "+" if p["expected_yield"] > 0 else ""
        rows_html += f"""
        <tr class="{cls}">
          <td>{p['ticker']}</td>
          <td>{p['type']}</td>
          <td>{p['qty']:.2f}</td>
          <td>{p['avg_price']:,.2f}</td>
          <td>{p['current_price']:,.2f}</td>
          <td>{p['market_value']:,.2f}</td>
          <td>{sign}{p['expected_yield']:,.2f}</td>
        </tr>"""

    type_badges = " ".join(
        f'<span class="badge">{k}: {v}</span>'
        for k, v in summary["type_counts"].items()
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Portfolio Report — {summary['account_id']}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f1117; color: #e0e0e0; padding: 32px; }}
    h1 {{ font-size: 1.6rem; margin-bottom: 4px; }}
    .meta {{ color: #888; font-size: .85rem; margin-bottom: 24px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
    .card {{ background: #1a1d27; border-radius: 10px; padding: 16px 20px; min-width: 180px; }}
    .card-label {{ font-size: .75rem; color: #888; text-transform: uppercase; letter-spacing: .05em; }}
    .card-value {{ font-size: 1.25rem; font-weight: 600; margin-top: 4px; }}
    .badges {{ margin-bottom: 20px; }}
    .badge {{ background: #252836; border-radius: 20px; padding: 4px 12px;
              font-size: .8rem; margin-right: 8px; color: #aaa; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #1a1d27; padding: 10px 12px; text-align: left;
          font-size: .8rem; color: #888; text-transform: uppercase; letter-spacing: .04em; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #1e2130; font-size: .9rem; }}
    tr:hover td {{ background: #1a1d27; }}
    tr.pos td:last-child {{ color: #4caf82; font-weight: 600; }}
    tr.neg td:last-child {{ color: #e05c5c; font-weight: 600; }}
    .yield-total {{ margin-top: 16px; text-align: right; font-size: .95rem; color: #888; }}
    .yield-total span {{ color: #e0e0e0; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>Portfolio Report</h1>
  <div class="meta">Account {summary['account_id']} &nbsp;·&nbsp; Generated {generated_at}</div>

  <div class="cards">
    <div class="card">
      <div class="card-label">Total portfolio</div>
      <div class="card-value">{summary['total_portfolio']}</div>
    </div>
    <div class="card">
      <div class="card-label">Bonds</div>
      <div class="card-value">{summary['total_bonds']}</div>
    </div>
    <div class="card">
      <div class="card-label">Shares</div>
      <div class="card-value">{summary['total_shares']}</div>
    </div>
    <div class="card">
      <div class="card-label">ETF</div>
      <div class="card-value">{summary['total_etf']}</div>
    </div>
    <div class="card">
      <div class="card-label">Currencies</div>
      <div class="card-value">{summary['total_currencies']}</div>
    </div>
  </div>

  <div class="badges">{type_badges}</div>

  <table>
    <thead>
      <tr>
        <th>Ticker</th><th>Type</th><th>Qty</th>
        <th>Avg Price</th><th>Current Price</th><th>Market Value</th><th>P&amp;L</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <div class="yield-total">
    Expected yield total: <span>{summary['expected_yield_total']}</span>
  </div>
</body>
</html>"""


async def generate_portfolio_report(
    client: TInvestClient,
    storage: SnapshotStorage,
    account_id: str,
    output_path: str,
) -> dict:
    """Pipeline: fetch → aggregate → save HTML report."""

    # Step 1 — search (fetch raw portfolio)
    raw = await _fetch(client, account_id)

    # Step 2 — summarize (aggregate positions)
    summary = _aggregate(raw)

    # Step 3 — save to file (render HTML)
    path = pathlib.Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = _render_html(summary, generated_at)
    path.write_text(html, encoding="utf-8")

    return {
        "status": "ok",
        "report_path": str(path),
        "account_id": account_id,
        "positions_count": len(summary["positions"]),
        "total_portfolio": summary["total_portfolio"],
        "generated_at": generated_at,
        "html_content": html,
    }

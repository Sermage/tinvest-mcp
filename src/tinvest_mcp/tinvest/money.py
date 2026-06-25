from decimal import Decimal


def quotation_to_decimal(q: dict | None) -> Decimal | None:
    """Convert T-Invest Quotation/MoneyValue JSON {units, nano} to Decimal."""
    if not q:
        return None
    units = Decimal(str(q.get("units", "0")))
    nano = Decimal(str(q.get("nano", 0))) / Decimal(1_000_000_000)
    return units + nano


def money_to_str(m: dict | None) -> str | None:
    if not m:
        return None
    value = quotation_to_decimal(m)
    if value is None:
        return None
    currency = (m.get("currency") or "").upper()
    return f"{value} {currency}".strip()

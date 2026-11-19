"""Build the D2 tag value (Common Currency table) from a currency-rate CSV.

Each entry is 5 bytes, written as hex:

    CCCC MMMM EE

* ``CCCC`` – ISO 4217 numeric currency code, zero-padded to 4 digits
* ``MMMM`` – rate mantissa, 4 BCD digits
* ``EE``   – ``0x80 | decimals``; rate = mantissa / 10**decimals

The rate is expressed as units of the *base* currency per 1 unit of the entry
currency. The CSV (moneymaster.csv) carries rates as units of currency per USD,
so ``rate = base_per_usd / currency_per_usd``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

_MAX_MANTISSA = 9999
_MAX_DECIMALS = 15
DEFAULT_BASE = "978"  # EUR


@dataclass
class CurrencyRate:
    code: str       # ISO alpha-3, e.g. "EUR"
    numeric: str    # ISO numeric, 3 digits, e.g. "978"
    name: str
    per_usd: Decimal  # units of this currency per 1 USD


def load_currency_rates(path: str | Path) -> dict[str, CurrencyRate]:
    """Read moneymaster.csv; return rates keyed by numeric code (first row wins)."""
    result: dict[str, CurrencyRate] = {}
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for raw in csv.DictReader(fh):
            row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
            numeric = row.get("Currency No Code", "")
            code = row.get("Currency Char 3 Code", "")
            if not numeric.isdigit() or not code:
                continue
            numeric = numeric.zfill(3)
            if numeric in result:
                continue
            try:
                per_usd = Decimal(row.get("rate", ""))
            except InvalidOperation:
                continue
            if per_usd <= 0:
                continue
            result[numeric] = CurrencyRate(code, numeric, row.get("Currency Name", ""), per_usd)
    return result


def cross_rate(base: CurrencyRate, cur: CurrencyRate) -> Decimal:
    """Units of *base* per 1 unit of *cur*."""
    return base.per_usd / cur.per_usd


def default_decimals(value: Decimal) -> int:
    """3 decimals normally, 4 for rates below 0.1; adjusted so the mantissa fits 4 digits."""
    decimals = 3 if value >= Decimal("0.1") else 4
    while decimals < _MAX_DECIMALS and _mantissa(value, decimals) < 10 and value >= Decimal(10) ** -_MAX_DECIMALS:
        decimals += 1
    while decimals > 0 and _mantissa(value, decimals) > _MAX_MANTISSA:
        decimals -= 1
    return decimals


def _mantissa(value: Decimal, decimals: int) -> int:
    return int((value * (Decimal(10) ** decimals)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def encode_entry(numeric: str, value: Decimal, decimals: int | None = None) -> str:
    """Return the 10-hex-digit entry for a currency; raises ValueError if it can't be encoded."""
    if decimals is None:
        decimals = default_decimals(value)
    if not 0 <= decimals <= _MAX_DECIMALS:
        raise ValueError(f"Decimals must be 0..{_MAX_DECIMALS}")
    mantissa = _mantissa(value, decimals)
    if not 0 <= mantissa <= _MAX_MANTISSA:
        raise ValueError(f"Rate {value} does not fit 4 digits with {decimals} decimals")
    return f"{int(numeric):04d}{mantissa:04d}{0x80 | decimals:02X}"


def build_d2_value(entries: list[str]) -> str:
    """Concatenate encoded entries into the D2 tag value."""
    return "".join(entries)


def decode_d2_value(hex_str: str) -> list[tuple[str, Decimal]]:
    """Split a D2 value into ``(numeric_code, rate)`` pairs."""
    s = "".join(hex_str.split()).upper()
    if len(s) % 10 or any(c not in "0123456789ABCDEF" for c in s):
        raise ValueError("D2 value must be hex made of 5-byte entries")
    out = []
    for i in range(0, len(s), 10):
        cur, mant, exp = s[i:i + 4], s[i + 4:i + 8], int(s[i + 8:i + 10], 16)
        if not (cur + mant).isdigit() or not exp & 0x80:
            raise ValueError(f"Malformed entry at offset {i // 2}: {s[i:i + 10]}")
        out.append((cur[1:], Decimal(int(mant)) / (Decimal(10) ** (exp & 0x7F))))
    return out

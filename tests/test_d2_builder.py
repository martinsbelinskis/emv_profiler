"""Tests for the D2 tag (Common Currency table) builder."""

from decimal import Decimal

import pytest

from emv_profiler.d2_builder import (
    build_d2_value,
    cross_rate,
    decode_d2_value,
    default_decimals,
    encode_entry,
    load_currency_rates,
)

EXAMPLE = (
    "09490029830826117783084009228309850235830975051183020300408307840251"
    "83094100858409460201830702068483037602528309520015840752086884098103"
    "36830578087884039800208407640252840348002684020801348307561008" "83"
)


def test_example_roundtrip_with_explicit_decimals():
    pairs = decode_d2_value(EXAMPLE)
    assert len(pairs) == 20
    rebuilt = []
    for i, (numeric, rate) in enumerate(pairs):
        decimals = int(EXAMPLE[i * 10 + 8:i * 10 + 10], 16) & 0x7F
        rebuilt.append(encode_entry(numeric, rate, decimals))
    assert build_d2_value(rebuilt) == EXAMPLE


def test_default_decimals_and_rounding():
    assert encode_entry("826", Decimal("1.1774")) == "0826117783"
    assert encode_entry("752", Decimal("0.08684")) == "0752086884"
    assert encode_entry("348", Decimal("0.00264")) == "0348002684"
    assert default_decimals(Decimal("12.5")) == 2
    assert encode_entry("8", Decimal("12.5")) == "0008125082"


def test_encode_rejects_overflow():
    with pytest.raises(ValueError):
        encode_entry("826", Decimal("12345"), 0)


def test_load_rates_and_cross_rate(tmp_path):
    csv_path = tmp_path / "moneymaster.csv"
    csv_path.write_text(
        "Country Name, Currency Name,Country Char 2 Code,Country Char 3 Code,"
        "Country No Code,Currency Char 3 Code,Currency No Code,Exponent,"
        "Issue Exponent, Effective Date,Expiration Date, rate, date\r\n"
        "X,US Dollar,US,USA,840,USD,840,2,,,,1,03/24/2026\r\n"
        "X,Euro,AT,AUT,040,EUR,978,2,,,,0.8,03/24/2026\r\n"
        "X,Lek,AL,ALB,008,ALL,8,2,,,,80,03/24/2026\r\n"
        "X,Euro dup,AD,AND,020,EUR,978,2,,,,9,03/24/2026\r\n",
        encoding="utf-8",
    )
    rates = load_currency_rates(csv_path)
    assert set(rates) == {"840", "978", "008"}
    assert rates["978"].per_usd == Decimal("0.8")
    assert cross_rate(rates["978"], rates["840"]) == Decimal("0.8")
    assert cross_rate(rates["978"], rates["008"]) == Decimal("0.01")

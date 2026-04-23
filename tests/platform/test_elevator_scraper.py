"""Unit tests for elevator_scraper._parse().

These tests exercise the pure parsing logic without hitting the network,
Selenium, or any database.  The API JSON fixture matches the actual RVC
response structure documented in scraper.py.
"""

from datetime import datetime, timezone

import pytest

from farm_platform.feeds.elevator_scraper import _parse

# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_JSON = {
    "locations": [
        {
            "name": "Toulon",
            "commodities": [
                {
                    "commodity_name": "Corn",
                    "cash_bids": [
                        {
                            "cash_price": "4.0100",
                            "basis": "-0.3900",
                            "futures_price": "4.4025",
                            "contract_date": "Dec",
                            "delivery_start": "2025-11-30T18:00:00-06:00",
                            "delivery_end": "2025-12-30T18:00:00-06:00",
                            "created": "2026-01-07T16:45:06.378484-06:00",
                            "modified": "2026-01-07T16:45:06.378497-06:00",
                        },
                        {
                            "cash_price": "4.1500",
                            "basis": "-0.2500",
                            "futures_price": "4.4025",
                            "contract_date": "Mar",
                            "delivery_start": "2026-02-28T18:00:00-06:00",
                            "delivery_end": "2026-03-30T18:00:00-06:00",
                            "created": "2026-01-07T16:45:06.378484-06:00",
                            "modified": "2026-01-07T16:45:06.378497-06:00",
                        },
                    ],
                },
                {
                    "commodity_name": "Soybeans",
                    "cash_bids": [
                        {
                            "cash_price": "10.2500",
                            "basis": "-0.6000",
                            "futures_price": "10.8500",
                            "contract_date": "Jan",
                            "delivery_start": "2025-12-31T18:00:00-06:00",
                            "delivery_end": "2026-01-30T18:00:00-06:00",
                            "created": "2026-01-07T22:00:00.000000+00:00",
                            "modified": "2026-01-07T22:00:00.000000+00:00",
                        }
                    ],
                },
            ],
        },
        {
            "name": "Kewanee",
            "commodities": [
                {
                    "commodity_name": "Corn",
                    "cash_bids": [
                        {
                            "cash_price": "3.9800",
                            "basis": "-0.4200",
                            "futures_price": "4.4025",
                            "contract_date": "Dec",
                            "created": "2026-01-07T16:45:06.378484-06:00",
                            "modified": "2026-01-07T16:45:06.378497-06:00",
                        }
                    ],
                }
            ],
        },
        {
            "name": "SomeOtherElevator",
            "commodities": [
                {
                    "commodity_name": "Corn",
                    "cash_bids": [
                        {
                            "cash_price": "3.9000",
                            "basis": "-0.5000",
                            "futures_price": "4.4025",
                            "contract_date": "Dec",
                            "created": "2026-01-07T16:45:06.378484-06:00",
                            "modified": "2026-01-07T16:45:06.378497-06:00",
                        }
                    ],
                }
            ],
        },
    ]
}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_parse_filters_to_configured_elevators() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    elevators = {r["elevator"] for r in records}
    assert elevators == {"Toulon"}
    assert "SomeOtherElevator" not in elevators
    assert "Kewanee" not in elevators


def test_parse_multiple_elevators() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon", "Kewanee"])
    elevators = {r["elevator"] for r in records}
    assert "Toulon" in elevators
    assert "Kewanee" in elevators


def test_parse_commodity_names_normalised() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    commodities = {r["commodity"] for r in records}
    assert commodities == {"corn", "soybeans"}


def test_parse_cash_price_type() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    for rec in records:
        assert isinstance(rec["cash_price"], float)
        assert rec["cash_price"] > 0


def test_parse_basis_correct() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    corn_dec = next(
        r for r in records if r["elevator"] == "Toulon"
        and r["commodity"] == "corn"
        and r["contract_month"] == "Dec"
    )
    assert corn_dec["basis"] == pytest.approx(-0.39, abs=1e-4)
    # basis = cash - futures_ref
    assert corn_dec["cash_price"] == pytest.approx(4.01, abs=1e-4)
    assert corn_dec["futures_ref"] == pytest.approx(4.4025, abs=1e-4)


def test_parse_basis_equals_cash_minus_futures() -> None:
    """Basis from API should equal cash_price - futures_ref."""
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    for rec in records:
        if rec["basis"] is not None and rec["futures_ref"] is not None:
            expected = rec["cash_price"] - rec["futures_ref"]
            assert rec["basis"] == pytest.approx(expected, abs=0.005), (
                f"Basis mismatch for {rec['elevator']} {rec['commodity']} "
                f"{rec['contract_month']}: got {rec['basis']}, expected {expected:.4f}"
            )


def test_parse_contract_month_present() -> None:
    records, _ = _parse(SAMPLE_JSON, ["Toulon"])
    months = {r["contract_month"] for r in records}
    assert "Dec" in months
    assert "Mar" in months
    assert "Jan" in months


def test_parse_scraped_at_uses_latest_created() -> None:
    """scraped_at should be the most recent 'created' timestamp across parsed bids."""
    records, scraped_at = _parse(SAMPLE_JSON, ["Toulon"])
    # Corn bids: "2026-01-07T16:45:06.378484-06:00" → UTC = 2026-01-07T22:45:06.378484Z
    # Soybean bid: "2026-01-07T22:00:00+00:00" → UTC = 2026-01-07T22:00:00Z
    # Corn bids are later, so scraped_at should be the corn bid timestamp.
    assert scraped_at == datetime(2026, 1, 7, 22, 45, 6, 378484, tzinfo=timezone.utc)


def test_parse_empty_json() -> None:
    records, scraped_at = _parse({}, ["Toulon"])
    assert records == []
    assert scraped_at.tzinfo is not None  # Falls back to now()


def test_parse_no_matching_elevator() -> None:
    records, _ = _parse(SAMPLE_JSON, ["NonExistent"])
    assert records == []


def test_parse_missing_cash_price_skipped() -> None:
    bad_json = {
        "locations": [
            {
                "name": "Toulon",
                "commodities": [
                    {
                        "commodity_name": "Corn",
                        "cash_bids": [
                            {"basis": "-0.39", "futures_price": "4.40", "contract_date": "Dec"}
                        ],
                    }
                ],
            }
        ]
    }
    records, _ = _parse(bad_json, ["Toulon"])
    assert records == []


def test_parse_zero_cash_price_skipped() -> None:
    bad_json = {
        "locations": [
            {
                "name": "Toulon",
                "commodities": [
                    {
                        "commodity_name": "Corn",
                        "cash_bids": [
                            {"cash_price": "0.0000", "contract_date": "Dec"}
                        ],
                    }
                ],
            }
        ]
    }
    records, _ = _parse(bad_json, ["Toulon"])
    assert records == []


def test_parse_case_insensitive_elevator_match() -> None:
    records, _ = _parse(SAMPLE_JSON, ["toulon"])
    assert len(records) > 0
    # Canonical name should be the configured one (lowercase preserved)
    assert all(r["elevator"] == "toulon" for r in records)


def test_parse_unknown_commodity_skipped() -> None:
    weird_json = {
        "locations": [
            {
                "name": "Toulon",
                "commodities": [
                    {
                        "commodity_name": "Wheat",
                        "cash_bids": [{"cash_price": "5.20", "contract_date": "Dec"}],
                    }
                ],
            }
        ]
    }
    records, _ = _parse(weird_json, ["Toulon"])
    assert records == []


def test_parse_optional_fields_none_when_missing() -> None:
    minimal_json = {
        "locations": [
            {
                "name": "Toulon",
                "commodities": [
                    {
                        "commodity_name": "Corn",
                        "cash_bids": [{"cash_price": "4.10"}],
                    }
                ],
            }
        ]
    }
    records, _ = _parse(minimal_json, ["Toulon"])
    assert len(records) == 1
    assert records[0]["futures_ref"] is None
    assert records[0]["basis"] is None
    assert records[0]["contract_month"] is None

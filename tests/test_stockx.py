"""Tests for the StockX CSV client (stub mode + parsing helpers + real CSV)."""

from __future__ import annotations

from datetime import date

from ingestion.stockx import StockXClient, StockXSale, clean_name, top_shoe_names


def test_stub_yields_valid_sales() -> None:
    sales = list(StockXClient(stub=True).fetch_sales(limit=20))
    assert len(sales) == 20
    assert all(isinstance(s, StockXSale) for s in sales)
    assert all(s.sold_price > 0 for s in sales)
    assert all(s.retail_price is not None for s in sales)
    assert all(s.sold_date >= s.release_date for s in sales)


def test_stub_is_deterministic() -> None:
    a = [s.sold_price for s in StockXClient(stub=True).fetch_sales(limit=10)]
    b = [s.sold_price for s in StockXClient(stub=True).fetch_sales(limit=10)]
    assert a == b


def test_clean_name_normalizes_slug() -> None:
    assert clean_name("Adidas-Yeezy-Boost-350-V2-Zebra") == "Adidas Yeezy Boost 350 V2 Zebra"


def test_top_shoe_names_ranks_by_volume() -> None:
    sales = list(StockXClient(stub=True).fetch_sales(limit=40))
    top = top_shoe_names(sales, 2)
    assert len(top) == 2
    # Stub cycles 4 shoes evenly, so the most common are valid shoe names.
    assert all(isinstance(name, str) and name for name in top)


def test_money_and_date_parsing() -> None:
    assert StockXClient._parse_money("$1,097.00") == 1097.0
    assert StockXClient._parse_money("220") == 220.0
    assert StockXClient._parse_money("") is None
    assert StockXClient._parse_date("2017-09-01") == date(2017, 9, 1)
    assert StockXClient._parse_date("9/1/2017") == date(2017, 9, 1)
    assert StockXClient._parse_date("") is None


def test_reads_real_csv(tmp_path) -> None:
    csv = tmp_path / "stockx.csv"
    csv.write_text(
        "Order Date,Brand,Sneaker Name,Sale Price,Retail Price,"
        "Release Date,Shoe Size,Buyer Region\n"
        "9/1/2017,Yeezy,Adidas-Yeezy-Boost-350-Low-V2-Beluga,"
        "1097,220,9/24/2016,11.0,California\n",
        encoding="utf-8",
    )
    sales = list(StockXClient(csv).fetch_sales())
    assert len(sales) == 1
    s = sales[0]
    # Slug is normalized into the conformed dim_shoes key.
    assert s.search_term == "Adidas Yeezy Boost 350 Low V2 Beluga"
    assert s.sold_price == 1097.0
    assert s.retail_price == 220.0
    assert s.sold_date == date(2017, 9, 1)
    assert s.release_date == date(2016, 9, 24)
    assert s.size == 11.0
    assert s.buyer_region == "California"

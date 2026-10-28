"""Characterisation tests for clean_rows (exercise 03).

These record what clean_rows does *today*, not what it should do. Tests marked
`# BUG?` pin behaviour that looks wrong. Expect to update them when the bug is
fixed - that's the warning they are here to give.

Each row is a list of strings, exactly as csv.reader returns it. Most branches
use the column order:

    transaction_id, timestamp, till_id, product, quantity, unit_price

Dublin uses:

    timestamp, product, unit_price, quantity, till_id, transaction_id
"""

from kettle.transform import clean_rows

# --- the happy path -----------------------------------------------------------


def test_leeds_row_is_cleaned_into_a_dict():
    rows = [["LDS-1", "14/09/2026 07:01", "T2", "Americano", "2", "3.00"]]

    assert clean_rows(rows, "leeds") == [
        {
            "transaction_id": "LDS-1",
            "branch": "leeds",
            "sold_at": "2026-09-14T07:01:00",
            "till_id": "T2",
            "product": "Americano",
            "quantity": 2,
            "unit_price_pence": 300,
            "line_total_pence": 600,
        }
    ]


def test_leeds_and_york_timestamps_are_day_first():
    # 01/02 is the 1st of February, not the 2nd of January
    rows = [["X-1", "01/02/2026 09:30", "T1", "Latte", "1", "3.50"]]

    assert clean_rows(rows, "leeds")[0]["sold_at"] == "2026-02-01T09:30:00"
    assert clean_rows(rows, "york")[0]["sold_at"] == "2026-02-01T09:30:00"


def test_manchester_timestamps_are_iso_and_prices_are_in_pence():
    rows = [["MAN-1", "2026-09-14T07:20:00", "T2", "Latte", "1", "350"]]

    row = clean_rows(rows, "manchester")[0]

    assert row["sold_at"] == "2026-09-14T07:20:00"
    assert row["unit_price_pence"] == 350


def test_manchester_price_in_pounds_is_dropped():
    # int("3.50") raises, and the error is swallowed
    rows = [["MAN-1", "2026-09-14T07:20:00", "T2", "Latte", "1", "3.50"]]

    assert clean_rows(rows, "manchester") == []


def test_dublin_columns_are_read_in_dublin_order():
    rows = [["2026-09-14T07:09:00", "Espresso", "2.00", "3", "T1", "DUB-1"]]

    row = clean_rows(rows, "dublin", eur_rate=1.0)[0]

    assert row["transaction_id"] == "DUB-1"
    assert row["sold_at"] == "2026-09-14T07:09:00"
    assert row["till_id"] == "T1"
    assert row["product"] == "Espresso"
    assert row["quantity"] == 3
    assert row["unit_price_pence"] == 200


def test_dublin_euro_price_is_multiplied_by_the_rate():
    # BUG? see KC-101. The rate is GBP -> EUR (1 GBP = 1.25 EUR), so EUR 4.00
    # should be GBP 3.20 (400 / 1.25 = 320p). The code multiplies instead.
    rows = [["2026-09-14T07:09:00", "Espresso", "4.00", "1", "T1", "DUB-1"]]

    row = clean_rows(rows, "dublin", eur_rate=1.25)[0]

    assert row["unit_price_pence"] == 500  # 400 * 1.25
    assert row["line_total_pence"] == 500


# --- quantities ---------------------------------------------------------------


def test_negative_quantity_becomes_positive():
    # BUG? see KC-102. A negative quantity looks like a refund, but abs()
    # turns it into a sale, adding GBP 3.20 instead of taking it away.
    rows = [["LDS-1", "14/09/2026 08:38", "T1", "Hot Chocolate", "-1", "3.20"]]

    row = clean_rows(rows, "leeds")[0]

    assert row["quantity"] == 1
    assert row["line_total_pence"] == 320


# --- product names ------------------------------------------------------------


def test_product_name_is_stripped_and_title_cased():
    rows = [["LDS-1", "14/09/2026 07:01", "T1", "  flat white ", "1", "3.40"]]

    assert clean_rows(rows, "leeds")[0]["product"] == "Flat White"


def test_product_name_is_not_matched_against_the_catalogue():
    # BUG? see KC-103. The catalogue has "Flat White" (alias "flat wht") and
    # "Pain au Chocolat", but the code only title-cases.
    rows = [
        ["LDS-1", "14/09/2026 07:01", "T1", "flat-white", "1", "3.40"],
        ["LDS-2", "14/09/2026 07:02", "T1", "Flat Wht", "1", "3.40"],
        ["LDS-3", "14/09/2026 07:03", "T1", "Pain au Chocolat", "1", "2.80"],
    ]

    products = [r["product"] for r in clean_rows(rows, "leeds")]

    assert products == ["Flat-White", "Flat Wht", "Pain Au Chocolat"]


def test_empty_product_name_is_kept():
    # BUG? see KC-103. The sale is kept with no product name.
    rows = [["LDS-1", "14/09/2026 07:01", "T1", "", "1", "3.40"]]

    assert clean_rows(rows, "leeds")[0]["product"] == ""


# --- de-duplication -----------------------------------------------------------


def test_exact_duplicate_row_is_removed():
    row = ["LDS-1", "14/09/2026 07:01", "T1", "Latte", "1", "3.50"]

    assert len(clean_rows([row, row], "leeds")) == 1


def test_same_product_in_same_minute_is_removed_even_in_another_transaction():
    # BUG? see KC-102. The duplicate key is (branch, minute, product), so a
    # second customer buying a latte in the same minute is dropped.
    rows = [
        ["LDS-1", "14/09/2026 07:01", "T1", "Latte", "1", "3.50"],
        ["LDS-2", "14/09/2026 07:01", "T2", "Latte", "2", "3.50"],
    ]

    cleaned = clean_rows(rows, "leeds")

    assert [r["transaction_id"] for r in cleaned] == ["LDS-1"]


def test_duplicate_check_happens_after_title_casing():
    rows = [
        ["LDS-1", "14/09/2026 07:01", "T1", "latte", "1", "3.50"],
        ["LDS-2", "14/09/2026 07:01", "T2", "LATTE", "1", "3.50"],
    ]

    assert len(clean_rows(rows, "leeds")) == 1


def test_same_product_in_different_minutes_is_kept():
    rows = [
        ["LDS-1", "14/09/2026 07:01", "T1", "Latte", "1", "3.50"],
        ["LDS-2", "14/09/2026 07:02", "T1", "Latte", "1", "3.50"],
    ]

    assert len(clean_rows(rows, "leeds")) == 2


# --- rows that are skipped or dropped -----------------------------------------


def test_blank_rows_are_skipped():
    rows = [
        [],
        ["", "14/09/2026 07:01", "T1", "Latte", "1", "3.50"],
        ["LDS-1", "14/09/2026 07:02", "T1", "Tea", "1", "2.20"],
    ]

    assert [r["product"] for r in clean_rows(rows, "leeds")] == ["Tea"]


def test_bad_rows_are_silently_dropped_and_the_rest_are_kept():
    # BUG? Nothing is logged or counted, so lost sales go unnoticed (KC-102).
    rows = [
        ["LDS-1", "14/09/2026 07:01", "T1", "Latte", "two", "3.50"],  # bad quantity
        ["LDS-2", "14/09/2026 07:02", "T1", "Latte", "1", "N/A"],  # bad price
        ["LDS-3", "2026-09-14T07:03:00", "T1", "Latte", "1", "3.50"],  # ISO date at Leeds
        ["LDS-4", "14/09/2026 07:04", "T1", "Latte", "1"],  # missing a column
        ["LDS-5", "14/09/2026 07:05", "T1", "Tea", "1", "2.20"],  # good
    ]

    assert [r["transaction_id"] for r in clean_rows(rows, "leeds")] == ["LDS-5"]


def test_dublin_row_without_a_rate_is_dropped():
    rows = [["2026-09-14T07:09:00", "Espresso", "4.00", "1", "T1", "DUB-1"]]

    assert clean_rows(rows, "dublin") == []

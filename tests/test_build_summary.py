"""Characterisation tests for build_summary (exercise 03).

These record what build_summary does *today*. Its input is the list of dicts
that clean_rows returns. Only the fields build_summary reads are filled in.
"""

from kettle.report import build_summary


def sale(branch, transaction_id, quantity, line_total_pence):
    return {
        "branch": branch,
        "transaction_id": transaction_id,
        "quantity": quantity,
        "line_total_pence": line_total_pence,
    }


def test_no_rows_gives_an_empty_summary():
    assert build_summary([], "2026-09-14") == []


def test_one_branch_is_totalled():
    rows = [
        sale("leeds", "LDS-1", 1, 300),  # LDS-1 has two lines
        sale("leeds", "LDS-1", 2, 440),
        sale("leeds", "LDS-2", 1, 340),
    ]

    assert build_summary(rows, "2026-09-14") == [
        {
            "date": "2026-09-14",
            "branch": "leeds",
            "transactions": 2,  # distinct transaction IDs
            "items_sold": 4,  # 1 + 2 + 1: quantities, not lines
            "revenue_gbp": "10.80",  # 300 + 440 + 340 = 1080p
        }
    ]


def test_branches_are_listed_in_order_of_first_appearance():
    rows = [
        sale("york", "YRK-1", 1, 100),
        sale("leeds", "LDS-1", 1, 100),
        sale("york", "YRK-2", 1, 100),
    ]

    branches = [s["branch"] for s in build_summary(rows, "2026-09-14")]

    assert branches == ["york", "leeds"]


def test_a_branch_with_no_rows_is_left_out():
    rows = [sale("leeds", "LDS-1", 1, 100)]

    assert [s["branch"] for s in build_summary(rows, "2026-09-14")] == ["leeds"]


def test_same_transaction_id_in_two_branches_is_counted_once_per_branch():
    rows = [sale("leeds", "T-1", 1, 100), sale("york", "T-1", 1, 100)]

    summary = build_summary(rows, "2026-09-14")

    assert [s["transactions"] for s in summary] == [1, 1]


def test_revenue_is_a_pounds_string_with_two_decimals():
    def revenue(pence):
        return build_summary([sale("leeds", "LDS-1", 1, pence)], "2026-09-14")[0]["revenue_gbp"]

    assert revenue(5) == "0.05"
    assert revenue(1000) == "10.00"
    assert revenue(123456) == "1234.56"  # no thousands separator, no £ sign


def test_date_comes_from_the_argument_not_the_rows():
    # build_summary doesn't look at sold_at, so it doesn't filter by date
    rows = [sale("leeds", "LDS-1", 1, 100)]

    assert build_summary(rows, "1999-12-31")[0]["date"] == "1999-12-31"

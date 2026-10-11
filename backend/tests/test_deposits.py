"""Term deposits: the interest arithmetic, and the range of dates it survives.

The numbers here are chosen so a reader can check them by hand: 1 000 000 000 ₫
at 6 % a year earns 60 000 000 ₫ over 365 days, and 30 000 000 ₫ over half a
year. Anything else the code produces is a bug in the day count.

The dates are all fixed, never "today", so the suite does not change its mind
about the answer tomorrow.
"""

from __future__ import annotations

import datetime

import pytest

from app import deposits, models
from app.money import DAYS_IN_YEAR

RATE_6 = 6.0
BILLION = 1_000_000_000.0


def make(**overrides) -> models.Deposit:
    """A deposit row, with only what a test cares about changed."""
    fields = {
        "name": "Vietcombank 6 tháng",
        "currency": "VND",
        "principal": BILLION,
        "annual_rate": RATE_6,
        "start_date": "2026-01-01",
        "maturity_date": "2026-07-01",
        "interest_mode": "at_maturity",
        "note": None,
    }
    fields.update(overrides)
    return models.Deposit(**fields)


class TestTheDayCount:
    def test_a_start_date_in_the_future_has_earned_nothing(self):
        # A negative term would subtract from the portfolio, which is worse
        # than saying zero.
        assert deposits.days_between("2026-06-01", datetime.date(2026, 1, 1)) == 0

    def test_the_day_the_money_left_has_earned_nothing(self):
        assert deposits.days_between("2026-01-01", datetime.date(2026, 1, 1)) == 0

    def test_a_missing_start_date_has_earned_nothing(self):
        assert deposits.days_between(None, datetime.date(2026, 1, 1)) == 0

    def test_days_are_actual_days(self):
        assert deposits.days_between("2026-01-01", datetime.date(2026, 1, 31)) == 30

    def test_a_leap_year_is_counted_as_the_days_it_really_has(self):
        # 2028 is a leap year; the arithmetic divides by 365 either way, which
        # is the contracted convention and must not drift to 366 on its own.
        assert deposits.days_between("2028-02-01", datetime.date(2028, 3, 1)) == 29
        assert DAYS_IN_YEAR == 365


class TestAccrual:
    def test_a_full_year_pays_exactly_the_rate(self):
        value = deposits.value_deposit(
            make(start_date="2025-01-01", maturity_date="2026-01-01"),
            as_of=datetime.date(2026, 1, 1),
        )
        assert value.days_accrued == 365
        assert value.interest_accrued == pytest.approx(60_000_000.0)
        assert value.value == pytest.approx(1_060_000_000.0)

    def test_half_a_year_pays_half_the_rate(self):
        value = deposits.value_deposit(make(), as_of=datetime.date(2026, 7, 1))
        assert value.days_accrued == 181
        # 1e9 × 6% × 181/365
        assert value.interest_accrued == pytest.approx(
            BILLION * 0.06 * 181 / 365
        )

    def test_interest_grows_by_the_day(self):
        row = make()
        first = deposits.value_deposit(row, as_of=datetime.date(2026, 2, 1))
        second = deposits.value_deposit(row, as_of=datetime.date(2026, 3, 1))
        third = deposits.value_deposit(row, as_of=datetime.date(2026, 4, 1))
        assert first.interest_accrued < second.interest_accrued < third.interest_accrued

    def test_a_zero_rate_earns_nothing_but_does_not_break(self):
        value = deposits.value_deposit(
            make(annual_rate=0.0), as_of=datetime.date(2026, 4, 1)
        )
        assert value.interest_accrued == 0.0
        assert value.value == pytest.approx(BILLION)

    def test_the_rate_is_read_as_a_percentage(self):
        # 6 must mean 6 %, not 600 %. A misplaced /100 is the classic version
        # of this bug and it is off by a factor of a hundred.
        value = deposits.value_deposit(
            make(start_date="2026-01-01", maturity_date="2027-01-01"),
            as_of=datetime.date(2027, 1, 1),
        )
        assert value.interest_accrued == pytest.approx(60_000_000.0)


class TestMaturity:
    def test_interest_stops_at_maturity(self):
        # Reading the same deposit a year after it matured must give the same
        # number as reading it on the day it matured: the contract rate is not
        # being paid any more, and carrying it forward would invent income.
        row = make()
        on_the_day = deposits.value_deposit(row, as_of=datetime.date(2026, 7, 1))
        long_after = deposits.value_deposit(row, as_of=datetime.date(2027, 7, 1))
        assert on_the_day.interest_accrued == pytest.approx(long_after.interest_accrued)
        assert long_after.matured is True

    def test_a_matured_deposit_says_so(self):
        assert deposits.value_deposit(make(), as_of=datetime.date(2026, 7, 1)).matured is True
        assert deposits.value_deposit(make(), as_of=datetime.date(2026, 6, 30)).matured is False

    def test_days_remaining_counts_down_and_then_disappears(self):
        before = deposits.value_deposit(make(), as_of=datetime.date(2026, 6, 1))
        after = deposits.value_deposit(make(), as_of=datetime.date(2026, 7, 2))
        assert before.days_remaining == 30
        assert after.days_remaining is None

    def test_the_value_at_maturity_is_the_contractual_payout(self):
        value = deposits.value_deposit(make(), as_of=datetime.date(2026, 3, 1))
        # 181 days from 1 Jan to 1 Jul 2026.
        assert value.value_at_maturity == pytest.approx(
            BILLION * (1 + 0.06 * 181 / 365)
        )
        assert value.value < value.value_at_maturity

    def test_once_matured_the_value_is_the_payout(self):
        value = deposits.value_deposit(make(), as_of=datetime.date(2026, 8, 1))
        assert value.value == pytest.approx(value.value_at_maturity)


class TestDemandDeposits:
    def test_a_deposit_with_no_maturity_never_matures(self):
        row = make(maturity_date=None)
        value = deposits.value_deposit(row, as_of=datetime.date(2030, 1, 1))
        assert value.matured is False
        assert value.days_remaining is None

    def test_a_deposit_with_no_maturity_keeps_accruing(self):
        row = make(maturity_date=None)
        first = deposits.value_deposit(row, as_of=datetime.date(2026, 6, 1))
        later = deposits.value_deposit(row, as_of=datetime.date(2027, 6, 1))
        assert later.interest_accrued > first.interest_accrued

    def test_the_value_at_maturity_of_a_demand_deposit_is_today(self):
        # There is no maturity to project towards, so the honest answer is the
        # figure for the day being asked about.
        value = deposits.value_deposit(make(maturity_date=None), as_of=datetime.date(2026, 6, 1))
        assert value.value_at_maturity == pytest.approx(value.value)


class TestSchedule:
    def test_the_projection_ends_on_the_maturity_date(self):
        points = deposits.schedule(make(), as_of=datetime.date(2026, 1, 1))
        assert points[-1]["as_of"] == "2026-07-01"

    def test_the_projection_only_ever_rises(self):
        points = deposits.schedule(make(), as_of=datetime.date(2026, 1, 1))
        values = [point["value"] for point in points]
        assert values == sorted(values)

    def test_a_demand_deposit_has_no_projection(self):
        assert deposits.schedule(make(maturity_date=None)) == []

    def test_an_ended_term_projects_the_one_point_that_matters(self):
        # Not an empty list: the point is the answer to "what did it become",
        # and a gap there would be a gap exactly where the user is looking.
        points = deposits.schedule(make(), as_of=datetime.date(2026, 8, 1))
        assert [point["as_of"] for point in points] == ["2026-07-01"]
        assert points[0]["value"] == pytest.approx(points[0]["value_at_maturity"])

    def test_the_last_point_agrees_with_the_value_at_maturity(self):
        points = deposits.schedule(make(), as_of=datetime.date(2026, 2, 1))
        assert points[-1]["value"] == pytest.approx(points[-1]["value_at_maturity"])

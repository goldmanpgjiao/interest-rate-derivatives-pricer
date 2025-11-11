"""Tests for date_helpers module."""

from datetime import date

import pytest

from montecarlo_ir.utils.date_helpers import (
    DayCountConvention,
    BusinessDayRule,
    days_between,
    is_business_day,
    adjust_business_day,
    add_months,
    add_years,
    generate_schedule,
    year_fraction,
)


class TestDayCountConvention:
    """Tests for day count convention calculations."""

    def test_act_360(self) -> None:
        """Test ACT/360 day count convention."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)  # 182 days
        result = days_between(start, end, DayCountConvention.ACT_360)
        assert abs(result - 182.0 / 360.0) < 1e-10

    def test_act_365(self) -> None:
        """Test ACT/365 day count convention."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)  # 182 days
        result = days_between(start, end, DayCountConvention.ACT_365)
        assert abs(result - 182.0 / 365.0) < 1e-10

    def test_act_365_25(self) -> None:
        """Test ACT/365.25 day count convention."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)  # 182 days
        result = days_between(start, end, DayCountConvention.ACT_365_25)
        assert abs(result - 182.0 / 365.25) < 1e-10

    def test_act_act_same_year(self) -> None:
        """Test ACT/ACT day count convention for same year."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)  # 182 days in 2024 (leap year, 366 days)
        result = days_between(start, end, DayCountConvention.ACT_ACT)
        assert abs(result - 182.0 / 366.0) < 1e-10

    def test_act_act_cross_year(self) -> None:
        """Test ACT/ACT day count convention across years."""
        start = date(2023, 6, 1)
        end = date(2024, 6, 1)  # 365 days: 214 in 2023, 152 in 2024
        result = days_between(start, end, DayCountConvention.ACT_ACT)
        # 2023: 214 days / 365 days, 2024: 152 days / 366 days
        expected = 214.0 / 365.0 + 152.0 / 366.0
        assert abs(result - expected) < 1e-6

    def test_thirty_360(self) -> None:
        """Test 30/360 day count convention."""
        start = date(2024, 1, 15)
        end = date(2024, 2, 15)  # 30 days
        result = days_between(start, end, DayCountConvention.THIRTY_360)
        assert abs(result - 30.0 / 360.0) < 1e-10

    def test_thirty_360_with_31st_day(self) -> None:
        """Test 30/360 day count convention with 31st day adjustment."""
        start = date(2024, 1, 31)
        end = date(2024, 2, 28)
        result = days_between(start, end, DayCountConvention.THIRTY_360)
        # d1=31 -> 30, d2=28, m1=1, m2=2, y1=y2=2024
        # days = 360*(0) + 30*(2-1) + (28-30) = 30 - 2 = 28
        assert abs(result - 28.0 / 360.0) < 1e-10

    def test_thirty_360_both_31st(self) -> None:
        """Test 30/360 when both dates have 31st day."""
        start = date(2024, 1, 31)
        end = date(2024, 3, 31)
        result = days_between(start, end, DayCountConvention.THIRTY_360)
        # d1=31 -> 30, d2=31 and d1=30 -> d2=30, m1=1, m2=3
        # days = 360*(0) + 30*(3-1) + (30-30) = 60
        assert abs(result - 60.0 / 360.0) < 1e-10

    def test_act_act_multiple_years(self) -> None:
        """Test ACT/ACT across multiple years."""
        start = date(2022, 1, 1)
        end = date(2024, 1, 1)  # Exactly 2 years (730 days)
        result = days_between(start, end, DayCountConvention.ACT_ACT)
        # 2022: 365 days / 365, 2023: 365 days / 365, 2024: 0 days (Jan 1 to Jan 1) / 366
        expected = 365.0 / 365.0 + 365.0 / 365.0 + 0.0 / 366.0
        assert abs(result - expected) < 1e-6

    def test_act_act_multiple_years_with_partial_last_year(self) -> None:
        """Test ACT/ACT across multiple years with partial last year."""
        start = date(2022, 1, 1)
        end = date(2024, 2, 1)  # 2 years + 1 month
        result = days_between(start, end, DayCountConvention.ACT_ACT)
        # 2022: 365 days / 365, 2023: 365 days / 365, 2024: 31 days / 366
        expected = 365.0 / 365.0 + 365.0 / 365.0 + 31.0 / 366.0
        assert abs(result - expected) < 1e-6

    def test_invalid_date_order(self) -> None:
        """Test that invalid date order raises ValueError."""
        start = date(2024, 7, 1)
        end = date(2024, 1, 1)
        with pytest.raises(ValueError, match="end_date.*must be >= start_date"):
            days_between(start, end)


class TestBusinessDayAdjustments:
    """Tests for business day adjustments."""

    def test_is_business_day_weekday(self) -> None:
        """Test that weekdays are business days."""
        assert is_business_day(date(2024, 1, 15))  # Monday
        assert is_business_day(date(2024, 1, 16))  # Tuesday
        assert is_business_day(date(2024, 1, 17))  # Wednesday
        assert is_business_day(date(2024, 1, 18))  # Thursday
        assert is_business_day(date(2024, 1, 19))  # Friday

    def test_is_business_day_weekend(self) -> None:
        """Test that weekends are not business days."""
        assert not is_business_day(date(2024, 1, 20))  # Saturday
        assert not is_business_day(date(2024, 1, 21))  # Sunday

    def test_is_business_day_holiday(self) -> None:
        """Test holiday handling."""
        holiday = date(2024, 1, 15)
        calendar = [holiday]
        assert not is_business_day(holiday, calendar)

    def test_adjust_following(self) -> None:
        """Test FOLLOWING business day rule."""
        saturday = date(2024, 1, 20)  # Saturday
        adjusted = adjust_business_day(saturday, BusinessDayRule.FOLLOWING)
        assert adjusted == date(2024, 1, 22)  # Monday

    def test_adjust_preceding(self) -> None:
        """Test PRECEDING business day rule."""
        saturday = date(2024, 1, 20)  # Saturday
        adjusted = adjust_business_day(saturday, BusinessDayRule.PRECEDING)
        assert adjusted == date(2024, 1, 19)  # Friday

    def test_adjust_none(self) -> None:
        """Test NONE business day rule."""
        saturday = date(2024, 1, 20)  # Saturday
        adjusted = adjust_business_day(saturday, BusinessDayRule.NONE)
        assert adjusted == saturday

    def test_adjust_modified_following(self) -> None:
        """Test MODIFIED_FOLLOWING business day rule."""
        # Saturday should move to Monday (following)
        saturday = date(2024, 1, 20)  # Saturday
        adjusted = adjust_business_day(saturday, BusinessDayRule.MODIFIED_FOLLOWING)
        assert adjusted == date(2024, 1, 22)  # Monday

    def test_adjust_modified_following_cross_month(self) -> None:
        """Test MODIFIED_FOLLOWING when following would cross month boundary."""
        # Use a date that would cross month if following
        # Jan 31, 2024 is a Wednesday, so if it were a holiday/weekend,
        # following would go to Feb, so it should use preceding
        # Let's use a case where the date itself is a weekend at month end
        # Actually, let's test with a calendar holiday
        holiday = date(2024, 1, 31)  # Wednesday - make it a holiday
        calendar = [holiday]
        adjusted = adjust_business_day(holiday, BusinessDayRule.MODIFIED_FOLLOWING, calendar)
        # Should move to previous business day (Jan 30) since following would be Feb
        assert adjusted == date(2024, 1, 30)  # Tuesday

    def test_adjust_modified_preceding(self) -> None:
        """Test MODIFIED_PRECEDING business day rule."""
        # Sunday should move to Friday (preceding)
        sunday = date(2024, 1, 21)  # Sunday
        adjusted = adjust_business_day(sunday, BusinessDayRule.MODIFIED_PRECEDING)
        assert adjusted == date(2024, 1, 19)  # Friday

    def test_adjust_modified_preceding_cross_month(self) -> None:
        """Test MODIFIED_PRECEDING when preceding would cross month boundary."""
        # Use a date at start of month that would cross month if preceding
        holiday = date(2024, 2, 1)  # Thursday - make it a holiday
        calendar = [holiday]
        adjusted = adjust_business_day(holiday, BusinessDayRule.MODIFIED_PRECEDING, calendar)
        # Should move to next business day (Feb 2) since preceding would be Jan
        assert adjusted == date(2024, 2, 2)  # Friday

    def test_adjust_business_day_with_calendar(self) -> None:
        """Test business day adjustment with holiday calendar."""
        holiday = date(2024, 1, 15)  # Monday
        calendar = [holiday]
        adjusted = adjust_business_day(holiday, BusinessDayRule.FOLLOWING, calendar)
        assert adjusted == date(2024, 1, 16)  # Tuesday

    def test_is_business_day_with_calendar_weekday(self) -> None:
        """Test that weekday not in calendar is business day."""
        calendar = [date(2024, 1, 15)]
        assert is_business_day(date(2024, 1, 16), calendar)  # Tuesday, not in calendar

    def test_is_business_day_already_business_day(self) -> None:
        """Test that already business day is not adjusted."""
        weekday = date(2024, 1, 15)  # Monday
        adjusted = adjust_business_day(weekday, BusinessDayRule.FOLLOWING)
        assert adjusted == weekday


class TestDateArithmetic:
    """Tests for date arithmetic functions."""

    def test_add_months_normal(self) -> None:
        """Test adding months to a date."""
        start = date(2024, 1, 15)
        result = add_months(start, 1)
        assert result == date(2024, 2, 15)

    def test_add_months_end_of_month(self) -> None:
        """Test adding months when day doesn't exist in target month."""
        start = date(2024, 1, 31)
        result = add_months(start, 1)  # February only has 29 days in 2024
        assert result == date(2024, 2, 29)

    def test_add_months_multiple(self) -> None:
        """Test adding multiple months."""
        start = date(2024, 1, 15)
        result = add_months(start, 3)
        assert result == date(2024, 4, 15)

    def test_add_months_negative(self) -> None:
        """Test subtracting months."""
        start = date(2024, 3, 15)
        result = add_months(start, -1)
        assert result == date(2024, 2, 15)

    def test_add_years_normal(self) -> None:
        """Test adding years to a date."""
        start = date(2024, 1, 15)
        result = add_years(start, 1)
        assert result == date(2025, 1, 15)

    def test_add_years_leap_day(self) -> None:
        """Test adding years when leap day doesn't exist in target year."""
        start = date(2024, 2, 29)  # Leap day
        result = add_years(start, 1)  # 2025 is not a leap year
        assert result == date(2025, 2, 28)

    def test_add_years_negative(self) -> None:
        """Test subtracting years."""
        start = date(2024, 1, 15)
        result = add_years(start, -1)
        assert result == date(2023, 1, 15)

    def test_add_years_leap_to_leap(self) -> None:
        """Test adding years from leap year to leap year."""
        start = date(2024, 2, 29)
        result = add_years(start, 4)  # 2028 is also a leap year
        assert result == date(2028, 2, 29)

    def test_add_months_year_boundary(self) -> None:
        """Test adding months across year boundary."""
        start = date(2024, 11, 15)
        result = add_months(start, 2)
        assert result == date(2025, 1, 15)

    def test_add_months_year_boundary_negative(self) -> None:
        """Test subtracting months across year boundary."""
        start = date(2024, 1, 15)
        result = add_months(start, -2)
        assert result == date(2023, 11, 15)

    def test_add_months_february_to_april(self) -> None:
        """Test adding months from February to April."""
        start = date(2024, 2, 29)  # Leap day
        result = add_months(start, 2)
        assert result == date(2024, 4, 29)

    def test_add_months_non_leap_year_february(self) -> None:
        """Test adding months when February has 28 days (non-leap year)."""
        start = date(2023, 1, 31)  # Jan 31 in non-leap year
        result = add_months(start, 1)  # Should go to Feb 28 (2023 is not a leap year)
        assert result == date(2023, 2, 28)


class TestScheduleGeneration:
    """Tests for schedule generation."""

    def test_generate_schedule_monthly(self) -> None:
        """Test generating monthly schedule."""
        start = date(2024, 1, 1)
        end = date(2024, 4, 1)
        schedule = generate_schedule(start, end, frequency="1M")
        assert len(schedule) >= 3
        assert schedule[0] == start
        assert schedule[-1] <= end

    def test_generate_schedule_quarterly(self) -> None:
        """Test generating quarterly schedule."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        schedule = generate_schedule(start, end, frequency="3M")
        assert len(schedule) >= 2
        assert schedule[0] == start

    def test_generate_schedule_semiannual(self) -> None:
        """Test generating semiannual schedule."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        schedule = generate_schedule(start, end, frequency="6M")
        assert len(schedule) >= 2
        assert schedule[0] == start

    def test_generate_schedule_invalid_date_order(self) -> None:
        """Test that invalid date order raises ValueError."""
        start = date(2024, 7, 1)
        end = date(2024, 1, 1)
        with pytest.raises(ValueError, match="end_date.*must be >= start_date"):
            generate_schedule(start, end, frequency="1M")

    def test_generate_schedule_yearly(self) -> None:
        """Test generating yearly schedule."""
        start = date(2024, 1, 1)
        end = date(2026, 1, 1)
        schedule = generate_schedule(start, end, frequency="1Y")
        assert len(schedule) >= 2
        assert schedule[0] == start
        assert schedule[-1] <= end

    def test_generate_schedule_with_business_day_rule(self) -> None:
        """Test schedule generation with business day adjustment."""
        start = date(2024, 1, 6)  # Saturday
        end = date(2024, 4, 6)  # Saturday
        schedule = generate_schedule(
            start, end, frequency="1M", business_day_rule=BusinessDayRule.FOLLOWING
        )
        # Start date should be adjusted to Monday
        assert schedule[0] == date(2024, 1, 8)  # Monday

    def test_generate_schedule_with_calendar(self) -> None:
        """Test schedule generation with holiday calendar."""
        start = date(2024, 1, 1)
        end = date(2024, 4, 1)
        holiday = date(2024, 2, 1)  # Thursday
        calendar = [holiday]
        schedule = generate_schedule(
            start, end, frequency="1M", business_day_rule=BusinessDayRule.FOLLOWING, calendar=calendar
        )
        # Check that holiday dates are adjusted
        for schedule_date in schedule:
            assert is_business_day(schedule_date, calendar)

    def test_generate_schedule_exact_end_date(self) -> None:
        """Test schedule generation when end date matches schedule."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        schedule = generate_schedule(start, end, frequency="6M")
        assert schedule[-1] == end or schedule[-1] == adjust_business_day(
            end, BusinessDayRule.MODIFIED_FOLLOWING
        )

    def test_generate_schedule_end_date_adjustment_different(self) -> None:
        """Test schedule generation when adjusted end date differs from last schedule date."""
        # Create a scenario where the end date needs adjustment and differs from last schedule date
        start = date(2024, 1, 1)
        end = date(2024, 6, 30)  # Sunday - will be adjusted
        schedule = generate_schedule(
            start, end, frequency="3M", business_day_rule=BusinessDayRule.FOLLOWING
        )
        # The end date (Sunday) should be adjusted and added if different from last schedule date
        assert len(schedule) > 0
        # Last date should be a business day
        assert is_business_day(schedule[-1])

    def test_generate_schedule_invalid_frequency(self) -> None:
        """Test that invalid frequency unit raises ValueError."""
        start = date(2024, 1, 1)
        end = date(2024, 4, 1)
        with pytest.raises(ValueError, match="Unsupported frequency unit"):
            generate_schedule(start, end, frequency="1D")  # Days not supported


class TestYearFraction:
    """Tests for year_fraction convenience function."""

    def test_year_fraction_with_enum(self) -> None:
        """Test year_fraction with DayCountConvention enum."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        result = year_fraction(start, end, DayCountConvention.ACT_360)
        assert abs(result - 182.0 / 360.0) < 1e-10

    def test_year_fraction_with_string(self) -> None:
        """Test year_fraction with string convention."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        result = year_fraction(start, end, "ACT/360")
        assert abs(result - 182.0 / 360.0) < 1e-10

    def test_year_fraction_invalid_string(self) -> None:
        """Test year_fraction with invalid string raises ValueError."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        with pytest.raises(ValueError, match="Unsupported day count convention"):
            year_fraction(start, end, "INVALID")

    def test_year_fraction_all_string_conventions(self) -> None:
        """Test year_fraction with all string convention formats."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)  # 182 days
        conventions = ["ACT/360", "ACT/365", "ACT/ACT", "ACT/365.25", "30/360"]
        for conv in conventions:
            result = year_fraction(start, end, conv)
            assert result > 0
            assert isinstance(result, float)

    def test_days_between_unsupported_convention(self) -> None:
        """Test that unsupported convention raises ValueError."""
        start = date(2024, 1, 1)
        end = date(2024, 7, 1)
        # Create a mock enum value that's not handled
        class MockConvention:
            value = "UNSUPPORTED"

        with pytest.raises(ValueError, match="Unsupported day count convention"):
            days_between(start, end, MockConvention())  # type: ignore[arg-type]

    def test_adjust_business_day_unsupported_rule(self) -> None:
        """Test that unsupported business day rule raises ValueError."""
        # Use a non-business day so the rule gets checked
        d = date(2024, 1, 20)  # Saturday
        # Create a mock rule that's not handled - use a string to bypass enum check
        # This tests the else clause in adjust_business_day
        class MockRule:
            def __eq__(self, other: object) -> bool:
                return False

        with pytest.raises(ValueError, match="Unsupported business day rule"):
            adjust_business_day(d, MockRule())  # type: ignore[arg-type]



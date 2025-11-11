"""Date handling utilities for interest rate derivatives.

This module provides functions for:
- Day count convention calculations
- Date arithmetic and period calculations
- Business day adjustments
- Date validation and conversions
"""

from datetime import date, datetime, timedelta
from enum import Enum
from typing import Final

import numpy as np


class DayCountConvention(Enum):
    """Day count conventions used in interest rate derivatives.

    References:
        - ACT/360: Actual days / 360
        - ACT/365: Actual days / 365
        - ACT/ACT: Actual days / Actual days in year
        - ACT/365.25: Actual days / 365.25 (includes leap year adjustment)
        - 30/360: 30 days per month / 360 days per year
    """

    ACT_360 = "ACT/360"
    ACT_365 = "ACT/365"
    ACT_ACT = "ACT/ACT"
    ACT_365_25 = "ACT/365.25"
    THIRTY_360 = "30/360"


class BusinessDayRule(Enum):
    """Business day adjustment rules.

    References:
        - FOLLOWING: Move to next business day if holiday
        - MODIFIED_FOLLOWING: Move to next business day, but if in next month,
          move to previous business day
        - PRECEDING: Move to previous business day if holiday
        - MODIFIED_PRECEDING: Move to previous business day, but if in previous
          month, move to next business day
        - NONE: No adjustment
    """

    FOLLOWING = "Following"
    MODIFIED_FOLLOWING = "Modified Following"
    PRECEDING = "Preceding"
    MODIFIED_PRECEDING = "Modified Preceding"
    NONE = "None"


def days_between(
    start_date: date, end_date: date, convention: DayCountConvention = DayCountConvention.ACT_360
) -> float:
    """Calculate the year fraction between two dates using a day count convention.

    Args:
        start_date: Start date.
        end_date: End date.
        convention: Day count convention to use. Defaults to ACT/360.

    Returns:
        Year fraction (time in years between the two dates).

    Raises:
        ValueError: If end_date is before start_date.

    Examples:
        >>> from datetime import date
        >>> days_between(date(2024, 1, 1), date(2024, 7, 1), DayCountConvention.ACT_360)
        0.5
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date})")

    if convention == DayCountConvention.ACT_360:
        return (end_date - start_date).days / 360.0

    elif convention == DayCountConvention.ACT_365:
        return (end_date - start_date).days / 365.0

    elif convention == DayCountConvention.ACT_365_25:
        return (end_date - start_date).days / 365.25

    elif convention == DayCountConvention.ACT_ACT:
        # Actual/Actual: count actual days in each period
        # and divide by actual days in the year
        year_start = date(start_date.year, 1, 1)
        year_end = date(start_date.year + 1, 1, 1)
        days_in_year = (year_end - year_start).days

        if start_date.year == end_date.year:
            return (end_date - start_date).days / days_in_year
        else:
            # Span multiple years
            total_days = 0.0
            current_year = start_date.year

            # Days in first year
            year_end_date = date(current_year + 1, 1, 1)
            days_in_first_year = (year_end_date - year_start).days
            total_days += (year_end_date - start_date).days / days_in_first_year

            # Full years in between
            current_year += 1
            while current_year < end_date.year:
                year_start_date = date(current_year, 1, 1)
                year_end_date = date(current_year + 1, 1, 1)
                days_in_year = (year_end_date - year_start_date).days
                total_days += 1.0  # Full year
                current_year += 1

            # Days in last year
            if current_year == end_date.year:
                year_start_date = date(current_year, 1, 1)
                year_end_date = date(current_year + 1, 1, 1)
                days_in_last_year = (year_end_date - year_start_date).days
                total_days += (end_date - year_start_date).days / days_in_last_year

            return total_days

    elif convention == DayCountConvention.THIRTY_360:
        # 30/360: Assume 30 days per month, 360 days per year
        d1, m1, y1 = start_date.day, start_date.month, start_date.year
        d2, m2, y2 = end_date.day, end_date.month, end_date.year

        # Adjust day if it's 31
        if d1 == 31:
            d1 = 30
        if d2 == 31 and d1 == 30:
            d2 = 30

        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return days / 360.0

    else:
        raise ValueError(f"Unsupported day count convention: {convention}")


def is_business_day(d: date, calendar: list[date] | None = None) -> bool:
    """Check if a date is a business day.

    Args:
        d: Date to check.
        calendar: List of holidays. If None, only weekends are considered non-business days.

    Returns:
        True if the date is a business day, False otherwise.
    """
    # Weekend check (Saturday = 5, Sunday = 6)
    if d.weekday() >= 5:
        return False

    # Holiday check
    if calendar is not None and d in calendar:
        return False

    return True


def adjust_business_day(
    d: date, rule: BusinessDayRule = BusinessDayRule.FOLLOWING, calendar: list[date] | None = None
) -> date:
    """Adjust a date according to a business day rule.

    Args:
        d: Date to adjust.
        rule: Business day adjustment rule.
        calendar: List of holidays. If None, only weekends are considered non-business days.

    Returns:
        Adjusted date.

    Examples:
        >>> from datetime import date
        >>> # If date is a Saturday, following moves to Monday
        >>> adjust_business_day(date(2024, 1, 6), BusinessDayRule.FOLLOWING)
        datetime.date(2024, 1, 8)
    """
    if rule == BusinessDayRule.NONE:
        return d

    if is_business_day(d, calendar):
        return d

    if rule == BusinessDayRule.FOLLOWING:
        adjusted = d
        while not is_business_day(adjusted, calendar):
            adjusted += timedelta(days=1)
        return adjusted

    elif rule == BusinessDayRule.PRECEDING:
        adjusted = d
        while not is_business_day(adjusted, calendar):
            adjusted -= timedelta(days=1)
        return adjusted

    elif rule == BusinessDayRule.MODIFIED_FOLLOWING:
        adjusted = d
        original_month = adjusted.month

        # Move forward
        while not is_business_day(adjusted, calendar):
            adjusted += timedelta(days=1)
            # If we've moved to next month, go back
            if adjusted.month != original_month:
                adjusted = d
                while not is_business_day(adjusted, calendar):
                    adjusted -= timedelta(days=1)
                break
        return adjusted

    elif rule == BusinessDayRule.MODIFIED_PRECEDING:
        adjusted = d
        original_month = adjusted.month

        # Move backward
        while not is_business_day(adjusted, calendar):
            adjusted -= timedelta(days=1)
            # If we've moved to previous month, go forward
            if adjusted.month != original_month:
                adjusted = d
                while not is_business_day(adjusted, calendar):
                    adjusted += timedelta(days=1)
                break
        return adjusted

    else:
        raise ValueError(f"Unsupported business day rule: {rule}")


def add_months(d: date, months: int) -> date:
    """Add months to a date.

    Args:
        d: Starting date.
        months: Number of months to add (can be negative).

    Returns:
        New date after adding months.

    Examples:
        >>> from datetime import date
        >>> add_months(date(2024, 1, 31), 1)
        datetime.date(2024, 2, 29)
        >>> add_months(date(2024, 1, 31), 2)
        datetime.date(2024, 3, 31)
    """
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day)


def add_years(d: date, years: int) -> date:
    """Add years to a date.

    Args:
        d: Starting date.
        years: Number of years to add (can be negative).

    Returns:
        New date after adding years.

    Examples:
        >>> from datetime import date
        >>> add_years(date(2024, 2, 29), 1)
        datetime.date(2025, 2, 28)
    """
    try:
        return date(d.year + years, d.month, d.day)
    except ValueError:
        # Handle leap year edge case (Feb 29 -> Feb 28 in non-leap year)
        return date(d.year + years, d.month, d.day - 1)


def _days_in_month(year: int, month: int) -> int:
    """Get the number of days in a month.

    Args:
        year: Year.
        month: Month (1-12).

    Returns:
        Number of days in the month.
    """
    if month == 2:
        # February: check for leap year
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            return 29
        return 28
    elif month in [4, 6, 9, 11]:
        return 30
    else:
        return 31


def generate_schedule(
    start_date: date,
    end_date: date,
    frequency: str = "6M",
    business_day_rule: BusinessDayRule = BusinessDayRule.MODIFIED_FOLLOWING,
    calendar: list[date] | None = None,
) -> list[date]:
    """Generate a schedule of dates between start and end dates.

    Args:
        start_date: Start date of the schedule.
        end_date: End date of the schedule.
        frequency: Frequency string (e.g., "1M", "3M", "6M", "1Y"). Defaults to "6M".
        business_day_rule: Business day adjustment rule. Defaults to MODIFIED_FOLLOWING.
        calendar: List of holidays. If None, only weekends are considered non-business days.

    Returns:
        List of dates in the schedule (including start_date and end_date).

    Examples:
        >>> from datetime import date
        >>> schedule = generate_schedule(date(2024, 1, 1), date(2024, 7, 1), "3M")
        >>> len(schedule)
        3
    """
    if end_date < start_date:
        raise ValueError(f"end_date ({end_date}) must be >= start_date ({start_date})")

    # Parse frequency
    frequency_value = int(frequency[:-1])
    frequency_unit = frequency[-1].upper()

    schedule: list[date] = []
    current_date = start_date

    # Adjust start date if needed
    adjusted_start = adjust_business_day(start_date, business_day_rule, calendar)
    schedule.append(adjusted_start)

    # Generate intermediate dates
    while current_date < end_date:
        if frequency_unit == "M":
            current_date = add_months(current_date, frequency_value)
        elif frequency_unit == "Y":
            current_date = add_years(current_date, frequency_value)
        else:
            raise ValueError(f"Unsupported frequency unit: {frequency_unit}")

        if current_date <= end_date:
            adjusted_date = adjust_business_day(current_date, business_day_rule, calendar)
            schedule.append(adjusted_date)

    # Ensure end date is included (adjusted)
    if schedule[-1] != end_date:
        adjusted_end = adjust_business_day(end_date, business_day_rule, calendar)
        if adjusted_end != schedule[-1]:
            schedule.append(adjusted_end)

    return schedule


def year_fraction(
    start_date: date,
    end_date: date,
    convention: DayCountConvention | str = DayCountConvention.ACT_360,
) -> float:
    """Calculate year fraction between two dates.

    Convenience function that accepts both DayCountConvention enum and string.

    Args:
        start_date: Start date.
        end_date: End date.
        convention: Day count convention (enum or string). Defaults to ACT/360.

    Returns:
        Year fraction.

    Examples:
        >>> from datetime import date
        >>> year_fraction(date(2024, 1, 1), date(2024, 7, 1), "ACT/360")
        0.5
    """
    if isinstance(convention, str):
        # Map string to enum
        convention_map = {
            "ACT/360": DayCountConvention.ACT_360,
            "ACT/365": DayCountConvention.ACT_365,
            "ACT/ACT": DayCountConvention.ACT_ACT,
            "ACT/365.25": DayCountConvention.ACT_365_25,
            "30/360": DayCountConvention.THIRTY_360,
        }
        if convention not in convention_map:
            raise ValueError(f"Unsupported day count convention: {convention}")
        convention = convention_map[convention]

    return days_between(start_date, end_date, convention)


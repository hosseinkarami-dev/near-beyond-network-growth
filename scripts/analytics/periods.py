"""Calendar period boundaries shared by analytics aggregations."""

from datetime import date, timedelta

CALENDAR_PERIODS = ("weekly", "monthly", "quarterly", "yearly")
CHART_PERIODS = ("daily", *CALENDAR_PERIODS)


def period_bounds(day: date, period: str) -> tuple[str, date, date]:
    if period == "weekly":
        start = day - timedelta(days=day.weekday())
        end = start + timedelta(days=6)
        return f"{start.isocalendar().year}-W{start.isocalendar().week:02d}", start, end
    if period == "monthly":
        start = day.replace(day=1)
        if day.month == 12:
            next_month = date(day.year + 1, 1, 1)
        else:
            next_month = date(day.year, day.month + 1, 1)
        return f"{day.year:04d}-{day.month:02d}", start, next_month - timedelta(days=1)
    if period == "quarterly":
        quarter = (day.month - 1) // 3 + 1
        month = (quarter - 1) * 3 + 1
        start = date(day.year, month, 1)
        if quarter == 4:
            next_quarter = date(day.year + 1, 1, 1)
        else:
            next_quarter = date(day.year, month + 3, 1)
        return f"{day.year:04d}-Q{quarter}", start, next_quarter - timedelta(days=1)
    if period == "yearly":
        return str(day.year), date(day.year, 1, 1), date(day.year, 12, 31)
    raise ValueError(f"Unsupported calendar period: {period}")

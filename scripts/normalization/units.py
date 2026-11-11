"""Exact unit conversions shared by normalized datasets."""

YOCTO_PER_NEAR = 10**24


def yocto_near_to_near(value):
    """Convert an integer yoctoNEAR amount to a lossless decimal string in NEAR."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise TypeError("yoctoNEAR amount must be an integer or decimal string")
    text = str(value)
    try:
        amount = int(text)
    except ValueError as exc:
        raise ValueError("yoctoNEAR amount must be an integer") from exc
    sign = "-" if amount < 0 else ""
    whole, fraction = divmod(abs(amount), YOCTO_PER_NEAR)
    fractional_text = f"{fraction:024d}".rstrip("0")
    return f"{sign}{whole}" + (f".{fractional_text}" if fractional_text else "")

"""Formatting helpers for India (INR, lakh/crore digit grouping)."""
from typing import Optional


def format_inr(amount: Optional[float], decimals: int = 2) -> str:
    """Format a number as Indian rupees with lakh/crore grouping, e.g. ₹12,34,567.00."""
    if amount is None:
        return "N/A"
    negative = amount < 0
    amount = abs(float(amount))
    whole, _, frac = f"{amount:.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    out = f"₹{whole}" + (f".{frac}" if decimals else "")
    return f"-{out}" if negative else out

"""Date parsing shared by the extractors, record adapters and packs."""
import datetime
import re

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

COMMON_FORMATS = ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d",
                  "%m/%d/%Y", "%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S", "%d-%b-%Y", "%d %b %Y", "%d %B %Y",
                  "%b %d, %Y", "%B %d, %Y", "%d.%m.%Y", "%Y%m%d", "%m/%d/%y", "%d-%b-%y"]


def valid(y, mo=1, d=1, lo=1000, hi=9999):
    return lo <= y <= hi and 1 <= mo <= 12 and 1 <= d <= 31


def parse_date(value, fmt=None, lo=1000, hi=9999, century=1900):
    """'12/28/1966 18:48' -> '1966-12-28'. Returns '' when nothing sensible is found.
    Two-digit years are read in `century` (1900 for NARA forms, 2000 for modern records)."""
    value = (value or "").strip()
    if not value:
        return ""
    for f in ([fmt] if fmt else []) + COMMON_FORMATS:
        try:
            dt = datetime.datetime.strptime(value, f)
        except ValueError:
            continue
        y = dt.year
        if "%y" in f:
            y = century + dt.year % 100
        if valid(y, dt.month, dt.day, lo, hi):
            return f"{y:04d}-{dt.month:02d}-{dt.day:02d}"
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", value)
    if m and lo <= int(m.group(1)) <= hi and len(value) <= 12:
        return m.group(1)
    return ""

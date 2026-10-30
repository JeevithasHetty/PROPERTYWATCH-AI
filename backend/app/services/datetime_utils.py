import datetime


def normalize_utc_naive(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is not None:
        return value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return value

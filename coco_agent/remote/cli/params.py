import re
from datetime import datetime, timedelta

import dateutil.parser as date_parser


def _date_delta_as_datetime(_date=None, delta=timedelta(days=0)) -> datetime:
    if _date is None:
        _date = datetime.utcnow().date()
    _date = _date + delta
    return datetime.combine(_date, datetime.min.time())


def date_parameter(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if value.lower() == "today":
        return _date_delta_as_datetime()
    if value.lower() == "yesterday":
        return _date_delta_as_datetime(delta=timedelta(days=-1))
    if value.lower() == "tomorrow":
        return _date_delta_as_datetime(delta=timedelta(days=1))
    if value.lstrip("-+").isdigit() and abs(
        int(value) < 19000000
    ):  # guard against accidental conversion of yyyymmdd dates
        return _date_delta_as_datetime(delta=timedelta(days=int(value)))

    # support yyyy-mm-dd and yyyymmdd
    if re.match(r"\d{4}-?\d{2}-?\d{2}", value):
        return date_parser.parse(value)

    raise ValueError(
        f"Argument {value} should be YYYY-MM-DD, one of "
        f"{{'yesterday', 'today', 'tomorrow'}}, or a number of days +/- today"
    )


def date_parameter_option(param_desc, required=False):
    return dict(
        type=date_parameter,
        required=required,
        help=f"{param_desc} as yyyy-dd-mm, integer days offset from today, or one of 'yesterday, today, tomorrow'",
    )

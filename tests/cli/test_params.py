from datetime import date, datetime, timedelta

import pytest
from _pytest.mark import param
from coco_agent.remote.cli import params


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        ("today", date.today()),
        ("yesterday", date.today() - timedelta(days=1)),
        ("TOMORROW", date.today() + timedelta(days=1)),
        (str(365 * 10), date.today() + timedelta(days=3650)),
        ("-3", date.today() - timedelta(days=3)),
        ("2021-01-03", date(2021, 1, 3)),
        ("20210103", date(2021, 1, 3)),
    ],
)
def test_date_parameter(value, expected):
    res = params.date_parameter(value)

    if expected is None:
        assert res is None
    else:
        assert res == datetime.combine(expected, datetime.min.time())


@pytest.mark.parametrize(
    "value, match",
    [
        ("doh", "Argument"),
        ("1.2", "Argument"),
    ],
)
def test_date_parameter_bad_format(value, match):
    with pytest.raises(ValueError, match=match):
        params.date_parameter(value)

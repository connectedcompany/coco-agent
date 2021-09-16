import pytest
from coco_agent.services import tm_id


def test_encode():
    res = tm_id.encode("hello")

    assert res == "13mw4kpp2xZTSK"


def test_sensor_id():
    res = tm_id.sensor("cust-id", "source-type", "source-id")

    assert res == "sen-" + tm_id.encode("cust-id::source-type::source-id")


@pytest.mark.parametrize(
    "connector_id, match",
    [
        (None, "Connector id is required"),
        ("just one part", "Invalid connector id"),
        ("a/b/c/", "Invalid connector id"),
        ("a/b/c", "Unsupported source type"),
    ],
)
def test_split_connector_id_bad_source_type(connector_id, match):
    with pytest.raises(ValueError, match=match):
        tm_id.split_connector_id(connector_id)

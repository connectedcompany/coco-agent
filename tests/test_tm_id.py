from coco_agent.services import tm_id


def test_encode():
    res = tm_id.encode("hello")

    assert res == "13mw4kpp2xZTSK"


def test_sensor_id():
    res = tm_id.sensor("cust-id", "source-type", "source-id")

    assert res == "sen-" + tm_id.encode("cust-id::source-type::source-id")

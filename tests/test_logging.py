import pytest
from coco_agent.remote.logging import apply_log_config


def test_cloud_logging_validation():
    with pytest.raises(ValueError, match="Unknown log level"):
        apply_log_config("whatever")

    with pytest.raises(ValueError, match="Credentials file path required"):
        apply_log_config("info", log_to_cloud=True)

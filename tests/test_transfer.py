import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

from coco_agent.remote import transfer
from coco_agent.services.gcs import GCSClient
from pytest import raises


def test_upload_dir_to_gcs_missing_bucket_spec():
    with raises(ValueError, match="Specify bucket name"):
        transfer.upload_dir_to_gcs("", ".")


@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload_dir_to_gcs(mock_gcs):
    test_data = {"something": "something else"}

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "testfile.json"), "w") as f:
            json.dump(test_data, f)

        mock_gcs_inst = MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        # act
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        transfer.upload_dir_to_gcs(
            os.path.join("tests", "fake_creds.json"),
            tmpdir,
            "test-cust-id",
            bucket_subpath="data",
        )

        # assert
        mock_gcs_inst.write_file.call_count == 1
        mock_gcs_inst.write_file.assert_called_with(
            os.path.join(tmpdir, "testfile.json"),
            "cc-upload-z7biauo6mvhvc",
            bucket_file_name=f"data/{ts}_testfile.json",
            skip_bucket_check=True,
        )

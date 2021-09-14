import json
import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, call, patch

from coco_agent.remote import transfer
from coco_agent.services.gcs import GCSClient
from pytest import raises


@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload_dir_to_gcs_single_source(mock_gcs):
    test_data = {"something": "something else"}

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "testfile.json"), "w") as f:
            json.dump(test_data, f)

        mock_gcs_inst = MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        # act
        # ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        transfer.upload_dir_to_gcs(
            os.path.join("tests", "fake_creds.json"),
            tmpdir,
            bucket_name="my-bucket",
            bucket_subpath="data",
        )

        # assert
        mock_gcs_inst.write_file.call_count == 1
        mock_gcs_inst.write_file.assert_called_with(
            os.path.join(tmpdir, "testfile.json"),
            # "cc-upload-z7biauo6mvhvc",
            "my-bucket",
            bucket_file_name=f"data/testfile.json",
            skip_bucket_check=True,
        )


@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload_dir_to_gcs_subtree(mock_gcs):
    test_data = {"something": "something else"}

    source_file_paths = [
        "f1.json",
        "abc/f2.json",
        "abc/f3.json",
        "abc/def/f4.json",
        "abc/def/ghi/jkl/f5.json",
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        for source_file_path in source_file_paths:
            dir_ = os.path.join(tmpdir, os.path.dirname(source_file_path))
            if not os.path.exists(dir_):
                os.makedirs(dir_)
            with open(os.path.join(tmpdir, source_file_path), "w") as f:
                json.dump(test_data, f)

        mock_gcs_inst = MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        # act
        transfer.upload_dir_to_gcs(
            os.path.join("tests", "fake_creds.json"),
            tmpdir,
            "my-bucket",
            bucket_subpath="data",
        )

        # assert
        mock_gcs_inst.write_file.call_count == len(source_file_paths)
        mock_gcs_inst.write_file.assert_has_calls(
            [
                call(
                    os.path.join(tmpdir, source_file_path),
                    "my-bucket",
                    bucket_file_name=f"data/{source_file_path.split('/')[-1]}",
                    skip_bucket_check=True,
                )
                for source_file_path in source_file_paths
            ]
        )


def test_upload_dir_to_cc_gcs_bad_resource_ids():
    # missing resource id
    with raises(ValueError, match="Resource id is required"):
        transfer.upload_dir_to_cc_gcs(
            os.path.join("tests", "fake_creds.json"), "mydir", None
        )

    # missing parts
    with raises(ValueError, match="Invalid resource id"):
        transfer.upload_dir_to_cc_gcs(
            os.path.join("tests", "fake_creds.json"), "mydir", "just one part"
        )

    # trailing slash
    with raises(ValueError, match="Invalid resource id"):
        transfer.upload_dir_to_cc_gcs(
            os.path.join("tests", "fake_creds.json"), "mydir", "a/b/c/"
        )


@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload_dir_to_cc_gcs(mock_gcs):
    test_data = {"something": "something else"}

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "testfile.json"), "w") as f:
            json.dump(test_data, f)

        mock_gcs_inst = MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        # act
        ts = datetime.utcnow().strftime("%y%m%d.%H%M%S")
        transfer.upload_dir_to_cc_gcs(
            os.path.join("tests", "fake_creds.json"),
            tmpdir,
            "test-cust-id/source-type/source-id",
        )

        # assert
        mock_gcs_inst.write_file.call_count == 1
        mock_gcs_inst.write_file.assert_called_with(
            os.path.join(tmpdir, "testfile.json"),
            "cc-upload-z7biauo6mvhvc",
            bucket_file_name=f"uploads/source-type/source-id/{ts}/testfile.json",
            skip_bucket_check=True,
        )

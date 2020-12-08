import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, call, patch

from click.testing import CliRunner
from coco_agent.remote import transfer
from coco_agent.remote.cli import cli
from coco_agent.services.gcs import GCSClient


def test_git_extract():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--customer-id=test",
                "--source-id=test",
                "--output-dir=" + tmpdir,
                "--forced-repo-name=test-repo",
                ".",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        files = [f for f in os.listdir(tmpdir)]
        assert len(files) == 3


@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload(mock_gcs):
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()

        # setup: export repo
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--customer-id=test",
                "--source-id=test",
                "--output-dir=" + tmpdir,
                "--forced-repo-name=test-repo",
                ".",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        # act: upload
        mock_gcs_inst = MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        result = runner.invoke(
            cli,
            [
                "upload",
                "data",
                "--customer-id=test",
                f"--credentials-file={os.path.join('tests', 'fake_creds.json')}",
                tmpdir,
            ],
            catch_exceptions=False,
        )

        # assert
        assert result.exit_code == 0, result.output
        mock_gcs_inst.write_file.call_count == 3
        mock_gcs_inst.write_file.assert_has_calls(
            [
                call(
                    os.path.join(tmpdir, f),
                    "cc-upload-3lvbl6fqqanq2r",
                    bucket_file_name=f"data/{ts}_{f}",
                    skip_bucket_check=True,
                )
                for f in os.listdir(tmpdir)
            ]
        )


def test_encode():
    runner = CliRunner()

    result = runner.invoke(cli, ["encode", "short", "text"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "3akJQjWFTeydzH"

    result = runner.invoke(cli, ["encode", "short", "--lower", "text"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "3akjqjwfteydzh"

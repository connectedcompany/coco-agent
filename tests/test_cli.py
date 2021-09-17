import os
import re
import tempfile
from datetime import datetime
from unittest import mock

import coco_agent
import pytest
import srsly
from click.testing import CliRunner
from coco_agent.remote import transfer
from coco_agent.remote.cli import cli, maybe_sleep
from coco_agent.services.gcs import GCSClient

# TODO: move out if used more widely
# Source: https://stackoverflow.com/questions/16976264/unittest-mock-asserting-partial-match-for-method-argument


class StringMatches(str):
    def __eq__(self, other):
        return re.match(self, other)

    def __hash__(self):
        return hash(str(self))


@mock.patch("builtins.print")
def test_version(mock_print):
    assert re.match(r"^\d+\.\d+\.\d+$", coco_agent.__version__)

    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "version",
        ],
        catch_exceptions=False,
    )
    mock_print.assert_called_with(coco_agent.__version__)


def test_git_extract():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--connector-id=test/git/test",
                "--output-dir=" + tmpdir,
                "--forced-repo-name=test-repo",
                "--log-level=debug",
                "--log-to-file",
                ".",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        files = [f for f in os.listdir(tmpdir)]
        assert len(files) == 3


def test_git_extract_repeatedly():
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()

        # note calls happen at the end of each run, so after 1st run this is still 0
        num_prev_calls = 0

        # simulate keyboard interrupt after 2 calls
        def maybe_sleep_patched(*args):
            nonlocal num_prev_calls
            if num_prev_calls >= 2:
                raise KeyboardInterrupt

            num_prev_calls += 1
            maybe_sleep(*args)

        with mock.patch(
            ".".join([maybe_sleep.__module__, maybe_sleep.__name__]),
            side_effect=maybe_sleep_patched,
        ):
            result = runner.invoke(
                cli,
                [
                    "extract",
                    "git-repo",
                    "--connector-id=test/git/test",
                    "--output-dir=" + tmpdir,
                    "--forced-repo-name=test-repo",
                    "--log-level=debug",
                    "--log-to-file",
                    "--repeat-interval-sec=5",
                    ".",
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 1, result.output
        assert num_prev_calls == 2

        files = [f for f in os.listdir(tmpdir)]
        assert len(files) == 3


@mock.patch("coco_agent.services.git.GitRepoExtractor.load_commit_diffs")
def test_git_extract_ignore_errors(mock_load_diffs):
    mock_load_diffs.side_effect = ValueError("simulated error")

    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--connector-id=test/git/test",
                "--output-dir=" + tmpdir,
                "--forced-repo-name=test-repo",
                "--log-level=debug",
                "--log-to-file",
                "--ignore-errors",
                "--use-non-native-repo-db",
                ".",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        commits_file = [f for f in os.listdir(tmpdir) if "git_commits" in f][0]
        assert (
            list(
                srsly.read_jsonl(
                    os.path.join(
                        tmpdir,
                        commits_file,
                    )
                )
            )
            == []
        )


@mock.patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_upload(mock_gcs):
    with tempfile.TemporaryDirectory() as tmpdir:
        runner = CliRunner()

        # setup: export repo
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--connector-id=test/git/test",
                "--output-dir=" + tmpdir,
                "--forced-repo-name=test-repo",
                ".",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        # act: upload
        mock_gcs_inst = mock.MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        ts = datetime.utcnow().strftime("%y%m%d.%H%M%S")
        result = runner.invoke(
            cli,
            [
                "upload",
                "data",
                f"--credentials-file={os.path.join('tests', 'fake_creds.json')}",
                "test/git/test",
                tmpdir,
            ],
            catch_exceptions=False,
        )

        # assert
        assert result.exit_code == 0, result.output
        mock_gcs_inst.write_file.call_count == 3
        mock_gcs_inst.write_file.assert_has_calls(
            [
                mock.call(
                    os.path.join(tmpdir, f),
                    "cc-upload-3lvbl6fqqanq2r",
                    bucket_file_name=f"uploads/git/test/{ts}/{f}",
                    skip_bucket_check=True,
                )
                for f in os.listdir(tmpdir)
            ]
        )
        mock_gcs_inst.write_data.assert_has_calls(
            [
                mock.call(
                    ".",
                    "cc-upload-3lvbl6fqqanq2r",
                    name=StringMatches(
                        r"uploads/git/test/\d{6}\.\d{6}/upload_complete_marker"
                    ),
                    skip_bucket_check=True,
                )
            ]
        )


def test_extract_and_upload_single_command_no_creds():
    runner = CliRunner()
    with pytest.raises(ValueError, match="Credentials file required"):
        runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                "--connector-id=test/git/test",
                "--forced-repo-name=test-repo",
                "--upload",
                ".",
            ],
            catch_exceptions=False,
        )


@mock.patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_extract_and_upload_single_command(mock_gcs):
    # setups
    runner = CliRunner()
    mock_gcs_inst = mock.MagicMock()
    mock_gcs.side_effect = lambda _: mock_gcs_inst

    ts = datetime.utcnow().strftime("%y%m%d.%H%M%S")

    # act
    result = runner.invoke(
        cli,
        [
            "extract",
            "git-repo",
            "--connector-id=test/git/test",
            "--forced-repo-name=test-repo",
            f"--credentials-file={os.path.join('tests', 'fake_creds.json')}",
            "--upload",
            ".",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    # assert
    assert result.exit_code == 0, result.output
    mock_gcs_inst.write_file.call_count == 3
    mock_gcs_inst.write_file.assert_has_calls(
        [
            mock.call(
                mock.ANY,
                "cc-upload-3lvbl6fqqanq2r",
                bucket_file_name=StringMatches(
                    r"uploads/git/test/\d{6}\.\d{6}/.*?\.jsonl"
                ),
                skip_bucket_check=True,
            )
            for f in range(3)
        ]
    )
    mock_gcs_inst.write_data.assert_called_with(
        ".",
        "cc-upload-3lvbl6fqqanq2r",
        name=StringMatches(r"uploads/git/test/\d{6}\.\d{6}/upload_complete_marker"),
        skip_bucket_check=True,
    )


def test_encode():
    runner = CliRunner()

    result = runner.invoke(cli, ["encode", "short", "text"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "3akJQjWFTeydzH"

    result = runner.invoke(cli, ["encode", "short", "--lower", "text"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "3akjqjwfteydzh"

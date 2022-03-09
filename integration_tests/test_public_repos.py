import os
import re
import tempfile
from datetime import datetime
from unittest import mock

import git as gitpython
import srsly
from click.testing import CliRunner
from coco_agent.remote import transfer
from coco_agent.remote.cli import cli, maybe_sleep
from coco_agent.services.gcs import GCSClient
from pytest import mark


class StringMatches(str):
    def __eq__(self, other):
        return re.match(self, other)

    def __hash__(self):
        return hash(str(self))


def test_pick_up_early_errors():
    connector_id = "test/git/test"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "extract",
            "git-repo",
            "--credentials-file=NONEXISTENT",
            f"--connector-id={connector_id}",
            "--log-to-cloud",
            "--upload",
            ".",
        ],
        catch_exceptions=True,
    )
    assert result.exit_code > 0
    assert "No such file or directory" in str(result)


@mark.parametrize(
    "repo_url, repo_name, branch_name, use_non_native_repo_db, min_commits",
    [
        # small-ish data repo
        ("https://github.com/pyro-ppl/numpyro.git", "numpyro", "master", False, 800),
        #  repo with head / master issues
        ("https://github.com/jbrowncfa/Cryptobomb", "Cryptobomb", "master", True, -1),
        #  large app repo(s), non-native db
        (
            "https://github.com/apache/incubator-superset.git",
            "superset",
            "master",
            True,
            6000,
        ),
        # older tool repo, native db
        (
            "https://github.com/findbugsproject/findbugs.git",
            "findbugs",
            "master",
            False,
            10000,
        ),
    ],
)
@mock.patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_repo_process_and_upload(
    mock_gcs, repo_url, repo_name, branch_name, use_non_native_repo_db, min_commits
):
    connector_id = "test/git/test"

    with tempfile.TemporaryDirectory() as tmpdir:
        # setup
        repo_path = os.path.join(tmpdir, repo_name)
        out_path = os.path.join(tmpdir, repo_name + "-out")
        os.mkdir(repo_path)
        os.mkdir(out_path)

        gitpython.Repo.clone_from(repo_url, repo_path)

        # extract repo
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                f"--connector-id={connector_id}",
                "--output-dir=" + out_path,
                "--forced-repo-name=test-repo",
                *(["--use-non-native-repo-db"] if use_non_native_repo_db else []),
                "--log-level=info",
                "--no-log-to-file",
                "--branch=" + branch_name,
                repo_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        #  check commits, if we're expecting some
        if min_commits > -1:
            commits_file = [
                f for f in os.listdir(out_path) if f.endswith("git_commits.jsonl")
            ][0]
            assert commits_file
            commits = srsly.read_jsonl(os.path.join(out_path, commits_file))
            assert len(list(commits)) > min_commits

        # upload
        mock_gcs_inst = mock.MagicMock()
        mock_gcs.side_effect = lambda _: mock_gcs_inst

        ts = datetime.utcnow().strftime("%y%m%d.%H%M%S")
        result = runner.invoke(
            cli,
            [
                "upload",
                "data",
                f"--credentials-file={os.path.join('tests', '../tests/fake_creds.json')}",
                connector_id,
                out_path,
            ],
            catch_exceptions=False,
        )

        # check upload
        assert result.exit_code == 0, result.output
        mock_gcs_inst.write_file.call_count == 3
        mock_gcs_inst.write_file.assert_has_calls(
            [
                mock.call(
                    os.path.join(out_path, f),
                    "cc-upload-3lvbl6fqqanq2r",
                    bucket_file_name=f"uploads/git/test/{ts}/{f}",
                    skip_bucket_check=True,
                )
                for f in os.listdir(out_path)
            ]
        )
        mock_gcs_inst.write_data.assert_called_with(
            ".",
            "cc-upload-3lvbl6fqqanq2r",
            name=StringMatches(r"uploads/git/test/\d{6}\.\d{6}/upload_complete_marker"),
            skip_bucket_check=True,
        )


@mock.patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
def test_repo_process_and_upload_repeatedly_single_command(mock_gcs):
    repo_url = "https://github.com/pyro-ppl/numpyro.git"
    repo_name = "numpyro"

    connector_id = "test/git/numpyro"
    mock_gcs_inst = mock.MagicMock()
    mock_gcs.side_effect = lambda _: mock_gcs_inst

    with tempfile.TemporaryDirectory() as tmpdir:
        # setup
        repo_path = os.path.join(tmpdir, repo_name)
        os.mkdir(repo_path)

        gitpython.Repo.clone_from(repo_url, repo_path)

        # simulate keyboard interrupt after 2 calls
        num_prev_calls = 0

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
            # extract repo
            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "extract",
                    "git-repo",
                    f"--connector-id={connector_id}",
                    f"--credentials-file={os.path.join('tests', 'fake_creds.json')}",
                    "--log-level=info",
                    "--no-log-to-file",
                    "--upload",
                    "--repeat-interval-sec=20",
                    repo_path,
                ],
                catch_exceptions=False,
            )
        assert result.exit_code == 1, result.output

        # check upload
        mock_gcs_inst.write_file.call_count == 3
        mock_gcs_inst.write_file.assert_has_calls(
            [
                mock.call(
                    mock.ANY,
                    "cc-upload-3lvbl6fqqanq2r",
                    bucket_file_name=StringMatches(
                        r"uploads/git/numpyro/\d{6}\.\d{6}/.*?\.jsonl"
                    ),
                    skip_bucket_check=True,
                )
                for _ in range(3)
            ]
        )
        mock_gcs_inst.write_data.assert_called_with(
            ".",
            "cc-upload-3lvbl6fqqanq2r",
            name=StringMatches(
                r"uploads/git/numpyro/\d{6}\.\d{6}/upload_complete_marker"
            ),
            skip_bucket_check=True,
        )


def test_repo_process_date_range():
    repo_url = "https://github.com/pyro-ppl/numpyro.git"
    repo_name = "numpyro"

    connector_id = "test/git/numpyro"

    with tempfile.TemporaryDirectory() as tmpdir:
        # setup
        repo_path = os.path.join(tmpdir, repo_name)
        out_path = os.path.join(tmpdir, repo_name + "-out")
        os.mkdir(repo_path)
        os.mkdir(out_path)

        gitpython.Repo.clone_from(repo_url, repo_path)

        # extract repo
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "extract",
                "git-repo",
                f"--connector-id={connector_id}",
                "--output-dir=" + out_path,
                "--log-level=info",
                "--no-log-to-file",
                "--start-date=2021-01-01",
                "--end-date=2021-02-01",
                repo_path,
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

        commits_file = [
            f for f in os.listdir(out_path) if f.endswith("git_commits.jsonl")
        ][0]
        assert commits_file

        commits = srsly.read_jsonl(os.path.join(out_path, commits_file))
        assert 30 > len(list(commits)) > 20

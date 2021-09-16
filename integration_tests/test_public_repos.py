import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import git as gitpython
import srsly
from click.testing import CliRunner
from coco_agent.remote import transfer
from coco_agent.remote.cli import cli
from coco_agent.services.gcs import GCSClient
from pytest import mark


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
@patch(".".join([transfer.__name__, GCSClient.__name__]), autospec=True)
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

        #  check commits
        commits_file = [
            f for f in os.listdir(out_path) if f.endswith("git_commits.jsonl")
        ][0]
        assert commits_file
        commits = srsly.read_jsonl(os.path.join(out_path, commits_file))
        assert len(list(commits)) > min_commits

        # upload
        mock_gcs_inst = MagicMock()
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
                call(
                    os.path.join(out_path, f),
                    "cc-upload-3lvbl6fqqanq2r",
                    bucket_file_name=f"uploads/git/test/{ts}/{f}",
                    skip_bucket_check=True,
                )
                for f in os.listdir(out_path)
            ]
        )

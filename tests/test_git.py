import os
import tempfile
from unittest.mock import MagicMock, patch

import git as gitpython
import pytest
import srsly
from coco_agent.services import git


def test_get_repo_name_from_remote():
    repo = MagicMock()
    repo.remotes = []
    assert git.get_repo_name_from_remote(repo) is None

    repo = MagicMock()
    repo.remotes.origin.url = "mylocaldir/."
    assert git.get_repo_name_from_remote(repo) is None

    repo = MagicMock()
    repo.remotes.origin.url = "https://somewhere/remote.git"
    assert git.get_repo_name_from_remote(repo) == "remote"


def test_get_repo_url_from_remote():
    repo = MagicMock()
    repo.remotes = None
    assert git.get_repo_url_from_remote(repo) is None

    repo = MagicMock()
    repo.remotes = []
    assert git.get_repo_url_from_remote(repo) is None

    repo = MagicMock()
    repo.remotes.origin.url = "url"
    assert git.get_repo_url_from_remote(repo) == "url"


def test_clone_repo_details():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = git.clone_repo(".", tmpdir)

    assert repo.remotes == []


def test_commit_iter_fall_back_from_master_to_main():
    repo = MagicMock()

    def side_effect(rev, reverse):
        if rev == "master":
            raise gitpython.GitCommandError(["cmd"], None)
        return ["stuff"]

    repo.iter_commits.side_effect = side_effect

    res = git.repo_commits_iter(repo, rev="master", fallback_rev="main")
    assert next(res) == "stuff"


@patch(git.__name__ + "." + git.get_repo_name_from_remote.__name__)
def test_git_repo_extractor_validation(mock_name_getter):
    mock_name_getter.return_value = None

    # with pytest.raises(ValueError, match="provide a sensor"):
    #     git.GitRepoExtractor(".")

    # with pytest.raises(ValueError, match="No repo id"):
    #     git.GitRepoExtractor(".", customer_id="cust-id", source_id="source-id")

    with pytest.raises(ValueError, match="repo name from remote"):
        next(
            git.GitRepoExtractor(
                ".",
                customer_id="cust-id",
                source_id="source-id",
                repo_tm_id="x",
            )("master")
        )


# ---- INTEGRATION TESTS ---- TODO: pull out

REPO_TM_ID = "gir-test"


def test_repo_extractor():
    extractor = git.GitRepoExtractor(
        ".",
        customer_id="test-cust-id",
        source_id="test-source-id",
        repo_tm_id=REPO_TM_ID,
        forced_repo_name="test-repo",
        # autogenerate_repo_id=False,
        # repo_link_url=None,
        use_repo_link_url_from_remote=True,
    )

    commits, repos = [], []
    for type_, item in extractor(rev="master", fallback_rev="main"):
        if type_ == git.GIT_COMMIT_TYPE:
            commits.append(item)
        elif type_ == git.GIT_REPO_TYPE:
            repos.append(item)
        else:
            pytest.fail(f"Unexpected item type: {type_}")

    assert len(repos) == 1
    assert repos[0]["tm_id"] == REPO_TM_ID
    assert repos[0]["name"] == "test-repo"

    assert len(commits) > 0
    assert commits[0]["authored_date"] < commits[1]["authored_date"]

    for commit in commits:
        assert commit["tm_id"].startswith("gic")
        assert commit["repo_id"] == REPO_TM_ID

        assert len(commit["diffs"]) > 0
        for diff in commit["diffs"]:
            assert diff["type"] in ["A", "D", "M", "R"]
            assert diff["repo_id"] == REPO_TM_ID
            assert diff["commit_id"] == commit["tm_id"]


@patch(git.__name__ + "." + git.get_repo_name_from_remote.__name__)
def test_ingest_repo_to_jsonl(mock_name_getter):
    mock_name_getter.return_value = "repo-name"

    with tempfile.TemporaryDirectory() as tmpdir:
        git.ingest_repo_to_jsonl(
            "customer-id", "source-id", ".", branch="master", output_dir=tmpdir
        )

        files = [f for f in os.listdir(tmpdir)]
        assert len(files) == 3

        for file_name in files:
            assert file_name.startswith(f"customer-id__source-id__")

            data = list(srsly.read_jsonl(os.path.join(tmpdir, file_name)))
            assert len(data)

            if git.GIT_REPO_TYPE in file_name:
                assert data[0]["name"] == "repo-name"
            elif git.GIT_COMMIT_TYPE in file_name:
                assert data[0]["tm_id"].startswith("gic")
            elif git.GIT_COMMIT_DIFF_TYPE in file_name:
                assert data[0]["tm_id"].startswith("gdf")
            else:
                pytest.fail("unexpected file type")

import os
import tempfile
from collections import defaultdict
from unittest.mock import MagicMock, PropertyMock, patch

import git as gitpython
import gitdb
import pytest
import srsly
from coco_agent.services import git
from pytest import raises


def test_generate_git_export_file_name():
    with pytest.raises(ValueError, match="parts missing"):
        git.generate_git_export_file_name(None, None, None, None, "name")
    with pytest.raises(ValueError, match="parts missing"):
        git.generate_git_export_file_name("a", "b", None, "d", "e")

    assert (
        git.generate_git_export_file_name(
            "jsonl", "cust-id", "source-id", "repo-id", "git_commits"
        )
        == "cust-id__source-id__repo-id__git_commits.jsonl"
    )


def test_parse_git_export_file_name():
    #  exceptions
    with pytest.raises(ValueError, match="file name structure"):
        git.parse_git_export_file_name("whatever")

    #  fixed input
    res = git.parse_git_export_file_name(
        "cust-id__source-id__repo-id__git_commits.jsonl"
    )
    assert res == ("cust-id", "source-id", "repo-id", "git_commits", "jsonl")

    #  round trip
    assert git.parse_git_export_file_name(
        git.generate_git_export_file_name(
            "jsonl", "cust-id", "source-id", "repo-id", "git_commits"
        )
    ) == ("cust-id", "source-id", "repo-id", "git_commits", "jsonl")


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

    with pytest.raises(ValueError, match="provide a sensor"):
        git.GitRepoExtractor(".")

    with pytest.raises(ValueError, match="No repo id"):
        git.GitRepoExtractor(".", customer_id="cust-id", source_id="source-id")

    with pytest.raises(ValueError, match="repo name from remote"):
        next(
            git.GitRepoExtractor(
                ".",
                customer_id="cust-id",
                source_id="source-id",
                repo_tm_id="x",
            )("master")
        )


def test_diff_size_error_handling():
    # handle sha missing error on size
    diff = MagicMock(a_blob=None, new_file=True)
    type(diff).b_blob = PropertyMock(
        side_effect=ValueError(
            "SHA b'3f7910b7586a7160be9b3760c17e71090a4ec9cf' could not be resolved, git returned: b'3f7910b7586a7160be9b3760c17e71090a4ec9cf missing'"
        )
    )
    assert git._diff_size(diff) is None

    # handle sha missing error on size - no caption
    diff = MagicMock(a_blob=None, new_file=True)
    type(diff).b_blob = PropertyMock(
        side_effect=ValueError("SHA could not be resolved, git returned: missing'")
    )
    assert git._diff_size(diff) is None

    # reraise arbitrary error
    diff = MagicMock(a_blob=None, new_file=True)
    type(diff).b_blob = PropertyMock(
        side_effect=ValueError("SHAme there's been an error")
    )
    with raises(ValueError, match="SHAme"):
        git._diff_size(diff)

    # handle badobject error on size
    diff = MagicMock(a_blob=None, new_file=True)
    type(diff).b_blob = PropertyMock(
        side_effect=gitdb.exc.BadObject(b"b90713be305978a582ff222db84f03262fce5416")
    )
    assert git._diff_size(diff) is None


def test_diff_type_error_handling():
    # handle sha missing error on type
    diff = MagicMock()
    type(diff).renamed = PropertyMock(
        side_effect=ValueError(
            "SHA b'3f7910b7586a7160be9b3760c17e71090a4ec9cf' could not be found"
        )
    )
    assert git._diff_type(diff) is None

    # reraise arbitrary error
    diff = MagicMock(renamed=False)
    type(diff).deleted_file = PropertyMock(side_effect=ValueError("Something else"))
    with raises(ValueError, match="Something"):
        git._diff_type(diff)

    # handle badobject error on size
    diff = MagicMock()
    type(diff).renamed = PropertyMock(
        side_effect=gitdb.exc.BadObject(b"b90713be305978a582ff222db84f03262fce5416")
    )
    assert git._diff_type(diff) is None


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
    assert repos[0]["sensor_id"] == "sen-3qSmBRpzjqOW07"

    assert len(commits) > 0
    assert commits[0]["authored_date"] < commits[1]["authored_date"]

    # it's possible to have zero diff commits - but they should be few and far between
    num_zero_diff_commits = 0
    for commit in commits:
        assert commit["tm_id"].startswith("gic")
        assert commit["repo_id"] == REPO_TM_ID

        if len(commit["diffs"]) == 0:
            num_zero_diff_commits += 1
            continue

        for diff in commit["diffs"]:
            assert diff["type"] in ["A", "D", "M", "R"]
            assert diff["size_delta"] is not None
            assert diff["repo_id"] == REPO_TM_ID
            assert diff["commit_id"] == commit["tm_id"]

    assert num_zero_diff_commits / len(commits) < 0.1


def test_repo_extractor_different_dbs_same_results():
    extractor_kwargs = dict(
        customer_id="test-cust-id",
        source_id="test-source-id",
        repo_tm_id=REPO_TM_ID,
        forced_repo_name="test-repo",
        use_repo_link_url_from_remote=True,
    )

    extractor_non_native = git.GitRepoExtractor(
        ".", **extractor_kwargs, use_non_native_repo_db=False
    )
    extractor_native = git.GitRepoExtractor(
        ".", **extractor_kwargs, use_non_native_repo_db=True
    )

    items_non_native = [item for item in extractor_non_native(rev="master")]
    items_native = [item for item in extractor_native(rev="master")]

    assert items_non_native == items_native


@patch("coco_agent.services.git.GitRepoExtractor.load_commit_diffs")
def test_repo_extractor_ignore_errors(mock_load):
    mock_load.side_effect = ValueError("boom")

    extractor = git.GitRepoExtractor(
        ".",
        customer_id="test-cust-id",
        source_id="test-source-id",
        repo_tm_id=REPO_TM_ID,
        forced_repo_name="test-repo",
        use_repo_link_url_from_remote=True,
    )

    extracted = defaultdict(list)
    for type_, item in extractor(rev="master", fallback_rev="main", ignore_errors=True):
        extracted[type_].append(item)

    assert len(extracted[git.GIT_REPO_TYPE]) == 1
    assert len(extracted[git.GIT_COMMIT_TYPE]) == 0  #  errored


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


def test_update_repo():
    repo_url = "https://github.com/connectedcompany/coco-agent.git"
    repo_name = repo_url.split("/")[-1]
    branch = "master"

    with tempfile.TemporaryDirectory() as tmpdir:
        # setup
        repo_path = os.path.join(tmpdir, repo_name)
        os.mkdir(repo_path)

        gitpython.Repo.clone_from(repo_url, repo_path)

        # act
        git.update_repo(repo_dir=os.path.join(tmpdir, repo_name), branch=branch)

    # no exception from error status implies success

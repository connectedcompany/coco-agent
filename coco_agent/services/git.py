import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import gitdb
import srsly

import git

from . import tm_id

EXPORT_FILE_NAME_REGEX = re.compile(r"^(.+)__(.+)__(.+)__(.+)\.(.+)$")
GIT_URL_SCHEMES = ("http", "https", "git")
GIT_SOURCE_TYPE = "git"
GIT_COMMIT_TYPE = "git_commits"
GIT_COMMIT_DIFF_TYPE = "git_commit_diffs"
GIT_REPO_TYPE = "git_repos"
DEFAULT_GIT_COMMIT_WRITE_BATCH_SIZE = 100
LOG_HEARTBEAT_COMMIT_BATCH_SIZE = 1000

log = logging.getLogger(__name__)


def get_path(objpath):
    matches = re.match(
        "^((?P<start>.*?)/?{)?(?P<a>.*) => .*?(}/(?P<end>.*))?$", objpath
    )
    if not matches:
        return objpath

    groups = ["start", "a", "end"]
    return "/".join([matches.group(g) for g in groups if matches.group(g)])


def check_repo(repo):
    # check refs
    num_refs = repo.refs
    log.debug(f"Repo has {len(num_refs)} ref(s)")

    # there should be a head commit
    repo.head.commit
    log.debug(f"Repo head commit check ok")


def _diff_size(diff):
    """
    Computes the size of the diff by comparing the size of the blobs.
    """
    try:
        if diff.b_blob is None and diff.deleted_file:
            # This is a deletion, so return negative the size of the original.
            return diff.a_blob.size * -1

        if diff.a_blob is None and diff.new_file:
            # This is a new file, so return the size of the new value.
            return diff.b_blob.size

        # Otherwise just return the size a-b
        return diff.a_blob.size - diff.b_blob.size
    except gitdb.exc.BadObject as e:
        log.info(f"Skipping failed diff size lookup due to bad object: {str(e)}")
        return None
    except ValueError as e:
        if re.match(r"^SHA .*\s*could not be ", str(e).strip()):
            # Was log.info, turning down due to log noise - lots of messages like
            # INFO: Skipping failed diff size lookup: SHA b'<hexsha>' could not be resolved, git returned: b'<same hexsha> missing'
            log.debug(f"Skipping failed diff size lookup: {str(e)}")
            return None
        raise


def _diff_type(diff):
    """
    Determines the type of the diff by looking at the diff flags.
    """
    try:
        if diff.renamed:
            return "R"
        if diff.deleted_file:
            return "D"
        if diff.new_file:
            return "A"
        return "M"
    except gitdb.exc.BadObject as e:
        log.info(f"Skipping failed diff size lookup due to bad object: {str(e)}")
        return None
    except ValueError as e:
        if re.match(r"^SHA .*\s*could not be ", str(e).strip()):
            log.info(f"Skipping failed diff type lookup: {str(e)}")
            return None
        raise


def clone_repo(clone_url, to_path, **kwargs):
    git.Repo.clone_from(clone_url, to_path, **kwargs)
    return git.Repo(to_path)


def generate_git_export_file_name(
    file_suffix, customer_id, source_id, repo_id, entity_name
):
    if not all([file_suffix, customer_id, source_id, repo_id, entity_name]):
        raise ValueError(f"One or more file name parts missing")

    return f"{customer_id}__{source_id}__{repo_id}__{entity_name}.{file_suffix}"


def parse_git_export_file_name(file_name):
    matches = re.findall(EXPORT_FILE_NAME_REGEX, file_name)
    if not matches:
        raise ValueError(f"Unexpected export file name structure: {file_name}")
    return matches[0]


def get_repo_name_from_remote(repo):
    if (
        not repo.remotes
        or not hasattr(repo.remotes, "origin")
        or not repo.remotes.origin.url.endswith(".git")
    ):
        return None

    return repo.remotes.origin.url.split(".git")[0].split("/")[-1]


def repo_commits_iter(repo, rev, fallback_rev=None, reverse=True):
    """
    :param reverse:  reverse commit order, passed by gitpython to git-rev-list;
                     reverse=False means newest-to-oldest. We default to oldest-
                     to-newest, to facilitate contiguous ingestion of new data
    """

    try:
        for commit in repo.iter_commits(rev, reverse=reverse):
            yield commit
    except git.GitCommandError:
        repo_name = get_repo_name_from_remote(repo)
        if fallback_rev:
            log.info(f"No rev {rev} for {repo_name} - falling back to {fallback_rev}")
            yield from repo_commits_iter(repo, fallback_rev)
        else:
            log.info(
                f"Could not fetch '{rev}' for {repo_name} - "
                "assuming revision specifier does not exist"
            )


def get_repo_url_from_remote(repo, remote="origin"):
    if not repo.remotes:
        return None
    if not hasattr(repo.remotes, remote):
        return None
    return getattr(repo.remotes, remote).url


class GitRepoExtractor:
    def __init__(
        self,
        clone_url_or_path,
        sensor=None,
        customer_id=None,
        source_id=None,
        repo_tm_id=None,
        forced_repo_name=None,
        autogenerate_repo_id=False,
        repo_link_url=None,
        use_repo_link_url_from_remote=False,
        use_non_native_repo_db=False,
        start_date=None,
        end_date=None,
    ) -> None:
        self.clone_url_or_path = clone_url_or_path
        if not sensor and (not customer_id or not source_id):
            raise ValueError(
                "Must either provide a sensor, or both customer and source ids"
            )
        if not repo_tm_id and not autogenerate_repo_id:
            raise ValueError(f"No repo id given or auto-gen requested")

        self.customer_id = sensor.customer_id if sensor else customer_id
        self.source_id = sensor.source_id if sensor else source_id
        self.sensor_id = (
            sensor.tm_id
            if sensor
            else tm_id.sensor(customer_id, GIT_SOURCE_TYPE, source_id)
        )

        self.repo_tm_id = repo_tm_id
        self.forced_repo_name = forced_repo_name
        self.autogenerate_repo_id = autogenerate_repo_id
        self.repo_link_url = repo_link_url
        self.use_repo_link_from_remote = use_repo_link_url_from_remote
        self.use_non_native_repo_db = use_non_native_repo_db
        self.start_date = start_date
        self.end_date = end_date

    def generate_repo_id_from_remote_name(self, repo):
        repo_name = get_repo_name_from_remote(repo)
        log.info(f"Using {repo_name} from remote origin as repo id")

        return tm_id.git_repo(self.customer_id, self.source_id, repo_name)

    def load_commit_diffs(self, repo_tm_id, commit):
        """
        Source: https://bbengfort.github.io/snippets/2016/05/06/git-diff-extract.html
        This function returns a generator which iterates through all commits of
        the repository located in the given path for the given branch. It yields
        file diff information to show a timeseries of file changes.
        """
        diffs = commit.parents[0].diff(commit) if commit.parents else commit.diff()
        diffs = {
            diff.a_path: diff
            for diff in diffs
            # TODO: create_patch=True to get changed lines
        }

        # The stats on the commit is a summary of all the changes for this
        # commit, we'll iterate through it to get the information we need.
        for objpath, stats in commit.stats.files.items():
            diff = diffs.get(get_path(objpath))
            if diff is None:
                log.debug("Couldn't find a diff for %s", get_path(objpath))
                continue

            # Update the stats with the additional information
            size_delta = _diff_size(diff)
            type_ = _diff_type(diff)

            stats.update(
                {
                    "tm_id": tm_id.git_commit_diff(commit.hexsha, objpath),
                    "sensor_id": self.sensor_id,
                    "repo_id": repo_tm_id,
                    "commit_id": tm_id.git_commit(commit.hexsha),
                    "a_path": diff.a_path,
                    "b_path": diff.b_path,
                    "a_object_id": tm_id.git_path(repo_tm_id, diff.a_path),
                    "b_object_id": tm_id.git_path(repo_tm_id, diff.b_path),
                    "size_delta": size_delta,
                    "type": type_,
                }
            )

            yield stats

    def _date_filter_predicate(self, commit_obj):
        # Using committed_date over authored_date as in general it may be more recent, e.g if
        # commits came from a different source - https://stackoverflow.com/questions/11856983/why-git-authordate-is-different-from-commitdate

        committed_date_epoch = getattr(commit_obj, "committed_date")

        return (
            self.start_date is None
            or committed_date_epoch >= int(self.start_date.strftime("%s"))
        ) and (
            self.end_date is None
            or committed_date_epoch < int(self.end_date.strftime("%s"))
        )

    def extract_commits_and_history(
        self, repo, repo_tm_id, rev, fallback_rev=None, ignore_errors=False
    ):
        # filter by date as required
        for idx, commit_obj in filter(
            lambda x: self._date_filter_predicate(x[1]),
            enumerate(repo_commits_iter(repo, rev, fallback_rev)),
        ):
            if idx and not (idx % LOG_HEARTBEAT_COMMIT_BATCH_SIZE):
                log.info(f"{idx} commits done - still working ...")

            try:
                log.debug(f"Processing commit {commit_obj.hexsha}")
                diffs = self.load_commit_diffs(repo_tm_id, commit_obj)

                commit = {
                    "tm_id": tm_id.git_commit(commit_obj.hexsha),
                    "sensor_id": self.sensor_id,
                    "repo_id": repo_tm_id,
                    "diffs": list(diffs),
                    "author.name": commit_obj.author.name,
                    "author.email": commit_obj.author.email,
                    "committer.name": commit_obj.committer.name,
                    "committer.email": commit_obj.committer.email,
                    "parents": [tm_id.git_commit(x.hexsha) for x in commit_obj.parents],
                }

                for attr in [
                    "hexsha",
                    "authored_date",
                    "committed_date",
                    "message",
                    "summary",
                ]:
                    commit[attr] = getattr(commit_obj, attr)

                yield commit
            except Exception as e:
                if ignore_errors:
                    log.exception(
                        f"Error processing commit {commit_obj.hexsha} - will continue as ignore_errors is set"
                    )
                else:
                    raise

    def __call__(self, rev, fallback_rev=None, ignore_errors=False):
        """
        Extractor for commits and diffs for a git repo. Emits 2-tuples of (rec type, record),
        Repo tuple first, followed by commits
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # see https://github.com/gitpython-developers/GitPython/issues/642
            repo_kwargs = dict(odbt=git.db.GitDB) if self.use_non_native_repo_db else {}
            if urlparse(self.clone_url_or_path).scheme in GIT_URL_SCHEMES:
                log.info(f"Cloning {self.clone_url_or_path}...")
                repo = clone_repo(self.clone_url_or_path, tmpdir, **repo_kwargs)
            else:
                repo = git.Repo(self.clone_url_or_path, **repo_kwargs)

            repo_name = self.forced_repo_name or get_repo_name_from_remote(repo)
            if not repo_name:
                raise ValueError(f"Could not infer repo name from remote")

            log.info(f"{'-' * 10} Starting extract for repo {repo_name} {'-' * 10}")

            repo_tm_id = self.repo_tm_id
            if not repo_tm_id and self.autogenerate_repo_id:
                repo_tm_id = self.generate_repo_id_from_remote_name(repo)

            # repo sanity checks
            check_repo(repo)

            # emit repo
            repo_link_url = self.repo_link_url
            if not repo_link_url and self.use_repo_link_from_remote:
                repo_link_url = get_repo_url_from_remote(repo)
            yield (
                GIT_REPO_TYPE,
                {
                    "tm_id": repo_tm_id,
                    "sensor_id": self.sensor_id,
                    "name": repo_name,
                    "url": repo_link_url,
                },
            )

            # emit commits
            for commit in self.extract_commits_and_history(
                repo,
                repo_tm_id,
                rev=rev,
                fallback_rev=fallback_rev,
                ignore_errors=ignore_errors,
            ):
                yield GIT_COMMIT_TYPE, commit


def ingest_and_store_repo(
    customer_id,
    source_id,
    repo_path,
    branch,
    store_fn,
    fallback_branch=None,
    forced_repo_name=None,
    ignore_errors=False,
    use_non_native_repo_db=False,
    commits_batch_size=DEFAULT_GIT_COMMIT_WRITE_BATCH_SIZE,
    start_date=None,
    end_date=None,
):
    extractor = GitRepoExtractor(
        customer_id=customer_id,
        source_id=source_id,
        clone_url_or_path=repo_path,
        autogenerate_repo_id=True,
        use_repo_link_url_from_remote=True,
        forced_repo_name=forced_repo_name,
        use_non_native_repo_db=use_non_native_repo_db,
        start_date=start_date,
        end_date=end_date,
    )

    items_gen = extractor(
        rev=branch, fallback_rev=fallback_branch, ignore_errors=ignore_errors
    )

    # Consume repo
    type_, repo = next(items_gen)
    assert (
        type_ == GIT_REPO_TYPE
    ), f"Expected first extracted item to be a repo, but was {type_}"
    store_fn(GIT_REPO_TYPE, repo["tm_id"], [repo])

    # consume commits im batches, and count them for reporting
    num_commits, num_commit_diffs = 0, 0

    def store_commits_batch(repo_id, commits):
        nonlocal num_commits, num_commit_diffs
        if not len(commits):
            return

        commit_diffs = []
        num_commits += len(commits)
        for commit in commits:
            commit_diffs.extend(commit["diffs"])
            num_commit_diffs += len(commit["diffs"])
            del commit["diffs"]

        store_fn(GIT_COMMIT_TYPE, repo_id, commits)
        store_fn(GIT_COMMIT_DIFF_TYPE, repo_id, commit_diffs)

    commits_batch = []
    for type_, item in items_gen:
        if type_ != GIT_COMMIT_TYPE:
            raise ValueError(f"Expected commit items, got {type_}")

        commits_batch.append(item)
        if len(commits_batch) >= commits_batch_size:
            store_commits_batch(repo["tm_id"], commits_batch)
            commits_batch = []

    store_commits_batch(repo["tm_id"], commits_batch)

    log.info(
        f"Ingested commits for repo {repo['name']}: {num_commits} commit(s), {num_commit_diffs} diff(s)"
    )


def ingest_repo_to_jsonl(
    customer_id,
    source_id,
    repo_path,
    branch,
    output_dir=None,
    fall_back_from_master_to_main=True,
    forced_repo_name=None,
    ignore_errors=False,
    use_non_native_repo_db=False,
    start_date=None,
    end_date=None,
):
    output_dir = output_dir or os.path.join(".", "out")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # in order to support batched writes, jsonl writer overwrites any existing files
    # at the beginning of the run, then appends
    appendable_file_paths = set()

    def jsonl_writer(type_, id_, iter):
        output_filename = generate_git_export_file_name(
            "jsonl", customer_id, source_id, id_, type_
        )
        path = os.path.join(output_dir, output_filename)
        is_path_appendable = path in appendable_file_paths

        srsly.write_jsonl(path, iter, append=is_path_appendable)
        appendable_file_paths.add(path)

    ingest_and_store_repo(
        customer_id,
        source_id,
        repo_path,
        branch,
        store_fn=jsonl_writer,
        fallback_branch=(
            "main" if branch == "master" and fall_back_from_master_to_main else None
        ),
        forced_repo_name=forced_repo_name,
        ignore_errors=ignore_errors,
        use_non_native_repo_db=use_non_native_repo_db,
        start_date=start_date,
        end_date=end_date,
    )


def update_repo(repo_dir, branch):
    """Do a git pull on given repo clone without local changes"""

    def run_cmd(cmd):
        assert isinstance(cmd, (list, tuple)), "command must be a list or tuple"
        log.info(f"Running command {' ' .join(cmd)} in {repo_dir}")

        result = subprocess.run(
            cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        output = result.stdout.decode("utf-8")
        log.debug(f"Command output:\n{output}")

        if result.returncode != 0:
            raise RuntimeError(
                f"Command exited with non-zero status code {result.returncode} - output was:\n{output}"
            )

    run_cmd(["git", "checkout", branch])
    run_cmd(["git", "pull"])

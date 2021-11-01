import logging
import sys
import tempfile
import time

import click
import coco_agent
from coco_agent.remote.logging import apply_log_config, install_thread_excepthook
from coco_agent.remote.transfer import upload_dir_to_cc_gcs
from coco_agent.services import tm_id
from coco_agent.services.git import ingest_repo_to_jsonl, update_repo

from . import params

CLI_LOG_LEVELS = ["debug", "info", "warn", "error"]
CLI_DEFAULT_LOG_LEVEL = "info"
CLI_LOG_LEVEL_OPT_KWARGS = dict(
    default=CLI_DEFAULT_LOG_LEVEL,
    type=click.Choice(["debug", "info", "warn", "error"], case_sensitive=False),
    help=f"Logging level - one of {','.join(CLI_LOG_LEVELS)}",
)

log = logging.getLogger(coco_agent.__name__)  # don't use "__main__", misses log config

# workaround to catch unhandled exceptions in threads (e.g. google logging) - so we can log them!
# source: https://stackoverflow.com/a/16993115/1933315
def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    log.error("Background exception", exc_info=(exc_type, exc_value, exc_traceback))


install_thread_excepthook()
sys.excepthook = handle_uncaught_exception


def _setup_logging(log_level, log_to_file, log_to_cloud, credentials_file):
    apply_log_config(
        log_level,
        log_to_file=log_to_file,
        log_to_cloud=log_to_cloud,
        credentials_file_path=credentials_file,
    )

    log.info(f"coco-agent v{coco_agent.__version__} - args: " + " ".join(sys.argv[1:]))


def maybe_sleep(start_time, interval_sec):
    sleep_interval = max(0, interval_sec - (time.time() - start_time))
    log.info(f"--- Sleeping for {int(sleep_interval)} sec until next run ---")
    time.sleep(sleep_interval)


@click.group()
def cli() -> str:
    pass


# --- basics ---


@cli.command("version")
def version() -> str:
    """Print version"""
    print(coco_agent.__version__)


# --- extractors ---


@cli.group("extract")
def extract() -> str:
    """Data extraction commands"""
    pass


@extract.command("git-repo")
@click.option("--connector-id", required=True, help="CC connector identifier")
@click.option(
    "--output-dir",
    default="./out",
    help="Output directory - ignored if upload flag specified, a temp dir will be used instead",
)
@click.option("--branch", default="master", help="Branch / rev spec")
@click.option(
    "--git-pull-latest/--no-git-pull-latest",
    default=False,
    help="Pull latest changes for given repo + branch",
)
@click.option(
    "--ignore-errors",
    is_flag=True,
    default=False,
    required=False,
    help="Ignore commit processing errorss",
)
@click.option(
    "--use-non-native-repo-db",
    is_flag=True,
    default=False,
    required=False,
    help="Use pure Python repo DB in case of issues - not suitable for server processes",
)
@click.option("--log-level", **CLI_LOG_LEVEL_OPT_KWARGS)
@click.option("--log-to-file/--no-log-to-file", required=False, default=True)
@click.option("--log-to-cloud/--no-log-to-cloud", required=False, default=False)
@click.option("--credentials-file", help="Used if logging or uploading to cloud")
@click.option("--forced-repo-name", help="Name to set if one can't be read from origin")
@click.option("--upload/--no-upload", default=False, help="Upload to CC once extracted")
@click.option("--repeat-interval-sec", type=int, required=False)
@click.option("--start-date", **params.date_parameter_option("Start date"))
@click.option("--end-date", **params.date_parameter_option("End date"))
@click.argument("repo_path")
def extract_git(
    connector_id,
    output_dir,
    branch,
    git_pull_latest,
    ignore_errors,
    use_non_native_repo_db,
    log_level,
    log_to_file,
    log_to_cloud,
    credentials_file,
    forced_repo_name,
    upload,
    repeat_interval_sec,
    repo_path,
    start_date,
    end_date,
) -> str:
    """Extract git repo to an output dir. JSONL is currently supported.

    REPO_PATH is the file system path to repo to extract.
    """

    _setup_logging(log_level, log_to_file, log_to_cloud, credentials_file)

    if upload and not credentials_file:
        raise ValueError(f"Credentials file required for upload")

    customer_id, _, source_id = tm_id.split_connector_id(connector_id)

    while True:
        start_time = time.time()
        temp_dir = None

        if git_pull_latest:
            update_repo(repo_dir=repo_path, branch=branch)

        try:
            if upload:
                temp_dir = tempfile.TemporaryDirectory()
                output_dir = temp_dir.name

            ingest_repo_to_jsonl(
                customer_id=customer_id,
                source_id=source_id,
                output_dir=output_dir,
                branch=branch,
                repo_path=repo_path,
                forced_repo_name=forced_repo_name,
                ignore_errors=ignore_errors,
                use_non_native_repo_db=use_non_native_repo_db,
                start_date=start_date,
                end_date=end_date,
            )

            if upload:
                upload_dir_to_cc_gcs(
                    credentials_file,
                    output_dir,
                    connector_id=connector_id,
                )
        except Exception:
            log.exception("Error running extract")
        finally:
            if temp_dir:
                temp_dir.cleanup()

        if not repeat_interval_sec or repeat_interval_sec <= 0:
            break

        # this is also used as a hook for testing - e.g. simulating a keyboardinterrupt
        maybe_sleep(start_time, repeat_interval_sec)


# --- uploaders ---


@cli.group("upload")
def upload() -> str:
    """Content uploading (data, logs, etc)"""
    pass


@upload.command("logs")
def upload_logs_dir() -> str:
    """Upload content of a logs directory"""
    raise NotImplementedError


@upload.command("data")
@click.option("--credentials-file", required=True, help="Path to credentials file")
@click.option("--log-level", **CLI_LOG_LEVEL_OPT_KWARGS)
@click.option("--log-to-file/--no-log-to-file", required=False, default=False)
@click.option("--log-to-cloud/--no-log-to-cloud", required=False, default=False)
@click.argument("connector_id")
@click.argument("directory")
def upload_data_dir(
    connector_id, credentials_file, log_level, log_to_file, log_to_cloud, directory
) -> str:
    """
    Upload source dataset from the content of a directory and its subdirectories.

    CONNECTOR_ID: Identifier of source data being uploaded, provided by CC.
    Structured like 'customer-id/source-type/source-id - for example:
    mycompany/jira/jira-instance-ids

    DIRECTORY:   Root path from which to upload
    """

    _setup_logging(log_level, log_to_file, log_to_cloud, credentials_file)

    upload_dir_to_cc_gcs(
        credentials_file,
        directory,
        connector_id=connector_id,
    )


@cli.group("update")
def update() -> str:
    """Update a resource"""
    pass


@update.command("git-repo")
@click.argument("repo_path")
@click.option("--log-level", **CLI_LOG_LEVEL_OPT_KWARGS)
@click.option("--log-to-file/--no-log-to-file", required=False, default=False)
@click.argument("branch")
def update_local_git(log_level, log_to_file, branch, repo_path) -> str:
    """Update git repo by pulling the latest changes for a given branch.
    Useful for testing that updates work.

    NOTE that the repo is assumed to have no local changes that would require
    a merge - just cloned for the purpose of data extraction.

    REPO_PATH   - the file system path to repo to update
    BRANCH      - the branch to pull changes for
    """

    _setup_logging(log_level, log_to_file, log_to_cloud=False, credentials_file=None)

    update_repo(repo_dir=repo_path, branch=branch)


# --- setup / admin stuff ---


@cli.group("encode")
def encode() -> str:
    """Name / string encoding helpers"""
    pass


@encode.command("short")
@click.option("-l", "--lower", is_flag=True, required=False, default=False)
@click.argument("text")
def encode_short_iden(lower, text):
    """Encode text as a short base62 encoded string"""
    res = tm_id.encode(text.strip())
    print(res.lower() if lower else res)


if __name__ == "__main__":
    cli()

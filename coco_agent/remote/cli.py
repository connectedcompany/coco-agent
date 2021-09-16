import logging
import sys
import tempfile

import click
import coco_agent
from coco_agent.remote.logging import apply_log_config
from coco_agent.remote.transfer import upload_dir_to_cc_gcs
from coco_agent.services import tm_id
from coco_agent.services.git import ingest_repo_to_jsonl

CLI_LOG_LEVELS = ["debug", "info", "warn", "error"]
CLI_DEFAULT_LOG_LEVEL = "info"
CLI_LOG_LEVEL_OPT_KWARGS = dict(
    default=CLI_DEFAULT_LOG_LEVEL,
    type=click.Choice(["debug", "info", "warn", "error"], case_sensitive=False),
    help=f"Logging level - one of {','.join(CLI_LOG_LEVELS)}",
)

log = logging.getLogger(coco_agent.__name__)  # don't use "__main__", misses log config


def _setup_logging(log_level, log_to_file, log_to_cloud, credentials_file):
    apply_log_config(
        log_level,
        log_to_file=log_to_file,
        log_to_cloud=log_to_cloud,
        credentials_file_path=credentials_file,
    )

    log.info(f"coco-agent v{coco_agent.__version__} - args: " + " ".join(sys.argv[1:]))


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
@click.argument("repo_path")
def extract_git(
    connector_id,
    output_dir,
    branch,
    ignore_errors,
    use_non_native_repo_db,
    log_level,
    log_to_file,
    log_to_cloud,
    credentials_file,
    forced_repo_name,
    upload,
    repo_path,
) -> str:
    """Extract git repo to an output dir. JSONL is currently supported.

    REPO_PATH is the file system path to repo to extract.
    """

    _setup_logging(log_level, log_to_file, log_to_cloud, credentials_file)

    customer_id, _, source_id = tm_id.split_connector_id(connector_id)

    temp_dir = None
    try:
        if upload:
            if not credentials_file:
                raise ValueError(f"Credentials file required for upload")
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
        )

        if upload:
            upload_dir_to_cc_gcs(
                credentials_file,
                output_dir,
                connector_id=connector_id,
            )
    finally:
        if temp_dir:
            temp_dir.cleanup()


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

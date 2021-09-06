import logging
import sys

import click
import coco_agent
from coco_agent.remote.logging import apply_log_config
from coco_agent.remote.transfer import upload_dir_to_gcs
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
@click.option("--customer-id", required=True, help="Customer identifier")
@click.option(
    "--source-id",
    required=False,
    help="Repo source ID - derived from customer ID if not set",
)
@click.option("--output-dir", default="./out", help="Output director")
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
@click.option(
    "--credentials-file",
    required=False,
    help="Path to credentials file if logging to cloud",
)
@click.option(
    "--forced-repo-name",
    required=False,
    help="Name to set if one can't be read from origin",
)
@click.argument("repo_path")
def extract_git(
    customer_id,
    source_id,
    output_dir,
    branch,
    ignore_errors,
    use_non_native_repo_db,
    log_level,
    log_to_file,
    log_to_cloud,
    credentials_file,
    forced_repo_name,
    repo_path,
) -> str:
    """Extract git repo to an output dir. JSONL is currently supported.

    REPO_PATH is the file system path to repo to extract.
    """

    apply_log_config(
        log_level,
        log_to_file=log_to_file,
        log_to_cloud=log_to_cloud,
        credentials_file_path=credentials_file,
    )
    log.info("CLI args: " + " ".join(sys.argv[1:]))

    if not source_id:
        source_id = f"{customer_id}-git"

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
@click.option("--customer-id", required=True, help="Customer identifier")
@click.option("--credentials-file", required=True, help="Path to credentials file")
@click.option("--log-level", **CLI_LOG_LEVEL_OPT_KWARGS)
@click.option("--log-to-file/--no-log-to-file", required=False, default=False)
@click.argument("directory")
def upload_data_dir(
    customer_id, credentials_file, log_level, log_to_file, directory
) -> str:
    """Upload content of a directory"""
    apply_log_config(log_level, log_to_file=log_to_file)

    upload_dir_to_gcs(
        credentials_file, directory, customer_id=customer_id, bucket_subpath="data"
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

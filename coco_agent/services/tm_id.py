import hashlib
import re
from datetime import date

import base62

# !!! NOTE that changing these (or 'encode' below) invalidates all existing IDs
IDENTIFIER_LENGTH_BITS = 80
HASH_LENGTH_BITS = 256
SEP = "-"

SENSOR_ID_PREFIX = "sen"
GITHUB_REPO_ID_PREFIX = "ghr"
GITHUB_LABEL_ID_PREFIX = "ghl"
GITHUB_ISSUE_ID_PREFIX = "ghi"
GITHUB_ISSUE_EVENT_ID_PREFIX = "ghe"
GITHUB_PULL_REQUEST_ID_PREFIX = "gpr"
GITHUB_USER_ID_PREFIX = "ghu"
GIT_COMMIT_ID_PREFIX = "gic"
GIT_COMMIT_DIFF_ID_PREFIX = "gdf"
GIT_PATH_ID_PREFIX = "gip"
GIT_REPO_ID_PREFIX = "gir"
GIT_USER_ID_PREFIX = "giu"

CC_AGENT_SOURCE_TYPES = ["git", "github"]


def encode(id_: str) -> str:
    if not id_:
        raise ValueError("Empty id for a tm_id")
    cleartext = id_
    hashed = hashlib.sha256(cleartext.encode("utf-8")).hexdigest()
    truncated = int(hashed, base=16) >> (HASH_LENGTH_BITS - IDENTIFIER_LENGTH_BITS)
    return base62.encode(truncated)


def split_connector_id(connector_id):
    if not connector_id:
        raise ValueError("Connector id is required")

    connector_id = connector_id.strip().lower()
    matched = re.match(r"^([\w-]+)/([\w-]+)/([\w-]+)$", connector_id)
    if not matched or not len(matched.groups()) == 3:
        raise ValueError(
            f"Invalid connector id format - expected <customer-id>/<source-type>/<source-ids>"
        )

    customer_id, source_type, source_id = matched.groups()
    if source_type not in CC_AGENT_SOURCE_TYPES:
        raise ValueError(f"Unsupported source type: {source_type}")

    return customer_id, source_type, source_id


def sensor(customer_id, source_type, source_id):
    id_ = f"{customer_id}::{source_type}::{source_id}"
    return f"{SENSOR_ID_PREFIX}{SEP}{encode(id_)}"


def git_commit(hexsha: str):
    return f"{GIT_COMMIT_ID_PREFIX}{SEP}{encode(hexsha)}"


def git_commit_diff(hexsha: str, object_path: str):
    id_ = f"{hexsha}::{object_path}"
    return f"{GIT_COMMIT_DIFF_ID_PREFIX}{SEP}{encode(id_)}"


def git_path(repo_id, objpath):
    id_ = f"{repo_id}::{objpath}"
    return f"{GIT_PATH_ID_PREFIX}{SEP}{encode(id_)}"


def github_repo(github_repo_id: str):
    return f"{GITHUB_REPO_ID_PREFIX}{SEP}{encode(str(github_repo_id))}"


def github_user(user_id):
    return f"{GITHUB_USER_ID_PREFIX}{SEP}{encode(str(user_id))}"


def github_label(github_repo_id, label_id):
    id_ = f"{str(github_repo_id)}|{str(label_id)}"
    return f"{GITHUB_LABEL_ID_PREFIX}{SEP}{encode(id_)}"


def github_issue(github_repo_id, issue_id):
    id_ = f"{str(github_repo_id)}|{str(issue_id)}"
    return f"{GITHUB_ISSUE_ID_PREFIX}{SEP}{encode(id_)}"


def github_issue_event(github_repo_id, issue_event_id):
    id_ = f"{str(github_repo_id)}|{str(issue_event_id)}"
    return f"{GITHUB_ISSUE_EVENT_ID_PREFIX}{SEP}{encode(id_)}"


def github_pull_request(github_repo_id, pull_reqest_id):
    id_ = f"{str(github_repo_id)}|{str(pull_reqest_id)}"
    return f"{GITHUB_PULL_REQUEST_ID_PREFIX}{SEP}{encode(id_)}"


def git_user(repo_id: str, email: str):
    id_ = f"{repo_id}|{email}"
    return f"{GIT_USER_ID_PREFIX}{SEP}{encode(id_)}"


def git_repo(customer_id: str, source_id: str, git_repo_id: str):
    id_ = f"{customer_id}::{source_id}::{str(git_repo_id)}"
    return f"{GIT_REPO_ID_PREFIX}{SEP}{encode(id_)}"

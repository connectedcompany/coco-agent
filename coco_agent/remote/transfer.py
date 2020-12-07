import json
import logging
import os

from coco_agent.services import tm_id
from coco_agent.services.gcs import GCSClient

log = logging.getLogger(__name__)


def _bucket_name_from_customer_id(customer_id):
    # lower() since bucket names must have lowercase alphanumerics only
    encoded = tm_id.encode(customer_id).lower()
    return f"cc-upload-{encoded}"


def upload_dir_to_gcs(
    credentials_file_path, dir_, customer_id=None, bucket_name=None, bucket_subpath=None
):
    if not bucket_name and not customer_id:
        raise ValueError(f"Specify bucket name explicitly, or provide a customer id")
    bucket_name = bucket_name or _bucket_name_from_customer_id(customer_id)
    bucket_subpath = (bucket_subpath.strip("/") + "/") if bucket_subpath else ""

    with open(credentials_file_path) as f:
        sa_info_creds = json.load(f)
    gcs = GCSClient(sa_info_creds)

    files = [f for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    for file_ in files:
        local_file_path = os.path.join(dir_, file_)
        bucket_file_name = bucket_subpath + file_

        log.debug(f"Uploading {local_file_path} to {bucket_name} as {bucket_file_name}")
        gcs.write_file(
            local_file_path,
            bucket_name,
            bucket_file_name=bucket_file_name,
            skip_bucket_check=True,
        )

    log.info(f"Uploaded {len(files)} file(s) to {bucket_name}")

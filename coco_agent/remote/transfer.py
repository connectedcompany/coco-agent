import json
import logging
import os
import re
from datetime import datetime

from coco_agent.services import tm_id
from coco_agent.services.gcs import GCSClient

log = logging.getLogger(__name__)

UPLOAD_COMPLETE_MARKER_FILENAME = "upload_complete_marker"


def _bucket_name_from_customer_id(customer_id):
    # lower() since bucket names must have lowercase alphanumerics only
    encoded = tm_id.encode(customer_id).lower()
    return f"cc-upload-{encoded}"


def upload_dir_to_cc_gcs(credentials_file_path, dir_, connector_id):
    customer_id, source_type, source_id = tm_id.split_connector_id(connector_id)

    bucket_name = _bucket_name_from_customer_id(customer_id)
    bucket_subpath = f"uploads/{source_type}/{source_id}/{datetime.utcnow().strftime('%y%m%d.%H%M%S')}"

    return upload_dir_to_gcs(
        credentials_file_path=credentials_file_path,
        dir_=dir_,
        bucket_name=bucket_name,
        bucket_subpath=bucket_subpath,
        write_complete_marker=True,
    )


def upload_dir_to_gcs(
    credentials_file_path,
    dir_,
    bucket_name,
    bucket_subpath=None,
    write_complete_marker=False,
):
    bucket_subpath = (bucket_subpath.strip("/") + "/") if bucket_subpath else ""

    with open(credentials_file_path) as f:
        sa_info_creds = json.load(f)
    gcs = GCSClient(sa_info_creds)

    # files = [f for f in os.listdir(dir_) if os.path.isfile(os.path.join(dir_, f))]
    source_files = [
        (file_dir, file_name)
        for file_dir, subdirs, files in os.walk(dir_)
        for file_name in files
    ]

    for file_dir, file_name in source_files:
        local_file_path = os.path.join(file_dir, file_name)
        dest_file_name = bucket_subpath + file_name

        log.debug(f"Uploading {local_file_path} to {bucket_name} as {dest_file_name}")
        gcs.write_file(
            local_file_path,
            bucket_name,
            bucket_file_name=dest_file_name,
            skip_bucket_check=True,
        )

    if write_complete_marker:
        gcs.write_data(
            ".",
            bucket_name,
            name=bucket_subpath + UPLOAD_COMPLETE_MARKER_FILENAME,
            skip_bucket_check=True,
        )

    log.info(
        f"Uploaded {len(source_files)} file(s) {'and completion marker file ' if write_complete_marker else ''}to {bucket_name}"
    )

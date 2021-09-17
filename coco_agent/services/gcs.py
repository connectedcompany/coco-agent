import logging

from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.cloud.storage import Blob, Bucket
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)


class GCSClient:
    def __init__(self, sa_info_credentials: dict):
        self.credentials = Credentials.from_service_account_info(sa_info_credentials)
        self.client = self.get_client()

    def read_data(self, bucket_name: str, name: str, skip_bucket_check=False) -> str:
        """skip_bucket_check avoids the need for roles/storage.buckets.get (get_bucket checks metadata) - https://github.com/googleapis/google-cloud-python/issues/9065"""
        bucket = (
            self.client.bucket(bucket_name.lower())
            if skip_bucket_check
            else self.get_bucket(bucket_name)
        )
        blob = Blob(name, bucket)
        return blob.download_as_string(self.client).decode()

    def write_data(
        self,
        data: str,
        bucket_name: str,
        name: str,
        content_type: str = None,
        skip_bucket_check=False,
    ):
        # if we call client.get_bucket, then we need more than objectCreate role (we need read as well)
        if skip_bucket_check:
            blob = Blob(name, self.client.bucket(bucket_name.lower()))
        else:
            blob = Blob(name, self.get_or_create_bucket(bucket_name))

        blob.upload_from_string(data, content_type=content_type)

    def write_file(
        self,
        upload_file_name: str,
        bucket_name: str,
        bucket_file_name: str,
        content_type: str = None,
        skip_bucket_check=False,
    ):
        log.info(f"Writing file to bucket {bucket_name} as {bucket_file_name}")

        # if we call client.get_bucket, then we need more than objectCreate role (we need read as well)
        if skip_bucket_check:
            blob = Blob(bucket_file_name, self.client.bucket(bucket_name.lower()))
        else:
            blob = Blob(bucket_file_name, self.get_or_create_bucket(bucket_name))

        blob.upload_from_filename(upload_file_name, content_type=content_type)

    def write_static_content(
        self, upload_file_name, bucket_file_name, content_type=None
    ):
        self.write_file(
            upload_file_name,
            self.param("static_content_bucket"),
            bucket_file_name,
            content_type=content_type,
        )

    def _file_path(self, dt, file_name, extension):
        return f"{dt.year}/{dt.month}/{dt.day}/{file_name}.{extension}"

    def _bucket_name(self, sensor_id, name):
        # TODO: remove tm_environment
        return f'{self.param("tm_environment")}-{sensor_id}-{name}'

    def _write_string(self, bucket_name, file_name, data):
        log.info(f"Storing data in {bucket_name}:{file_name}")
        blob = Blob(file_name, self.get_or_create_bucket(bucket_name))
        blob.upload_from_string(data)

    def get_or_create_bucket(self, bucket_name) -> Bucket:
        try:
            return self.get_bucket(bucket_name)
        except NotFound:
            log.info(f"Creating bucket {bucket_name}")
            return self.client.create_bucket(bucket_name.lower())

    def get_bucket(self, bucket_name) -> Bucket:
        return self.client.get_bucket(bucket_name.lower())

    def get_client(self):
        return storage.Client(
            project=self.credentials.project_id, credentials=self.credentials
        )

    def get_prefixes(self, bucket_name, delimiter="/"):
        """
        Get blob prefixes

        For example delimiting with '/'for blobs A/x.json & B/x.json will
        return A/ & B/. Using '/x' as the delimiter would return A/x and B/x.
        """
        bucket = self.get_bucket(bucket_name)
        iterator = bucket.list_blobs(delimiter=delimiter)
        prefixes = set()

        for page in iterator.pages:
            prefixes.update(page.prefixes)
            return prefixes

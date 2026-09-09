from io import BytesIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

from .config import settings


client = boto3.client(
    "s3",
    endpoint_url=f"http://{settings.minio_endpoint}",
    aws_access_key_id=settings.minio_access_key,
    aws_secret_access_key=settings.minio_secret_key,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def ensure_bucket() -> None:
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.minio_bucket)


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    client.upload_fileobj(
        BytesIO(data), settings.minio_bucket, key, ExtraArgs={"ContentType": content_type}
    )


def put_fileobj(key: str, stream, content_type: str, callback=None) -> None:
    client.upload_fileobj(
        stream,
        settings.minio_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
        Callback=callback,
        Config=TransferConfig(use_threads=False),
    )


def upload_file(key: str, path: str, content_type: str) -> None:
    client.upload_file(path, settings.minio_bucket, key, ExtraArgs={"ContentType": content_type})


def download_file(key: str, path: str) -> None:
    client.download_file(settings.minio_bucket, key, path)


def get_object(key: str, range_header: str | None = None):
    args = {"Bucket": settings.minio_bucket, "Key": key}
    if range_header:
        args["Range"] = range_header
    return client.get_object(**args)


def delete_object(key: str) -> None:
    client.delete_object(Bucket=settings.minio_bucket, Key=key)


def object_exists(key: str) -> bool:
    try:
        client.head_object(Bucket=settings.minio_bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def delete_prefix(prefix: str) -> None:
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.minio_bucket, Prefix=prefix):
        objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=settings.minio_bucket, Delete={"Objects": objects})


def move_object(source_key: str, target_key: str) -> None:
    if source_key == target_key:
        return
    client.copy_object(
        Bucket=settings.minio_bucket,
        CopySource={"Bucket": settings.minio_bucket, "Key": source_key},
        Key=target_key,
    )
    delete_object(source_key)

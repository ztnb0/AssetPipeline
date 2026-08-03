from io import BytesIO

import boto3
from botocore.client import Config

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


def get_object(key: str):
    return client.get_object(Bucket=settings.minio_bucket, Key=key)


def delete_object(key: str) -> None:
    client.delete_object(Bucket=settings.minio_bucket, Key=key)


def move_object(source_key: str, target_key: str) -> None:
    if source_key == target_key:
        return
    client.copy_object(
        Bucket=settings.minio_bucket,
        CopySource={"Bucket": settings.minio_bucket, "Key": source_key},
        Key=target_key,
    )
    delete_object(source_key)

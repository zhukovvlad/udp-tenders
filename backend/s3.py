import os

import anyio
import boto3
from botocore.config import Config

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "invoices")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket():
    """Создать бакет если не существует."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=S3_BUCKET)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=S3_BUCKET)


def upload_file(file_bytes: bytes, object_name: str) -> str:
    """Загрузить файл в S3. Возвращает ключ объекта."""
    client = get_s3_client()
    client.put_object(Bucket=S3_BUCKET, Key=object_name, Body=file_bytes, ContentType="application/pdf")
    return object_name


def download_file(object_name: str) -> bytes:
    """Скачать файл из S3."""
    client = get_s3_client()
    response = client.get_object(Bucket=S3_BUCKET, Key=object_name)
    return response["Body"].read()


def delete_file(object_name: str):
    """Удалить файл из S3."""
    client = get_s3_client()
    client.delete_object(Bucket=S3_BUCKET, Key=object_name)


async def upload_file_async(file_bytes: bytes, object_name: str) -> str:
    """Async-обёртка upload_file: sync-boto3 уходит в поток, event loop свободен (S0-6)."""
    return await anyio.to_thread.run_sync(upload_file, file_bytes, object_name)


async def download_file_async(object_name: str) -> bytes:
    """Async-обёртка download_file через поток."""
    return await anyio.to_thread.run_sync(download_file, object_name)


async def delete_file_async(object_name: str) -> None:
    """Async-обёртка delete_file через поток."""
    await anyio.to_thread.run_sync(delete_file, object_name)

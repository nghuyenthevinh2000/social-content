"""S3-compatible object storage layer (RustFS, Cloudflare R2, Google Cloud Storage)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

_CLIENT: Optional[boto3.client] = None
_URL_CLIENT: Optional[boto3.client] = None


def get_bucket() -> str:
    return os.environ.get("BLOB_BUCKET", "aibrand")


def reset_client() -> None:
    global _CLIENT, _URL_CLIENT
    _CLIENT = None
    _URL_CLIENT = None


def get_client():
    global _CLIENT
    if _CLIENT is None:
        endpoint = os.environ.get("BLOB_ENDPOINT", "http://localhost:9000")
        access_key = os.environ.get("BLOB_ACCESS_KEY", "rustfsadmin")
        secret_key = os.environ.get("BLOB_SECRET_KEY", "rustfsadmin")
        region = os.environ.get("BLOB_REGION", "us-east-1")
        _CLIENT = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _CLIENT


def get_url_client():
    global _URL_CLIENT
    if _URL_CLIENT is None:
        public_endpoint = os.environ.get("BLOB_PUBLIC_ENDPOINT")
        if not public_endpoint:
            return get_client()
        access_key = os.environ.get("BLOB_ACCESS_KEY", "rustfsadmin")
        secret_key = os.environ.get("BLOB_SECRET_KEY", "rustfsadmin")
        region = os.environ.get("BLOB_REGION", "us-east-1")
        _URL_CLIENT = boto3.client(
            "s3",
            endpoint_url=public_endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _URL_CLIENT


def put(key: str, data: bytes, content_type: Optional[str] = None) -> None:
    client = get_client()
    bucket = get_bucket()
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)


def get(key: str) -> bytes:
    client = get_client()
    bucket = get_bucket()
    try:
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(f"Blob key not found: {key}") from exc
        raise


def download(key: str, path: Union[str, Path]) -> Path:
    client = get_client()
    bucket = get_bucket()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.download_file(Bucket=bucket, Key=key, Filename=str(p))
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            raise FileNotFoundError(f"Blob key not found: {key}") from exc
        raise
    return p


def upload_file(key: str, path: Union[str, Path], content_type: Optional[str] = None) -> None:
    client = get_client()
    bucket = get_bucket()
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    client.upload_file(
        Filename=str(path),
        Bucket=bucket,
        Key=key,
        ExtraArgs=extra or None,
    )


def delete(key: str) -> None:
    client = get_client()
    bucket = get_bucket()
    client.delete_object(Bucket=bucket, Key=key)


def delete_prefix(prefix: str) -> int:
    """Lists then deletes one key at a time, since GCS interop has no batch delete."""
    client = get_client()
    bucket = get_bucket()
    paginator = client.get_paginator("list_objects_v2")
    count = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            client.delete_object(Bucket=bucket, Key=obj["Key"])
            count += 1
    return count


def url(key: str, ttl: int = 3600, filename: Optional[str] = None) -> str:
    client = get_url_client()
    bucket = get_bucket()
    params = {"Bucket": bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return client.generate_presigned_url("get_object", Params=params, ExpiresIn=ttl)

"""Object storage adapter for LibraAI (local, S3, and MinIO).

Local storage is intended for development or an explicitly managed persistent
volume. Cloud backends fail closed: missing dependencies, credentials, or
provider responses never silently redirect data to a different storage system.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO, Optional, Union
from urllib.parse import urlencode

STORAGE_BACKEND = os.getenv('LIBRAAI_STORAGE_BACKEND', 'local').lower()
S3_BUCKET = os.getenv('LIBRAAI_STORAGE_BUCKET', 'libraai-assets')
S3_ENDPOINT = os.getenv('LIBRAAI_STORAGE_ENDPOINT', '')
S3_REGION = os.getenv('LIBRAAI_STORAGE_REGION', 'us-east-1')
S3_ACCESS_KEY = os.getenv('LIBRAAI_STORAGE_KEY', '')
S3_SECRET_KEY = os.getenv('LIBRAAI_STORAGE_SECRET', '')
LOCAL_STORAGE_DIR = Path(os.getenv('LIBRAAI_LOCAL_STORAGE_DIR', Path(__file__).resolve().parent / 'storage_data'))


def normalize_key(key: str) -> str:
    """Return a portable relative object key, rejecting traversal and ambiguity."""
    if not isinstance(key, str):
        raise TypeError('Storage key must be a string')
    normalized = key.replace('\\', '/')
    parts = normalized.split('/')
    if (not normalized or normalized.startswith('/') or '\x00' in normalized
            or any(part in ('', '.', '..') for part in parts)
            or (parts and len(parts[0]) > 1 and parts[0][1] == ':')):
        raise ValueError('Storage key must be a non-empty relative path without traversal')
    return normalized


def _missing_object_error(exc: Exception) -> bool:
    response = getattr(exc, 'response', {})
    error = response.get('Error', {}) if isinstance(response, dict) else {}
    return error.get('Code') in ('NoSuchKey', 'NoSuchObject', '404', 404)


class CloudStorageProvider:
    def __init__(self, backend: Optional[str] = None, local_root: Optional[Union[str, Path]] = None):
        self.backend = (backend or STORAGE_BACKEND).lower()
        if self.backend not in ('local', 's3', 'minio'):
            raise ValueError('LIBRAAI_STORAGE_BACKEND must be local, s3, or minio')
        self.local_root = Path(local_root or LOCAL_STORAGE_DIR).expanduser().resolve()
        self.local_root.mkdir(parents=True, exist_ok=True)
        self._s3_client = None

    def _local_path(self, key: str) -> Path:
        normalized = normalize_key(key)
        target = (self.local_root / normalized).resolve()
        if target != self.local_root and self.local_root not in target.parents:
            raise ValueError('Storage path escapes the configured local root')
        return target

    def _get_s3(self):
        if self.backend not in ('s3', 'minio'):
            raise RuntimeError('Cloud storage is not configured for this provider')
        if not S3_BUCKET.strip() or not S3_ACCESS_KEY.strip() or not S3_SECRET_KEY.strip():
            raise RuntimeError('Cloud storage requires a bucket, access key, and secret key')
        if self._s3_client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError('Cloud storage requires the optional boto3 package') from exc
            kwargs = {
                'aws_access_key_id': S3_ACCESS_KEY,
                'aws_secret_access_key': S3_SECRET_KEY,
                'region_name': S3_REGION,
            }
            if S3_ENDPOINT:
                kwargs['endpoint_url'] = S3_ENDPOINT
            self._s3_client = boto3.client('s3', **kwargs)
        return self._s3_client

    def put_object(self, key: str, data: Union[bytes, BinaryIO], content_type: str = 'application/octet-stream') -> dict:
        """Store an object and return its size and SHA-256 integrity metadata."""
        normalized = normalize_key(key)
        if isinstance(data, str):
            data = data.encode('utf-8')
        byte_data = data if isinstance(data, bytes) else data.read()
        if not isinstance(byte_data, bytes):
            raise TypeError('Storage data must be bytes or a binary file-like object')
        sha256 = hashlib.sha256(byte_data).hexdigest()
        size = len(byte_data)

        if self.backend in ('s3', 'minio'):
            self._get_s3().put_object(
                Bucket=S3_BUCKET,
                Key=normalized,
                Body=byte_data,
                ContentType=content_type,
                Metadata={'sha256': sha256},
            )
            return {'key': normalized, 'size': size, 'sha256': sha256, 'backend': self.backend, 'stored': True}

        destination = self._local_path(normalized)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(byte_data)
        return {'key': normalized, 'size': size, 'sha256': sha256, 'backend': 'local', 'path': str(destination), 'stored': True}

    def get_object(self, key: str) -> Optional[bytes]:
        """Retrieve an object, returning None only when it does not exist."""
        normalized = normalize_key(key)
        if self.backend in ('s3', 'minio'):
            try:
                response = self._get_s3().get_object(Bucket=S3_BUCKET, Key=normalized)
                return response['Body'].read()
            except Exception as exc:
                if _missing_object_error(exc):
                    return None
                raise

        target = self._local_path(normalized)
        return target.read_bytes() if target.is_file() else None

    def exists(self, key: str) -> bool:
        """Check object existence without hiding provider or credential failures."""
        normalized = normalize_key(key)
        if self.backend in ('s3', 'minio'):
            try:
                self._get_s3().head_object(Bucket=S3_BUCKET, Key=normalized)
                return True
            except Exception as exc:
                if _missing_object_error(exc):
                    return False
                raise
        return self._local_path(normalized).is_file()

    def object_size(self, key: str) -> Optional[int]:
        """Return object size without loading the object into application memory."""
        normalized = normalize_key(key)
        if self.backend in ('s3', 'minio'):
            try:
                return int(self._get_s3().head_object(Bucket=S3_BUCKET, Key=normalized)['ContentLength'])
            except Exception as exc:
                if _missing_object_error(exc):
                    return None
                raise
        target = self._local_path(normalized)
        return target.stat().st_size if target.is_file() else None

    def iter_object_range(self, key: str, start: int, end: int, chunk_size: int = 1024 * 1024):
        """Yield a byte range in bounded chunks; callers must validate offsets first."""
        normalized = normalize_key(key)
        if start < 0 or end < start or chunk_size < 1:
            raise ValueError('Invalid object byte range')
        if self.backend in ('s3', 'minio'):
            response = self._get_s3().get_object(Bucket=S3_BUCKET, Key=normalized, Range=f'bytes={start}-{end}')
            body = response['Body']
            try:
                while True:
                    chunk = body.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                body.close()
            return
        target = self._local_path(normalized)
        with target.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                chunk = stream.read(min(chunk_size, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    def generate_download_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Generate a pre-signed cloud URL or an authorized local download route."""
        normalized = normalize_key(key)
        if not isinstance(expires_seconds, int) or not 1 <= expires_seconds <= 604800:
            raise ValueError('Download URL expiry must be between 1 second and 7 days')
        if self.backend in ('s3', 'minio'):
            return self._get_s3().generate_presigned_url(
                'get_object',
                Params={'Bucket': S3_BUCKET, 'Key': normalized},
                ExpiresIn=expires_seconds,
            )
        return '/api/storage/download?' + urlencode({'key': normalized})


storage = CloudStorageProvider()

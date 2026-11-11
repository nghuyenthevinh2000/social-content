import os
from pathlib import Path
import tempfile
import urllib.request
import pytest
from tools.app.backend import blobs

os.environ["BLOB_ENDPOINT"] = "http://localhost:9000"
os.environ["BLOB_BUCKET"] = "test-aibrand"
os.environ["BLOB_ACCESS_KEY"] = "rustfsadmin"
os.environ["BLOB_SECRET_KEY"] = "rustfsadmin"
os.environ["BLOB_REGION"] = "us-east-1"
blobs.reset_client()


def test_blobs_round_trip():
    # 1. Put and Get
    key = "test/roundtrip.txt"
    data = b"Hello, RustFS S3 storage!"
    blobs.put(key, data, content_type="text/plain")
    fetched = blobs.get(key)
    assert fetched == data

    # 2. Upload file and Download
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        up_file = tmp / "upload.bin"
        up_file.write_bytes(b"File payload 1234567890")
        fkey = "test/file.bin"
        blobs.upload_file(fkey, up_file, content_type="application/octet-stream")

        down_file = tmp / "downloaded.bin"
        res_path = blobs.download(fkey, down_file)
        assert res_path.exists()
        assert res_path.read_bytes() == b"File payload 1234567890"

    # 3. Presigned URL with Range header
    presigned = blobs.url(fkey, ttl=60)
    req = urllib.request.Request(presigned, headers={"Range": "bytes=0-3"})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 206
        range_data = resp.read()
        assert range_data == b"File"

    # 4. Delete prefix
    deleted = blobs.delete_prefix("test/")
    assert deleted >= 2

    # Verify not found
    with pytest.raises(FileNotFoundError):
        blobs.get(key)

import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tools.app.backend import blobs
from tools.app.backend.credits import CREDIT_STORE
from tools.app.backend.media import MEDIA_STORE
from tools.app.backend.server import Handler
from tools.app.backend.video_jobs import VIDEO_STORE


class FakeServer:
    pass


class DummyHandler(Handler):
    def __init__(self, method: str, path: str, headers: dict, body: bytes = b""):
        self.command = method
        self.path = path
        self.headers = dict(headers)
        if body and "Content-Length" not in self.headers:
            self.headers["Content-Length"] = str(len(body))
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.client_address = ("127.0.0.1", 12345)
        self.server = FakeServer()
        self.response_status = None
        self.response_headers = {}

    def send_response(self, code, message=None):
        self.response_status = code

    def send_header(self, keyword, value):
        self.response_headers[keyword.lower()] = value

    def end_headers(self):
        pass


def test_server_video_and_media_routes():
    m_store = MEDIA_STORE.__class__()
    c_store = CREDIT_STORE.__class__()
    v_store = VIDEO_STORE.__class__()

    import unittest.mock as mock
    import tools.app.backend.server as s
    import tools.app.backend.video_jobs as vj
    s.MEDIA_STORE = m_store
    s.CREDIT_STORE = c_store
    s.VIDEO_STORE = v_store
    s.VIDEO_RUNNER = mock.MagicMock()
    vj.CREDIT_STORE = c_store

    user_hdr = {"X-User-Id": "u_test_1", "Content-Type": "application/json"}

    # 1. GET /api/credits -> balance 0
    h = DummyHandler("GET", "/api/credits", user_hdr)
    h.do_GET()
    assert h.response_status == 200
    res = json.loads(h.wfile.getvalue().decode())
    assert res["balance"] == 0

    # 2. POST /api/videos/estimate
    h = DummyHandler("POST", "/api/videos/estimate", user_hdr, body=b"{}")
    h.do_POST()
    assert h.response_status == 200
    res = json.loads(h.wfile.getvalue().decode())
    assert res["duration_sec"] == 15
    assert res["cost_micro"] == 345000
    assert res["can_afford"] is False

    # 3. Upload media: profile & context
    img_bytes = b"\xff\xd8\xff\xe01234567890"
    img_hdr = {"X-User-Id": "u_test_1", "Content-Type": "image/jpeg", "Content-Length": str(len(img_bytes))}
    h = DummyHandler("POST", "/api/media?kind=profile", img_hdr, body=img_bytes)
    h.do_POST()
    assert h.response_status == 200
    media_prof = json.loads(h.wfile.getvalue().decode())["media"]
    assert media_prof["kind"] == "profile"

    ctx_bytes = b"\x89PNG\r\n\x1a\nctxdata"
    ctx_hdr = {"X-User-Id": "u_test_1", "Content-Type": "image/png", "Content-Length": str(len(ctx_bytes))}
    h = DummyHandler("POST", "/api/media?kind=context", ctx_hdr, body=ctx_bytes)
    h.do_POST()
    assert h.response_status == 200
    media_ctx = json.loads(h.wfile.getvalue().decode())["media"]
    assert media_ctx["kind"] == "context"

    # 3b. Browser <img> tag GET /api/media/<id>?uid=u_test_1 (no headers!) -> 302
    h = DummyHandler("GET", f"/api/media/{media_prof['id']}?uid=u_test_1", {})
    h.do_GET()
    assert h.response_status == 302
    assert "location" in h.response_headers

    # 3c. Unauthenticated GET /api/media/<id> (no header, no uid) -> 401
    h = DummyHandler("GET", f"/api/media/{media_prof['id']}", {})
    h.do_GET()
    assert h.response_status == 401

    # 3d. Cross-user GET /api/media/<id>?uid=other_user -> 404
    h = DummyHandler("GET", f"/api/media/{media_prof['id']}?uid=other_user", {})
    h.do_GET()
    assert h.response_status == 404

    # 4. POST /api/videos without credits -> 402
    body_job = json.dumps({
        "prompt": "Hello",
        "profile_media_id": media_prof["id"],
        "context_media_ids": [media_ctx["id"]],
        "duration": 10,
    }).encode()
    job_hdr = {"X-User-Id": "u_test_1", "Content-Type": "application/json", "Content-Length": str(len(body_job))}
    h = DummyHandler("POST", "/api/videos", job_hdr, body=body_job)
    h.do_POST()
    assert h.response_status == 402

    # 5. Grant credits; test invalid media id -> 400 without deducting credits
    c_store.grant("u_test_1", 1000000)
    bad_job = json.dumps({"prompt": "Hello", "profile_media_id": "nonexistent"}).encode()
    bad_hdr = {"X-User-Id": "u_test_1", "Content-Type": "application/json", "Content-Length": str(len(bad_job))}
    h = DummyHandler("POST", "/api/videos", bad_hdr, body=bad_job)
    h.do_POST()
    assert h.response_status == 400
    assert c_store.get_balance("u_test_1") == 1000000

    # 6. POST /api/videos with valid profile & context -> 201
    h = DummyHandler("POST", "/api/videos", job_hdr, body=body_job)
    h.do_POST()
    assert h.response_status == 201
    created_job = json.loads(h.wfile.getvalue().decode())["job"]
    assert created_job["status"] == "pending"
    assert created_job["context_media_ids"] == [media_ctx["id"]]
    assert c_store.get_balance("u_test_1") == 655000

    # 7. GET /api/videos
    h = DummyHandler("GET", "/api/videos", user_hdr)
    h.do_GET()
    assert h.response_status == 200
    jobs = json.loads(h.wfile.getvalue().decode())["jobs"]
    assert len(jobs) == 1

    # 8. Test completed video streaming via presigned 302 redirect
    fake_key = f"videos/u_test_1/{created_job['id']}/output.mp4"
    blobs.put(fake_key, b"0123456789abcdef", content_type="video/mp4")
    v_store.mark_completed(created_job["id"], fake_key)

    h = DummyHandler("GET", f"/api/videos/{created_job['id']}/file?uid=u_test_1", {})
    h.do_GET()
    assert h.response_status == 302
    assert "location" in h.response_headers

    # 8b. Test download=1 sets Content-Disposition attachment in presigned URL
    h = DummyHandler("GET", f"/api/videos/{created_job['id']}/file?uid=u_test_1&download=1", {})
    h.do_GET()
    assert h.response_status == 302
    assert f'video-{created_job["id"]}.mp4' in h.response_headers["location"]

    # 9. Create a second job and cancel while pending -> refunds credits
    h = DummyHandler("POST", "/api/videos", job_hdr, body=body_job)
    h.do_POST()
    assert h.response_status == 201
    job2 = json.loads(h.wfile.getvalue().decode())["job"]
    assert c_store.get_balance("u_test_1") == 310000

    h = DummyHandler("POST", f"/api/videos/{job2['id']}/cancel", user_hdr)
    h.do_POST()
    assert h.response_status == 200
    assert c_store.get_balance("u_test_1") == 655000

    # 10. POST /api/videos/<id>/delete
    for jid in (created_job["id"], job2["id"]):
        h = DummyHandler("POST", f"/api/videos/{jid}/delete", user_hdr)
        h.do_POST()
        assert h.response_status == 200
    assert len(v_store.list_jobs("u_test_1")) == 0

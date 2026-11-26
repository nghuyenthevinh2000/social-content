import json
from pathlib import Path
import sys
import unittest.mock as mock

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tools.app.backend import blobs
from tools.app.backend.tests.test_server_video_routes import DummyHandler
from tools.app.backend.video_engine.edit import (
    REA_RUNS_ROOT,
    REFERENCE_EDIT_WORKFLOW,
    _prepare_reference_decompose,
    _prepare_user_source,
    build_video_edit_acp_prompt,
    edit_video,
    extract_reference_url,
    ref_cache_dir,
)
from tools.app.backend.video_engine.jobs import VideoJobStore, VideoRunner


def test_extract_reference_url():
    assert extract_reference_url("edit my video", "https://www.facebook.com/reel/123") == "https://www.facebook.com/reel/123"
    assert (
        extract_reference_url("Copy edit from https://www.tiktok.com/@a/video/999 please.")
        == "https://www.tiktok.com/@a/video/999"
    )
    assert extract_reference_url("Add Vietnamese captions") is None


def test_build_video_edit_acp_prompt_with_and_without_reference(tmp_path: Path):
    src = tmp_path / "input.mp4"
    out = tmp_path / "output.mp4"
    work = tmp_path / "work"
    rea = Path("/opt/rea-video")

    with_ref = build_video_edit_acp_prompt(
        source_video_path=src,
        output_path=out,
        prompt="Copy pacing and captions",
        work_dir=work,
        reference_video_url="https://www.facebook.com/reel/555",
        rea_video_bin=rea,
    )
    assert REFERENCE_EDIT_WORKFLOW.is_file()
    assert str(REFERENCE_EDIT_WORKFLOW) in with_ref
    assert "edit_config.json" in with_ref
    assert "--check" in with_ref
    assert "https://www.facebook.com/reel/555" in with_ref
    assert "rea-video" in with_ref
    assert "decompose" in with_ref
    assert "--no-stems --no-speakers --no-vlm" in with_ref
    assert "--no-asr" in with_ref
    assert "-t 25" in with_ref
    assert str(src) in with_ref
    assert str(out) in with_ref

    no_ref = build_video_edit_acp_prompt(
        source_video_path=src,
        output_path=out,
        prompt="Trim first 2 seconds",
        work_dir=work,
        reference_video_url=None,
        rea_video_bin=rea,
    )
    assert str(REFERENCE_EDIT_WORKFLOW) in no_ref
    assert "uv run yt-dlp" not in no_ref
    assert "decompose" in no_ref
    assert "--no-stems --no-speakers --no-vlm" in no_ref
    assert "Trim first 2 seconds" in no_ref

    pre_done = build_video_edit_acp_prompt(
        source_video_path=src,
        output_path=out,
        prompt="Copy captions",
        work_dir=work,
        reference_video_url="https://www.facebook.com/reel/555",
        rea_video_bin=rea,
        user_out_ready=True,
        ref_out_dir=tmp_path / "cached_ref_out",
    )
    assert "ALREADY decomposed" in pre_done
    assert "Do NOT re-download or re-run `rea-video`" in pre_done
    assert "effect_editor.py" in pre_done
    assert "json_video_editor.py" not in pre_done


def test_effect_editor_renders_synthetic_clip(tmp_path: Path):
    import subprocess
    from tools.app.backend.video_engine.edit import resolve_rea_video_bin

    repo_root = Path(__file__).resolve().parents[4]
    editor_path = repo_root / ".agents/skills/video-editing/scripts/video_engine/effect_editor.py"
    rea_bin = resolve_rea_video_bin()
    py_bin = str(rea_bin.parent / "python") if rea_bin else sys.executable

    in_mp4 = tmp_path / "in.mp4"
    out_mp4 = tmp_path / "out.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(in_mp4),
        ],
        check=True,
        capture_output=True,
    )
    plan_path = tmp_path / "edit_plan.json"
    plan_path.write_text(
        json.dumps({
            "input_video": str(in_mp4),
            "output_video": str(out_mp4),
            "width": 360,
            "height": 640,
            "effects": [
                {"type": "punch_zoom", "start": 0.1, "end": 0.5, "scale": 1.08},
                {"type": "transition", "kind": "flash", "time": 0.5, "duration": 0.12},
                {"type": "color_grade", "contrast": 1.05, "saturation": 1.08},
                {"type": "text_box", "variant": "hook", "lines": ["TEST"], "start": 0.0, "end": 0.8, "y": 40},
                {"type": "text_box", "variant": "info", "title": "Info", "body": ["Line 1"], "start": 0.3, "end": 0.9, "y": 240},
                {"type": "subtitles", "items": [{"start": 0.1, "end": 0.8, "text": "HELLO"}]},
                {"type": "sfx", "time": 0.1, "sound": "pop"},
            ],
        }),
        encoding="utf-8",
    )
    subprocess.run([py_bin, str(editor_path), str(plan_path)], check=True, capture_output=True)
    assert out_mp4.exists() and out_mp4.stat().st_size > 0


def test_prepare_reference_decompose_uses_cache(monkeypatch, tmp_path: Path):
    url = "https://www.tiktok.com/@user/video/123"
    cache_out = ref_cache_dir(url, tmp_path) / "out"
    cache_out.mkdir(parents=True)
    (cache_out / "VIDEO.md").write_text("# cached", encoding="utf-8")
    (cache_out / "breakdown.json").write_text("{}", encoding="utf-8")

    def fail_run(*_args, **_kwargs):
        raise AssertionError("subprocess should not run on cache hit")

    monkeypatch.setattr("tools.app.backend.video_engine.edit.subprocess.run", fail_run)
    res = _prepare_reference_decompose(url, Path("/opt/rea-video"), cache_root=tmp_path)
    assert res == cache_out
    assert str(REA_RUNS_ROOT).endswith("local/aibrand/rea-video-runs")


def test_prepare_user_source_and_fast_prompt(tmp_path: Path):
    import subprocess

    in_mp4 = tmp_path / "src.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=360x640:d=1",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-shortest", "-c:v", "libx264", "-c:a", "aac", str(in_mp4),
        ],
        check=True,
        capture_output=True,
    )
    work = tmp_path / "work"
    prep = _prepare_user_source(in_mp4, work, py_bin=None)
    assert prep is not None
    assert prep["probe_path"].exists()
    assert prep["probe"]["width"] == 360 and prep["probe"]["height"] == 640
    for idx in range(3):
        assert (prep["frames_dir"] / f"f_{idx}.jpg").exists()

    prep_with_tx = {**prep, "transcript_path": work / "user_transcript.json"}
    prompt = build_video_edit_acp_prompt(
        source_video_path=in_mp4,
        output_path=tmp_path / "out.mp4",
        prompt="Add highlight captions",
        work_dir=work,
        user_prep=prep_with_tx,
    )
    assert "Do NOT re-run" in prompt
    assert "user_transcript.json" in prompt
    assert "highlight_lines" in prompt
    assert "outer_stroke_width" in prompt
    assert "3–4" in prompt


def test_edit_video_invokes_acp_and_verifies_output(monkeypatch, tmp_path: Path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"fake-mp4")
    out = tmp_path / "out.mp4"
    captured = {}

    class FakeACPClient:
        def __init__(self, command, cwd, timeout_sec=600.0):
            captured["command"] = command
            captured["cwd"] = cwd

        def initialize(self):
            return {}

        def new_session(self):
            return "sess_edit_1"

        def prompt(self, session_id, text):
            captured["session_id"] = session_id
            captured["prompt"] = text
            out.write_bytes(b"edited-mp4-bytes")
            return "done"

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("tools.app.backend.video_engine.edit.ACPClient", FakeACPClient)
    monkeypatch.setattr(
        "tools.app.backend.research_engine.research.configured_agent",
        lambda: {"id": "opencode", "command": ["opencode", "acp"]},
    )

    res = edit_video(
        source_video_path=src,
        prompt="Copy edit style from https://www.facebook.com/reel/777",
        output_path=out,
        work_dir=tmp_path / "work",
        pre_decompose=False,
    )
    assert res == out
    assert out.read_bytes() == b"edited-mp4-bytes"
    assert captured["closed"] is True
    assert "https://www.facebook.com/reel/777" in captured["prompt"]
    assert "decompose" in captured["prompt"]


def test_video_runner_executes_edit_job():
    store = VideoJobStore()
    src_key = "videos/u_edit/uploads/src.mp4"
    blobs.put(src_key, b"raw-user-video", content_type="video/mp4")

    job = store.create_edit_job(
        user_id="u_edit",
        prompt="Copy hook card and captions",
        source_video_blob_key=src_key,
        reference_video_url="https://www.facebook.com/reel/888",
    )
    assert job["job_type"] == "edit"
    assert job["cost"] == 0
    assert job["reference_video_url"] == "https://www.facebook.com/reel/888"

    called = {}

    def fake_editor(source_video_path: Path, prompt: str, output_path: Path, reference_video_url=None):
        called["src_bytes"] = source_video_path.read_bytes()
        called["prompt"] = prompt
        called["ref"] = reference_video_url
        output_path.write_bytes(b"edited-result-video")
        return output_path

    runner = VideoRunner(store, editor=fake_editor)
    try:
        claimed = store.claim_next_pending()
        assert claimed and claimed["id"] == job["id"]
        runner._run_job(claimed)
    finally:
        runner.shutdown()

    updated = store.get_job("u_edit", job["id"])
    assert updated["status"] == "completed"
    assert called["src_bytes"] == b"raw-user-video"
    assert called["ref"] == "https://www.facebook.com/reel/888"
    assert blobs.get(updated["blob_key"]) == b"edited-result-video"


def test_server_video_edit_routes():
    import tools.app.backend.server as s

    v_store = VideoJobStore()
    s.VIDEO_STORE = v_store
    s.VIDEO_RUNNER = mock.MagicMock()

    # 1. Binary upload to POST /api/videos/edit
    hdr = {
        "X-User-Id": "u_edit_srv",
        "Content-Type": "video/mp4",
        "Content-Length": "9",
        "X-Edit-Prompt": "Add%20captions",
        "X-Reference-Url": "https%3A%2F%2Fwww.facebook.com%2Freel%2F111",
    }
    h = DummyHandler("POST", "/api/videos/edit", hdr, body=b"123456789")
    h.do_POST()
    assert h.response_status == 201
    job1 = json.loads(h.wfile.getvalue().decode())["job"]
    assert job1["job_type"] == "edit"
    assert job1["prompt"] == "Add captions"
    assert job1["reference_video_url"] == "https://www.facebook.com/reel/111"

    # 2. JSON submission referencing an existing completed job
    out_key = f"videos/u_edit_srv/{job1['id']}/output.mp4"
    blobs.put(out_key, b"completed-video", content_type="video/mp4")
    v_store.mark_completed(job1["id"], out_key)

    payload = json.dumps({
        "source_job_id": job1["id"],
        "prompt": "Apply punch zoom",
        "reference_video_url": "https://www.facebook.com/reel/222",
    }).encode()
    json_hdr = {"X-User-Id": "u_edit_srv", "Content-Type": "application/json", "Content-Length": str(len(payload))}
    h2 = DummyHandler("POST", "/api/videos/edit", json_hdr, body=payload)
    h2.do_POST()
    assert h2.response_status == 201
    job2 = json.loads(h2.wfile.getvalue().decode())["job"]
    assert job2["job_type"] == "edit"
    assert job2["source_video_blob_key"] == out_key
    assert s.VIDEO_RUNNER.trigger.call_count == 2

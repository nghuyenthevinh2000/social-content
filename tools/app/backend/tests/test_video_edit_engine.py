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
    plan_edit_video,
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


def test_build_video_edit_acp_prompt_render_on_client(tmp_path: Path):
    prompt = build_video_edit_acp_prompt(
        source_video_path=None,
        output_path=None,
        prompt="Add Vietnamese hook card and captions",
        work_dir=tmp_path / "work",
        render_on_client=True,
    )
    assert "PLAN-ONLY MODE" in prompt
    assert "edit_config.json" in prompt
    assert "Do NOT run `effect_editor.py`, `ffmpeg`, or `ffprobe`" in prompt
    assert "punch_zoom" in prompt


def test_plan_edit_video_from_client_metadata(monkeypatch, tmp_path: Path):
    captured = {}
    work_dir = tmp_path / "plan_work"

    def fail_subprocess(*_args, **_kwargs):
        raise AssertionError("subprocess should not run when client metadata is provided")

    class FakeACPClient:
        def __init__(self, command, cwd, timeout_sec=600.0):
            captured["command"] = command

        def initialize(self):
            return {}

        def new_session(self):
            return "sess_plan_1"

        def prompt(self, session_id, text):
            captured["prompt"] = text
            (work_dir / "edit_config.json").write_text(
                json.dumps({
                    "input_video": "/tmp/should_be_stripped.mp4",
                    "output_video": "/tmp/should_be_stripped_out.mp4",
                    "width": 720,
                    "height": 1280,
                    "fps": 24,
                    "loudnorm": True,
                    "effects": [{"type": "color_grade", "contrast": 1.05}],
                }),
                encoding="utf-8",
            )
            return "done"

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("tools.app.backend.video_engine.edit.subprocess.run", fail_subprocess)
    monkeypatch.setattr("tools.app.backend.video_engine.edit.ACPClient", FakeACPClient)
    monkeypatch.setattr(
        "tools.app.backend.research_engine.research.configured_agent",
        lambda: {"id": "opencode", "command": ["opencode", "acp"]},
    )

    plan = plan_edit_video(
        prompt="Add subtle color grade",
        probe={"width": 1080, "height": 1920, "fps": 30.0, "duration": 12.5, "has_audio": True},
        keyframes=[b"jpg0", b"jpg1"],
        transcript={"language": "vi", "segments": []},
        work_dir=work_dir,
        pre_decompose=True,
    )
    assert captured["closed"] is True
    assert "PLAN-ONLY MODE" in captured["prompt"]
    assert (work_dir / "user_probe.json").exists()
    assert (work_dir / "user_frames" / "f_0.jpg").read_bytes() == b"jpg0"
    assert (work_dir / "user_frames" / "f_1.jpg").read_bytes() == b"jpg1"
    assert (work_dir / "user_transcript.json").exists()
    assert "input_video" not in plan
    assert "output_video" not in plan
    assert plan["effects"] == [{"type": "color_grade", "contrast": 1.05}]


def test_plan_edit_video_transcribes_client_audio(monkeypatch, tmp_path: Path):
    work_dir = tmp_path / "plan_asr_work"
    asr_calls = []

    def fake_asr(audio_bytes: bytes, audio_format: str = "wav", speech_segments=None):
        asr_calls.append((audio_bytes, audio_format))
        from tools.app.backend.video_engine.edit import _align_text_to_speech_segments
        segs = _align_text_to_speech_segments("Xin chào các bạn", speech_segments or [])
        return {"engine": "local", "language": "Vietnamese", "text": "Xin chào các bạn", "segments": segs}

    class FakeACPClient:
        def __init__(self, command, cwd, timeout_sec=600.0):
            pass

        def initialize(self):
            return {}

        def new_session(self):
            return "sess_asr"

        def prompt(self, session_id, text):
            assert "user_transcript.json" in text
            (work_dir / "edit_config.json").write_text(
                json.dumps({"width": 720, "height": 1280, "fps": 24, "effects": [{"type": "color_grade"}]}),
                encoding="utf-8",
            )
            return "done"

        def close(self):
            pass

    monkeypatch.setattr("tools.app.backend.video_engine.edit._transcribe_client_audio", fake_asr)
    monkeypatch.setattr("tools.app.backend.video_engine.edit.ACPClient", FakeACPClient)
    monkeypatch.setattr(
        "tools.app.backend.research_engine.research.configured_agent",
        lambda: {"id": "opencode", "command": ["opencode", "acp"]},
    )

    plan = plan_edit_video(
        prompt="Add captions",
        probe={
            "width": 720,
            "height": 1280,
            "fps": 30,
            "duration": 8.0,
            "has_audio": True,
            "speech_segments": [{"start": 0.4, "end": 1.2, "energy": 0.2}, {"start": 1.5, "end": 2.6, "energy": 0.2}],
        },
        audio_bytes=b"RIFFfakewav",
        audio_format="wav",
        work_dir=work_dir,
        pre_decompose=False,
    )
    assert asr_calls == [(b"RIFFfakewav", "wav")]
    tx_data = json.loads((work_dir / "user_transcript.json").read_text(encoding="utf-8"))
    assert tx_data["text"] == "Xin chào các bạn"
    assert len(tx_data["segments"]) == 2
    assert tx_data["segments"][0]["start"] == 0.4
    assert plan["effects"] == [{"type": "color_grade"}]


def test_video_runner_executes_edit_plan_job_and_separate_pool():
    import base64
    import threading

    store = VideoJobStore()
    meta_key = "videos/u_plan/uploads/meta.json"
    blobs.put(
        meta_key,
        json.dumps({
            "probe": {"width": 720, "height": 1280, "fps": 30, "duration": 10.0, "has_audio": True},
            "keyframes_b64": [base64.b64encode(b"frame0").decode("ascii")],
            "transcript": {"language": "vi", "segments": []},
        }).encode("utf-8"),
        content_type="application/json",
    )

    # Occupy the single heavy-pool slot to verify edit_plan runs in its own pool.
    heavy_key = "videos/u_heavy/uploads/src.mp4"
    blobs.put(heavy_key, b"raw-video", content_type="video/mp4")
    heavy_job = store.create_edit_job(user_id="u_heavy", prompt="heavy", source_video_blob_key=heavy_key)
    plan_job = store.create_edit_plan_job(
        user_id="u_plan",
        prompt="Plan hook card",
        input_blob_key=meta_key,
        reference_video_url="https://www.tiktok.com/@a/video/1",
    )
    assert plan_job["job_type"] == "edit_plan"
    assert plan_job["cost"] == 0

    heavy_started = threading.Event()
    release_heavy = threading.Event()
    plan_done = threading.Event()
    captured = {}

    def slow_editor(source_video_path, prompt, output_path, reference_video_url=None):
        heavy_started.set()
        release_heavy.wait(timeout=5.0)
        output_path.write_bytes(b"heavy-out")
        return output_path

    def fast_planner(prompt, probe=None, keyframes=None, transcript=None, audio_bytes=None, audio_format="wav", reference_video_url=None):
        captured["prompt"] = prompt
        captured["probe"] = probe
        captured["keyframes"] = keyframes
        captured["transcript"] = transcript
        captured["ref"] = reference_video_url
        plan_done.set()
        return {"width": 720, "height": 1280, "fps": 24, "effects": [{"type": "color_grade"}]}

    runner = VideoRunner(store, max_workers=1, max_plan_workers=4, editor=slow_editor, planner=fast_planner)
    try:
        runner.trigger()
        assert heavy_started.wait(timeout=3.0)
        assert plan_done.wait(timeout=3.0)
    finally:
        release_heavy.set()
        runner.shutdown()

    # Wait briefly for mark_completed DB write
    for _ in range(30):
        updated = store.get_job("u_plan", plan_job["id"])
        if updated and updated["status"] == "completed":
            break
        import time
        time.sleep(0.05)

    assert updated["status"] == "completed"
    assert captured["keyframes"] == [b"frame0"]
    assert captured["ref"] == "https://www.tiktok.com/@a/video/1"
    saved_plan = json.loads(blobs.get(updated["blob_key"]).decode("utf-8"))
    assert saved_plan["effects"] == [{"type": "color_grade"}]


def test_server_video_edit_plan_routes():
    import base64
    import tools.app.backend.server as s

    v_store = VideoJobStore()
    s.VIDEO_STORE = v_store
    s.VIDEO_RUNNER = mock.MagicMock()

    payload = json.dumps({
        "prompt": "Add hook card and subtitles",
        "probe": {"width": 720, "height": 1280, "fps": 30, "duration": 10.0, "has_audio": True},
        "keyframes_b64": [base64.b64encode(b"jpg0").decode("ascii")],
        "reference_video_url": "https://www.facebook.com/reel/333",
    }).encode("utf-8")
    hdr = {
        "X-User-Id": "u_plan_srv",
        "Content-Type": "application/json",
        "Content-Length": str(len(payload)),
    }
    h = DummyHandler("POST", "/api/videos/edit-plan", hdr, body=payload)
    h.do_POST()
    assert h.response_status == 201
    job = json.loads(h.wfile.getvalue().decode())["job"]
    assert job["job_type"] == "edit_plan"
    assert job["reference_video_url"] == "https://www.facebook.com/reel/333"
    assert s.VIDEO_RUNNER.trigger.call_count == 1

    # Complete the plan job and fetch GET /api/videos/<id>/plan
    plan_key = f"videos/u_plan_srv/{job['id']}/edit_config.json"
    blobs.put(plan_key, json.dumps({"width": 720, "height": 1280, "effects": [{"type": "color_grade"}]}).encode("utf-8"), content_type="application/json")
    v_store.mark_completed(job["id"], plan_key)

    h_get = DummyHandler("GET", f"/api/videos/{job['id']}/plan", {"X-User-Id": "u_plan_srv"})
    h_get.do_GET()
    assert h_get.response_status == 200
    body = json.loads(h_get.wfile.getvalue().decode())
    assert body["ok"] is True
    assert body["plan"]["effects"] == [{"type": "color_grade"}]

    # Upload rendered MP4 back to POST /api/videos/<id>/file
    mp4_bytes = b"rendered-client-mp4"
    h_up = DummyHandler(
        "POST",
        f"/api/videos/{job['id']}/file",
        {"X-User-Id": "u_plan_srv", "Content-Type": "video/mp4", "Content-Length": str(len(mp4_bytes))},
        body=mp4_bytes,
    )
    h_up.do_POST()
    assert h_up.response_status == 200
    up_body = json.loads(h_up.wfile.getvalue().decode())
    assert up_body["ok"] is True
    assert up_body["job"]["video_path"].endswith("/output.mp4")
    assert blobs.get(up_body["job"]["video_path"]) == mp4_bytes

    # GET /plan still works after video_path switched to output.mp4
    h_get2 = DummyHandler("GET", f"/api/videos/{job['id']}/plan", {"X-User-Id": "u_plan_srv"})
    h_get2.do_GET()
    assert h_get2.response_status == 200
    assert json.loads(h_get2.wfile.getvalue().decode())["plan"]["effects"] == [{"type": "color_grade"}]


def test_template_sanitizer_and_extractor():
    from tools.app.backend.video_engine.templates import (
        extract_template_from_edit_config,
        sanitize_template_config,
    )

    sanitized = sanitize_template_config({
        "name": "My Style",
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "input_video": "/etc/passwd",
        "sfx_dir": "/tmp/sfx",
        "step_sfx": "pop",
        "cta_sfx": "rm -rf",
        "hook_card_style": {
            "type": "text_box",
            "bg_color": "#B91C1C",
            "lines": ["SECRET"],
            "start": 0.0,
            "font": "../evil.ttf",
        },
    })
    assert "input_video" not in sanitized
    assert "sfx_dir" not in sanitized
    assert sanitized["step_sfx"] == "pop"
    assert "cta_sfx" not in sanitized
    assert sanitized["hook_card_style"] == {"bg_color": "#B91C1C"}

    extracted = extract_template_from_edit_config({
        "width": 720,
        "height": 1280,
        "fps": 24,
        "effects": [
            {"type": "color_grade", "contrast": 1.05, "saturation": 1.1},
            {"type": "text_box", "variant": "hook", "bg_color": "#B91C1C", "lines": ["HOOK"], "start": 0.0, "end": 2.0},
            {"type": "text_box", "variant": "box", "stroke_color": "#0284C7", "lines": ["STEP 1"], "start": 2.0, "end": 4.0},
            {"type": "text_box", "variant": "info", "y": 1100, "title": "CTA", "start": 4.0, "end": 6.0},
            {"type": "subtitles", "color": "#FFE119", "outline_color": "#000000", "uppercase": True, "items": [{"start": 0.0, "end": 1.0, "text": "hi"}]},
            {"type": "punch_zoom", "windows": [{"start": 2.0, "end": 2.4, "scale": 1.08}]},
            {"type": "sfx", "time": 2.0, "sound": "pop"},
            {"type": "sfx", "time": 4.0, "sound": "ding"},
        ],
    })
    assert extracted["color_grade"] == {"contrast": 1.05, "saturation": 1.1}
    assert extracted["hook_card_style"] == {"variant": "hook", "bg_color": "#B91C1C"}
    assert extracted["step_anchor_style"] == {"variant": "box", "stroke_color": "#0284C7"}
    assert extracted["cta_style"] == {"variant": "info", "y": 1100}
    assert extracted["subtitle_style"]["color"] == "#FFE119"
    assert extracted["subtitle_style"]["outline_color"] == "#000000"
    assert extracted["subtitle_style"]["uppercase"] is True
    assert extracted["punch_zoom_scale"] == 1.08
    assert extracted["punch_zoom_duration"] == 0.4
    assert extracted["step_sfx"] == "pop"
    assert extracted["cta_sfx"] == "ding"


def test_video_template_store_and_routes():
    import tools.app.backend.server as s
    from tools.app.backend.video_engine.templates import VideoTemplateStore

    tpl_store = VideoTemplateStore()
    synced = tpl_store.sync_builtin_templates()
    assert synced >= 1
    assert tpl_store.delete_template("u_owner", "kinetic-explainer") == "forbidden"

    v_store = VideoJobStore()
    s.VIDEO_STORE = v_store
    s.TEMPLATE_STORE = tpl_store
    s.VIDEO_RUNNER = mock.MagicMock()

    # 1. GET /api/videos/templates returns built-in kinetic-explainer
    h_list = DummyHandler("GET", "/api/videos/templates", {"X-User-Id": "u_owner"})
    h_list.do_GET()
    assert h_list.response_status == 200
    tpls = json.loads(h_list.wfile.getvalue().decode())["templates"]
    assert any(t["id"] == "kinetic-explainer" and t["source"] == "builtin" and t["is_owner"] is False for t in tpls)

    # 2. POST /api/videos/edit-plan with template_id and empty prompt
    payload = json.dumps({
        "prompt": "",
        "template_id": "kinetic-explainer",
        "probe": {"width": 720, "height": 1280, "fps": 30, "duration": 8.0, "has_audio": False},
    }).encode("utf-8")
    h_plan = DummyHandler(
        "POST",
        "/api/videos/edit-plan",
        {"X-User-Id": "u_owner", "Content-Type": "application/json", "Content-Length": str(len(payload))},
        body=payload,
    )
    h_plan.do_POST()
    assert h_plan.response_status == 201
    job = json.loads(h_plan.wfile.getvalue().decode())["job"]
    assert job["template_id"] == "kinetic-explainer"
    assert "kinetic-explainer" in job["prompt"]

    # Complete the job with produced_template
    v_store.mark_completed(
        job["id"],
        f"videos/u_owner/{job['id']}/edit_config.json",
        produced_template={"width": 1080, "height": 1920, "color_grade": {"contrast": 1.06}},
    )

    # 3. POST /api/videos/templates saves template from completed job
    save_payload = json.dumps({"job_id": job["id"], "name": "Owner Custom Style", "visibility": "public"}).encode("utf-8")
    h_save = DummyHandler(
        "POST",
        "/api/videos/templates",
        {"X-User-Id": "u_owner", "Content-Type": "application/json", "Content-Length": str(len(save_payload))},
        body=save_payload,
    )
    h_save.do_POST()
    assert h_save.response_status == 201
    saved_tpl = json.loads(h_save.wfile.getvalue().decode())["template"]
    assert saved_tpl["is_owner"] is True
    assert saved_tpl["config"]["color_grade"] == {"contrast": 1.06}

    # 4. Non-owner cannot delete (403); built-in cannot be deleted (403); owner can delete (200)
    h_del_other = DummyHandler("POST", f"/api/videos/templates/{saved_tpl['id']}/delete", {"X-User-Id": "u_other"})
    h_del_other.do_POST()
    assert h_del_other.response_status == 403

    h_del_builtin = DummyHandler("POST", "/api/videos/templates/kinetic-explainer/delete", {"X-User-Id": "u_owner"})
    h_del_builtin.do_POST()
    assert h_del_builtin.response_status == 403

    h_del_owner = DummyHandler("POST", f"/api/videos/templates/{saved_tpl['id']}/delete", {"X-User-Id": "u_owner"})
    h_del_owner.do_POST()
    assert h_del_owner.response_status == 200
    assert tpl_store.get_template(saved_tpl["id"], user_id="u_owner") is None

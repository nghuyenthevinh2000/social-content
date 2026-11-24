"""Video Research Pipeline: transcript analysis, visual extraction, video-structure breakdown, and director prompts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer import profiling, runtime
from tools.loop.viral_analyzer.platforms import (
    REEL_PATTERNS,
    canonicalize_reel_url,
    detect_platform,
    extract_video_id,
    is_reel_url,
    resolve_short_url,
)
from tools.loop.viral_analyzer.video_research.collect import (
    _download_reel_video,
    _extract_video_frames,
)
from tools.loop.viral_analyzer.video_research.config import (
    TEMP_DIR,
    VISUAL_PROMPT,
    _fallback_reel_url,
    _reel_digest,
    build_video_structure_prompt,
    format_director_prompt,
    get_visual_prompt,
)
from tools.loop.viral_analyzer.video_research.transcriber import (
    fetch_reel_transcript,
    fetch_top_reels_transcripts,
)

logger = logging.getLogger("reel_research")


def _normalize_outline(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[\n;•]+", value) if part.strip()]
    return []


def _normalize_sources(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value.startswith("http") else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).startswith("http")]
    return []


def _resolve_to_reel_url(url: str, reels: List[Dict[str, Any]]) -> str:
    """Ensure URL points directly to a reel/video rather than a generic profile/page."""
    url = url.strip()
    if not url:
        return ""
    if is_reel_url(url) or any(
        tok in url
        for tok in ("/reel/", "/reels/", "/videos/", "/video/", "/posts/", "permalink.php", "/watch", "/shorts/", "youtu.be/", "/p/", "/tv/")
    ):
        return url

    clean = url.rstrip("/")
    target_handle = clean.split("/")[-1].replace("@", "").lower()

    for r in reels:
        r_handle = str(r.get("author_handle") or "").strip().lower()
        if r_handle and (r_handle == target_handle or target_handle in r_handle or r_handle in target_handle):
            if r.get("url") or r.get("reel_url"):
                return str(r.get("url") or r.get("reel_url")).strip()
            if r.get("video_id"):
                return _fallback_reel_url(r)

    if "facebook.com" in clean and not clean.endswith("/reels"):
        return f"{clean}/reels/"

    return url


def normalize_video_analyses(
    data: Any,
    fallback: List[Dict[str, Any]],
    reels: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        data = data.get("analyses") or data.get("videos") or data.get("topics") or data.get("ideas") or [data]
    if not isinstance(data, list):
        return fallback
    analyses = []
    dur = get_video_duration()
    ranked_reels = sorted(
        reels or [],
        key=lambda r: (int(r.get("views") or 0), float(r.get("velocity_per_hour") or 0)),
        reverse=True,
    )
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        raw_sources = _normalize_sources(item.get("source_urls") or item.get("sources"))
        sources = [_resolve_to_reel_url(u, reels or []) for u in raw_sources if u]
        if not sources and index < len(fallback):
            sources = fallback[index].get("source_urls", [])
        if not sources and ranked_reels and index < len(ranked_reels):
            top_url = (
                ranked_reels[index].get("url")
                or ranked_reels[index].get("reel_url")
                or _fallback_reel_url(ranked_reels[index])
                or None
            )
            if top_url:
                sources = [top_url]
        prompt_val = str(item.get("prompt") or item.get("director_prompt") or "").strip()
        if not prompt_val:
            prompt_val = format_director_prompt(item, sheet_name=sheet_name, actor_profile=actor_profile)
        elif actor_profile:
            from tools.app.backend.video_engine import _apply_actor_profile_to_structured_prompt
            prompt_val = _apply_actor_profile_to_structured_prompt(prompt_val, actor_profile)

        matched_reel = None
        if ranked_reels:
            for r in ranked_reels:
                r_url = r.get("url") or r.get("reel_url") or ""
                r_id = str(r.get("video_id") or "")
                if sources and any((r_url and r_url in s) or (r_id and r_id in s) for s in sources):
                    matched_reel = r
                    break
            if not matched_reel and index < len(ranked_reels):
                matched_reel = ranked_reels[index]

        fb_item = fallback[index] if index < len(fallback) else {}
        t_views = int((matched_reel.get("views") if matched_reel else fb_item.get("views")) or 0)
        t_vel = float((matched_reel.get("velocity_per_hour") if matched_reel else fb_item.get("velocity_per_hour")) or 0)
        t_pool = (matched_reel.get("current_pool") if matched_reel else fb_item.get("current_pool")) or 0
        t_pool_name = str((matched_reel.get("pool_name") if matched_reel else fb_item.get("pool_name")) or "")
        t_likes = int((matched_reel.get("likes") if matched_reel else fb_item.get("likes")) or 0)
        t_comments = int((matched_reel.get("comments") if matched_reel else fb_item.get("comments")) or 0)
        t_video_url = (matched_reel.get("video_url") if matched_reel else fb_item.get("video_url")) or None
        t_video_id = str((matched_reel.get("video_id") if matched_reel else fb_item.get("video_id")) or "")
        t_handle = str((matched_reel.get("author_handle") if matched_reel else fb_item.get("author_handle")) or "")
        t_name = str((matched_reel.get("author_name") if matched_reel else fb_item.get("author_name")) or "")
        t_transcript = str((matched_reel.get("transcript") if matched_reel else fb_item.get("transcript")) or "").strip()
        t_visual = str((matched_reel.get("visual") if matched_reel else fb_item.get("visual")) or "").strip()
        resolved_reel_url = sources[0] if sources else (matched_reel.get("url") or matched_reel.get("reel_url") if matched_reel else "")
        t_platform = str((matched_reel.get("platform") if matched_reel else fb_item.get("platform")) or "").strip()
        if not t_platform and resolved_reel_url:
            detected = detect_platform(resolved_reel_url)
            t_platform = detected if detected != "web" else "facebook"
        if not t_platform:
            t_platform = "facebook"

        analyses.append(
            {
                "title": str(item.get("title") or "").strip() or (fallback[index]["title"] if index < len(fallback) else "Phân tích cấu trúc video"),
                "hook": str(item.get("hook") or "").strip(),
                "angle": str(item.get("angle") or "").strip(),
                "why_viral": str(item.get("why_viral") or item.get("why") or "").strip(),
                "outline": _normalize_outline(item.get("outline")),
                "format": str(item.get("format") or f"Reels {dur}s UGC").strip(),
                "source_urls": sources,
                "reel_url": resolved_reel_url,
                "platform": t_platform,
                "video_url": t_video_url,
                "video_id": t_video_id,
                "views": t_views,
                "velocity_per_hour": t_vel,
                "current_pool": t_pool,
                "pool_name": t_pool_name,
                "likes": t_likes,
                "comments": t_comments,
                "author_handle": t_handle,
                "author_name": t_name,
                "transcript": t_transcript,
                "visual": t_visual,
                "prompt": prompt_val,
                "generated_by": "agent",
            }
        )
    if limit is not None:
        while len(analyses) < len(fallback) and len(analyses) < limit:
            analyses.append(fallback[len(analyses)])

    has_views = any((a.get("views") or 0) > 0 for a in analyses)
    if has_views:
        analyses.sort(
            key=lambda x: (
                int(x.get("views") or 0),
                float(x.get("velocity_per_hour") or 0),
            ),
            reverse=True,
        )
    return analyses[:limit] if limit is not None else analyses


def _extract_json_candidates(text: str) -> List[str]:
    text = text.strip()
    candidates = [text]
    candidates.extend(re.findall(r"```(?:json)?\s*(.*?)```", text, re.S | re.I))
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    return candidates


def parse_video_analyses(
    text: str,
    fallback: List[Dict[str, Any]],
    reels: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    for candidate in _extract_json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        analyses = normalize_video_analyses(
            data, fallback, reels=reels, sheet_name=sheet_name, actor_profile=actor_profile, limit=limit
        )
        if analyses:
            return analyses
    return fallback


def heuristic_video_analyses(
    sheet_name: str,
    reels: List[Dict[str, Any]],
    actor_profile: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not reels:
        return []
    dur = get_video_duration()
    ranked = sorted(
        reels,
        key=lambda r: (
            int(r.get("views") or 0),
            float(r.get("velocity_per_hour") or 0),
            int(r.get("current_pool") or 0),
        ),
        reverse=True,
    )
    target_reels = ranked[:limit] if limit is not None else ranked
    analyses: List[Dict[str, Any]] = []
    for reel in target_reels:
        title = str(reel.get("title") or "").strip() or f"Video từ @{reel.get('author_handle', 'reel')}"
        views = int(reel.get("views") or 0)
        velocity = float(reel.get("velocity_per_hour") or 0)
        reel_url = reel.get("url") or reel.get("reel_url") or _fallback_reel_url(reel)
        platform = str(reel.get("platform") or "").strip()
        if not platform and reel_url:
            detected = detect_platform(reel_url)
            platform = detected if detected != "web" else "facebook"
        if not platform:
            platform = "facebook"
        entry = {
            "title": title[:90],
            "hook": f"Mở đầu 3s giữ chân người xem ({views:,} lượt xem / 48h)." if views else "Mở đầu 3 giây đầu gây tò mò trực tiếp từ video gốc.",
            "angle": f"Cấu trúc P{reel.get('current_pool', 0)} - {reel.get('pool_name', '')}: giữ nhịp nhanh và bám sát bố cục gốc." if views else "Phân tích cấu trúc mở đầu - triển khai - kết của video gốc.",
            "why_viral": f"{views:,} views, {velocity:,.0f} views/giờ, pool P{reel.get('current_pool', 0)}." if views else "Video giữ chân người xem nhờ hook mở đầu và nhịp triển khai gọn.",
            "outline": [
                f"00:00-00:03 Hook mở đầu từ video gốc của @{reel.get('author_handle', 'creator')}",
                "00:03-00:26 Triển khai nội dung chính theo nhịp video gốc",
                "00:26-00:30 Kết luận & CTA tương tác",
            ],
            "format": f"Reels {dur}s UGC",
            "source_urls": [reel_url] if reel_url else [],
            "reel_url": reel_url,
            "platform": platform,
            "video_url": reel.get("video_url"),
            "video_id": str(reel.get("video_id") or ""),
            "views": views,
            "velocity_per_hour": velocity,
            "current_pool": reel.get("current_pool", 0),
            "pool_name": str(reel.get("pool_name") or ""),
            "likes": int(reel.get("likes") or 0),
            "comments": int(reel.get("comments") or 0),
            "shares": int(reel.get("shares") or 0),
            "author_handle": str(reel.get("author_handle") or ""),
            "author_name": str(reel.get("author_name") or ""),
            "transcript": str(reel.get("transcript") or "").strip(),
            "visual": str(reel.get("visual") or "").strip(),
            "generated_by": "heuristic",
        }
        entry["prompt"] = format_director_prompt(entry, sheet_name=sheet_name, actor_profile=actor_profile, language=language)
        analyses.append(entry)
    return analyses


def analyze_video_structure(
    agent_id: str,
    sheet_name: str,
    targets: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
    cwd: Path,
    timeout_sec: float,
    log: Callable[[str], None],
    model: Optional[str] = None,
    actor_profile: Optional[Dict[str, Any]] = None,
    ctx: Optional[runtime.EngineContext] = None,
    limit: Optional[int] = None,
    language: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not reels:
        log(f"Không có reel nào cho '{sheet_name}'; bỏ qua phân tích video.")
        return [], None
    fallback = heuristic_video_analyses(sheet_name, reels, actor_profile=actor_profile, limit=limit, language=language)
    prompt = build_video_structure_prompt(
        sheet_name, targets, reels, actor_profile=actor_profile, language=language
    )
    eng_ctx = ctx or runtime.default_context()

    if eng_ctx.agent_runner is not None:
        try:
            text = eng_ctx.agent_runner(prompt)
            if not str(text).strip():
                raise ACPError("Agent trả về nội dung rỗng.")
            analyses = parse_video_analyses(
                str(text), fallback, reels=reels, sheet_name=sheet_name, actor_profile=actor_profile, limit=limit
            )
            fetch_top_reels_transcripts(analyses[:limit] if limit is not None else analyses, ctx=eng_ctx)
            return analyses, None
        except Exception as exc:
            log(f"Agent runner thất bại: {exc}")
            fb_slice = fallback[:limit] if limit is not None else fallback
            fetch_top_reels_transcripts(fb_slice, ctx=eng_ctx)
            return fb_slice, str(exc)

    client = None
    from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

    with _harness_lock(log):
        try:
            preset = resolve_agent(agent_id, model=model)
            model_info = f" ({preset['model']})" if preset.get("model") else ""
            log(f"Gọi harness {preset['label']}{model_info} qua ACP...")
            client = ACPClient(preset["command"], cwd=cwd, timeout_sec=timeout_sec, log=log)
            client.initialize()
            session_id = client.new_session()
            text = client.prompt(session_id, prompt)
            if not text.strip():
                raise ACPError("Agent trả về nội dung rỗng.")
            analyses = parse_video_analyses(
                text, fallback, reels=reels, sheet_name=sheet_name, actor_profile=actor_profile, limit=limit
            )
            if analyses and analyses[0].get("generated_by") == "agent":
                log(f"Agent đã trả về {len(analyses)} phân tích video.")
            else:
                log("Không parse được JSON từ agent; dùng phân tích dự phòng.")
            fetch_top_reels_transcripts(analyses[:limit] if limit is not None else analyses)
            return analyses, None
        except Exception as exc:
            detail = str(exc)
            if client is not None and client.stderr_tail:
                detail = f"{detail} | stderr: {client.stderr_tail}"
            if "auth" in detail.lower():
                detail = f"{detail} | Gợi ý đăng nhập harness rồi thử lại."
            log(f"ACP thất bại: {detail}")
            fb_slice = fallback[:limit] if limit is not None else fallback
            fetch_top_reels_transcripts(fb_slice)
            return fb_slice, detail
        finally:
            if client is not None:
                client.close()


def analyze_video_visuals(
    video_path: Path,
    agent_id: str,
    cwd: Path,
    timeout_sec: float,
    log: Callable[[str], None],
    model: Optional[str] = None,
    ctx: Optional[runtime.EngineContext] = None,
    language: Optional[str] = None,
) -> str:
    """Describe the downloaded Reel's on-screen visuals with an injected runner or CLI harness."""
    frame_dir = video_path.parent / f"{video_path.stem}_frames"
    frames = _extract_video_frames(video_path, frame_dir)
    if not frames:
        log("Không trích xuất được khung hình video.")
        return ""

    eng_ctx = ctx or runtime.default_context()
    client = None
    visual_prompt = get_visual_prompt(language)
    try:
        images = [(frame.read_bytes(), "image/jpeg") for frame in frames]
        if eng_ctx.agent_runner is not None:
            return str(eng_ctx.agent_runner(visual_prompt, images=images)).strip()

        from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

        with _harness_lock(log):
            preset = resolve_agent(agent_id, model=model)
            log(f"Phân tích hình ảnh bằng harness {preset['label']}...")
            client = ACPClient(preset["command"], cwd=cwd, timeout_sec=timeout_sec, log=log)
            client.initialize()
            session_id = client.new_session()
            return client.prompt(session_id, visual_prompt, images=images).strip()
    except Exception as exc:
        log(f"Phân tích hình ảnh bằng harness thất bại: {exc}")
        return ""
    finally:
        if client is not None:
            client.close()
        for frame in frames:
            try:
                frame.unlink()
            except OSError:
                pass
        try:
            frame_dir.rmdir()
        except OSError:
            pass


_LOCAL_TRANSCRIBER: Any = None


def _get_local_transcriber() -> Any:
    global _LOCAL_TRANSCRIBER
    if _LOCAL_TRANSCRIBER is None:
        from tools.loop.viral_analyzer.video_research.transcriber.local import UnifiedTranscriber
        _LOCAL_TRANSCRIBER = UnifiedTranscriber()
    return _LOCAL_TRANSCRIBER


def _transcribe_local_fallback(
    video_path: Path,
    vid: Optional[str],
    clean_url: str,
    log: Callable[[str], None],
) -> Optional[str]:
    """Run local ASR on an already-downloaded reel video when Glasser transcript is unavailable."""
    audio_path = video_path.with_suffix(".wav")
    chunk_paths: List[Path] = []
    try:
        from tools.loop.viral_analyzer.cache import save_cached_transcript
        from tools.loop.viral_analyzer.video_research.transcriber.local import extract_audio_ffmpeg, ffmpeg_bin

        if not extract_audio_ffmpeg(video_path, audio_path, max_duration_sec=300):
            return None
        chunk_pattern = video_path.parent / f"{video_path.stem}_chunk_%03d.wav"
        proc = subprocess.run(
            [
                ffmpeg_bin(),
                "-y",
                "-i", str(audio_path),
                "-f", "segment",
                "-segment_time", "45",
                "-c", "copy",
                str(chunk_pattern),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        chunk_paths = sorted(video_path.parent.glob(f"{video_path.stem}_chunk_*.wav"))
        targets = chunk_paths if (proc.returncode == 0 and chunk_paths) else [audio_path]

        transcriber = _get_local_transcriber()
        parts: List[str] = []
        for idx, part_path in enumerate(targets, 1):
            log(f"Đang chạy transcript local đoạn {idx}/{len(targets)}...")
            result = transcriber.transcribe_audio(part_path)
            chunk_text = str(result.get("transcript") or result.get("text") or "").strip()
            if chunk_text:
                parts.append(chunk_text)

        text = " ".join(parts).strip()
        if text:
            log(f"Đã trích xuất transcript local ({len(text)} ký tự).")
            if vid:
                save_cached_transcript(vid, text, url=clean_url)
            return text
    except Exception as exc:
        log(f"Không thể chạy transcript local: {exc}")
    finally:
        for p in [audio_path, *chunk_paths]:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
    return None


def _resolve_reel_author(
    clean_url: str,
    vid: Optional[str],
    author_handle: Optional[str] = None,
) -> str:
    handle = (author_handle or "").strip().lstrip("@")
    if handle and handle not in {"saved_reel", "unknown"}:
        return handle
    m = re.search(r"/@([^/?#]+)", clean_url)
    if m:
        return m.group(1)
    m_fb = re.search(r"facebook\.com/([^/?#]+)/videos/", clean_url, re.I)
    if m_fb and m_fb.group(1).lower() not in {"watch", "reel", "share", "groups"}:
        return m_fb.group(1)
    try:
        from tools.app.backend.db import ro

        with ro() as conn:
            row = conn.execute(
                "SELECT author_handle FROM videos WHERE url = %s OR (%s <> '' AND video_id = %s) LIMIT 1",
                (clean_url, vid or "", vid or ""),
            ).fetchone()
            if row and row[0] and str(row[0]).strip() not in {"saved_reel", "unknown"}:
                return str(row[0]).strip().lstrip("@")
    except Exception:
        pass
    return ""


def research_single_reel(
    reel_url: str,
    sheet_name: str = "Reel đã lưu",
    actor_profile: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    cwd: Optional[Path] = None,
    timeout_sec: float = 120.0,
    ctx: Optional[runtime.EngineContext] = None,
    language: Optional[str] = None,
    author_handle: Optional[str] = None,
    author_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute direct deep research on an individual Reel URL."""
    _log = log or (lambda msg: logger.info(msg))
    canon_res = canonicalize_reel_url(reel_url)
    clean_url = canon_res[0] if canon_res else reel_url.strip()
    if canon_res:
        platform = canon_res[1]
    else:
        detected = detect_platform(clean_url)
        platform = detected if detected != "web" else "facebook"
    vid = extract_video_id(clean_url)

    _log(f"Bắt đầu phân tích Reel: {clean_url}")

    with profiling.span("video", "transcript"):
        transcript = fetch_reel_transcript(clean_url, video_id=vid)
    if transcript:
        _log(f"Đã trích xuất transcript ({len(transcript)} ký tự).")
    else:
        _log("Không tìm thấy transcript; tiến hành phân tích qua cấu trúc video và hook.")

    visual = ""
    has_runner = bool(agent_id or (ctx and ctx.agent_runner))
    ctx_kwargs: Dict[str, Any] = {"ctx": ctx} if ctx is not None else {}
    with profiling.span("video", "visuals"):
        if has_runner and cwd:
            video_path = _download_reel_video(clean_url, vid, _log)
            if video_path:
                if not transcript:
                    transcript = _transcribe_local_fallback(video_path, vid, clean_url, _log)
                visual = analyze_video_visuals(
                    video_path, agent_id or "", cwd, timeout_sec, _log, model=model, language=language, **ctx_kwargs
                )
                if visual:
                    _log(f"Đã phân tích hình ảnh video ({len(visual)} ký tự).")
                    try:
                        video_path.unlink()
                        _log("Đã xoá video tạm sau khi phân tích.")
                    except OSError:
                        pass
                else:
                    _log(f"Chưa phân tích được hình ảnh; giữ video tạm để kiểm tra: {video_path}")
        else:
            _log("Không có harness để phân tích hình ảnh video; bỏ qua.")

    eff_author_handle = _resolve_reel_author(clean_url, vid, author_handle=author_handle)

    reel_obj: Dict[str, Any] = {
        "url": clean_url,
        "reel_url": clean_url,
        "video_id": vid or "",
        "platform": platform,
        "title": sheet_name or f"Reel {vid or ''}",
        "transcript": transcript or "",
        "visual": visual,
        "views": 0,
        "velocity_per_hour": 0,
        "current_pool": 0,
        "pool_name": "Direct Saved Reel",
        "author_handle": eff_author_handle,
        "author_name": (author_name or "").strip(),
    }

    topics: List[Dict[str, Any]] = []
    error: Optional[str] = None

    with profiling.span("video", "analyze_video_structure"):
        if has_runner and cwd:
            targets = [{"name": sheet_name, "url": clean_url}]
            topics, error = analyze_video_structure(
                agent_id=agent_id or "",
                sheet_name=sheet_name,
                targets=targets,
                reels=[reel_obj],
                cwd=cwd,
                timeout_sec=timeout_sec,
                log=_log,
                model=model,
                actor_profile=actor_profile,
                limit=1,
                language=language,
                **ctx_kwargs,
            )
            topics = topics[:1]

    if not topics:
        topics = heuristic_video_analyses(sheet_name, [reel_obj], actor_profile=actor_profile, limit=1)
        for t in topics:
            t["source_urls"] = [clean_url]
            t["reel_url"] = clean_url
            t["transcript"] = transcript or ""
            t["visual"] = visual

    return {
        "ok": True,
        "reel_url": clean_url,
        "video_id": vid,
        "platform": platform,
        "transcript": transcript,
        "visual": visual,
        "topics": topics,
        "error": error,
    }


def research_reels(
    reels: List[Dict[str, Any]],
    sheet_name: str,
    actor_profile: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    cwd: Optional[Path] = None,
    timeout_sec: float = 180.0,
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Analyze viral structure and generate replication director prompts for a collection of reels."""
    _log = log or (lambda msg: logger.info(msg))
    if not reels:
        return [], None
    targets = [{"name": r.get("author_name") or r.get("author_handle", "Reel"), "url": r.get("url") or r.get("reel_url", "")} for r in reels]
    if agent_id and cwd:
        return analyze_video_structure(
            agent_id=agent_id,
            sheet_name=sheet_name,
            targets=targets,
            reels=reels,
            cwd=cwd,
            timeout_sec=timeout_sec,
            log=_log,
            model=model,
            actor_profile=actor_profile,
            ctx=ctx,
        )
    analyses = heuristic_video_analyses(sheet_name, reels, actor_profile=actor_profile)
    fetch_top_reels_transcripts(analyses, **({"ctx": ctx} if ctx is not None else {}))
    return analyses, None

"""
effects/subtitles.py
────────────────────
Kinetic typography and subtitle rendering module.
Generates word-by-word karaoke typography with active gold highlighting,
top context badges, and bottom CTA cards in Advanced SubStation Alpha (ASS) format.
"""

import json
from pathlib import Path

DEFAULT_MAX_LINE_LEN = 24


def format_ass_time(sec: float) -> str:
    """Format seconds into ASS timestamp format H:MM:SS.cs."""
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def extract_words_from_alignment(align_path: Path, clause_bounds: list[list[float]] | None = None) -> list[dict]:
    """Extract words and timecodes from ElevenLabs character alignment."""
    align = json.loads(align_path.read_text(encoding="utf-8"))
    chars = align.get("characters", [])
    starts = align.get("characterStartTimesSeconds", [])
    ends = align.get("characterEndTimesSeconds", [])

    raw_words = []
    curr = ""
    w_start = None
    prev_e = 0.0

    for c, s, e in zip(chars, starts, ends):
        if c == " ":
            if curr:
                raw_words.append({"word": curr, "start": w_start, "end": prev_e})
                curr = ""
                w_start = None
        else:
            if w_start is None:
                w_start = s
            curr += c
        prev_e = e
    if curr:
        raw_words.append({"word": curr, "start": w_start, "end": prev_e})

    if not clause_bounds:
        return raw_words

    mapped = []
    for w in raw_words:
        mid = (w["start"] + w["end"]) / 2.0
        matched = None
        for s_s, s_e, t_s, t_e in clause_bounds:
            if s_s - 0.05 <= mid <= s_e + 0.05:
                matched = (s_s, s_e, t_s, t_e)
                break
        if matched:
            s_s, s_e, t_s, t_e = matched
            scale = (t_e - t_s) / max(0.01, (s_e - s_s))
            vw_s = t_s + (w["start"] - s_s) * scale
            vw_e = t_s + (w["end"] - s_s) * scale
            mapped.append({"word": w["word"], "start": round(vw_s, 2), "end": round(vw_e, 2)})
        else:
            mapped.append(w)
    return mapped


def group_words_into_chunks(words: list[dict], max_words: int = 4, max_gap: float = 0.45) -> list[list[dict]]:
    """Group sequential aligned words into readable 2-4 word kinetic caption chunks."""
    chunks = []
    curr_chunk = []
    for w in words:
        if not curr_chunk:
            curr_chunk.append(w)
            continue
        prev = curr_chunk[-1]
        gap = w["start"] - prev["end"]
        punct = prev["word"].endswith((".", ",", "?", "!", "…"))
        if len(curr_chunk) >= max_words or gap > max_gap or (punct and len(curr_chunk) >= 2):
            chunks.append(curr_chunk)
            curr_chunk = [w]
        else:
            curr_chunk.append(w)
    if curr_chunk:
        chunks.append(curr_chunk)
    return chunks


def format_multiline_text(text: str, max_line_len: int = DEFAULT_MAX_LINE_LEN) -> str:
    """Format text into balanced multiline ASS text if it exceeds max_line_len."""
    if not text:
        return ""
    if "\\N" in text:
        return text
    if len(text) <= max_line_len:
        return text
    for delim in (": ", "? ", ", ", " - "):
        if delim in text:
            parts = text.split(delim, 1)
            d_clean = delim.strip()
            suffix = "" if d_clean == ":" else d_clean
            return f"{parts[0]}{suffix}\\N{parts[1]}"
    words = text.split()
    half = max(1, len(words) // 2)
    return " ".join(words[:half]) + "\\N" + " ".join(words[half:])


def build_ass_subtitles(
    chunks: list[list[dict]],
    badges: list[dict],
    hook_banner: dict | None,
    out_ass_path: Path,
    width: int = 720,
    height: int = 1280,
    hook_card: dict | None = None
) -> Path:
    """Build Advanced SubStation Alpha (.ass) subtitle file."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookBanner,Arial,25,&H00000000,&H00000000,&H0000E6FF,&H80000000,-1,0,0,0,100,100,0.5,0,3,8,0,8,40,40,150,1
Style: BadgeCard,Arial,25,&H00FFFFFF,&H00000000,&H90141414,&H00000000,-1,0,0,0,100,100,0.5,0,3,8,0,8,40,40,150,1
Style: BadgeBottom,Arial,25,&H00000000,&H00000000,&H0000E6FF,&H80000000,-1,0,0,0,100,100,0.5,0,3,8,0,2,40,40,320,1
Style: CaptionBase,Arial,34,&H00FFFFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,3.5,1.2,2,30,30,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # 1. Hook Card / Banner handling
    if hook_card and hook_card.get("enabled", True):
        hook_banner = None
        if hook_card.get("suppress_captions", True):
            card_end = float(hook_card.get("end", 3.35))
            chunks = [c for c in chunks if c[-1]["end"] > card_end]

    # 2. Hook Banner (Multi-line formatted, balanced safe box)
    if hook_banner and hook_banner.get("text"):
        st = format_ass_time(hook_banner["start"])
        et = format_ass_time(hook_banner["end"])
        text = format_multiline_text(hook_banner["text"])
        events.append(f"Dialogue: 1,{st},{et},HookBanner,,0,0,0,,{{\\fade(100,100)}} {text} ")

    # 3. Badges (Unified Cards)
    for b in badges:
        st = format_ass_time(b["start"])
        et = format_ass_time(b["end"])
        pos = b.get("pos", "top")
        main_text = format_multiline_text(b["text"], max_line_len=28)
        if pos == "top":
            sub_str = f"\\N{{\\fs21\\c&H0000E6FF&}}{b['subtext']}" if b.get("subtext") else ""
            events.append(f"Dialogue: 1,{st},{et},BadgeCard,,0,0,0,,{{\\fade(120,120)}} {main_text}{sub_str} ")
        else:
            sub_str = f"\\N{{\\fs22\\c&H00000000&}}{b['subtext']}" if b.get("subtext") else ""
            events.append(f"Dialogue: 1,{st},{et},BadgeBottom,,0,0,0,,{{\\fade(120,120)}} {main_text}{sub_str} ")

    # 4. Dynamic Karaoke Captions
    for chunk in chunks:
        ch_start = chunk[0]["start"]
        ch_end = chunk[-1]["end"] + 0.15
        for i, active_w in enumerate(chunk):
            w_start = format_ass_time(active_w["start"])
            w_end = format_ass_time(chunk[i + 1]["start"] if i + 1 < len(chunk) else ch_end)
            formatted_words = []
            for j, w in enumerate(chunk):
                raw = w["word"].upper()
                if j == i:
                    formatted_words.append(f"{{\\c&H0000E6FF&\\3c&H00000000&\\fscx112\\fscy112\\bord4.0}}{raw}{{\\rCaptionBase}}")
                else:
                    formatted_words.append(f"{{\\c&H00FFFFFF&\\3c&H00000000&\\bord3.5}}{raw}{{\\rCaptionBase}}")
            line_text = " ".join(formatted_words)
            events.append(f"Dialogue: 0,{w_start},{w_end},CaptionBase,,0,0,0,,{line_text}")

    content = header + "\n".join(events) + "\n"
    out_ass_path.write_text(content, encoding="utf-8")
    return out_ass_path


def _hex_to_ass_bgr(hex_color: str, default_alpha: str = "00") -> str:
    s = hex_color.strip().lstrip("#")
    if len(s) == 6:
        r, g, b = s[0:2], s[2:4], s[4:6]
        return f"&H{default_alpha.upper()}{b.upper()}{g.upper()}{r.upper()}"
    if len(s) == 8:
        r, g, b, a = s[0:2], s[2:4], s[4:6], s[6:8]
        ass_a = f"{255 - int(a, 16):02X}"
        return f"&H{ass_a}{b.upper()}{g.upper()}{r.upper()}"
    return f"&H{default_alpha.upper()}FFFFFF"


def build_ass_from_items(
    items: list[dict],
    style: dict | None,
    out_ass_path: Path,
    width: int = 720,
    height: int = 1280,
) -> Path:
    """Write an ASS subtitle file from explicit timed caption items."""
    st = style or {}
    font = str(st.get("font", "DejaVu Sans"))
    color = _hex_to_ass_bgr(str(st.get("color", "#97E12E")))
    outline_color = _hex_to_ass_bgr(str(st.get("outline_color", "#000000")))
    outline_width = float(st.get("outline_width", 4))
    outer_color_raw = st.get("outer_outline_color")
    outer_color = _hex_to_ass_bgr(str(outer_color_raw)) if outer_color_raw else None
    outer_width = float(st.get("outer_outline_width", outline_width + 4))
    shadow = float(st.get("shadow", 1))
    font_size = int(st.get("font_size", 46))
    margin_v = int(st.get("margin_v", int(height * 0.16)))
    margin_l = int(st.get("margin_l", 36))
    margin_r = int(st.get("margin_r", 36))
    alignment = int(st.get("alignment", 2))
    bold = -1 if st.get("bold", True) else 0
    italic = -1 if st.get("italic", False) else 0
    spacing = float(st.get("spacing", 0))
    border_style = int(st.get("border_style", 1))
    back_color = _hex_to_ass_bgr(str(st.get("back_color", "#000000")), default_alpha="80")
    outer_back = _hex_to_ass_bgr(str(st.get("back_color", "#000000")), default_alpha="70")
    wrap_style = int(st.get("wrap_style", 2))
    uppercase = bool(st.get("uppercase", True))
    pop_in = bool(st.get("pop_in", True))

    inner_shadow = 0 if outer_color else shadow
    styles = []
    if outer_color:
        styles.append(
            f"Style: DefaultOuter,{font},{font_size},{outer_color},&H00FFFFFF,{outer_color},{outer_back},{bold},{italic},0,0,100,100,{spacing:g},0,{border_style},{outer_width:g},{shadow:g},{alignment},{margin_l},{margin_r},{margin_v},1"
        )
    styles.append(
        f"Style: Default,{font},{font_size},{color},&H00FFFFFF,{outline_color},{back_color},{bold},{italic},0,0,100,100,{spacing:g},0,{border_style},{outline_width:g},{inner_shadow:g},{alignment},{margin_l},{margin_r},{margin_v},1"
    )

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        f"WrapStyle: {wrap_style}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *styles,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if bool(item.get("uppercase", uppercase)):
            text = text.upper()
        text = text.replace("\n", "\\N")
        tags = []
        if "alignment" in item:
            tags.append(f"\\an{int(item['alignment'])}")
        if "font_size" in item:
            tags.append(f"\\fs{int(item['font_size'])}")
        if "bold" in item:
            tags.append(f"\\b{1 if item['bold'] else 0}")
        if "italic" in item:
            tags.append(f"\\i{1 if item['italic'] else 0}")
        if "color" in item:
            tags.append(f"\\c{_hex_to_ass_bgr(str(item['color']))}")
        if "outline_color" in item:
            tags.append(f"\\3c{_hex_to_ass_bgr(str(item['outline_color']))}")
        if bool(item.get("pop_in", pop_in)):
            tags.append(r"\fscx85\fscy85\t(0,80,\fscx100\fscy100)")
        prefix = f"{{{''.join(tags)}}}" if tags else ""
        item_mv = int(item.get("margin_v", 0))
        start = format_ass_time(float(item.get("start", 0.0)))
        end = format_ass_time(float(item.get("end", 0.0)))
        if outer_color:
            lines.append(f"Dialogue: 0,{start},{end},DefaultOuter,,0,0,{item_mv},,{prefix}{text}")
            lines.append(f"Dialogue: 1,{start},{end},Default,,0,0,{item_mv},,{prefix}{text}")
        else:
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,{item_mv},,{prefix}{text}")

    out_ass_path.parent.mkdir(parents=True, exist_ok=True)
    out_ass_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_ass_path


def apply_subtitles_filter(ass_path: Path, base_label: str = "", out_label: str = "") -> str:
    """Build FFmpeg subtitles filter string with escaped ASS path."""
    escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
    return f"{base_label}subtitles='{escaped}'{out_label}"


def apply_subtitles(cfg: dict, ctx) -> None:
    """Stack ASS subtitles (from explicit items or ElevenLabs alignment) onto the video stream."""
    ass_path = ctx.work_dir / f"{ctx.next_id('sub')}.ass"
    items = cfg.get("items")
    if items:
        merged_style = {**cfg, **(cfg.get("style") or {})}
        build_ass_from_items(items, merged_style, ass_path, ctx.width, ctx.height)
    elif cfg.get("alignment_json"):
        align_path = ctx.resolve_path(cfg["alignment_json"])
        cb_val = cfg.get("clause_bounds")
        if isinstance(cb_val, (str, Path)):
            clause_bounds = json.loads(ctx.resolve_path(cb_val).read_text(encoding="utf-8"))
        elif isinstance(cb_val, list):
            clause_bounds = cb_val
        else:
            cand_cb = align_path.parent / "clause_bounds.json"
            clause_bounds = json.loads(cand_cb.read_text(encoding="utf-8")) if cand_cb.exists() else None
        words = extract_words_from_alignment(align_path, clause_bounds)
        chunks = group_words_into_chunks(words)
        print(f"  [Captions] Extracted {len(words)} aligned words into {len(chunks)} kinetic chunks")
        build_ass_subtitles(
            chunks=chunks,
            badges=cfg.get("badges", []),
            hook_banner=cfg.get("hook_banner"),
            out_ass_path=ass_path,
            width=ctx.width,
            height=ctx.height,
            hook_card=cfg.get("hook_card"),
        )
    else:
        return

    out_lbl = ctx.next_v_label("sub")
    ctx.v_filters.append(apply_subtitles_filter(ass_path, base_label=ctx.cur_v, out_label=out_lbl))
    ctx.cur_v = out_lbl

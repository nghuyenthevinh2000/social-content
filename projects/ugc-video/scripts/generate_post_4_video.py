#!/usr/bin/env python3
"""Generate Video Post 4 (Scene 1): Woman presenting Giấy Ánh Kim 180 (Wedding Card Paper)."""

import base64
import json
import sys
import time
from pathlib import Path
from google import genai


def main():
    start_time = time.time()
    project_dir = Path("/Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video")
    images_dir = project_dir / "assets" / "images"
    renders_dir = project_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    output_render_path = renders_dir / "post_4.mp4"

    face_path = images_dir / "face.jpg"
    clothes_path = images_dir / "clothes.jpg"

    b64_face = base64.b64encode(face_path.read_bytes()).decode("utf-8")
    b64_clothes = base64.b64encode(clothes_path.read_bytes()).decode("utf-8")

    prompt = (
        "[CAMERA & COMPOSITION]\n"
        "Vertical 9:16 mobile POV. High-angle perspective (35-degree downward tilt) filmed beside workshop workbench, "
        "looking down across the table. Natural handheld camera breathing and responsive motion tracking presenter's hands, "
        "raw behind-the-scenes (BTS) workshop documentary style. Pristine clean camera footage, absolutely no watermarks, "
        "no logos, no text overlays, no usernames, no social media icons.\n\n"
        "[ENVIRONMENT & ATMOSPHERE]\n"
        "Active paper workshop (xưởng sản xuất và gia công giấy mỹ thuật). In background: commercial guillotine paper "
        "cutting machine, neatly stacked pallets of paper reams under bright overhead workshop lighting. On the sturdy "
        "wooden workbench: gleaming sheets of specialty metallic pearlescent paper (giấy ánh kim 180gsm) shimmering under "
        "light, accompanied by sample wedding invitation cards.\n\n"
        "[SUBJECT & APPEARANCE]\n"
        "Adult 30-year-old female artisan matching <IMAGE_REF_0> wearing the muted pale lavender / soft lilac relaxed "
        "short-sleeved top with tonal floral embroidery on the chest in <IMAGE_REF_1>. Standing beside workbench, leaning "
        "forward energetically over pearlescent paper sheets, smiling warmly and engaging directly with camera.\n\n"
        "[ACTION & TIMECODE]\n"
        "00:00 - 00:03: She enthusiastically uncovers and fans out large sheets of lustrous metallic pearlescent paper "
        "(giấy ánh kim) on table, tilting under light to catch pearlescent shimmer, smiling welcomingly into camera.\n"
        "00:03 - 00:07: She lifts one sheet of metallic paper, gently curling it to demonstrate crisp flexibility and "
        "smooth texture, showing fold edge without cracking while speaking enthusiastically.\n"
        "00:07 - 00:10: She places paper down alongside reams, smiling warmly, nodding and resting her hands lightly on "
        "the paper stack.\n\n"
        "[AUDIO & DIALOGUE]\n"
        'Lively spoken Vietnamese dialogue: "Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không? '
        'Dòng Giấy Ánh Kim 180 bên em bề mặt nhũ xà cừ cực mịn, ăn mực sắc nét, lên máy bế hay gấp nếp không lo nứt gãy." '
        "Ambient print shop background."
    )

    client = genai.Client(vertexai=True, project="gen-lang-client-0582170752", location="global")
    interaction = client.interactions.create(
        model="gemini-omni-1.1-flash-preview",
        input=[
            {"type": "image", "data": b64_face, "mime_type": "image/jpeg"},
            {"type": "image", "data": b64_clothes, "mime_type": "image/jpeg"},
            {"type": "text", "text": prompt},
        ],
        response_format={"type": "video", "aspect_ratio": "9:16", "duration": "10s", "resolution": "720p"},
        store=True,
    )

    video_data = next(
        (getattr(item, "data", None) for item in (getattr(interaction, "outputs", None) or []) if getattr(item, "type", None) == "video"),
        None,
    )
    if not video_data:
        print(f"Error: No video data returned: {interaction}", file=sys.stderr)
        sys.exit(1)

    output_render_path.write_bytes(base64.b64decode(video_data))
    (renders_dir / "post_4.json").write_text(
        json.dumps(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "interaction_id": getattr(interaction, "id", None),
                "output_path": str(output_render_path),
                "elapsed_seconds": round(time.time() - start_time, 2),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved Scene 1 raw video to: {output_render_path}")


if __name__ == "__main__":
    main()

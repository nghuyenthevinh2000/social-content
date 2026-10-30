#!/usr/bin/env python3
"""Generate Video Scene 2 for Post 4 20s Long-Form UGC using gemini-omni-1.1-flash-preview image_to_video."""

import base64
import json
import sys
import time
from pathlib import Path
from google import genai


def main():
    start_time = time.time()
    project_dir = Path("/Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video")
    first_frame_path = project_dir / "assets" / "images" / "scene_1_end.jpg"
    out_dir = project_dir / "renders" / "omni-1.1-flash"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_render_path = out_dir / "scene2_omni11_raw.mp4"

    if not first_frame_path.exists():
        print(f"Error: Missing first frame image: {first_frame_path}", file=sys.stderr)
        sys.exit(1)

    b64_first_frame = base64.b64encode(first_frame_path.read_bytes()).decode("utf-8")
    prompt = (
        "[CAMERA & COMPOSITION]\n"
        "Vertical 9:16 mobile POV. High-angle 35-degree downward tilt filmed beside workshop workbench. "
        "Exact visual and spatial continuation from the provided starting frame. Pristine clean camera footage, "
        "absolutely no watermarks, no logos, no text overlays, no usernames.\n\n"
        "[ENVIRONMENT & ATMOSPHERE]\n"
        "Same active paper workshop from the starting frame: commercial guillotine paper cutting machine in background, "
        "large flat 79x109cm sheets of metallic pearlescent paper on the right and center of the wooden workbench, "
        "and two small printed floral wedding invitation cards resting on the left side of the wooden workbench.\n\n"
        "[SUBJECT & CONTINUITY]\n"
        "Exact continuation from the starting frame. The adult 30-year-old female print shop owner in the muted pale "
        "lavender short-sleeved top stands in her exact position beside the workbench, smiling warmly at the camera.\n\n"
        "[ACTION & TIMECODE]\n"
        "00:00 - 00:04: Continuing smoothly from her exact pose in the starting frame, she keeps her right hand resting "
        "lightly on the large flat 79x109cm pearlescent paper stack while gesturing naturally with her left hand toward "
        "the paper stack as she speaks.\n"
        "00:04 - 00:07: Her left hand reaches over to the left side of the workbench and picks up the small printed "
        "floral wedding invitation card already lying there, holding the small card up slightly to show its sharp print quality.\n"
        "00:07 - 00:10: She places the small wedding card back down on the left side of the table, smiles warmly at the "
        "camera, and gives a friendly wave goodbye.\n\n"
        "[AUDIO & DIALOGUE]\n"
        'Clear spoken Vietnamese dialogue with natural northern artisan cadence: '
        '"Khổ tiêu chuẩn 79x109 luôn sẵn tại kho xưởng, nhận đơn từ 2 ram cho xưởng in test máy. '
        'Đặc biệt lên thiệp in cực kỳ sắc nét. Nhắn tin xưởng em gửi mẫu miễn phí nhé!". Ambient workshop room tone.'
    )

    client = genai.Client(vertexai=True, project="gen-lang-client-0582170752", location="global")
    interaction = client.interactions.create(
        model="gemini-omni-1.1-flash-preview",
        input=[
            {"type": "image", "data": b64_first_frame, "mime_type": "image/jpeg"},
            {"type": "text", "text": prompt},
        ],
        response_format={"type": "video", "aspect_ratio": "9:16", "duration": "10s", "resolution": "720p"},
        generation_config={"video_config": {"task": "image_to_video"}},
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
    (out_dir / "scene2_omni11_meta.json").write_text(
        json.dumps(
            {
                "model": "gemini-omni-1.1-flash-preview",
                "task": "image_to_video",
                "interaction_id": getattr(interaction, "id", None),
                "elapsed_seconds": round(time.time() - start_time, 2),
                "output_path": str(output_render_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved Scene 2 video to: {output_render_path}")


if __name__ == "__main__":
    main()

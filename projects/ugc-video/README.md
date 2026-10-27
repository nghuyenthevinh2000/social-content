# UGC Video Project Workspace

Project workspace for vertical (9:16) UGC-style avatar and creator videos, integrated with [OpenMontage](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/OpenMontage).

## Structure

```text
projects/ugc-video/
├── project.json       # OpenMontage project marker (avatar-spokesperson pipeline)
├── artifacts/         # Stage artifacts (brief, script, scene_plan, asset_manifest)
├── assets/
│   ├── audio/         # Voiceovers, TTS narration, audio tracks
│   ├── images/        # Creator portrait photos, product shots, b-roll
│   ├── music/         # Background music tracks
│   └── video/         # Avatar clips, raw creator video, overlay video
├── renders/           # Rendered 9:16 MP4 deliverables
└── local/             # Local scratch, drafts, or test files
```

## Quick Start with OpenMontage

```bash
# 1. Navigate to OpenMontage
cd /Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/OpenMontage

# 2. Open the Backlot visual board in your browser
.venv/bin/python -m backlot open ugc-video

# 3. Target specs for UGC:
# - Aspect ratio: 9:16 (1080x1920)
# - Safe zone: 900x1400 centered (keep bottom 320px clear of critical UI)
# - Captions: Word-by-word spring highlight via Remotion CaptionOverlay
# - Preferred avatar: HeyGen Avatar V or Kling for authentic human micro-expressions
```

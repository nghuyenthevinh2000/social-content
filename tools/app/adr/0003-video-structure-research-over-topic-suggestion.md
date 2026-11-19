# ADR 0003: Video-Structure Research over Topic Suggestion

```text
Reel(s) -> analyze_video_structure() -> why_viral + outline + director prompt [Active]
Reel(s) -> suggest_topics() -> 3 brainstormed topics + generic fallback     [Obsolete]
```

| Field | Value |
|---|---|
| ADR Number | 0003 |
| Title | Specialize video research to viral video-structure analysis and replication |
| Status | Accepted |
| Decision Date | 2026-11-19 |
| Scope | `tools/loop/viral_analyzer/video_research`, `tools/app/backend/research_engine` |

| Context & Driver | Description |
|---|---|
| Topic-Proposal Drift | `suggest_topics()` and `build_topic_prompt()` asked the agent to invent 3 distinct video topics (`"Đề xuất ĐÚNG 3 chủ đề"`), even when researching a single reference video. |
| Padding & Generic Fallbacks | `normalize_topics()` padded results to 3 items and `heuristic_topics()` appended generic brainstorming templates (`90% hiểu sai`, `Thử thách 7 ngày`, `3 mẹo`) unrelated to the input video. |
| Core Goal | Video research exists purely to dissect why an observed video went viral (`why_viral`), break down its pacing/structure (`outline`), and produce a replication director `prompt`. |

| Aspect | Topic Suggestion (Removed) | Video-Structure Research (Adopted) |
|---|---|---|
| Primary Entrypoint | `suggest_topics(..., limit=3)` | `analyze_video_structure(..., limit=None)` |
| Prompt Builder | `build_topic_prompt()` asking for 3 topics | `build_video_structure_prompt()` analyzing actual video structure |
| Normalizer & Fallback | `normalize_topics()`, `parse_topics()`, `heuristic_topics()` with `generic` templates | `normalize_video_analyses()`, `parse_video_analyses()`, `heuristic_video_analyses()` (returns `[]` if no reels) |
| Single-Video Behavior | Requested 3 topics, then sliced `[:1]` | Requests 1 analysis (`limit=1`) focused on `why_viral`, `outline`, and replication `prompt` |
| Batch-Reel Behavior | Hardcoded `limit=3` cap | Analyzes provided reels without artificial `3`-topic cap |

| Decision Outcome | Detail |
|---|---|
| Pure Video Research | Video research never invents unrelated topics; every output maps 1:1 to an analyzed reel's viral mechanics and structure. |
| API / UI Boundary | Backend/frontend job storage and UI components (`JobResult`, `TopicCard`) retain the `topics` JSON array key for wire compatibility; internal `video_research` symbols use `analyses`. |

| Component | Status | Notes |
|---|---|---|
| [`tools/loop/viral_analyzer/video_research/config.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/video_research/config.py#L154-L215) | Updated | `build_video_structure_prompt()` replaces `build_topic_prompt()`. |
| [`tools/loop/viral_analyzer/video_research/pipeline.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/video_research/pipeline.py#L87-L380) | Updated | `analyze_video_structure()`, `normalize_video_analyses()`, `parse_video_analyses()`, `heuristic_video_analyses()` replace topic-based functions and `limit=3`. |
| [`tools/app/backend/research_engine/research.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/app/backend/research_engine/research.py#L48-L525) | Updated | Imports and calls `analyze_video_structure()`. |

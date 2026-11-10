# Video generation tab plan (lite engine, 10 s only)

| Item | Decision |
| --- | --- |
| Goal | **Video** tab: prompt + 1 profile image + N context images; confirm cost, then generate immediately |
| Length | **Fixed 10 s**, one Omni call. No scene count, no chaining, no concat |
| Engine | New **lite** module `tools/app/backend/video_engine.py`; no import from `projects/` |
| Provider config | `.env` already has `VERTEX_VIDEO_API_KEY` (API key) and `VERTEX_VIDEO_MODEL` (`gemini-omni-1.2-flash`) |
| Voice | Native Omni audio: spoken Vietnamese goes in the prompt. No ElevenLabs |
| Isolation | Per-user directories, owner-checked routes |
| Credits | Per-user balance starting at **0**, estimate before run, reserve on start, refund on failure |
| Quality | Fixed **360p**; no resolution option |
| Script | No preview. Server drafts action and dialogue inside the job |

```text
Confirm modal (shows cost) -> POST /api/videos
reserve credits -> draft prompt -> one 10 s Omni call
-> normalize -> history
failure or cancel -> refund
```

## Lite vs ugc-video

| Stage | ugc-video | Lite engine |
| --- | --- | --- |
| Scene render | Reference call, then image-to-video chain | **One** `reference_to_video` call, 10 s |
| Voice | ElevenLabs plus mouth alignment | **Drop**; Omni native audio |
| Seam editor, lighting, lip tracking, effects | Yes | **Drop** |
| Normalize | BT.709, loudnorm | **Keep** (one ffmpeg call) |
| Safety retry | Neutral dialogue fallback | **Keep** |
| Config | Hand-written JSON | Built in memory from prompt |

## Multi-user runs

| Concern | Design |
| --- | --- |
| Directories | `RUNS_ROOT/videos/<user_id>/<job_id>/`; media in `RUNS_ROOT/media/<user_id>/` |
| Access | Every route checks `user_id`; client never supplies file paths |
| Concurrency | Reuse `MAX_PROCESSES` and `MAX_PER_CLIENT` from [handler.py](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/app/backend/handler.py); defaults 2 global, 1 per user |
| Cancel | Allowed while `pending`; a running Omni call cannot be aborted, so no refund after it starts |
| Crash recovery | On startup, mark stale `running` jobs `failed` and refund |
| Secrets | Key stays in gitignored `.env` (verified ignored); add empty `VERTEX_VIDEO_API_KEY=` and `VERTEX_VIDEO_MODEL=` to `.env.example`; never log or return the key |

## Credits and cost calculator

| Element | Design |
| --- | --- |
| Cost | `10 s x $0.023/s = $0.23` per video (Omni flash, 360p) |
| Unit | Integer micro-USD (`230000` per video); no floats. Balance and ledger use the same unit |
| Draft call | Prompt-drafting cost not yet priced; excluded until measured in phase 6 |
| Rate source | One constant `RATE_PER_SEC_MICRO = 23000` in `credits.py`; change when pricing changes |
| Estimate | `POST /api/videos/estimate` returns cost, balance, `can_afford`; UI disables Generate if false |
| Reserve | `POST /api/videos` debits in one SQLite transaction; insufficient funds returns HTTP 402 |
| Refund | Failure refunds in full; success keeps the charge |
| Ledger | `credit_ledger`: user_id, delta, reason, job_id, created_at |
| New users | Balance 0, so Generate is disabled and the UI shows an empty-credit state |
| Top-up | Deferred. Interim: dev-only grant script (CLI, writes a ledger row) for testing |

## Data model

| Table | Columns |
| --- | --- |
| `user_media` | id, user_id, kind (`profile`/`context`), path, mime, bytes, created_at |
| `video_jobs` | id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at |
| `user_credits` | user_id, balance |
| `credit_ledger` | id, user_id, delta, reason, job_id, created_at |

## API

| Route | Purpose |
| --- | --- |
| `GET`, `POST /api/media`, `POST /api/media/delete`, `GET /api/media/<id>` | Profile and context images, owner only |
| `GET /api/credits` | Balance and recent ledger |
| `POST /api/videos/estimate` | Cost preview |
| `POST /api/videos` | Reserve credits, start job |
| `GET /api/videos`, `/<id>`, `/<id>/file` | History, status, mp4 (range streaming) |
| `POST /api/videos/<id>/cancel`, `/delete` | Cancel pending job with refund; remove entry and files |

## Frontend

| Area | Change |
| --- | --- |
| `TABS` | Add `video` between Analyze and Profile |
| Profile tab | Panel: one profile image, context image grid, credit balance |
| Video tab | Prompt, profile picker, context picker, live cost, balance |
| Confirm modal | Shows cost and remaining balance; **Confirm** starts generation at once |
| History | Thumbnail, prompt, status, player, delete |
| Tour | Add Video and credits steps |
| Structure | `VideoTab.tsx`, `MediaPanel.tsx`; keep `Home.tsx` small |

## Phases

| Phase | Scope | Check |
| --- | --- | --- |
| 1 Media | `media.py`, APIs, Profile panel | pytest: owner isolation, size limits |
| 2 Credits | `credits.py`, tables, estimate, reserve, refund | pytest: concurrent debits never go negative |
| 3 Lite engine | `video_engine.py` with stubbed Vertex client | pytest: prompt build, safety retry, normalize |
| 4 Jobs | Queue, per-user limit, cancel, crash recovery | pytest: two users in parallel stay isolated |
| 5 Video tab | Form, confirm modal, history | Vitest; Playwright e2e |
| 6 Real run | One 360p job; check real charge against $0.23 and measure draft-call cost | Manual |

## Risks and unknowns

| Item | Question or mitigation |
| --- | --- |
| Omni native Vietnamese voice quality | Unverified; test in phase 6 |
| Model differs from ugc-video | ugc-video uses `gemini-omni-1.1`; confirm 1.2 accepts the same `interactions.create` fields (`reference_to_video`, duration, resolution) in phase 3 |
| API key auth | Client uses `genai.Client(vertexai=True, api_key=...)`, not project ADC; verify in phase 6. Key is shared, so quota is global |
| Top-up method | Undecided; users cannot generate until it exists |
| Max context images | Omni reference limit unknown |
| Face image privacy | Owner-only access; deletion removes files |

Next action: decide the top-up method.

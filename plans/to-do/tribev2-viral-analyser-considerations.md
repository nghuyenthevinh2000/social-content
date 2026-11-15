# TRIBE v2 ViralAnalyser Considerations

| Topic | Finding | Constraint / Impact |
|---|---|---|
| **Local setup** | Needs Python 3.11, 16 GB RAM, 30+ GB SSD, NVIDIA GPU (6–12+ GB VRAM); Windows-first launcher | Current local machine lacks hardware resources; macOS needs manual `venv` + `TRIBE_CHROME_PATH` |
| **Online TRIBE v2 hosting** | No managed serverless API (Replicate/Fal/HF Inference API); only Meta Demo, Colab, HF Spaces | Must self-host `facebook/tribev2` on cloud GPU (Modal, RunPod, EC2/GCP) for programmatic runs |
| **Licensing** | `facebook/tribev2` is **CC BY-NC 4.0**; `tribeV2_ViralAnalyser` is non-commercial evaluation code | Commercial SaaS or paid client productization is blocked without separate licensing |
| **CPU-only execution** | Built-in CPU fallback; LLaMA text encoder skipped by default (`TRIBE_ENABLE_TEXT_EVENTS` unset) | V-JEPA2 + Wav2Vec-BERT still run on CPU; viable only for async/low-volume queues (~16 GB RAM) |
| **Zero-GPU local modes** | Website URL (`website_analysis.py`) & Visual Grid (`visual_grid_analysis.py`) use no `torch`/`tribev2` | Can run locally on CPU/RAM for landing-page and static-grid attention checks |
| **Commercial alternatives** | Neurons (Predict), Attention Insight, Dragonfly AI, Expoze.io | Hosted SaaS for video/image attention heatmaps with commercial licensing |

```text
Decision Flow:
  Commercial use?
    |-- Yes --> Evaluate Neurons / Attention Insight / Dragonfly AI / Expoze.io
    '-- No (internal/R&D) --> Need video neural curves?
                               |-- No  --> Run Website / Visual Grid modes locally
                               '-- Yes --> Real-time?
                                             |-- Yes --> Cloud GPU (Colab / RunPod / Modal)
                                             '-- No  --> Async CPU queue (16GB RAM, short clips)
```

| Next To-Do | Owner | Status |
|---|---|---|
| Confirm commercial vs. internal/non-commercial use case | User | Open |
| Test Google Colab official `tribev2` notebook on sample clip | User | Open |
| Decide between SaaS alternative, Cloud GPU (Modal/RunPod), or local Grid/Website modes | User | Open |

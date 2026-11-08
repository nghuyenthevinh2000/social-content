"""Configuration parser and validator for viral analyzer pipeline."""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PoolDefinition:
    name: str
    min_views: int
    max_views: Optional[int] = None

    def contains(self, views: int) -> bool:
        if views < self.min_views:
            return False
        if self.max_views is not None and views >= self.max_views:
            return False
        return True


DEFAULT_POOLS = {
    1: PoolDefinition(name="sandbox", min_views=0, max_views=500),
    2: PoolDefinition(name="testing", min_views=500, max_views=5000),
    3: PoolDefinition(name="niche", min_views=5000, max_views=50000),
    4: PoolDefinition(name="surge", min_views=50000, max_views=500000),
    5: PoolDefinition(name="mega_breakout", min_views=500000, max_views=None),
}


from tools.loop.viral_analyzer.cache import default_db_path, default_video_dir


@dataclass
class StorageConfig:
    db_path: Path = field(default_factory=default_db_path)
    video_dir: Path = field(default_factory=default_video_dir)
    output_file: Path = Path("local/app-runs/viral_reels_48h.json")


@dataclass
class TranscriptionConfig:
    engine: str = "qwen3"
    model: str = "Qwen/Qwen3-ASR-0.6B"
    language: Optional[str] = None
    max_audio_duration_sec: int = 180


@dataclass
class ViralAnalyzerConfig:
    window_hours: int = 48
    retention_days: int = 7
    pools: Dict[int, PoolDefinition] = field(default_factory=lambda: dict(DEFAULT_POOLS))
    storage: StorageConfig = field(default_factory=StorageConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    targets: List[Dict[str, Any]] = field(default_factory=list)
    creators_file: Optional[Path] = None
    max_videos: Optional[int] = None
    glasser_provider: str = "scrapecreators"
    glasser_endpoint: str = "/v1/facebook/profile/reels"
    glasser_endpoint_version: int = 2
    budget_ceiling_usd: float = 1.0


def load_config(config_path_or_dict: Any) -> ViralAnalyzerConfig:
    """Load configuration from JSON file or dictionary."""
    if isinstance(config_path_or_dict, (str, Path)):
        p = Path(config_path_or_dict)
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
    elif isinstance(config_path_or_dict, dict):
        raw = config_path_or_dict
    else:
        raise TypeError(f"Expected path or dict, got {type(config_path_or_dict)}")

    # Parse Pools
    pools = dict(DEFAULT_POOLS)
    if "pools" in raw and isinstance(raw["pools"], dict):
        parsed_pools = {}
        for k, v in raw["pools"].items():
            pool_id = int(k)
            parsed_pools[pool_id] = PoolDefinition(
                name=v.get("name", f"pool_{pool_id}"),
                min_views=int(v.get("min_views", 0)),
                max_views=int(v["max_views"]) if v.get("max_views") is not None else None,
            )
        pools = parsed_pools

    # Parse Storage
    st_raw = raw.get("storage", {})
    storage = StorageConfig(
        db_path=Path(st_raw["db_path"]) if st_raw.get("db_path") else default_db_path(),
        video_dir=Path(st_raw["video_dir"]) if st_raw.get("video_dir") else default_video_dir(),
        output_file=Path(st_raw.get("output_file", "local/app-runs/viral_reels_48h.json")),
    )

    # Parse Transcription
    tr_raw = raw.get("transcription", {})
    transcription = TranscriptionConfig(
        engine=tr_raw.get("engine", "qwen3"),
        model=tr_raw.get("model", "Qwen/Qwen3-ASR-0.6B"),
        language=tr_raw.get("language"),
        max_audio_duration_sec=int(tr_raw.get("max_audio_duration_sec", 180)),
    )

    # Parse Targets / Creators
    targets = raw.get("targets", [])
    creators_file = Path(raw["creators_file"]) if raw.get("creators_file") else None
    if creators_file and creators_file.exists():
        try:
            with open(creators_file, "r", encoding="utf-8") as cf:
                cdata = json.load(cf)
                creators = cdata.get("creators", [])
                if creators and not targets:
                    targets = creators
        except Exception:
            pass

    return ViralAnalyzerConfig(
        window_hours=int(raw.get("window_hours", 48)),
        retention_days=int(raw.get("retention_days", 7)),
        pools=pools,
        storage=storage,
        transcription=transcription,
        targets=targets,
        creators_file=creators_file,
        max_videos=int(raw["max_videos"]) if raw.get("max_videos") is not None else None,
        glasser_provider=raw.get("glasser_provider", "scrapecreators"),
        glasser_endpoint=raw.get("glasser_endpoint", "/v1/facebook/profile/reels"),
        glasser_endpoint_version=int(raw.get("glasser_endpoint_version", 2)),
        budget_ceiling_usd=float(raw.get("budget_ceiling_usd", 1.0)),
    )

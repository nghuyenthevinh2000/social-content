"""Official watermark backend: the calibrated allenk/VeoWatermarkRemover CLI."""

from __future__ import annotations

import hashlib
import io
import os
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from .corners import QuadError
from .io import sha256_file, utc_now, write_json

VERSION = "v0.6.5-demo"
RELEASE = f"https://github.com/allenk/VeoWatermarkRemover/releases/tag/{VERSION}"
BIN_DIR = Path(__file__).parent / ".bin" / VERSION
ASSETS = {
    "Darwin": ("macOS-Universal", "1998739f3a881d4cd9894b087a3eccba03d22b02bbcd9cfcc70dbeacf5aa6280"),
    "Linux": ("Linux-x64", "958a8f429208848af55d461754a841d5c5703301a61ac66d045831c5a9622654"),
    "Windows": ("Windows-x64", "542d413f0cc0467e90bc0a13a197df55a811fce312f3f0fb6a151f548e2964a0"),
}
EXECUTABLE = "GeminiWatermarkTool-Video.exe" if os.name == "nt" else "GeminiWatermarkTool-Video"


def install_backend() -> Path:
    """Explicit, pinned download; verify the release digest before extracting."""
    system = platform.system()
    if system not in ASSETS or (system != "Darwin" and platform.machine().lower() not in ("x86_64", "amd64")):
        raise QuadError("no pinned build for this platform; set VEO_WATERMARK_BIN to a compatible executable")
    name, expected = ASSETS[system]
    url = f"https://github.com/allenk/VeoWatermarkRemover/releases/download/{VERSION}/GeminiWatermarkTool-{name}-Video.zip"
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            archive = response.read()
        if hashlib.sha256(archive).hexdigest() != expected:
            raise QuadError("backend download checksum mismatch; nothing installed")
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            matches = [entry for entry in bundle.infolist() if Path(entry.filename).name == EXECUTABLE]
            if len(matches) != 1:
                raise QuadError("backend archive does not contain exactly one expected executable")
            binary = bundle.read(matches[0])
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=BIN_DIR, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(binary)
        try:
            temporary.chmod(0o755)
            temporary.replace(BIN_DIR / EXECUTABLE)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, urllib.error.URLError, zipfile.BadZipFile) as error:
        raise QuadError(f"could not install watermark backend: {error}") from error
    return BIN_DIR / EXECUTABLE


def find_backend(explicit: str | Path | None = None) -> Path:
    configured = explicit or os.environ.get("VEO_WATERMARK_BIN")
    candidate = str(configured) if configured else str(BIN_DIR / EXECUTABLE)
    located = shutil.which(candidate)
    if not located and not configured:
        located = shutil.which(EXECUTABLE)
    if not located:
        raise QuadError("watermark backend unavailable; run `uv run python -m tools.video_edit watermark-install` "
                        "or set VEO_WATERMARK_BIN to an executable")
    return Path(located).resolve()


def render_watermark(
    source: str | Path,
    out_dir: str | Path,
    *,
    backend: str | Path | None = None,
    image: bool = False,
    cpu: bool = True,
    legacy: bool = False,
    region: str | None = None,
    alpha: float | None = None,
    sigma: float | None = None,
    ml: bool = False,
    force: bool = False,
) -> dict:
    """Run only the official engine; retain logs and report skipped frames.

    Images support calibrated repair of individual skipped frames. No custom
    fill/clone fallback runs, and existing inputs or results are never replaced.
    """
    source, out_dir = Path(source).resolve(), Path(out_dir).resolve()
    output = out_dir / ("result.png" if image else "result.mp4")
    if not source.is_file():
        raise QuadError(f"input does not exist: {source}")
    if output == source or output.exists():
        raise QuadError(f"refusing to overwrite {output}; choose a new output directory")
    if alpha is not None and not .05 <= alpha <= 3:
        raise QuadError("alpha must be between 0.05 and 3")
    if sigma is not None and not 1 <= sigma <= 150:
        raise QuadError("sigma must be between 1 and 150")
    if region is not None:
        try:
            parts = tuple(int(value) for value in region.split(","))
        except ValueError as error:
            raise QuadError("region must be x,y,w,h in pixels") from error
        if len(parts) != 4 or min(parts[:2]) < 0 or min(parts[2:]) <= 0:
            raise QuadError("region must be nonnegative x,y and positive w,h")
    executable = find_backend(backend)
    out_dir.mkdir(parents=True, exist_ok=True)
    flags = []
    if cpu:
        flags.append("--cpu")
    if legacy:
        flags.append("--legacy")
    if ml:
        flags.append("--ml")
    if force:
        flags.append("--force")
    for option, value in (("--region", region), ("--veo-alpha", alpha), ("--sigma", sigma)):
        if value is not None:
            flags.extend((option, str(value)))
    if image:
        flags.extend(("--denoise", "ai"))
    digest = sha256_file(source)
    with tempfile.TemporaryDirectory(dir=out_dir, prefix=".watermark-") as work:
        staged = Path(work) / output.name
        command = [str(executable), "--no-banner", *flags, "-i", str(source), "-o", str(staged)]
        print(f"watermark   allenk/VeoWatermarkRemover ({executable})", flush=True)
        try:
            result = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False)
        except OSError as error:
            raise QuadError(f"could not run watermark backend: {error}") from error
        log = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout + result.stderr)
        (out_dir / "backend.log").write_text(log, encoding="utf-8")
        if result.returncode != 0 or not staged.is_file() or staged.stat().st_size == 0:
            raise QuadError(f"watermark backend failed or skipped the input (exit {result.returncode}); "
                            f"see {out_dir / 'backend.log'}")
        if sha256_file(source) != digest:
            raise QuadError("source changed during processing; refusing to publish the result")
        staged.replace(output)
    skips = re.search(r"\((\d+) skip\)", log)
    skipped = int(skips.group(1)) if skips else None
    manifest = {
        "schema_version": 2, "generated_on": utc_now(),
        "backend": "allenk/VeoWatermarkRemover", "release": RELEASE,
        "executable": str(executable), "executable_sha256": sha256_file(executable),
        "input": str(source), "input_sha256": digest,
        "output": str(output), "output_sha256": sha256_file(output),
        "options": flags, "reported_skipped_frames": skipped,
        "log": str(out_dir / "backend.log"),
        "limits": ["Inspect output for residue and skipped frames; no fallback repair runs automatically.",
                   "Visible watermark processing does not remove invisible SynthID."],
    }
    write_json(out_dir / "manifest.json", manifest)
    if skipped:
        print(f"warning     backend skipped {skipped} frame(s); inspect backend.log and repair individually")
    print(f"output      {output}")
    return manifest

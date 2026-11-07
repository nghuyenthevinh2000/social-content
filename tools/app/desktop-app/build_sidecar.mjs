#!/usr/bin/env node
// Build the Python API + transcription server as a Tauri sidecar.
import { execFileSync } from "node:child_process";
import { chmodSync, copyFileSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const appDir = dirname(fileURLToPath(import.meta.url));
const root = join(appDir, "..", "..", "..");
const triple = execFileSync("rustc", ["--print", "host-tuple"], { encoding: "utf8" }).trim();
const ext = process.platform === "win32" ? ".exe" : "";

const args = [
  "run",
  "--no-project",
  "--with", "pyinstaller",
  "--with", "openpyxl",
  "--with", "yt-dlp",
  "--with", "imageio-ffmpeg",
];

if (process.platform === "darwin") {
  args.push("--with", "mlx-qwen3-asr");
} else {
  args.push(
    "--with", "transformers>=5.13",
    "--with", "torch",
    "--with", "accelerate",
    "--with", "soundfile",
    "--with", "librosa",
    "--with", "imageio-ffmpeg",
  );
}

args.push(
  "pyinstaller",
  "--noconfirm", "--clean", "--onefile", "--console",
  "--name", "viral-server",
  "--paths", root,
  "--exclude-module", "playwright",
  "--exclude-module", "cv2",
  "--exclude-module", "matplotlib",
  "--exclude-module", "onnxruntime",
  "--exclude-module", "mcp",
  "--exclude-module", "av",
  "--exclude-module", "ctranslate2",
  "--exclude-module", "faster_whisper",
);

if (process.platform === "darwin") {
  const mlxLib = execFileSync(
    "uv",
    ["run", "--no-project", "--with", "mlx-qwen3-asr", "python", "-c",
      "import importlib.util, pathlib; s=importlib.util.find_spec('mlx'); print(pathlib.Path(next(iter(s.submodule_search_locations))) / 'lib')"],
    { encoding: "utf8" },
  ).trim();
  args.push(
    "--exclude-module", "torch",
    "--exclude-module", "transformers",
    "--collect-all", "mlx",
    "--collect-all", "mlx_qwen3_asr",
    "--add-data", `${mlxLib}/mlx.metallib:.`,
    "--add-data", `${mlxLib}/libjaccl.dylib:.`,
  );
} else {
  args.push(
    "--exclude-module", "mlx",
    "--exclude-module", "mlx_qwen3_asr",
    "--collect-all", "transformers",
    "--collect-all", "soundfile",
    "--collect-all", "librosa",
    "--collect-all", "imageio_ffmpeg",
    "--hidden-import", "torch",
  );
}

args.push(
  "--distpath", join(appDir, "build", "sidecar"),
  "--workpath", join(appDir, "build", "work-sidecar"),
  "--specpath", join(appDir, "build"),
  join(appDir, "..", "backend", "server.py"),
);

rmSync(join(appDir, "build", "sidecar"), { recursive: true, force: true });
rmSync(join(appDir, "build", "work-sidecar"), { recursive: true, force: true });
execFileSync("uv", args, { cwd: appDir, stdio: "inherit", env: process.env });

const source = join(appDir, "build", "sidecar", `viral-server${ext}`);
const destination = join(appDir, "src-tauri", "binaries", `viral-server-${triple}${ext}`);
mkdirSync(dirname(destination), { recursive: true });
copyFileSync(source, destination);
if (process.platform !== "win32") chmodSync(destination, 0o755);
console.log(`Sidecar: ${destination}`);

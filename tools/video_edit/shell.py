"""Section 3: Thin-shell paper mechanics (isometric flap warp + headless Blender Cloth/PBR)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .blend import bgr_to_rgb_float, luminance, rgb_float_to_bgr
from .io import describe_image, utc_now, write_json, write_png
from .proxy import flatten_texture, tile_mirror


def extract_svbrdf(texture_bgr: np.ndarray, out_dir: str | Path) -> dict[str, Path]:
    """Single-image SVBRDF extraction: mirror-tiled seamless Albedo, Micro-Normal, Roughness, Translucency."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    flat_bgr = tile_mirror(flatten_texture(texture_bgr, sigma=30.0), 512, 680)
    flat_rgb = bgr_to_rgb_float(flat_bgr)
    lum = luminance(flat_rgb)
    base_lum = cv2.GaussianBlur(lum, (0, 0), 6.0)
    relief = cv2.GaussianBlur(lum - base_lum, (1, 5), 0.0)

    albedo_bgr = rgb_float_to_bgr(cv2.GaussianBlur(flat_rgb, (0, 0), 8.0))
    nx = np.clip(relief / (2.2 * float(relief.std()) + 1e-6), -0.90, 0.90)
    ny = np.clip(cv2.Sobel(lum - base_lum, cv2.CV_32F, 0, 1, ksize=3) * 1.5, -0.35, 0.35)
    nz = np.sqrt(np.maximum(1.0 - nx * nx - ny * ny, 0.05))
    normal_rgb = ((np.stack([nx, ny, nz], axis=-1) * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    roughness = (np.clip(0.82 - 2.5 * relief, 0.45, 0.96) * 255.0).astype(np.uint8)
    translucency = (np.clip(0.38 + 3.0 * relief, 0.15, 0.80) * 255.0).astype(np.uint8)

    paths = {
        "albedo": write_png(out_dir / "svbrdf_albedo.png", albedo_bgr),
        "normal": write_png(out_dir / "svbrdf_normal.png", cv2.cvtColor(normal_rgb, cv2.COLOR_RGB2BGR)),
        "roughness": write_png(out_dir / "svbrdf_roughness.png", roughness),
        "translucency": write_png(out_dir / "svbrdf_translucency.png", translucency),
    }
    return paths


def warp_shell_flap(warped_bgr: np.ndarray, mask: np.ndarray, illumination: np.ndarray) -> np.ndarray:
    """Isometric thin-shell UV bend across a folded flap crease (k_stretch -> inf).

    When a corner flap bends forward over a diagonal crease (indicated by an
    adjacent cast-shadow wedge and a bright tilted flap), a flat homography
    leaves vertical grooves running straight across the fold. This warps the
    flap pixels by cylindrical foreshortening near the crease ridge and tangent
    rotation across the diagonal crease line.
    """
    inside = mask > 0.5
    if int(inside.sum()) < 4000:
        return warped_bgr

    ys, _ = np.nonzero(inside)
    y_min, y_max = float(ys.min()), float(ys.max())
    h_sheet = max(y_max - y_min, 1.0)
    h, w = warped_bgr.shape[:2]
    grid_y, grid_x = np.mgrid[0:h, 0:w].astype(np.float32)

    # Smooth vertical envelope restricted to the upper half of the sheet so the flat lower body is untouched.
    wy = np.clip((y_min + 0.52 * h_sheet - grid_y) / (0.12 * h_sheet), 0.0, 1.0)
    shadow_upper = float((np.clip((0.78 - illumination) / 0.12, 0.0, 1.0) * inside * (wy > 0.05)).sum())
    alpha_crease = float(np.clip((shadow_upper - 1200.0) / 4500.0, 0.0, 1.0))
    if alpha_crease <= 1e-3:
        return warped_bgr

    # Centroid-free smooth cylindrical arch pull across the crease (no connected-component switching or wobble).
    bright_flap = np.clip((illumination - 1.02) / 0.16, 0.0, 1.0) * wy
    w_arch = cv2.GaussianBlur(bright_flap.astype(np.float32), (0, 0), 14.0) * wy * alpha_crease
    map_x = (grid_x - 3.6 * w_arch).astype(np.float32)
    map_y = (grid_y - 2.4 * w_arch).astype(np.float32)
    return cv2.remap(warped_bgr, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)


_BLENDER_SCRIPT = """\
import sys, bpy, math
argv = sys.argv[sys.argv.index("--") + 1:]
albedo_p, normal_p, rough_p, frames_dir, blend_out, n_frames = argv[:6]
n_frames = int(n_frames)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 1, n_frames
scene.render.engine = "CYCLES"
scene.render.resolution_x, scene.render.resolution_y = 720, 1280
scene.render.fps = 24
scene.cycles.samples = 24
scene.use_gravity = False
scene.view_settings.view_transform = "Standard"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    scene.cycles.device = "GPU"
except Exception:
    pass

# Camera & Studio Raking + Back-Rim Lights
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 52
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
cam.location = (0.0, -2.15, 0.05)
cam.rotation_euler = (math.radians(88.5), 0.0, 0.0)
scene.camera = cam

for name, loc, energy, size, color in [
    ("KeyRaking", (-0.95, -0.75, 0.85), 11.0, 0.55, (1.0, 0.96, 0.92)),
    ("SubsurfaceRim", (0.22, 0.45, 0.55), 22.0, 0.45, (1.0, 0.16, 0.04)),
    ("Fill", (0.95, -1.50, 0.10), 3.2, 1.4, (1.0, 0.96, 0.94)),
]:
    ld = bpy.data.lights.new(name, type="AREA")
    ld.energy, ld.size, ld.color = energy, size, color
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc

# 120gsm Thin-Shell Paper Mesh (79x109 aspect ~ 0.725)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=64, size=1.0, location=(0, 0, 0))
sheet = bpy.context.active_object
sheet.name = "Giay_Do_Nhung_120gsm_Sheet"
sheet.scale = (0.52, 0.68, 1.0)
bpy.ops.object.transform_apply(scale=True)
sheet.rotation_euler = (math.radians(90.0), 0.0, math.radians(-5.0))
bpy.ops.object.transform_apply(rotation=True)
bpy.ops.object.shade_smooth()

# Pin group (held base + pinched top corner) driven by isometric fold shape key
pin_vg = sheet.vertex_groups.new(name="Pin")
sk_basis = sheet.shape_key_add(name="Basis")
sk_fold = sheet.shape_key_add(name="CornerPeel")

# Diagonal crease line: n_x * x + n_z * z = c0 in the upper-right quadrant
nx_c, nz_c, c0 = 0.64, 0.77, 0.06
R_cyl = 0.18  # 120gsm cylindrical bend radius
for i, v in enumerate(sheet.data.vertices):
    x, y, z = v.co.x, v.co.y, v.co.z
    d = nx_c * x + nz_c * z - c0
    if d <= -0.03:
        pin_vg.add([i], 1.0, "REPLACE")
    elif d > 0.0:
        phi = min(math.pi * 0.72, d / R_cyl)
        over = max(0.0, d - R_cyl * math.pi * 0.72)
        arc_s = R_cyl * math.sin(phi) + over * math.cos(math.pi * 0.72)
        lift_y = -R_cyl * (1.0 - math.cos(phi)) - over * math.sin(math.pi * 0.72)
        shift = arc_s - d
        sk_fold.data[i].co = (x + shift * nx_c, y + lift_y, z + shift * nz_c)
        pin_w = min(0.96, max(0.18, (d / 0.24) ** 1.5))
        pin_vg.add([i], pin_w, "REPLACE")

sk_fold.value = 0.0
sk_fold.keyframe_insert(data_path="value", frame=1)
sk_fold.value = 1.0
sk_fold.keyframe_insert(data_path="value", frame=max(2, int(n_frames * 0.65)))
sk_fold.value = 0.88
sk_fold.keyframe_insert(data_path="value", frame=n_frames)

# Blender Thin-Shell Cloth Solver calibrated for 120gsm Heavy Paper
cloth_mod = sheet.modifiers.new(name="PaperShell", type="CLOTH")
cs = cloth_mod.settings
cs.quality = 14
cs.mass = 0.12  # 120 g/m^2
cs.bending_model = "ANGULAR"
cs.tension_stiffness = 80.0
cs.compression_stiffness = 80.0
cs.shear_stiffness = 80.0
cs.bending_stiffness = 24.0
cs.pin_stiffness = 3.5
cs.vertex_group_mass = "Pin"
cs.use_dynamic_mesh = True
cloth_mod.point_cache.frame_start = 1
cloth_mod.point_cache.frame_end = n_frames

# PBR + Translucent BSDF Shader for Giay Do Nhung 120gsm
mat = bpy.data.materials.new("Giay_Do_Nhung_120gsm")
mat.use_nodes = True
nt = mat.node_tree
nodes, links = nt.nodes, nt.links
bsdf = nodes.get("Principled BSDF")
out_node = nodes.get("Material Output")

tex_coord = nodes.new("ShaderNodeTexCoord")
mapping = nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

def add_tex(path, non_color=False):
    node = nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(path)
    if non_color:
        node.image.colorspace_settings.name = "Non-Color"
    links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    return node

alb_n = add_tex(albedo_p, False)
nrm_n = add_tex(normal_p, True)
rgh_n = add_tex(rough_p, True)

nmap = nodes.new("ShaderNodeNormalMap")
nmap.inputs["Strength"].default_value = 2.1
links.new(nrm_n.outputs["Color"], nmap.inputs["Color"])
links.new(alb_n.outputs["Color"], bsdf.inputs["Base Color"])
links.new(rgh_n.outputs["Color"], bsdf.inputs["Roughness"])
links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
if "Specular IOR Level" in bsdf.inputs:
    bsdf.inputs["Specular IOR Level"].default_value = 0.04
if "Sheen Weight" in bsdf.inputs:
    bsdf.inputs["Sheen Weight"].default_value = 0.25
if "Thin Wall" in bsdf.inputs:
    bsdf.inputs["Thin Wall"].default_value = True

trans = nodes.new("ShaderNodeBsdfTranslucent")
trans.inputs["Color"].default_value = (0.85, 0.04, 0.01, 1.0)  # Deep Scarlet
links.new(nmap.outputs["Normal"], trans.inputs["Normal"])

mix = nodes.new("ShaderNodeMixShader")
mix.inputs["Fac"].default_value = 0.14
links.new(bsdf.outputs["BSDF"], mix.inputs[1])
links.new(trans.outputs["BSDF"], mix.inputs[2])
links.new(mix.outputs["Shader"], out_node.inputs["Surface"])
sheet.data.materials.append(mat)

# Bake physics & render frames
bpy.ops.ptcache.bake_all(bake=True)
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
for f in range(1, n_frames + 1):
    scene.frame_set(f)
    scene.render.filepath = f"{frames_dir}/{f - 1:05d}.png"
    bpy.ops.render.render(write_still=True)
"""


def run_blender_simulation(
    texture_path: str | Path,
    out_dir: str | Path,
    *,
    frames: int = 24,
    blender_bin: str | None = None,
) -> dict:
    """Run headless Blender 5.2+ Cloth Thin-Shell + Cycles PBR simulation."""
    blender = blender_bin or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
    if not Path(blender).exists() and not shutil.which(str(blender)):
        raise SystemExit("blender executable not found; install with: brew install --cask blender")

    texture_path = Path(texture_path).resolve()
    out_dir = Path(out_dir).resolve()
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    tex_bgr = cv2.imread(str(texture_path), cv2.IMREAD_COLOR)
    if tex_bgr is None:
        raise SystemExit(f"could not read texture: {texture_path}")

    svbrdf = extract_svbrdf(tex_bgr, out_dir / "svbrdf")
    blend_out = out_dir / "paper_120gsm.blend"
    script_path = out_dir / "run_sim.py"
    script_path.write_text(_BLENDER_SCRIPT, encoding="utf-8")

    cmd = [
        str(blender),
        "-b",
        "-P",
        str(script_path),
        "--",
        str(svbrdf["albedo"]),
        str(svbrdf["normal"]),
        str(svbrdf["roughness"]),
        str(frames_dir),
        str(blend_out),
        str(frames),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise SystemExit(f"Blender simulation failed:\n{res.stderr.strip() or res.stdout[-800:]}")

    from .video import encode

    mp4_out = encode(frames_dir, frames_dir / "00000.png", out_dir / "result.mp4", 24.0, crf=14)
    manifest = {
        "schema_version": 1,
        "generated_on": utc_now(),
        "architecture": "inverse-svbrdf-blender-thin-shell-pbr",
        "blender_binary": str(blender),
        "texture": describe_image(texture_path),
        "svbrdf": {k: str(v) for k, v in svbrdf.items()},
        "physics": {
            "solver": "Blender Cloth ANGULAR Thin-Shell",
            "mass_kg_m2": 0.12,
            "tension_stiffness": 80.0,
            "compression_stiffness": 80.0,
            "shear_stiffness": 80.0,
            "bending_stiffness": 1.8,
        },
        "outputs": {
            "blend_preset": str(blend_out),
            "frames_dir": str(frames_dir),
            "video": str(mp4_out),
        },
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest

import os
import numpy as np
import trimesh
from PIL import Image
import json
import cv2

# =========================================================
# 🔧 CONFIGURATION
# =========================================================
BED_SIZE_MM = (500, 500)
DPI = 300
LAYER_HEIGHT = 0.2

MAX_DIST_MM = 0.3          # edge falloff (already tuned)
SHELL_THICKNESS_MM = 1.5   # outer strong shell
CORE_BINDER_RATIO = 0.6    # inner binder reduction (0–1)
GAMMA = 2.5                # edge sharpness

# 🔥 IMPORTANT CONTROL (edge strength)
MAX_DIST_MM = 0.4   # adjust: 0.3 → sharp, 1.0 → smooth

JOB_DIR = "job_001"
TIFF_DIR = os.path.join(JOB_DIR, "tiff")

os.makedirs(TIFF_DIR, exist_ok=True)

PIXEL_SIZE = 25.4 / DPI
IMG_WIDTH = max(1, int(BED_SIZE_MM[0] / PIXEL_SIZE))
IMG_HEIGHT = max(1, int(BED_SIZE_MM[1] / PIXEL_SIZE))




# =========================================================
# 📦 LOAD + CLEAN MESH
# =========================================================
mesh = trimesh.load("Body1.stl")
mesh = mesh.process(validate=True)

print("Is watertight:", mesh.is_watertight)
print("Euler number:", mesh.euler_number)

# =========================================================
# ⚠️ SIZE CHECK
# =========================================================
min_bound = mesh.bounds[0]
max_bound = mesh.bounds[1]
model_size = max_bound - min_bound

if model_size[0] > BED_SIZE_MM[0] or model_size[1] > BED_SIZE_MM[1]:
    raise ValueError("❌ Model exceeds bed size!")

# =========================================================
# 🎯 POSITION MODEL
# =========================================================
mesh.apply_translation(-min_bound)

offset_x = (BED_SIZE_MM[0] - model_size[0]) / 2
offset_y = (BED_SIZE_MM[1] - model_size[1]) / 2

mesh.apply_translation([offset_x, offset_y, 0])

# Align Z
min_z = mesh.bounds[0][2]
mesh.apply_translation([0, 0, -min_z])

print("FINAL BOUNDS:", mesh.bounds)

# =========================================================
# 📏 Z RANGE (MID-LAYER)
# =========================================================
z_min, z_max = mesh.bounds[:, 2]
z = z_min + (LAYER_HEIGHT / 2)

layer_num = 0
MAX_LAYERS = 10000

# =========================================================
# 🔪 SLICING LOOP
# =========================================================
while z <= z_max and layer_num < MAX_LAYERS:

    print(f"Processing layer {layer_num} at Z={z:.3f}")

    try:
        section = mesh.section(
            plane_origin=[0, 0, z],
            plane_normal=[0, 0, 1]
        )
    except Exception as e:
        print(f"⚠️ Skipping layer {layer_num}: {e}")
        z += LAYER_HEIGHT
        layer_num += 1
        continue

    if section is None or len(section.entities) == 0:
        z += LAYER_HEIGHT
        layer_num += 1
        continue

    slice_2D, transform = section.to_2D()

    # =====================================================
    # 🧩 STEP 1: CREATE BINARY MASK
    # =====================================================
    mask = np.full((IMG_HEIGHT, IMG_WIDTH), 255, dtype=np.uint8)

    for polygon in slice_2D.polygons_full:

        if polygon.area < 0.05:
            continue

        pts = []

        for x, y in np.array(polygon.exterior.coords):

            point_2d = np.array([x, y, 0, 1])
            point_3d = transform @ point_2d

            world_x = point_3d[0]
            world_y = point_3d[1]

            px = int(world_x / PIXEL_SIZE)
            py = int(world_y / PIXEL_SIZE)

            py = IMG_HEIGHT - py

            px = max(0, min(px, IMG_WIDTH - 1))
            py = max(0, min(py, IMG_HEIGHT - 1))

            pts.append([px, py])

        if len(pts) > 2:
            pts = np.array(pts, dtype=np.int32)
            cv2.fillPoly(mask, [pts], 0)

    # =====================================================
    # 🧠 STEP 2: DISTANCE TRANSFORM
    # =====================================================
    binary = (mask == 0).astype(np.uint8)

    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

    # =====================================================
    # 🎯 STEP 3: NORMALIZE DISTANCE
    # =====================================================
    MAX_DIST_PX = MAX_DIST_MM / PIXEL_SIZE

    dist_clipped = np.clip(dist, 0, MAX_DIST_PX)
    norm = dist_clipped / MAX_DIST_PX

    # =====================================================
    # 🎨 STEP 4: MAP TO GRAYSCALE
    # =====================================================
    gamma = 2.0
    # Convert shell thickness to pixels
    SHELL_PX = SHELL_THICKNESS_MM / PIXEL_SIZE

    grayscale = np.zeros_like(norm)

    # Shell region (strong)
    shell_mask = dist <= SHELL_PX
    grayscale[shell_mask] = 0  # full binder

    # Core region (lighter)
    core_mask = dist > SHELL_PX

    # Normalize only core region
    core_dist = dist[core_mask] - SHELL_PX
    core_max = MAX_DIST_PX - SHELL_PX

    core_norm = np.clip(core_dist / core_max, 0, 1)

    gamma = GAMMA

    # Apply reduced binder
    core_values = (1 - (core_norm ** gamma)) * 255

    # Apply binder reduction
    core_values = core_values * CORE_BINDER_RATIO

    grayscale[core_mask] = 255 - core_values

    # Keep outside white
    grayscale[mask == 255] = 255

    grayscale_img = grayscale.astype(np.uint8)

    # keep outside white
    grayscale[mask == 255] = 255

    grayscale_img = grayscale.astype(np.uint8)

    img_pil = Image.fromarray(grayscale_img)

    # =====================================================
    # 💾 SAVE TIFF
    # =====================================================
    filename = os.path.join(TIFF_DIR, f"layer_{layer_num:04d}.tiff")
    img_pil.save(filename, format="TIFF")

    z += LAYER_HEIGHT
    layer_num += 1

print("✅ TIFF generation complete")

# =========================================================
# ⚙️ G-CODE GENERATION
# =========================================================
GCODE_FILE = os.path.join(JOB_DIR, "motion.gcode")

with open(GCODE_FILE, "w") as f:

    f.write("; Binder Jetting G-code\n")
    f.write("G21\n")
    f.write("G90\n\n")

    total_layers = layer_num

    for i in range(total_layers):

        layer_file = f"layer_{i:04d}.tiff"

        f.write(f"; ===== Layer {i} =====\n")
        f.write("G1 X500 F3000\n")
        f.write("G1 X0 F3000\n")
        f.write(f"G1 Z-{LAYER_HEIGHT} F300\n")
        f.write(f"M_PRINT {layer_file}\n")
        f.write("M400\n\n")

print("✅ G-code generated:", GCODE_FILE)

# =========================================================
# 🧾 CONFIG FILE
# =========================================================
config = {
    "bed_size_mm": BED_SIZE_MM,
    "dpi": DPI,
    "layer_height": LAYER_HEIGHT,
    "total_layers": total_layers,
    "pixel_size_mm": PIXEL_SIZE,
    "edge_control_mm": MAX_DIST_MM
}

config_path = os.path.join(JOB_DIR, "config.json")

with open(config_path, "w") as f:
    json.dump(config, f, indent=4)

print("✅ Config saved:", config_path)
import os

import numpy as np
import trimesh
from PIL import Image
import json
import cv2

# =========================================================
# PART CLASS
# =========================================================
class Part:
    def __init__(self, filepath):
        self.filepath = filepath
        self.mesh = trimesh.load(filepath)

        # process in-place
        self.mesh.process(validate=True)

        # fix non-watertight meshes safely
        if not self.mesh.is_watertight:
            self.mesh.fill_holes()

        self.min_bound = self.mesh.bounds[0]
        self.max_bound = self.mesh.bounds[1]
        self.size = self.max_bound - self.min_bound

        self.position = np.array([0.0, 0.0, 0.0])

    def move_to_origin(self):
        # only move in X and Y, NOT Z
        translation = [-self.min_bound[0], -self.min_bound[1], 0]
        self.mesh.apply_translation(translation)

    def apply_position(self):
        self.mesh.apply_translation(self.position)

# =========================================================
# AUTO PLACEMENT (GRID)
# =========================================================
def place_parts(parts, bed_size, spacing=5.0):

    x_cursor = 0
    y_cursor = 0
    row_height = 0

    for part in parts:

        part.move_to_origin()

        size_x, size_y = part.size[0], part.size[1]

        if x_cursor + size_x > bed_size[0]:
            x_cursor = 0
            y_cursor += row_height + spacing
            row_height = 0

        if y_cursor + size_y > bed_size[1]:
            raise ValueError("Parts do not fit on bed")

        part.position = np.array([x_cursor, y_cursor, 0])
        part.apply_position()

        x_cursor += size_x + spacing
        row_height = max(row_height, size_y)


# =========================================================
# CONFIG
# =========================================================
BED_SIZE_MM = (500, 500)
DPI = 150
LAYER_HEIGHT = 0.2

MAX_DIST_MM = 0.4
SHELL_THICKNESS_MM = 1.5
CORE_BINDER_RATIO = 0.6
GAMMA = 2.5

PADDING_MM = 10   # distance from edge in mm


JOB_DIR = "job_001"
TIFF_DIR = os.path.join(JOB_DIR, "tiff")

os.makedirs(TIFF_DIR, exist_ok=True)

PIXEL_SIZE = 25.4 / DPI
IMG_WIDTH = max(1, int(BED_SIZE_MM[0] / PIXEL_SIZE))
IMG_HEIGHT = max(1, int(BED_SIZE_MM[1] / PIXEL_SIZE))

PADDING_PX = int(PADDING_MM / PIXEL_SIZE)


# =========================================================
# LOAD PARTS
# =========================================================
file_list = [
    "handle.stl",
    "scraper.stl",
    "pcb.stl",
    "pcb2.stl",
]

parts = []

for f in file_list:
    part = Part(f)
    print(f"Loaded: {f}")
    print("  Watertight:", part.mesh.is_watertight)
    parts.append(part)

place_parts(parts, BED_SIZE_MM)

# =========================================================
# COMBINE MESHES
# =========================================================
combined_mesh = trimesh.util.concatenate([p.mesh for p in parts])

print("FINAL BOUNDS:", combined_mesh.bounds)
# =========================================================
# REGION CROP (FIXED VERSION)
# =========================================================
min_x, min_y = combined_mesh.bounds[0][:2]
max_x, max_y = combined_mesh.bounds[1][:2]

# convert to pixel space
min_px = int(min_x / PIXEL_SIZE)
min_py = int(min_y / PIXEL_SIZE)
max_px = int(max_x / PIXEL_SIZE)
max_py = int(max_y / PIXEL_SIZE)

# margin (important)
margin = 150

min_px = max(0, min_px - margin)
min_py = max(0, min_py - margin)
max_px = min(IMG_WIDTH, max_px + margin)
max_py = min(IMG_HEIGHT, max_py + margin)

CROP_WIDTH = max_px - min_px
CROP_HEIGHT = max_py - min_py

print("Crop size:", CROP_WIDTH, CROP_HEIGHT)

# =========================================================
# SLICING SETUP
# =========================================================
z_min, z_max = combined_mesh.bounds[:, 2]
z = z_min + (LAYER_HEIGHT / 2)

layer_num = 0

# =========================================================
# SLICING LOOP (FIXED STRUCTURE)
# =========================================================
while z <= z_max:

    print(f"Processing layer {layer_num} at Z={z:.3f}")

    try:
        section = combined_mesh.section(
            plane_origin=[0, 0, z],
            plane_normal=[0, 0, 1]
        )
    except Exception:
        z += LAYER_HEIGHT
        layer_num += 1
        continue

    if section is None or len(section.entities) == 0:
        z += LAYER_HEIGHT
        layer_num += 1
        continue

    slice_2D, transform = section.to_2D()

    # =====================================================
    # CREATE MASK (IMPORTANT)
    # =====================================================
    mask = np.full((IMG_HEIGHT, IMG_WIDTH), 255, dtype=np.uint8)

    # =====================================================
    # DRAW GEOMETRY (FIXED)
    # =====================================================
    for path in slice_2D.discrete:

        if len(path) < 3:
            continue

        pts = []

        for x, y in path:

            point_2d = np.array([x, y, 0, 1])
            point_3d = transform @ point_2d

            px = int(round(point_3d[0] / PIXEL_SIZE)) + PADDING_PX
            py = int(round(point_3d[1] / PIXEL_SIZE)) + PADDING_PX

            # flip Y AFTER padding
            py = IMG_HEIGHT - 1 - py

            # clamp with padding safety
            px = max(PADDING_PX, min(px, IMG_WIDTH - PADDING_PX - 1))
            py = max(PADDING_PX, min(py, IMG_HEIGHT - PADDING_PX - 1))

            pts.append([px, py])

        if len(pts) >= 3:
            pts_np = np.array(pts, dtype=np.int32)

            cv2.fillPoly(mask, [pts_np], 0)
            cv2.polylines(mask, [pts_np], True, 0, 1)

    # =====================================================
    # MORPHOLOGY (EDGE FIX)
    # =====================================================
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # =====================================================
    # DISTANCE FIELD
    # =====================================================
    binary = (mask == 0).astype(np.uint8)
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

    MAX_DIST_PX = MAX_DIST_MM / PIXEL_SIZE
    SHELL_PX = SHELL_THICKNESS_MM / PIXEL_SIZE

    grayscale = np.zeros_like(dist)

    shell_mask = dist <= SHELL_PX
    grayscale[shell_mask] = 0

    core_mask = dist > SHELL_PX

    core_dist = dist[core_mask] - SHELL_PX
    core_max = max(MAX_DIST_PX - SHELL_PX, 1e-6)

    core_norm = np.clip(core_dist / core_max, 0, 1)

    core_values = (1 - (core_norm ** GAMMA)) * 255
    core_values *= CORE_BINDER_RATIO

    grayscale[core_mask] = 255 - core_values
    grayscale[mask == 255] = 255

    grayscale_img = grayscale.astype(np.uint8)

    img = Image.fromarray(grayscale_img)

    filename = os.path.join(TIFF_DIR, f"layer_{layer_num:04d}.tiff")
    img.save(filename, format="TIFF")

    # IMPORTANT: increment INSIDE LOOP
    z += LAYER_HEIGHT
    layer_num += 1

print("TIFF generation complete")


# =========================================================
# GCODE
# =========================================================
GCODE_FILE = os.path.join(JOB_DIR, "motion.gcode")

with open(GCODE_FILE, "w") as f:

    f.write("G21\nG90\n\n")

    for i in range(layer_num):
        f.write(f"; Layer {i}\n")
        f.write("G1 X500\nG1 X0\n")
        f.write(f"G1 Z-{LAYER_HEIGHT}\n")
        f.write(f"M_PRINT layer_{i:04d}.tiff\n\n")

print("G-code generated")


# =========================================================
# CONFIG
# =========================================================
config = {
    "layers": layer_num,
    "dpi": DPI,
    "bed": BED_SIZE_MM
}

with open(os.path.join(JOB_DIR, "config.json"), "w") as f:
    json.dump(config, f, indent=4)
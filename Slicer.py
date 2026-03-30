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


    # ROTATION FUNCTION
    def rotate_z(self, angle_deg):
        angle_rad = np.radians(angle_deg)

        rot_matrix = trimesh.transformations.rotation_matrix(
            angle_rad, [0, 0, 1]
        )

        self.mesh.apply_transform(rot_matrix)

        # recompute bounds after rotation
        self.min_bound = self.mesh.bounds[0]
        self.max_bound = self.mesh.bounds[1]
        self.size = self.max_bound - self.min_bound



# =========================================================
# COLLISION CHECK (GLOBAL)
# =========================================================
# def is_collision_poly(part, placed_parts, spacing):

#     for p in placed_parts:

#         moved = translate(
#             part.footprint,
#             xoff=part.position[0],
#             yoff=part.position[1]
#         )

#         existing = translate(
#             p.footprint,
#             xoff=p.position[0],
#             yoff=p.position[1]
#         )

#         if moved.buffer(spacing).intersects(existing):
#             return True

#     return False


# =========================================================
# AUTO NESTING (GLOBAL)
# =========================================================
def auto_nest(parts, bed_size, spacing=5):

    EDGE_MARGIN = max(spacing, 10)   # safe margin from edges

    # SORT BIG → SMALL
    parts_sorted = sorted(parts, key=lambda p: p.size[0]*p.size[1], reverse=True)

    placed_parts = []

    # START WITH MARGIN (IMPORTANT)
    x_cursor = EDGE_MARGIN
    y_cursor = EDGE_MARGIN
    current_row_height = 0

    for part in parts_sorted:

        best_part = None

        # TRY ROTATIONS
        for angle in [0, 90]:

            test_part = Part(part.filepath)

            if angle != 0:
                test_part.rotate_z(angle)

            test_part.move_to_origin()

            size_x, size_y = test_part.size[0], test_part.size[1]

            # CHECK IF FITS IN CURRENT ROW (WITH EDGE MARGIN)
            if x_cursor + size_x > bed_size[0] - EDGE_MARGIN:
                continue

            best_part = test_part
            break

        # IF DOESN’T FIT → NEW ROW
        if best_part is None:
            x_cursor = EDGE_MARGIN
            y_cursor += current_row_height + spacing
            current_row_height = 0

            # retry placement in new row
            for angle in [0, 90]:

                test_part = Part(part.filepath)

                if angle != 0:
                    test_part.rotate_z(angle)

                test_part.move_to_origin()

                size_x, size_y = test_part.size[0], test_part.size[1]

                if x_cursor + size_x <= bed_size[0] - EDGE_MARGIN:
                    best_part = test_part
                    break

        if best_part is None:
            raise ValueError(f"Cannot place part: {part.filepath}")

        # PLACE PART
        best_part.position = np.array([x_cursor, y_cursor, 0])
        best_part.apply_position()

        placed_parts.append(best_part)

        # UPDATE CURSORS
        x_cursor += best_part.size[0] + spacing
        current_row_height = max(current_row_height, best_part.size[1])

        # CHECK BED HEIGHT (WITH MARGIN)
        if y_cursor + current_row_height > bed_size[1] - EDGE_MARGIN:
            raise ValueError("Parts exceed bed height")

    return placed_parts, parts_sorted

# =========================================================
# Gapfilling
# =========================================================

def fill_gaps(placed_parts, remaining_parts, bed_size, spacing=5):

    EDGE_MARGIN = max(spacing, 10)

    for part in remaining_parts:

        placed = False

        for angle in [0, 90]:

            test_part = Part(part.filepath)

            if angle != 0:
                test_part.rotate_z(angle)

            test_part.move_to_origin()

            size_x, size_y = test_part.size[0], test_part.size[1]

            # scan entire bed
            for y in range(EDGE_MARGIN, int(bed_size[1] - EDGE_MARGIN), spacing):
                for x in range(EDGE_MARGIN, int(bed_size[0] - EDGE_MARGIN), spacing):

                    test_part.position = np.array([x, y, 0])

                    # boundary check
                    if (
                        x + size_x > bed_size[0] - EDGE_MARGIN or
                        y + size_y > bed_size[1] - EDGE_MARGIN
                    ):
                        continue

                    # collision check
                    collision = False

                    for p in placed_parts:
                        if (
                            test_part.position[0] < p.position[0] + p.size[0] + spacing and
                            test_part.position[0] + size_x + spacing > p.position[0] and
                            test_part.position[1] < p.position[1] + p.size[1] + spacing and
                            test_part.position[1] + size_y + spacing > p.position[1]
                        ):
                            collision = True
                            break

                    if not collision:
                        test_part.apply_position()
                        placed_parts.append(test_part)
                        placed = True
                        break

                if placed:
                    break

            if placed:
                break

    return placed_parts


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
    "Head.stl",
    "PCB CMPT 1.stl",
    "Body1.stl",
    "handle.stl",
    "scraper.stl",
    "pcb.stl",
    "pcb2.stl",
    "Head.stl",
    "PCB CMPT 1.stl",
    "Body1.stl",
    "handle.stl",
    "scraper.stl",
    "pcb.stl",
    "pcb2.stl",
    "Head.stl",
    "PCB CMPT 1.stl",
    "Body1.stl",
]

parts = []

for f in file_list:
    part = Part(f)
    print(f"Loaded: {f}")
    print("  Watertight:", part.mesh.is_watertight)
    parts.append(part)

placed_parts, all_parts = auto_nest(parts, BED_SIZE_MM)

# remaining = parts not placed initially
remaining_parts = [p for p in all_parts if p.filepath not in [pp.filepath for pp in placed_parts]]

parts = fill_gaps(placed_parts, remaining_parts, BED_SIZE_MM)

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
total_black_pixels = 0
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
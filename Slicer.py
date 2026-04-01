import os

import numpy as np
import trimesh
from PIL import Image
import json
import cv2

from datetime import datetime


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


    def auto_fit(self, bed_size):

        best_fit = None
        best_area = float("inf")

        for angle in [0, 90]:

            test = self.mesh.copy()

            # rotate
            rot = trimesh.transformations.rotation_matrix(
                np.radians(angle), [0, 0, 1]
            )
            test.apply_transform(rot)

            bounds = test.bounds
            size = bounds[1] - bounds[0]

            if size[0] <= bed_size[0] and size[1] <= bed_size[1]:
                area = size[0] * size[1]

                if area < best_area:
                    best_area = area
                    best_fit = (angle, test, size)

        # if fits → apply best rotation
        if best_fit:
            angle, mesh, size = best_fit
            self.mesh = mesh
            self.size = size
            self.min_bound = mesh.bounds[0]
            self.max_bound = mesh.bounds[1]
            return

        # ❌ DOES NOT FIT → SCALE DOWN
        bounds = self.mesh.bounds
        size = bounds[1] - bounds[0]

        scale_x = bed_size[0] / size[0]
        scale_y = bed_size[1] / size[1]

        scale = min(scale_x, scale_y) * 0.95  # small margin

        self.mesh.apply_scale(scale)

        # recompute bounds
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

MAX_DIST_MM = 0.4
SHELL_THICKNESS_MM = 1.5
CORE_BINDER_RATIO = 0.6
GAMMA = 2.5
PADDING_MM = 10   # distance from edge in mm


# JOB_DIR = "job_001"
# TIFF_DIR = os.path.join(JOB_DIR, "tiff")

# os.makedirs(TIFF_DIR, exist_ok=True)

# PIXEL_SIZE = 25.4 / DPI
# IMG_WIDTH = max(1, int(BED_SIZE_MM[0] / PIXEL_SIZE))
# IMG_HEIGHT = max(1, int(BED_SIZE_MM[1] / PIXEL_SIZE))

# PADDING_PX = int(PADDING_MM / PIXEL_SIZE)

# MACHINE PARAMETERS
# RECOAT_TIME_SEC = 8        # layer spreading
# PRINT_TIME_PER_LAYER_SEC = 12   # head movement pass


# =========================================================
# LOAD PARTS
# =========================================================
def run_slicer(file_list, progress_callback=None, settings=None):

        # =========================
    # APPLY SETTINGS
    # =========================
    if settings is None:
        settings = {}

    BED_SIZE_MM = (
        settings.get("bed_x", 500),
        settings.get("bed_y", 500)
    )

    DPI = settings.get("dpi", 300)
    LAYER_HEIGHT = settings.get("layer_height", 0.2)
    # =========================
    # BINDER SETTINGS FROM UI
    # =========================
    SHELL_PX = settings.get("shell_thickness", 2) * 3
    CORE_RATIO = settings.get("core_density", 0.6)
    GAMMA = settings.get("gamma", 2.5)
    PRINT_MODE = settings.get("print_mode", "Solid")
    HOLLOW_DENSITY = settings.get("hollow_density", 0.5)
    

    PIXEL_SIZE = 25.4 / DPI

    IMG_WIDTH = max(1, int(BED_SIZE_MM[0] / PIXEL_SIZE))
    IMG_HEIGHT = max(1, int(BED_SIZE_MM[1] / PIXEL_SIZE))
    PADDING_MM = 10   # distance from edge in mm

    PADDING_PX = int(PADDING_MM / PIXEL_SIZE)

   
   


    JOB_DIR = f"job_{datetime.now().strftime('%H%M%S')}"
    TIFF_DIR = os.path.join(JOB_DIR, "tiff")

    os.makedirs(TIFF_DIR, exist_ok=True)

    PADDING_PX = int(PADDING_MM / PIXEL_SIZE)

    # MACHINE PARAMETERS
    RECOAT_TIME_SEC = 8        # layer spreading
    PRINT_TIME_PER_LAYER_SEC = 12   # head movement pass


    

    # =========================
    # LOAD PARTS
    # =========================
    parts = []
    

    for f in file_list:
        part = Part(f)
        part.auto_fit(BED_SIZE_MM)
        parts.append(part)

    # 🔥 SORT BY SIZE (largest first)
    parts.sort(key=lambda p: p.size[0] * p.size[1], reverse=True)

    # =========================
    # NESTING (RUN ONCE)
    # =========================
    placed_parts, all_parts = auto_nest(parts, BED_SIZE_MM)

    remaining_parts = all_parts[len(placed_parts):]

    parts = fill_gaps(placed_parts, remaining_parts, BED_SIZE_MM)

    # =========================
    # COMBINE MESH
    # =========================
    combined_mesh = trimesh.util.concatenate([p.mesh for p in parts])

    print("FINAL BOUNDS:", combined_mesh.bounds)

    # =========================
    # SLICING SETUP
    # =========================
    z_min, z_max = combined_mesh.bounds[:, 2]
    z = z_min + (LAYER_HEIGHT / 2)

    layer_num = 0
    total_black_pixels = 0

    # =========================
    # SLICING LOOP
    # =========================
    total_layers_est = int((z_max - z_min) / LAYER_HEIGHT) + 1

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

        mask = np.full((IMG_HEIGHT, IMG_WIDTH), 255, dtype=np.uint8)

        for path in slice_2D.discrete:

            if len(path) < 3:
                continue

            pts = []

            for x, y in path:
                point_2d = np.array([x, y, 0, 1])
                point_3d = transform @ point_2d

                px = int(round(point_3d[0] / PIXEL_SIZE)) + PADDING_PX
                py = int(round(point_3d[1] / PIXEL_SIZE)) + PADDING_PX

                py = IMG_HEIGHT - 1 - py

                px = max(PADDING_PX, min(px, IMG_WIDTH - PADDING_PX - 1))
                py = max(PADDING_PX, min(py, IMG_HEIGHT - PADDING_PX - 1))

                pts.append([px, py])

            if len(pts) >= 3:
                pts_np = np.array(pts, dtype=np.int32)
                cv2.fillPoly(mask, [pts_np], 0)

        # =========================
        # BINDER CALCULATION (NEW)
        # =========================

        binary = (mask == 0).astype(np.uint8)

        # IMPORTANT: distance expects 0 background, 1 object
        dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)

        # shell thickness directly in pixels
        shell_mask = (dist > 0) & (dist <= SHELL_PX)
        core_mask = dist > SHELL_PX

        output = np.full_like(mask, 255, dtype=np.uint8)

        # shell always solid
        output[shell_mask] = 0

        if PRINT_MODE == "Solid":
            output[core_mask] = int(255 * (1 - CORE_RATIO))

        elif PRINT_MODE == "Hollow":

            # RANDOM PATTERN BASED ON DENSITY
            random_mask = np.random.rand(*output.shape)

            # keep some pixels, remove others
            keep = random_mask < HOLLOW_DENSITY

            # apply only inside core
            hollow_pixels = core_mask & keep
            empty_pixels = core_mask & (~keep)

            # keep some binder
            output[hollow_pixels] = int(255 * (1 - CORE_RATIO))

            # remove rest (empty)
            output[empty_pixels] = 255

        # apply gamma

        output = output.astype(np.uint8)

        print("Shell:", np.sum(shell_mask))
        print("Core:", np.sum(core_mask))

        # =========================
        # COUNT PIXELS
        # =========================
        binder_strength = (255 - output) / 255.0
        total_black_pixels += np.sum(binder_strength)

        # =========================
        # SAVE IMAGE
        # =========================
        img = Image.fromarray(output)
        filename = os.path.join(TIFF_DIR, f"layer_{layer_num:04d}.tiff")
        img.save(filename)

        # =========================
        # PROGRESS + PREVIEW (FIXED)
        # =========================
        if progress_callback:
            progress = int((layer_num / total_layers_est) * 100)
            preview = output
            progress_callback(progress, preview)

        # =========================
        # NEXT LAYER
        # =========================
        z += LAYER_HEIGHT
        layer_num += 1


    # =========================
    # FINAL PROGRESS
    # =========================
    if progress_callback:
        progress_callback(100, None)

    print("TIFF generation complete")

    # =========================
    # ESTIMATION
    # =========================
    total_layers = layer_num

    time_per_layer = RECOAT_TIME_SEC + PRINT_TIME_PER_LAYER_SEC
    total_time_hr = (total_layers * time_per_layer) / 3600

    build_height = total_layers * LAYER_HEIGHT
    build_volume_liters = (
        BED_SIZE_MM[0] * BED_SIZE_MM[1] * build_height
    ) / 1e6
    solid_fraction = total_black_pixels / (IMG_WIDTH * IMG_HEIGHT * total_layers)

    powder_volume_liters = build_volume_liters * (1 - solid_fraction)

    pixel_volume_mm3 = PIXEL_SIZE * PIXEL_SIZE * LAYER_HEIGHT
    binder_volume_ml = (total_black_pixels * pixel_volume_mm3) / 1000

    powder_cost = powder_volume_liters * 50
    binder_cost = binder_volume_ml * 1.2  # ₹ per ml

    total_cost = powder_cost + binder_cost

    # =========================
    # RETURN (VERY IMPORTANT)
    # =========================
    return {
        "layers": total_layers,
        "time_hr": total_time_hr,
        "cost": total_cost,
        "binder_ml": binder_volume_ml,
        "powder_l": powder_volume_liters
    }
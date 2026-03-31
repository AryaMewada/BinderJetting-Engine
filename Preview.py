import os
import cv2
import numpy as np

TIFF_DIR = "job_001/tiff"

files = sorted([f for f in os.listdir(TIFF_DIR) if f.endswith(".tiff")])
total = len(files)

index = 0
zoom = 1.0
pan_x, pan_y = 0, 0
autoplay = False

# window
cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

# slider
def on_trackbar(val):
    global index
    index = val

cv2.createTrackbar("Layer", "Preview", 0, total - 1, on_trackbar)


# mouse for pan
dragging = False
last_x, last_y = 0, 0

def mouse(event, x, y, flags, param):
    global pan_x, pan_y, dragging, last_x, last_y

    if event == cv2.EVENT_LBUTTONDOWN:
        dragging = True
        last_x, last_y = x, y

    elif event == cv2.EVENT_MOUSEMOVE and dragging:
        dx = x - last_x
        dy = y - last_y
        pan_x += dx
        pan_y += dy
        last_x, last_y = x, y

    elif event == cv2.EVENT_LBUTTONUP:
        dragging = False

cv2.setMouseCallback("Preview", mouse)


while True:

    path = os.path.join(TIFF_DIR, files[index])
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

    if img is None:
        continue

    # convert to color for overlay
    display = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    # =====================================
    # ZOOM
    # =====================================
    h, w = display.shape[:2]
    zoomed = cv2.resize(display, (int(w * zoom), int(h * zoom)))

    # =====================================
    # PAN
    # =====================================
    canvas = np.zeros_like(zoomed)

    x1 = max(0, pan_x)
    y1 = max(0, pan_y)

    x2 = min(zoomed.shape[1], zoomed.shape[1] + pan_x)
    y2 = min(zoomed.shape[0], zoomed.shape[0] + pan_y)

    canvas[y1:y2, x1:x2] = zoomed[y1 - pan_y:y2 - pan_y, x1 - pan_x:x2 - pan_x]

    display = canvas

    # =====================================
    # OVERLAY INFO
    # =====================================
    cv2.putText(display, f"Layer: {index}/{total-1}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.putText(display, f"Zoom: {zoom:.2f}", (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    if autoplay:
        cv2.putText(display, "PLAY", (20, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    cv2.imshow("Preview", display)

    key = cv2.waitKey(30)

    # =====================================
    # CONTROLS
    # =====================================

    if key == 27:  # ESC
        break

    elif key == ord('d'):  # next
        index = min(index + 1, total - 1)
        cv2.setTrackbarPos("Layer", "Preview", index)

    elif key == ord('a'):  # prev
        index = max(index - 1, 0)
        cv2.setTrackbarPos("Layer", "Preview", index)

    elif key == ord(' '):  # autoplay toggle
        autoplay = not autoplay

    elif key == ord('='):  # zoom in
        zoom *= 1.2

    elif key == ord('-'):  # zoom out
        zoom = max(0.2, zoom / 1.2)

    elif key == ord('r'):  # reset view
        zoom = 1.0
        pan_x, pan_y = 0, 0

    # autoplay logic
    if autoplay:
        index += 1
        if index >= total:
            index = 0
        cv2.setTrackbarPos("Layer", "Preview", index)

cv2.destroyAllWindows()
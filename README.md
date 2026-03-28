# ApexView — Bird's-Eye View Converter

Converts oblique-angle video (30° / 45° camera elevation) into a
top-down (90°) bird's-eye view using per-frame homographic normalization.

```
birdseye/
├── backend/
│   ├── main.py          ← FastAPI app + REST endpoints
│   ├── processor.py     ← Core CV: homography, warping, video I/O
│   └── requirements.txt
├── frontend/
│   ├── index.html       ← Single-page UI
│   └── static/
│       ├── css/app.css
│       └── js/app.js
└── run.sh               ← One-command startup
```

---

## Quick start

```bash
# 1. Clone / unzip the project
cd birdseye

# 2. (Optional but recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Start the server
chmod +x run.sh && ./run.sh
# OR manually:
cd backend && pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Open the browser
open http://localhost:8000
```

---

## Requirements

- Python 3.10+
- `pip install -r backend/requirements.txt`
- **ffmpeg** (optional) — enables H.264 re-encoding for better browser playback
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: https://ffmpeg.org/download.html

---

## How it works

### Automatic mode (default)
The system estimates the ground-plane quadrilateral from the camera
elevation angle using a foreshortening model:

- **Horizon line** is placed at `(1 - angle/90) * frame_height`
- **Top edge width** scales as `(angle/90) * 0.55 * frame_width`
- **Bottom edge** spans nearly the full frame width

This works well for parking lots, roads, and open-ground footage.

### Manual corner mode
Click 4 corners on the first frame of the video (TL → TR → BR → BL).
The homography is computed exactly from those points. Use this when:
- The camera is at an unusual angle
- The scene has strong geometric features you want to preserve
- Auto mode produces a skewed result

### Homography math
For each frame:
1. Source points `src_pts` (4×2 float32, TL→TR→BR→BL order)
2. `H = cv2.findHomography(src_pts, dst_pts)` — 3×3 matrix
3. `warped = cv2.warpPerspective(frame, H, dst_size)`
4. Points can be re-projected: `q = H @ [x, y, 1]`, then `q[:2] / q[2]`

The homography `H` is computed **once** from the first frame and reused
for all subsequent frames (stable camera assumption).

---

## REST API

| Method | Endpoint              | Description                              |
|--------|-----------------------|------------------------------------------|
| POST   | `/api/upload`         | Upload video + settings, returns job_id  |
| GET    | `/api/status/{id}`    | Poll job progress (0.0–1.0)              |
| GET    | `/api/download/{id}`  | Download the output MP4                  |
| GET    | `/api/preview/{id}`   | Get a JPEG frame from the output         |
| DELETE | `/api/job/{id}`       | Clean up job files                       |

### Upload form fields

| Field          | Type   | Default  | Description                              |
|----------------|--------|----------|------------------------------------------|
| `file`         | file   | —        | Video file (mp4/mov/avi/mkv/webm)        |
| `angle`        | float  | 45.0     | Camera elevation in degrees              |
| `output_width` | int    | 800      | Output canvas width in pixels            |
| `output_height`| int    | 600      | Output canvas height in pixels           |
| `corner_mode`  | string | "auto"   | "auto" or "manual"                       |
| `corners`      | string | null     | JSON array [[x,y],[x,y],[x,y],[x,y]]     |

---

## Extending the system

### Plug in a YOLO-based corner detector
```python
# In processor.py, replace angle_to_roi():
def yolo_detect_corners(frame, model) -> np.ndarray:
    # Run inference, extract 4 corner keypoints
    # Return shape (4,2) float32, order TL TR BR BL
    ...

# Then in VideoProcessor.process():
src_pts = yolo_detect_corners(first_frame, model)
```

### Add video stabilization
Apply `cv2.estimateAffinePartial2D` between consecutive frames before
computing the homography to smooth out camera shake.

### Multi-slot support
Call `warp_to_birdseye()` independently for each detected slot polygon.
Each slot gets its own normalized patch.

### Camera calibration (undistortion)
If you have the camera matrix `K` and distortion coefficients `D`:
```python
frame = cv2.undistort(frame, K, D)
# Then run the homography pipeline on the undistorted frame
```

---

## Troubleshooting

**Output looks stretched / warped incorrectly**
→ Try manual corner mode and click the exact corners of the ground plane.

**Output video won't play in browser**
→ Install ffmpeg. The processor re-encodes to H.264 automatically when ffmpeg is available.

**Processing is slow**
→ Reduce output resolution (800×600 instead of 1920×1080).
→ Use a GPU-enabled OpenCV build: `pip install opencv-python-headless` → replace with CUDA build.

**ModuleNotFoundError: cv2**
→ Run `pip install opencv-python-headless` inside your virtual environment.
# Homography-Normalization-system
# Normalization-Homography-System

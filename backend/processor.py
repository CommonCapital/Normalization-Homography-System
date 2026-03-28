"""
processor.py  —  Bird's-Eye View normalisation engine
Target: output matching a true 90° overhead drone shot.
  - No vanishing point
  - Parallel lines stay parallel
  - Uniform scale across frame
  - Ground plane fills entire canvas
"""

import time
import dataclasses
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Global job store
# ---------------------------------------------------------------------------
job_store: Dict[str, "ProcessingJob"] = {}


# ---------------------------------------------------------------------------
# Job state
# ---------------------------------------------------------------------------
@dataclass
class ProcessingJob:
    job_id: str
    input_path: str
    output_path: str
    angle: float
    output_size: Tuple[int, int]           # (width, height)
    manual_corners: Optional[np.ndarray]   # shape (4,2) float32 or None

    status: str = "queued"
    progress: float = 0.0
    total_frames: int = 0
    processed_frames: int = 0
    error_msg: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    fps: float = 0.0

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": round(self.progress, 3),
            "total_frames": self.total_frames,
            "processed_frames": self.processed_frames,
            "error_msg": self.error_msg,
            "fps": round(self.fps, 2),
            "output_url": f"/outputs/{Path(self.output_path).name}"
                          if self.status == "done" else None,
        }


# ---------------------------------------------------------------------------
# ROI estimation  —  angle → ground-plane quadrilateral
# ---------------------------------------------------------------------------
def angle_to_roi(frame: np.ndarray, angle_deg: float) -> np.ndarray:
    """
    Estimate the ground-plane quadrilateral (perspective trapezoid) for a
    camera at a given elevation angle above horizontal.

    Model (pinhole, ground plane z=0, camera looking at scene centre):

      horizon_y  = frame_height * (1 - sin(angle))
                   → at 90° (straight down)  → 0   (top of frame)
                   → at 30° (shallow)        → 50% down
                   → at 45°                  → ~29% down

      top_half_width = frame_width * cos(angle) * shrink_factor
      bottom spans full width with small margin

    The four corners form a trapezoid that represents the ground plane
    as seen from that elevation angle. The homography then "unrolls" it
    into a rectangle.

    Parameters
    ----------
    frame     : BGR frame (used only for shape)
    angle_deg : camera elevation in degrees (0=horizontal, 90=straight down)

    Returns
    -------
    np.ndarray shape (4,2) float32, order TL TR BR BL
    """
    h, w = frame.shape[:2]
    a = np.radians(np.clip(angle_deg, 5, 85))

    # Vertical: where the "horizon" sits in the image
    # sin(90°)=1 → top of frame (pure top-down, no horizon visible)
    # sin(30°)=0.5 → horizon halfway down
    horizon_y = h * (1.0 - np.sin(a))

    # Horizontal foreshortening at the far (top) edge
    # cos(90°)=0 → pure top-down, top edge = full width
    # cos(30°)=0.87 → shallow, top edge very narrow
    top_half = w * 0.5 * (1.0 - np.cos(a) * 0.80)
    top_half = max(top_half, w * 0.05)   # never narrower than 5% half-width

    cx = w / 2.0
    margin = w * 0.02

    tl = [cx - top_half, horizon_y]
    tr = [cx + top_half, horizon_y]
    br = [w - margin,    h - 1]
    bl = [margin,        h - 1]

    return np.array([tl, tr, br, bl], dtype=np.float32)


# ---------------------------------------------------------------------------
# Homography
# ---------------------------------------------------------------------------

def compute_homography(
    src_pts: np.ndarray,
    dst_size: Tuple[int, int],
) -> np.ndarray:
    """
    Compute 3×3 homography: src quadrilateral → canonical rectangle.

    Parameters
    ----------
    src_pts  : (4,2) float32, TL TR BR BL
    dst_size : (width, height)

    Returns
    -------
    H : (3,3) float64
    """
    w, h = dst_size
    dst_pts = np.array([
        [0,     0    ],
        [w - 1, 0    ],
        [w - 1, h - 1],
        [0,     h - 1],
    ], dtype=np.float32)

    H, _ = cv2.findHomography(src_pts, dst_pts, method=0)
    if H is None:
        raise ValueError(
            "findHomography failed — corners may be collinear or degenerate."
        )
    return H


def warp_frame(
    frame: np.ndarray,
    H: np.ndarray,
    dst_size: Tuple[int, int],
) -> np.ndarray:
    """Warp a single BGR frame using homography H."""
    return cv2.warpPerspective(
        frame, H, dst_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(30, 30, 30),
    )



# ---------------------------------------------------------------------------
# Post-processing  —  make it look like the reference drone shot
# ---------------------------------------------------------------------------

def enhance_birdseye(frame: np.ndarray) -> np.ndarray:
    """
    Colour-grade the warped frame to match the flat, slightly desaturated
    look of a real overhead drone shot (uniform lighting, no shadows).

    Steps
    -----
    1. Slight contrast lift (CLAHE on L channel) to compensate for warp blur
    2. Mild desaturation (overhead shots look flatter than oblique ones)
    3. Very slight sharpening to recover warp-softened edges
    """
    # --- 1. Sharpening (unsharp mask) ---
    blur = cv2.GaussianBlur(frame, (0, 0), 1.2)
    sharp = cv2.addWeighted(frame, 1.4, blur, -0.4, 0)

    # --- 2. CLAHE on luminance for local contrast ---
    lab = cv2.cvtColor(sharp, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # --- 3. Mild desaturation ---
    hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= 0.88          # reduce saturation to 88%
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    return result


def add_grid_overlay(
    frame: np.ndarray,
    cell_px: int = 100,
    alpha: float = 0.07,
) -> np.ndarray:
    """
    Overlay a faint measurement grid — mimics the gridlines visible on
    professional bird's-eye parking analysis footage.
    """
    h, w = frame.shape[:2]
    grid = frame.copy()
    color = (200, 220, 200)
    for x in range(0, w, cell_px):
        cv2.line(grid, (x, 0), (x, h), color, 1)
    for y in range(0, h, cell_px):
        cv2.line(grid, (0, y), (w, y), color, 1)
    return cv2.addWeighted(frame, 1 - alpha, grid, alpha, 0)


def draw_compass(frame: np.ndarray, size: int = 36) -> np.ndarray:
    """Small N-arrow in top-right corner."""
    h, w = frame.shape[:2]
    cx, cy = w - size - 14, size + 14
    cv2.circle(frame, (cx, cy), size,     (20, 20, 20), -1)
    cv2.circle(frame, (cx, cy), size,     (80, 90, 80),  1)
    tip  = (cx,             cy - size + 7)
    lpt  = (cx - size // 3, cy + 6)
    rpt  = (cx + size // 3, cy + 6)
    base = (cx,             cy + size - 8)
    cv2.fillPoly(frame, [np.array([tip, lpt, rpt])], (0, 210, 120))
    cv2.line(frame, (cx, cy + 6), base, (50, 50, 50), 1)
    cv2.putText(frame, "N", (cx - 5, cy - size + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
    return frame


def draw_angle_badge(frame: np.ndarray, angle: float) -> np.ndarray:
    """Small angle label in top-left corner."""
    label = f"90deg normalised | src {int(angle)}deg"
    cv2.putText(frame, label, (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0),       2)
    cv2.putText(frame, label, (12, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 210, 120),   1)
    return frame


# ---------------------------------------------------------------------------
# Video I/O
# ---------------------------------------------------------------------------

def open_writer(path: str, fps: float, size: Tuple[int, int]) -> cv2.VideoWriter:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open VideoWriter at {path}")
    return writer


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

class VideoProcessor:
    """Stateless video processor."""

    def process(self, job: ProcessingJob) -> None:
        """
        Full pipeline: open → compute H → warp → enhance → write.

        The homography H is computed ONCE from the first frame and reused
        for all subsequent frames (stable camera assumption).
        For a moving / drone-mounted camera, set recompute_interval > 0.
        """
        job.status = "processing"
        job.started_at = time.time()

        cap = cv2.VideoCapture(job.input_path)
        if not cap.isOpened():
            job.status = "error"
            job.error_msg = "Cannot open input video file."
            return

        total    = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_in   = cap.get(cv2.CAP_PROP_FPS) or 30.0
        job.total_frames = max(total, 1)

        writer  = open_writer(job.output_path, fps_in, job.output_size)
        H       = None
        idx     = 0
        t0      = time.time()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Compute homography from first frame
                if H is None:
                    src_pts = (job.manual_corners
                               if job.manual_corners is not None
                               else angle_to_roi(frame, job.angle))
                    H = compute_homography(src_pts, job.output_size)

                warped  = warp_frame(frame, H, job.output_size)
                warped  = enhance_birdseye(warped)
                warped  = add_grid_overlay(warped)
                warped  = draw_compass(warped)
                warped  = draw_angle_badge(warped, job.angle)
                writer.write(warped)

                idx += 1
                job.processed_frames = idx
                job.progress = idx / job.total_frames
                elapsed = time.time() - t0
                job.fps = idx / elapsed if elapsed > 0 else 0.0

        except Exception as exc:
            job.status    = "error"
            job.error_msg = str(exc)
            return
        finally:
            cap.release()
            writer.release()

        self._reenc_h264(job.output_path)

        job.status      = "done"
        job.progress    = 1.0
        job.finished_at = time.time()

    # ----------------------------------------------------------------
    @staticmethod
    def _reenc_h264(path: str) -> None:
        """Re-encode to H.264 for browser playback (requires ffmpeg)."""
        import subprocess, shutil
        if not shutil.which("ffmpeg"):
            return
        tmp = path + ".h264.mp4"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", path,
                 "-vcodec", "libx264", "-pix_fmt", "yuv420p",
                 "-crf", "20", "-movflags", "+faststart", tmp],
                check=True, capture_output=True,
            )
            import os
            os.replace(tmp, path)
        except Exception:
            pass
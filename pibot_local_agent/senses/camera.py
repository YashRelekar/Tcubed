"""
Camera module for Raspberry Pi 5 with IMX219 MIPI sensor.

Supports two backends:
  1. libcamera-still / libcamera-vid command-line tools  (preferred on Pi OS Bookworm)
  2. OpenCV VideoCapture with libcamera GStreamer backend (for programmatic access)

Usage
-----
    from senses.camera import Camera

    cam = Camera()
    if cam.capture("/tmp/snapshot.jpg"):
        print("Snapshot saved")

    # Or get a numpy frame directly:
    frame = cam.capture_frame()
    if frame is not None:
        import cv2
        cv2.imwrite("/tmp/frame.jpg", frame)

Environment variables
---------------------
    CAMERA_INDEX       - integer index for OpenCV backend (default: 0)
    LIBCAMERA_DEVICE   - libcamera device path (default: auto-select)
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


# ---------------------------------------------------------------------------
# Module-level defaults (overrideable by env vars)
# ---------------------------------------------------------------------------
_CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
_LIBCAMERA_DEVICE = os.getenv("LIBCAMERA_DEVICE", "")  # empty → auto


def _libcamera_available() -> bool:
    """Return True if libcamera-still is installed."""
    try:
        result = subprocess.run(
            ["libcamera-still", "--version"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


class Camera:
    """
    Thin camera abstraction for the Pi 5 IMX219 MIPI sensor.

    Priority:
      1. libcamera-still (native, best quality, no extra deps)
      2. OpenCV with libcamera GStreamer pipeline
      3. OpenCV with V4L2 (fallback)
    """

    def __init__(
        self,
        camera_index: Optional[int] = None,
        libcamera_device: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
    ):
        self.camera_index = camera_index if camera_index is not None else _CAMERA_INDEX
        self.libcamera_device = (
            libcamera_device if libcamera_device is not None else _LIBCAMERA_DEVICE
        )
        self.width = width
        self.height = height
        self._use_libcamera = _libcamera_available()

        if self._use_libcamera:
            print("    Camera: libcamera backend (IMX219 MIPI)")
        elif CV2_AVAILABLE:
            print("    Camera: OpenCV backend (index {})".format(self.camera_index))
        else:
            print("    Camera: no backend available (install libcamera or opencv-python)")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture(self, output_path: str, timeout: int = 5000) -> bool:
        """
        Capture a still image to *output_path* (JPEG).

        Args:
            output_path: Destination file path (should end in .jpg).
            timeout:     libcamera-still timeout in ms (default 5000).

        Returns:
            True on success, False on failure.
        """
        if self._use_libcamera:
            return self._capture_libcamera(output_path, timeout)
        elif CV2_AVAILABLE:
            frame = self._capture_opencv()
            if frame is not None:
                cv2.imwrite(output_path, frame)
                return True
            return False
        else:
            print("Camera: no backend available")
            return False

    def capture_frame(self) -> Optional["np.ndarray"]:
        """
        Capture a frame and return it as a BGR numpy array (OpenCV format).

        Returns:
            numpy ndarray (H×W×3, BGR) or None on failure.
        """
        if not NUMPY_AVAILABLE:
            raise RuntimeError("numpy is required for capture_frame()")

        if self._use_libcamera:
            # Use a temp file as the bridge
            fd, tmp = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            try:
                if self._capture_libcamera(tmp):
                    if CV2_AVAILABLE:
                        frame = cv2.imread(tmp)
                        return frame
                    else:
                        # Return raw bytes if cv2 is missing
                        with open(tmp, "rb") as f:
                            raw = f.read()
                        buf = np.frombuffer(raw, dtype=np.uint8)
                        return buf  # caller must decode
                return None
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        elif CV2_AVAILABLE:
            return self._capture_opencv()
        else:
            return None

    def is_available(self) -> bool:
        """Return True if at least one camera backend is usable."""
        return self._use_libcamera or CV2_AVAILABLE

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _capture_libcamera(self, output_path: str, timeout: int = 5000) -> bool:
        """Capture using libcamera-still."""
        cmd = [
            "libcamera-still",
            "--output", output_path,
            "--timeout", str(timeout),
            "--width", str(self.width),
            "--height", str(self.height),
            "--nopreview",
        ]
        if self.libcamera_device:
            cmd += ["--camera", self.libcamera_device]
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=timeout // 1000 + 10
            )
            if result.returncode != 0:
                print("libcamera-still error: {}".format(
                    result.stderr.decode(errors="replace")))
                return False
            return Path(output_path).exists()
        except subprocess.TimeoutExpired:
            print("libcamera-still timed out")
            return False
        except Exception as e:
            print("libcamera-still exception: {}".format(e))
            return False

    def _capture_opencv(self) -> Optional["np.ndarray"]:
        """Capture a frame using OpenCV VideoCapture."""
        # Try libcamera GStreamer pipeline first (Pi OS Bookworm)
        gst_pipeline = (
            "libcamerasrc ! "
            "video/x-raw,width={w},height={h},framerate=30/1 ! "
            "videoconvert ! appsink"
        ).format(w=self.width, h=self.height)

        cap = None
        try:
            cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    return frame
        except Exception:
            pass
        finally:
            if cap is not None:
                cap.release()

        # Fallback: plain V4L2
        cap = None
        try:
            cap = cv2.VideoCapture(self.camera_index)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    return frame
        except Exception as e:
            print("OpenCV capture error: {}".format(e))
        finally:
            if cap is not None:
                cap.release()

        return None

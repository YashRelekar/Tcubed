#!/usr/bin/env python3
"""
Test IMX219 camera capture via libcamera and OpenCV.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_camera_capture():
    """Test still image capture from IMX219 MIPI camera."""
    from senses.camera import Camera

    print("Testing camera capture...\n")

    cam = Camera()

    if not cam.is_available():
        print("✗ No camera backend available.")
        print("  Install libcamera-apps:  sudo apt install -y libcamera-apps")
        print("  Or OpenCV:               pip install opencv-python")
        return False

    fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)

    try:
        success = cam.capture(tmp_path)
        if success and os.path.getsize(tmp_path) > 0:
            print(f"✓ Camera capture successful → {tmp_path}")
            print(f"  File size: {os.path.getsize(tmp_path)} bytes")
            return True
        else:
            print("✗ Camera capture failed (empty or missing file)")
            return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def test_camera_frame():
    """Test numpy frame capture."""
    from senses.camera import Camera

    print("\nTesting camera frame capture (numpy)...")

    cam = Camera()
    frame = cam.capture_frame()

    if frame is not None:
        print(f"✓ Frame captured, shape: {getattr(frame, 'shape', 'unknown')}")
        return True
    else:
        print("✗ Frame capture returned None")
        return False


if __name__ == "__main__":
    results = [
        ("Still capture", test_camera_capture()),
        ("Frame capture", test_camera_frame()),
    ]

    print("\n" + "=" * 40)
    print("Results:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
